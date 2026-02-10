"""OHLC price data endpoint for Price-Sentiment Overlay feature.

Implements:
- GET /api/v2/tickers/{ticker}/ohlc - Historical OHLC candlestick data

For On-Call Engineers:
    If OHLC data is not available:
    1. Check Tiingo/Finnhub API keys are configured
    2. Verify ticker symbol is valid (uppercase, 1-5 chars)
    3. Check rate limits on external APIs
    4. Review adapter logs for specific errors

Security Notes:
    - OHLC data is public market data
    - Uses existing X-User-ID authentication
"""

import logging
import os
import time
from datetime import date, datetime, timedelta

import orjson
from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.router import Router

from src.lambdas.shared.cache.ohlc_cache import (
    candles_to_cached,
    get_cached_candles,
    put_cached_candles,
)
from src.lambdas.shared.dependencies import get_tiingo_adapter
from src.lambdas.shared.logging_utils import get_safe_error_info
from src.lambdas.shared.middleware.auth_middleware import extract_auth_context
from src.lambdas.shared.models import (
    RESOLUTION_MAX_DAYS,
    TIME_RANGE_DAYS,
    OHLCResolution,
    OHLCResponse,
    PriceCandle,
    SentimentHistoryResponse,
    SentimentPoint,
    TimeRange,
)
from src.lambdas.shared.utils.event_helpers import get_query_params
from src.lambdas.shared.utils.market import get_cache_expiration

logger = logging.getLogger(__name__)

# ============================================================================
# OHLC Response Cache (Feature 1076)
# ============================================================================
# Module-level cache to prevent 429 rate limit errors when users rapidly
# switch resolution buckets. Similar pattern to sentiment.py caching.
# ============================================================================

# Cache TTLs per resolution (seconds) - more volatile = shorter TTL
OHLC_CACHE_TTLS: dict[str, int] = {
    "1": 300,  # 5 minutes for 1-minute resolution
    "5": 900,  # 15 minutes for 5-minute resolution
    "15": 900,  # 15 minutes for 15-minute resolution
    "30": 900,  # 15 minutes for 30-minute resolution
    "60": 1800,  # 30 minutes for hourly resolution
    "D": 3600,  # 1 hour for daily resolution
}
OHLC_CACHE_DEFAULT_TTL = 300  # 5 minutes fallback
OHLC_CACHE_MAX_ENTRIES = int(os.environ.get("OHLC_CACHE_MAX_ENTRIES", "256"))

# Cache storage: {cache_key: (timestamp, response_dict)}
_ohlc_cache: dict[str, tuple[float, dict]] = {}
_ohlc_cache_stats: dict[str, int] = {"hits": 0, "misses": 0, "evictions": 0}


def _get_ohlc_cache_key(
    ticker: str,
    resolution: str,
    time_range: str,
    start_date: date,
    end_date: date,
) -> str:
    """Generate cache key for OHLC request including end_date.

    Cache Remediation (CACHE-001): Always include end_date in cache key to prevent
    stale data across days. Previously, predefined ranges used only the range name,
    which caused the same cache key on different days (e.g., "1W" on Monday vs Friday
    would return Monday's data on Friday).

    Args:
        ticker: Stock ticker symbol
        resolution: OHLC resolution (1, 5, 15, 30, 60, D)
        time_range: Time range string ("1W", "1M", "3M", "6M", "1Y", or "custom")
        start_date: Range start date (used for custom ranges)
        end_date: Range end date (used for day-anchoring all ranges)

    Returns:
        Cache key string with end_date included
    """
    ticker_upper = ticker.upper()
    date_anchor = end_date.isoformat()

    if time_range == "custom":
        # Custom ranges include both dates for full specificity
        return f"ohlc:{ticker_upper}:{resolution}:custom:{start_date.isoformat()}:{date_anchor}"
    else:
        # Predefined ranges include end_date to prevent cross-day staleness
        # Same day + same range + same resolution = cache hit (correct)
        # Different day + same range = different key (prevents stale data)
        return f"ohlc:{ticker_upper}:{resolution}:{time_range}:{date_anchor}"


def _get_cached_ohlc(cache_key: str, resolution: str) -> dict | None:
    """Get OHLC response from cache if valid.

    Args:
        cache_key: The cache key to look up
        resolution: Resolution string for TTL lookup

    Returns:
        Cached response dict if valid, None if expired or missing
    """
    if cache_key in _ohlc_cache:
        timestamp, response = _ohlc_cache[cache_key]
        ttl = OHLC_CACHE_TTLS.get(resolution, OHLC_CACHE_DEFAULT_TTL)
        if time.time() - timestamp < ttl:
            _ohlc_cache_stats["hits"] += 1
            return response
        # Expired, remove it
        del _ohlc_cache[cache_key]
    _ohlc_cache_stats["misses"] += 1
    return None


def _set_cached_ohlc(cache_key: str, response: dict) -> None:
    """Store OHLC response in cache with LRU eviction.

    Args:
        cache_key: The cache key
        response: Response dict to cache
    """
    global _ohlc_cache
    if len(_ohlc_cache) >= OHLC_CACHE_MAX_ENTRIES:
        # Evict oldest entry by timestamp (LRU)
        oldest_key = min(_ohlc_cache.keys(), key=lambda k: _ohlc_cache[k][0])
        del _ohlc_cache[oldest_key]
        _ohlc_cache_stats["evictions"] += 1
    _ohlc_cache[cache_key] = (time.time(), response)


def get_ohlc_cache_stats() -> dict[str, int]:
    """Return cache statistics for observability."""
    return _ohlc_cache_stats.copy()


def invalidate_ohlc_cache(ticker: str | None = None) -> int:
    """Invalidate OHLC cache entries.

    Args:
        ticker: If provided, only invalidate entries for this ticker.
                If None, clear entire cache.

    Returns:
        Number of entries invalidated
    """
    global _ohlc_cache
    if ticker is None:
        count = len(_ohlc_cache)
        _ohlc_cache = {}
        return count
    prefix = f"ohlc:{ticker.upper()}:"
    keys_to_remove = [k for k in _ohlc_cache if k.startswith(prefix)]
    for key in keys_to_remove:
        del _ohlc_cache[key]
    return len(keys_to_remove)


# ============================================================================
# DynamoDB Persistent Cache (Feature 1087 / CACHE-001)
# ============================================================================
# Write-through caching: After fetching from Tiingo, persist to DynamoDB.
# This survives Lambda cold starts and reduces external API calls.
# ============================================================================


def _write_through_to_dynamodb(
    ticker: str,
    source: str,
    resolution: str,
    ohlc_candles: list,
) -> None:
    """Persist OHLC candles to DynamoDB for cross-invocation caching.

    Fire-and-forget: errors are logged but don't fail the request.
    Historical data is immutable, so overwrites are safe.

    Args:
        ticker: Stock symbol (e.g., "AAPL")
        source: Data provider ("tiingo" or "finnhub")
        resolution: Candle resolution ("D", "1", "5", etc.)
        ohlc_candles: List of OHLCCandle from adapter
    """
    if not ohlc_candles:
        logger.debug("No candles to cache", extra={"ticker": ticker})
        return

    try:
        # Convert adapter candles to cache format
        cached_candles = candles_to_cached(ohlc_candles, source, resolution)

        if not cached_candles:
            logger.debug(
                "Candle conversion produced no results",
                extra={"ticker": ticker, "input_count": len(ohlc_candles)},
            )
            return

        # Write to DynamoDB (batched, max 25 per request)
        written = put_cached_candles(
            ticker=ticker,
            source=source,
            resolution=resolution,
            candles=cached_candles,
        )

        logger.info(
            "OHLC write-through complete",
            extra={
                "ticker": ticker,
                "source": source,
                "resolution": resolution,
                "candles_written": written,
                "candles_input": len(ohlc_candles),
            },
        )
    except Exception as e:
        # Log but don't fail - write-through is best-effort
        logger.warning(
            "OHLC write-through failed",
            extra=get_safe_error_info(e),
        )


def _read_from_dynamodb(
    ticker: str,
    source: str,
    resolution: OHLCResolution,
    start_date: date,
    end_date: date,
) -> list[PriceCandle] | None:
    """Query DynamoDB for cached OHLC candles.

    Returns None if:
    - No data found
    - Query fails (graceful degradation to API)
    - Partial data (less than 80% expected candles)

    Args:
        ticker: Stock symbol
        source: Data provider
        resolution: Candle resolution
        start_date: Range start
        end_date: Range end

    Returns:
        List of PriceCandle if cache hit, None otherwise
    """
    try:
        # Import here to avoid potential import timing issues
        from datetime import UTC
        from datetime import time as dt_time

        # Convert dates to datetime for cache query
        start_time = datetime.combine(start_date, dt_time.min, tzinfo=UTC)
        end_time = datetime.combine(end_date, dt_time.max, tzinfo=UTC)

        result = get_cached_candles(
            ticker=ticker,
            source=source,
            resolution=resolution.value,
            start_time=start_time,
            end_time=end_time,
        )

        if not result.cache_hit or not result.candles:
            logger.debug(
                "DynamoDB cache miss",
                extra={"ticker": ticker, "resolution": resolution.value},
            )
            return None

        # Convert CachedCandle to PriceCandle
        price_candles = [
            PriceCandle.from_cached_candle(c, resolution) for c in result.candles
        ]

        # Validate we have reasonable coverage (80% threshold)
        expected_candles = _estimate_expected_candles(start_date, end_date, resolution)
        if len(price_candles) < expected_candles * 0.8:
            # Less than 80% coverage - treat as miss, fetch fresh
            logger.info(
                "DynamoDB cache partial hit, fetching fresh",
                extra={
                    "ticker": ticker,
                    "found": len(price_candles),
                    "expected": expected_candles,
                },
            )
            return None

        logger.info(
            "OHLC cache hit (DynamoDB)",
            extra={
                "ticker": ticker,
                "source": source,
                "resolution": resolution.value,
                "candle_count": len(price_candles),
            },
        )
        return price_candles

    except Exception as e:
        # Graceful degradation - log and fall through to API
        logger.warning(
            "DynamoDB cache read failed, falling back to API",
            extra=get_safe_error_info(e),
        )
        return None


def _estimate_expected_candles(
    start_date: date,
    end_date: date,
    resolution: OHLCResolution,
) -> int:
    """Estimate expected candle count for cache validation.

    Used to detect partial cache hits (missing data).
    Returns conservative estimates to avoid false negatives.

    Args:
        start_date: Range start
        end_date: Range end
        resolution: Candle resolution

    Returns:
        Estimated number of candles expected
    """
    days = (end_date - start_date).days + 1

    if resolution == OHLCResolution.DAILY:
        # ~252 trading days/year, ~5 per week
        return int(days * 5 / 7)
    elif resolution == OHLCResolution.ONE_HOUR:
        # 6.5 market hours/day, 5 days/week
        return int(days * 5 / 7 * 7)
    else:
        # Intraday: estimate based on resolution
        candles_per_hour = {
            OHLCResolution.ONE_MINUTE: 60,
            OHLCResolution.FIVE_MINUTES: 12,
            OHLCResolution.FIFTEEN_MINUTES: 4,
            OHLCResolution.THIRTY_MINUTES: 2,
        }
        per_hour = candles_per_hour.get(resolution, 12)
        return int(days * 5 / 7 * 6.5 * per_hour)


def _build_response_from_cache(
    ticker: str,
    candles: list[PriceCandle],
    resolution: OHLCResolution,
    time_range_str: str,
    source: str = "tiingo",
) -> OHLCResponse:
    """Build OHLCResponse from cached candles.

    Args:
        ticker: Stock symbol
        candles: List of PriceCandle from cache
        resolution: Original resolution
        time_range_str: Time range string for response
        source: Original data source

    Returns:
        OHLCResponse built from cached data
    """
    # Sort by date
    candles.sort(key=lambda c: c.date)

    # Extract dates, handling datetime vs date types
    first_candle_date = candles[0].date
    last_candle_date = candles[-1].date
    start_date_value = (
        first_candle_date.date()
        if isinstance(first_candle_date, datetime)
        else first_candle_date
    )
    end_date_value = (
        last_candle_date.date()
        if isinstance(last_candle_date, datetime)
        else last_candle_date
    )

    return OHLCResponse(
        ticker=ticker,
        candles=candles,
        time_range=time_range_str,
        start_date=start_date_value,
        end_date=end_date_value,
        count=len(candles),
        source=source,
        cache_expires_at=get_cache_expiration(),
        resolution=resolution.value,
        resolution_fallback=False,
        fallback_message=None,
    )


# Create router
router = Router()


def _get_user_id_from_event(event: dict) -> str | Response:
    """Extract and validate user_id from event (Feature 1049).

    Uses shared auth middleware for consistent auth handling.
    Supports both Bearer token and X-User-ID header.

    Args:
        event: Lambda event dict

    Returns:
        Validated user_id string, or Response with 401 error
    """
    auth_context = extract_auth_context(event)

    user_id = auth_context.get("user_id")
    if not user_id:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Missing user identification"}).decode(),
        )

    return user_id


@router.get("/api/v2/tickers/<ticker>/ohlc")
def get_ohlc_data(ticker: str) -> Response:
    """Get OHLC candlestick data for a ticker.

    Returns historical price data for visualization.
    Supports intraday resolutions (1, 5, 15, 30, 60 minutes) and daily.
    Uses Tiingo as primary source (daily only), Finnhub for all resolutions.

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, MSFT)

    Query Parameters:
        range: Predefined time range (1W, 1M, 3M, 6M, 1Y)
        resolution: Candle resolution - 1/5/15/30/60 min or D (daily)
        start_date: Custom start date (overrides range if provided)
        end_date: Custom end date (defaults to today)

    Returns:
        Response with OHLCResponse JSON

    Raises:
        400: Invalid ticker symbol or date range
        401: Missing user identification
        404: No price data available
        503: External data source unavailable
    """
    # Feature 1049: Use standardized auth extraction
    user_id_or_error = _get_user_id_from_event(router.current_event.raw_event)
    if isinstance(user_id_or_error, Response):
        return user_id_or_error

    # Get adapters (catch RuntimeError and return 503)
    try:
        tiingo = get_tiingo_adapter()
    except RuntimeError as e:
        logger.warning("Tiingo adapter unavailable", extra=get_safe_error_info(e))
        return Response(
            status_code=503,
            content_type="application/json",
            body=orjson.dumps({"detail": "Tiingo data source unavailable"}).decode(),
        )

    # Extract query parameters
    query_params = get_query_params(router.current_event.raw_event)

    # Parse range parameter
    range_str = query_params.get("range", TimeRange.ONE_MONTH.value)
    try:
        range_param = TimeRange(range_str)
    except ValueError:
        range_param = TimeRange.ONE_MONTH

    # Parse resolution parameter
    resolution_str = query_params.get("resolution", OHLCResolution.DAILY.value)
    try:
        resolution = OHLCResolution(resolution_str)
    except ValueError:
        resolution = OHLCResolution.DAILY

    # Parse date parameters
    start_date_str = query_params.get("start_date")
    end_date_str = query_params.get("end_date")

    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
        except ValueError:
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps(
                    {"detail": "Invalid start_date format. Use YYYY-MM-DD."}
                ).decode(),
            )
    if end_date_str:
        try:
            end_date = date.fromisoformat(end_date_str)
        except ValueError:
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps(
                    {"detail": "Invalid end_date format. Use YYYY-MM-DD."}
                ).decode(),
            )

    # Normalize ticker
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 5 or not ticker.isalpha():
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": f"Invalid ticker symbol: {ticker}. Must be 1-5 letters."}
            ).decode(),
        )

    # Calculate date range
    if start_date and end_date:
        # Custom date range
        time_range_str = "custom"
        if start_date > end_date:
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps(
                    {"detail": "start_date must be before end_date"}
                ).decode(),
            )
    else:
        # Use predefined range
        end_date = date.today()
        days = TIME_RANGE_DAYS.get(range_param, 30)
        start_date = end_date - timedelta(days=days)
        time_range_str = range_param.value

    # Apply time range limiting based on resolution (per data-model.md)
    max_days = RESOLUTION_MAX_DAYS.get(resolution, 365)
    actual_days = (end_date - start_date).days
    if actual_days > max_days:
        start_date = end_date - timedelta(days=max_days)
        logger.info(
            "Time range limited for resolution",
            extra={
                "resolution": resolution.value,
                "max_days": max_days,
                "requested_days": actual_days,
            },
        )

    # Log without user-derived values to prevent log injection (CWE-117)
    # CodeQL traces taint from range param -> days -> start_date/end_date
    # See: https://github.com/github/codeql/discussions/10702
    logger.info("Fetching OHLC data")

    # Feature 1076/1078: Check cache before making external API calls
    # Use time_range_str (not dates) for cache key to ensure hits on predefined ranges
    cache_key = _get_ohlc_cache_key(
        ticker, resolution.value, time_range_str, start_date, end_date
    )
    cached_response = _get_cached_ohlc(cache_key, resolution.value)
    if cached_response:
        safe_cache_key = (
            str(cache_key)
            .replace("\r\n", " ")
            .replace("\n", " ")
            .replace("\r", " ")[:200]
        )
        logger.info(
            "OHLC cache hit (in-memory)",
            extra={"cache_key": safe_cache_key, "stats": get_ohlc_cache_stats()},
        )
        # Return cached OHLCResponse directly
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(cached_response).decode(),
        )

    # =========================================================================
    # Cache check #2: DynamoDB persistent cache (Feature 1087 / CACHE-001)
    # Survives Lambda cold starts, reduces external API calls
    # =========================================================================
    ddb_candles = _read_from_dynamodb(
        ticker=ticker,
        source="tiingo",  # Primary source
        resolution=resolution,
        start_date=start_date,
        end_date=end_date,
    )

    if ddb_candles:
        # Build response from DynamoDB data
        response = _build_response_from_cache(
            ticker=ticker,
            candles=ddb_candles,
            resolution=resolution,
            time_range_str=time_range_str,
            source="tiingo",
        )

        # Populate in-memory cache for subsequent requests
        _set_cached_ohlc(cache_key, response.model_dump(mode="json"))

        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(response.model_dump(mode="json")).decode(),
        )

    # Track fallback state
    resolution_fallback = False
    fallback_message = None
    actual_resolution = resolution

    # Feature 1055: Use Tiingo for ALL resolutions
    # - Daily: Tiingo daily endpoint (existing)
    # - Intraday: Tiingo IEX endpoint (new) - Finnhub free tier doesn't support candles
    source = "tiingo"
    candles = []

    if resolution == OHLCResolution.DAILY:
        # Use Tiingo daily endpoint for daily data (primary source per FR-014)
        try:
            ohlc_candles = tiingo.get_ohlc(ticker, start_date, end_date)
            if ohlc_candles:
                candles = [
                    PriceCandle.from_ohlc_candle(c, resolution) for c in ohlc_candles
                ]
                # Write-through to DynamoDB (CACHE-001)
                _write_through_to_dynamodb(
                    ticker=ticker,
                    source=source,
                    resolution=resolution.value,
                    ohlc_candles=ohlc_candles,
                )
        except Exception as e:
            logger.warning(
                "Tiingo daily OHLC fetch failed",
                extra=get_safe_error_info(e),
            )
    else:
        # Feature 1055: Use Tiingo IEX for intraday resolutions
        try:
            ohlc_candles = tiingo.get_intraday_ohlc(
                ticker, start_date, end_date, resolution=resolution.value
            )
            if ohlc_candles:
                candles = [
                    PriceCandle.from_ohlc_candle(c, resolution) for c in ohlc_candles
                ]
                # Write-through to DynamoDB (CACHE-001)
                _write_through_to_dynamodb(
                    ticker=ticker,
                    source=source,
                    resolution=resolution.value,
                    ohlc_candles=ohlc_candles,
                )
        except Exception as e:
            logger.warning(
                "Tiingo IEX intraday fetch failed",
                extra=get_safe_error_info(e),
            )

    # Fallback: If intraday data unavailable, try daily (T006)
    # Feature 1055: Simplified - only Tiingo for fallback (Finnhub free tier doesn't work)
    if not candles and resolution != OHLCResolution.DAILY:
        logger.info(
            "Intraday data unavailable, falling back to daily",
            extra={"requested_resolution": resolution.value},
        )
        resolution_fallback = True
        fallback_message = f"Intraday data unavailable for {ticker}, showing daily"
        actual_resolution = OHLCResolution.DAILY

        # Use Tiingo daily endpoint for fallback
        source = "tiingo"
        try:
            ohlc_candles = tiingo.get_ohlc(ticker, start_date, end_date)
            if ohlc_candles:
                candles = [
                    PriceCandle.from_ohlc_candle(c, actual_resolution)
                    for c in ohlc_candles
                ]
                # Write-through to DynamoDB (CACHE-001)
                _write_through_to_dynamodb(
                    ticker=ticker,
                    source=source,
                    resolution=actual_resolution.value,
                    ohlc_candles=ohlc_candles,
                )
        except Exception as e:
            logger.warning(
                "Tiingo daily fallback failed",
                extra=get_safe_error_info(e),
            )

    # Check if we got any data
    if not candles:
        logger.warning("No OHLC data available from any source")
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": f"No price data available for {ticker}"}
            ).decode(),
        )

    # Sort candles by date (oldest first)
    candles.sort(key=lambda c: c.date)

    # Calculate cache expiration (FR-009)
    cache_expires = get_cache_expiration()

    logger.info(
        "OHLC data retrieved successfully",
        extra={
            "source": source,
            "candle_count": len(candles),
            "resolution": actual_resolution.value,
            "fallback": resolution_fallback,
        },
    )

    # Extract start/end dates, handling datetime vs date types
    # Note: datetime is a subclass of date, so check datetime FIRST
    first_candle_date = candles[0].date
    last_candle_date = candles[-1].date
    start_date_value = (
        first_candle_date.date()
        if isinstance(first_candle_date, datetime)
        else first_candle_date
    )
    end_date_value = (
        last_candle_date.date()
        if isinstance(last_candle_date, datetime)
        else last_candle_date
    )

    response = OHLCResponse(
        ticker=ticker,
        candles=candles,
        time_range=time_range_str,
        start_date=start_date_value,
        end_date=end_date_value,
        count=len(candles),
        source=source,
        cache_expires_at=cache_expires,
        resolution=actual_resolution.value,
        resolution_fallback=resolution_fallback,
        fallback_message=fallback_message,
    )

    # Feature 1076/1078: Cache the response for future requests
    # Use time_range_str (not dates) to ensure cache key matches lookup
    actual_cache_key = _get_ohlc_cache_key(
        ticker,
        actual_resolution.value,
        time_range_str,
        start_date_value,
        end_date_value,
    )
    response_dict = response.model_dump(mode="json")
    _set_cached_ohlc(actual_cache_key, response_dict)
    safe_actual_cache_key = (
        str(actual_cache_key)
        .replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")[:200]
    )
    logger.debug(
        "OHLC response cached",
        extra={"cache_key": safe_actual_cache_key, "stats": get_ohlc_cache_stats()},
    )

    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps(response_dict).decode(),
    )


@router.get("/api/v2/tickers/<ticker>/sentiment/history")
def get_sentiment_history(ticker: str) -> Response:
    """Get historical sentiment data for a ticker.

    Returns sentiment scores over time for chart overlay.
    Sentiment is available for all calendar days (including weekends).

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, MSFT)

    Query Parameters:
        source: Sentiment source (tiingo, finnhub, our_model, aggregated)
        range: Predefined time range (1W, 1M, 3M, 6M, 1Y)
        start_date: Custom start date (overrides range if provided)
        end_date: Custom end date (defaults to today)

    Returns:
        Response with SentimentHistoryResponse JSON

    Raises:
        400: Invalid parameters
        401: Missing user identification
        404: No sentiment data available
    """
    # Feature 1049: Use standardized auth extraction
    user_id_or_error = _get_user_id_from_event(router.current_event.raw_event)
    if isinstance(user_id_or_error, Response):
        return user_id_or_error

    # Extract query parameters
    query_params = get_query_params(router.current_event.raw_event)

    # Parse source parameter
    valid_sources = ("tiingo", "finnhub", "our_model", "aggregated")
    source_str = query_params.get("source", "aggregated")
    source = source_str if source_str in valid_sources else "aggregated"

    # Parse range parameter
    range_str = query_params.get("range", TimeRange.ONE_MONTH.value)
    try:
        range_param = TimeRange(range_str)
    except ValueError:
        range_param = TimeRange.ONE_MONTH

    # Parse date parameters
    start_date_str = query_params.get("start_date")
    end_date_str = query_params.get("end_date")

    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
        except ValueError:
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps(
                    {"detail": "Invalid start_date format. Use YYYY-MM-DD."}
                ).decode(),
            )
    if end_date_str:
        try:
            end_date = date.fromisoformat(end_date_str)
        except ValueError:
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps(
                    {"detail": "Invalid end_date format. Use YYYY-MM-DD."}
                ).decode(),
            )

    # Normalize ticker
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 5 or not ticker.isalpha():
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": f"Invalid ticker symbol: {ticker}. Must be 1-5 letters."}
            ).decode(),
        )

    # Calculate date range
    if start_date and end_date:
        if start_date > end_date:
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps(
                    {"detail": "start_date must be before end_date"}
                ).decode(),
            )
    else:
        end_date = date.today()
        days = TIME_RANGE_DAYS.get(range_param, 30)
        start_date = end_date - timedelta(days=days)

    # Log without user-derived values to prevent log injection (CWE-117)
    # CodeQL traces taint from range param -> days -> start_date/end_date
    # See: https://github.com/github/codeql/discussions/10702
    logger.info("Fetching sentiment history")

    # Generate sentiment history
    # In production, this would query DynamoDB for historical sentiment records
    # For now, generate synthetic data based on existing sentiment values
    history: list[SentimentPoint] = []
    current_date = start_date

    import hashlib
    import random

    # Use hashlib for deterministic seed (hash() is randomized by PYTHONHASHSEED)
    ticker_hash = int(hashlib.sha256(ticker.encode()).hexdigest(), 16)
    random.seed(ticker_hash)

    base_score = 0.3  # Slightly positive base
    while current_date <= end_date:
        # Add some variability
        daily_variation = random.uniform(-0.3, 0.3)
        score = max(-1.0, min(1.0, base_score + daily_variation))

        # Determine label
        if score >= 0.33:
            label = "positive"
        elif score <= -0.33:
            label = "negative"
        else:
            label = "neutral"

        history.append(
            SentimentPoint(
                date=current_date,
                score=round(score, 4),
                source=source,
                confidence=round(random.uniform(0.6, 0.95), 4),
                label=label,
            )
        )

        # Slight trend continuation
        base_score = score * 0.8 + base_score * 0.2

        current_date += timedelta(days=1)

    if not history:
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": f"No sentiment data available for {ticker}"}
            ).decode(),
        )

    logger.info(
        "Sentiment history retrieved",
        extra={"point_count": len(history)},
    )

    response = SentimentHistoryResponse(
        ticker=ticker,
        source=source,
        history=history,
        start_date=history[0].date,
        end_date=history[-1].date,
        count=len(history),
    )

    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps(response.model_dump(mode="json")).decode(),
    )

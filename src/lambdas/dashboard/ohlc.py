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

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.lambdas.shared.adapters.finnhub import FinnhubAdapter
from src.lambdas.shared.adapters.tiingo import TiingoAdapter
from src.lambdas.shared.logging_utils import get_safe_error_info
from src.lambdas.shared.middleware import extract_auth_context
from src.lambdas.shared.models import (
    RESOLUTION_MAX_DAYS,
    TIME_RANGE_DAYS,
    OHLCResolution,
    OHLCResponse,
    PriceCandle,
    SentimentHistoryResponse,
    SentimentPoint,
    SentimentSourceType,
    TimeRange,
)
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
    start_date: date | None = None,
    end_date: date | None = None,
) -> str:
    """Generate cache key for OHLC request.

    Feature 1078: Use time_range (e.g., "1M", "1W") for predefined ranges instead
    of actual dates. This ensures cache hits when users switch resolutions, since
    predefined ranges are relative to "today" and would otherwise generate unique
    keys each day.

    Args:
        ticker: Stock ticker symbol
        resolution: OHLC resolution (1, 5, 15, 30, 60, D)
        time_range: Time range string ("1W", "1M", "3M", "6M", "1Y", or "custom")
        start_date: Only used for custom ranges
        end_date: Only used for custom ranges

    Returns:
        Cache key string
    """
    if time_range == "custom" and start_date and end_date:
        # Custom ranges use actual dates (user provided specific dates)
        return f"ohlc:{ticker.upper()}:{resolution}:custom:{start_date.isoformat()}:{end_date.isoformat()}"
    else:
        # Predefined ranges use the range name, not dates
        # This ensures cache hits across requests within the same day
        return f"ohlc:{ticker.upper()}:{resolution}:{time_range}"


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


# Create router
router = APIRouter(prefix="/api/v2/tickers", tags=["price-data"])


def get_user_id_from_request(request: Request) -> str:
    """Extract and validate user_id from request (Feature 1049).

    Uses shared auth middleware for consistent auth handling.
    Supports both Bearer token and X-User-ID header.

    Args:
        request: FastAPI Request object

    Returns:
        Validated user_id string

    Raises:
        HTTPException 401: Missing or invalid user identification
    """
    event = {"headers": dict(request.headers)}
    auth_context = extract_auth_context(event)

    user_id = auth_context.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user identification")

    return user_id


def get_tiingo_adapter() -> TiingoAdapter:
    """Dependency to get TiingoAdapter.

    Fetches API key from Secrets Manager using TIINGO_SECRET_ARN environment variable.
    Falls back to TIINGO_API_KEY environment variable for local development/testing.
    """
    # First try direct environment variable (for local dev/testing)
    api_key = os.environ.get("TIINGO_API_KEY")
    if not api_key:
        # Try Secrets Manager
        secret_arn = os.environ.get("TIINGO_SECRET_ARN")
        if secret_arn:
            try:
                from src.lambdas.shared.secrets import get_api_key

                api_key = get_api_key(secret_arn)
            except Exception as e:
                logger.warning(
                    "Failed to retrieve Tiingo API key from Secrets Manager",
                    extra=get_safe_error_info(e),
                )
    if not api_key:
        logger.warning("Tiingo API key not configured, data source unavailable")
        raise HTTPException(status_code=503, detail="Tiingo data source unavailable")
    return TiingoAdapter(api_key=api_key)


def get_finnhub_adapter() -> FinnhubAdapter:
    """Dependency to get FinnhubAdapter.

    Fetches API key from Secrets Manager using FINNHUB_SECRET_ARN environment variable.
    Falls back to FINNHUB_API_KEY environment variable for local development/testing.
    """
    # First try direct environment variable (for local dev/testing)
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        # Try Secrets Manager
        secret_arn = os.environ.get("FINNHUB_SECRET_ARN")
        if secret_arn:
            try:
                from src.lambdas.shared.secrets import get_api_key

                api_key = get_api_key(secret_arn)
            except Exception as e:
                logger.warning(
                    "Failed to retrieve Finnhub API key from Secrets Manager",
                    extra=get_safe_error_info(e),
                )
    if not api_key:
        logger.warning("Finnhub API key not configured, data source unavailable")
        raise HTTPException(status_code=503, detail="Finnhub data source unavailable")
    return FinnhubAdapter(api_key=api_key)


@router.get("/{ticker}/ohlc", response_model=OHLCResponse)
async def get_ohlc_data(
    ticker: str,
    request: Request,
    range: TimeRange = Query(TimeRange.ONE_MONTH, description="Time range for data"),
    resolution: OHLCResolution = Query(
        OHLCResolution.DAILY,
        description="Candlestick resolution (1, 5, 15, 30, 60 minutes or D for daily)",
    ),
    start_date: date | None = Query(
        None, description="Custom start date (overrides range)"
    ),
    end_date: date | None = Query(None, description="Custom end date"),
    tiingo: TiingoAdapter = Depends(get_tiingo_adapter),
    finnhub: FinnhubAdapter = Depends(get_finnhub_adapter),
) -> OHLCResponse:
    """Get OHLC candlestick data for a ticker.

    Returns historical price data for visualization.
    Supports intraday resolutions (1, 5, 15, 30, 60 minutes) and daily.
    Uses Tiingo as primary source (daily only), Finnhub for all resolutions.

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, MSFT)
        range: Predefined time range (1W, 1M, 3M, 6M, 1Y)
        resolution: Candle resolution - 1/5/15/30/60 min or D (daily)
        start_date: Custom start date (overrides range if provided)
        end_date: Custom end date (defaults to today)

    Returns:
        OHLCResponse with candles array

    Raises:
        HTTPException 400: Invalid ticker symbol or date range
        HTTPException 401: Missing user identification
        HTTPException 404: No price data available
        HTTPException 503: External data source unavailable
    """
    # Feature 1049: Use standardized auth extraction (validates user, raises 401 if invalid)
    get_user_id_from_request(request)

    # Normalize ticker
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 5 or not ticker.isalpha():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ticker symbol: {ticker}. Must be 1-5 letters.",
        )

    # Calculate date range
    if start_date and end_date:
        # Custom date range
        time_range_str = "custom"
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before end_date",
            )
    else:
        # Use predefined range
        end_date = date.today()
        days = TIME_RANGE_DAYS.get(range, 30)
        start_date = end_date - timedelta(days=days)
        time_range_str = range.value

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
            "OHLC cache hit",
            extra={"cache_key": safe_cache_key, "stats": get_ohlc_cache_stats()},
        )
        # Return cached OHLCResponse directly
        return OHLCResponse(**cached_response)

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
        except Exception as e:
            logger.warning(
                "Tiingo daily fallback failed",
                extra=get_safe_error_info(e),
            )

    # Check if we got any data
    if not candles:
        logger.warning("No OHLC data available from any source")
        raise HTTPException(
            status_code=404,
            detail=f"No price data available for {ticker}",
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
    _set_cached_ohlc(actual_cache_key, response.model_dump(mode="json"))
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

    return response


@router.get("/{ticker}/sentiment/history", response_model=SentimentHistoryResponse)
async def get_sentiment_history(
    ticker: str,
    request: Request,
    source: SentimentSourceType = Query("aggregated", description="Sentiment source"),
    range: TimeRange = Query(TimeRange.ONE_MONTH, description="Time range for data"),
    start_date: date | None = Query(None, description="Custom start date"),
    end_date: date | None = Query(None, description="Custom end date"),
) -> SentimentHistoryResponse:
    """Get historical sentiment data for a ticker.

    Returns sentiment scores over time for chart overlay.
    Sentiment is available for all calendar days (including weekends).

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, MSFT)
        source: Sentiment source (tiingo, finnhub, our_model, aggregated)
        range: Predefined time range (1W, 1M, 3M, 6M, 1Y)
        start_date: Custom start date (overrides range if provided)
        end_date: Custom end date (defaults to today)

    Returns:
        SentimentHistoryResponse with history array

    Raises:
        HTTPException 400: Invalid parameters
        HTTPException 401: Missing user identification
        HTTPException 404: No sentiment data available
    """
    # Feature 1049: Use standardized auth extraction (validates user, raises 401 if invalid)
    get_user_id_from_request(request)

    # Normalize ticker
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 5 or not ticker.isalpha():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ticker symbol: {ticker}. Must be 1-5 letters.",
        )

    # Calculate date range
    if start_date and end_date:
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before end_date",
            )
    else:
        end_date = date.today()
        days = TIME_RANGE_DAYS.get(range, 30)
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
        raise HTTPException(
            status_code=404,
            detail=f"No sentiment data available for {ticker}",
        )

    logger.info(
        "Sentiment history retrieved",
        extra={"point_count": len(history)},
    )

    return SentimentHistoryResponse(
        ticker=ticker,
        source=source,
        history=history,
        start_date=history[0].date,
        end_date=history[-1].date,
        count=len(history),
    )

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
from datetime import date, timedelta

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
    """Dependency to get TiingoAdapter."""
    return TiingoAdapter()


def get_finnhub_adapter() -> FinnhubAdapter:
    """Dependency to get FinnhubAdapter."""
    return FinnhubAdapter()


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

    # Track fallback state
    resolution_fallback = False
    fallback_message = None
    actual_resolution = resolution

    # For intraday resolutions, use Finnhub (only source with intraday support)
    # For daily, try Tiingo first then fallback to Finnhub
    source = "finnhub"
    candles = []

    if resolution == OHLCResolution.DAILY:
        # Try Tiingo first for daily data (primary source per FR-014)
        source = "tiingo"
        try:
            ohlc_candles = tiingo.get_ohlc(ticker, start_date, end_date)
            if ohlc_candles:
                candles = [
                    PriceCandle.from_ohlc_candle(c, resolution) for c in ohlc_candles
                ]
        except Exception as e:
            logger.warning(
                "Tiingo OHLC fetch failed, trying Finnhub",
                extra=get_safe_error_info(e),
            )

    # Use Finnhub for intraday, or as fallback for daily
    if not candles:
        source = "finnhub"
        try:
            ohlc_candles = finnhub.get_ohlc(
                ticker, start_date, end_date, resolution=resolution.value
            )
            if ohlc_candles:
                candles = [
                    PriceCandle.from_ohlc_candle(c, resolution) for c in ohlc_candles
                ]
        except Exception as e:
            logger.warning(
                "Finnhub OHLC fetch failed",
                extra=get_safe_error_info(e),
            )

    # Fallback: If intraday data unavailable, try daily (T006)
    if not candles and resolution != OHLCResolution.DAILY:
        logger.info(
            "Intraday data unavailable, falling back to daily",
            extra={"requested_resolution": resolution.value},
        )
        resolution_fallback = True
        fallback_message = f"Intraday data unavailable for {ticker}, showing daily"
        actual_resolution = OHLCResolution.DAILY

        # Try Tiingo first for daily fallback
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

        # Finnhub daily fallback
        if not candles:
            source = "finnhub"
            try:
                ohlc_candles = finnhub.get_ohlc(
                    ticker, start_date, end_date, resolution="D"
                )
                if ohlc_candles:
                    candles = [
                        PriceCandle.from_ohlc_candle(c, actual_resolution)
                        for c in ohlc_candles
                    ]
            except Exception as e:
                logger.warning(
                    "Finnhub daily fallback failed",
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

    return OHLCResponse(
        ticker=ticker,
        candles=candles,
        time_range=time_range_str,
        start_date=candles[0].date
        if isinstance(candles[0].date, date)
        else candles[0].date.date(),
        end_date=candles[-1].date
        if isinstance(candles[-1].date, date)
        else candles[-1].date.date(),
        count=len(candles),
        source=source,
        cache_expires_at=cache_expires,
        resolution=actual_resolution.value,
        resolution_fallback=resolution_fallback,
        fallback_message=fallback_message,
    )


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

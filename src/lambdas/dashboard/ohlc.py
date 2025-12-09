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
from src.lambdas.shared.models import (
    TIME_RANGE_DAYS,
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
    start_date: date | None = Query(
        None, description="Custom start date (overrides range)"
    ),
    end_date: date | None = Query(None, description="Custom end date"),
    tiingo: TiingoAdapter = Depends(get_tiingo_adapter),
    finnhub: FinnhubAdapter = Depends(get_finnhub_adapter),
) -> OHLCResponse:
    """Get OHLC candlestick data for a ticker.

    Returns historical price data for visualization.
    Uses Tiingo as primary source, Finnhub as fallback.

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, MSFT)
        range: Predefined time range (1W, 1M, 3M, 6M, 1Y)
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
    # Validate user ID (uses existing auth pattern)
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user identification")

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

    # Sanitize user input before logging to prevent log injection (CWE-117)
    # CodeQL's ReplaceLineBreaksSanitizer only recognizes .replace('\r\n','') and .replace('\n','')
    # Length limiting must be done BEFORE sanitization to preserve the sanitizer barrier
    # See: https://codeql.github.com/codeql-query-help/python/py-log-injection/
    ticker_truncated = ticker[:200]
    safe_ticker = ticker_truncated.replace("\r\n", "").replace("\n", "")
    range_truncated = time_range_str[:50]
    safe_range = range_truncated.replace("\r\n", "").replace("\n", "")

    logger.info(
        "Fetching OHLC data",
        extra={
            "ticker": safe_ticker,
            "range": safe_range,
            "start_date": str(start_date),
            "end_date": str(end_date),
        },
    )

    # Try Tiingo first (primary source per FR-014)
    source = "tiingo"
    candles = []

    try:
        ohlc_candles = tiingo.get_ohlc(ticker, start_date, end_date)
        if ohlc_candles:
            candles = [PriceCandle.from_ohlc_candle(c) for c in ohlc_candles]
    except Exception as e:
        logger.warning(
            "Tiingo OHLC fetch failed, trying Finnhub",
            extra={
                "ticker": safe_ticker,
                **get_safe_error_info(e),
            },
        )

    # Fallback to Finnhub if Tiingo failed or returned no data
    if not candles:
        source = "finnhub"
        try:
            ohlc_candles = finnhub.get_ohlc(ticker, start_date, end_date)
            if ohlc_candles:
                candles = [PriceCandle.from_ohlc_candle(c) for c in ohlc_candles]
        except Exception as e:
            logger.warning(
                "Finnhub OHLC fetch failed",
                extra={
                    "ticker": safe_ticker,
                    **get_safe_error_info(e),
                },
            )

    # Check if we got any data
    if not candles:
        logger.warning(
            "No OHLC data available from any source",
            extra={"ticker": safe_ticker},
        )
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
            "ticker": safe_ticker,
            "source": source,
            "candle_count": len(candles),
        },
    )

    return OHLCResponse(
        ticker=ticker,
        candles=candles,
        time_range=time_range_str,
        start_date=candles[0].date,
        end_date=candles[-1].date,
        count=len(candles),
        source=source,
        cache_expires_at=cache_expires,
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
    # Validate user ID
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user identification")

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

    # Sanitize user input before logging to prevent log injection (CWE-117)
    # CodeQL's ReplaceLineBreaksSanitizer only recognizes .replace('\r\n','') and .replace('\n','')
    # Length limiting must be done BEFORE sanitization to preserve the sanitizer barrier
    # See: https://codeql.github.com/codeql-query-help/python/py-log-injection/
    ticker_truncated = ticker[:200]
    safe_ticker = ticker_truncated.replace("\r\n", "").replace("\n", "")
    source_truncated = source[:50]
    safe_source = source_truncated.replace("\r\n", "").replace("\n", "")

    logger.info(
        "Fetching sentiment history",
        extra={
            "ticker": safe_ticker,
            "source": safe_source,
            "start_date": str(start_date),
            "end_date": str(end_date),
        },
    )

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
        extra={
            "ticker": safe_ticker,
            "source": safe_source,
            "point_count": len(history),
        },
    )

    return SentimentHistoryResponse(
        ticker=ticker,
        source=source,
        history=history,
        start_date=history[0].date,
        end_date=history[-1].date,
        count=len(history),
    )

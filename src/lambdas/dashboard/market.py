"""Market status and refresh endpoints for Feature 006.

Implements market information (T060-T063):
- GET /api/v2/configurations/{id}/refresh/status - Refresh status
- POST /api/v2/configurations/{id}/refresh - Manual refresh trigger
- GET /api/v2/market/status - Market status
- GET /api/v2/configurations/{id}/premarket - Pre-market estimates

For On-Call Engineers:
    Market status is calculated based on NYSE hours.
    If status is incorrect:
    1. Check timezone handling
    2. Verify holiday calendar is up to date
    3. Check Finnhub pre-market data availability

Security Notes:
    - Market status is public information
    - Pre-market data may have lower accuracy
"""

import logging
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from src.lambdas.shared.logging_utils import sanitize_for_log

logger = logging.getLogger(__name__)


# Response schemas


class RefreshStatusResponse(BaseModel):
    """Response for GET /api/v2/configurations/{id}/refresh/status."""

    last_refresh: str
    next_scheduled_refresh: str
    refresh_interval_seconds: int
    countdown_seconds: int
    is_refreshing: bool


class RefreshTriggerResponse(BaseModel):
    """Response for POST /api/v2/configurations/{id}/refresh."""

    status: str = "refresh_queued"
    estimated_completion: str


class MarketStatusResponse(BaseModel):
    """Response for GET /api/v2/market/status."""

    status: str = Field(..., pattern="^(open|closed)$")
    exchange: str
    current_time: str
    market_open: str | None
    market_close: str | None
    next_open: str | None
    reason: str | None = None
    is_extended_hours: bool = False
    is_holiday: bool = False
    holiday_name: str | None = None


class PremarketEstimate(BaseModel):
    """Pre-market estimate for a single ticker."""

    symbol: str
    premarket_price: float | None
    previous_close: float | None
    change_percent: float | None
    estimated_sentiment: dict[str, Any]
    overnight_news_count: int
    updated_at: str


class PremarketResponse(BaseModel):
    """Response for GET /api/v2/configurations/{id}/premarket."""

    config_id: str
    market_status: str
    data_source: str = "finnhub_premarket"
    estimates: list[PremarketEstimate] | None = None
    message: str | None = None
    redirect_to: str | None = None
    disclaimer: str | None = None
    next_market_open: str | None = None


# Constants

REFRESH_INTERVAL_SECONDS = 300  # 5 minutes
NYSE_TZ = ZoneInfo("America/New_York")

# NYSE market hours (Eastern Time)
MARKET_OPEN_TIME = time(9, 30)
MARKET_CLOSE_TIME = time(16, 0)
PREMARKET_START = time(4, 0)
AFTERHOURS_END = time(20, 0)

# 2025 NYSE holidays (markets closed)
NYSE_HOLIDAYS_2025 = {
    (1, 1): "New Year's Day",
    (1, 20): "Martin Luther King Jr. Day",
    (2, 17): "Presidents' Day",
    (4, 18): "Good Friday",
    (5, 26): "Memorial Day",
    (6, 19): "Juneteenth",
    (7, 4): "Independence Day",
    (9, 1): "Labor Day",
    (11, 27): "Thanksgiving Day",
    (12, 25): "Christmas Day",
}


# Service functions


def get_refresh_status(
    config_id: str,
    last_refresh_time: datetime | None = None,
) -> RefreshStatusResponse:
    """Get refresh status for a configuration.

    Args:
        config_id: Configuration ID
        last_refresh_time: Last refresh timestamp

    Returns:
        RefreshStatusResponse with timing information
    """
    now = datetime.now(UTC)

    if last_refresh_time is None:
        last_refresh_time = now - timedelta(seconds=REFRESH_INTERVAL_SECONDS)

    next_refresh = last_refresh_time + timedelta(seconds=REFRESH_INTERVAL_SECONDS)
    countdown = max(0, int((next_refresh - now).total_seconds()))

    return RefreshStatusResponse(
        last_refresh=last_refresh_time.isoformat().replace("+00:00", "Z"),
        next_scheduled_refresh=next_refresh.isoformat().replace("+00:00", "Z"),
        refresh_interval_seconds=REFRESH_INTERVAL_SECONDS,
        countdown_seconds=countdown,
        is_refreshing=False,
    )


def trigger_refresh(config_id: str) -> RefreshTriggerResponse:
    """Trigger a manual refresh for a configuration.

    Args:
        config_id: Configuration ID

    Returns:
        RefreshTriggerResponse with estimated completion
    """
    now = datetime.now(UTC)
    estimated_completion = now + timedelta(seconds=30)

    logger.info(
        "Triggered manual refresh",
        extra={"config_id": sanitize_for_log(config_id[:8] if config_id else "")},
    )

    return RefreshTriggerResponse(
        status="refresh_queued",
        estimated_completion=estimated_completion.isoformat().replace("+00:00", "Z"),
    )


def get_market_status() -> MarketStatusResponse:
    """Get current market status.

    Returns:
        MarketStatusResponse with market hours info
    """
    now_utc = datetime.now(UTC)
    now_ny = now_utc.astimezone(NYSE_TZ)

    # Check if today is a holiday
    today_key = (now_ny.month, now_ny.day)
    if today_key in NYSE_HOLIDAYS_2025:
        holiday_name = NYSE_HOLIDAYS_2025[today_key]
        next_open = _get_next_market_open(now_ny)

        return MarketStatusResponse(
            status="closed",
            exchange="NYSE",
            current_time=now_utc.isoformat().replace("+00:00", "Z"),
            market_open=None,
            market_close=None,
            next_open=(
                next_open.astimezone(UTC).isoformat().replace("+00:00", "Z")
                if next_open
                else None
            ),
            reason="holiday",
            is_holiday=True,
            holiday_name=holiday_name,
        )

    # Check if weekend
    if now_ny.weekday() >= 5:  # Saturday or Sunday
        next_open = _get_next_market_open(now_ny)

        return MarketStatusResponse(
            status="closed",
            exchange="NYSE",
            current_time=now_utc.isoformat().replace("+00:00", "Z"),
            market_open=None,
            market_close=None,
            next_open=(
                next_open.astimezone(UTC).isoformat().replace("+00:00", "Z")
                if next_open
                else None
            ),
            reason="weekend",
        )

    current_time = now_ny.time()

    # Check if market is open
    if MARKET_OPEN_TIME <= current_time < MARKET_CLOSE_TIME:
        market_open_dt = now_ny.replace(
            hour=MARKET_OPEN_TIME.hour,
            minute=MARKET_OPEN_TIME.minute,
            second=0,
            microsecond=0,
        )
        market_close_dt = now_ny.replace(
            hour=MARKET_CLOSE_TIME.hour,
            minute=MARKET_CLOSE_TIME.minute,
            second=0,
            microsecond=0,
        )

        return MarketStatusResponse(
            status="open",
            exchange="NYSE",
            current_time=now_utc.isoformat().replace("+00:00", "Z"),
            market_open=market_open_dt.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            market_close=market_close_dt.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            next_open=None,
        )

    # Market is closed
    next_open = _get_next_market_open(now_ny)

    # Determine reason
    if current_time < MARKET_OPEN_TIME:
        reason = "premarket"
        is_extended = current_time >= PREMARKET_START
    else:
        reason = "after_hours"
        is_extended = current_time < AFTERHOURS_END

    return MarketStatusResponse(
        status="closed",
        exchange="NYSE",
        current_time=now_utc.isoformat().replace("+00:00", "Z"),
        market_open=None,
        market_close=None,
        next_open=(
            next_open.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if next_open
            else None
        ),
        reason=reason,
        is_extended_hours=is_extended,
    )


def get_premarket_estimates(
    config_id: str,
    tickers: list[str],
    finnhub_adapter: Any | None = None,
) -> PremarketResponse:
    """Get pre-market estimates for configuration tickers.

    Args:
        config_id: Configuration ID
        tickers: List of ticker symbols
        finnhub_adapter: FinnhubAdapter for pre-market data

    Returns:
        PremarketResponse with estimates or redirect
    """
    market_status = get_market_status()

    # If market is open, redirect to live sentiment
    if market_status.status == "open":
        return PremarketResponse(
            config_id=config_id,
            market_status="open",
            message="Market is open. Use /sentiment endpoint for live data.",
            redirect_to=f"/api/v2/configurations/{config_id}/sentiment",
        )

    now_utc = datetime.now(UTC)
    estimates = []

    for symbol in tickers:
        estimate = PremarketEstimate(
            symbol=symbol,
            premarket_price=None,
            previous_close=None,
            change_percent=None,
            estimated_sentiment={
                "score": 0.0,
                "label": "neutral",
                "confidence": 0.5,
                "basis": "premarket_momentum",
            },
            overnight_news_count=0,
            updated_at=now_utc.isoformat().replace("+00:00", "Z"),
        )

        # Try to get pre-market data from Finnhub
        if finnhub_adapter:
            try:
                # Get quote for pre-market price
                quote = finnhub_adapter.get_quote(symbol)
                if quote:
                    estimate.premarket_price = quote.get("c")  # Current price
                    estimate.previous_close = quote.get("pc")  # Previous close

                    if estimate.premarket_price and estimate.previous_close:
                        change = (
                            (estimate.premarket_price - estimate.previous_close)
                            / estimate.previous_close
                            * 100
                        )
                        estimate.change_percent = round(change, 2)

                        # Estimate sentiment from price momentum
                        if change > 1.0:
                            sentiment_score = min(0.8, change / 5)
                        elif change < -1.0:
                            sentiment_score = max(-0.8, change / 5)
                        else:
                            sentiment_score = change / 10

                        estimate.estimated_sentiment = {
                            "score": round(sentiment_score, 2),
                            "label": (
                                "positive"
                                if sentiment_score >= 0.33
                                else (
                                    "negative"
                                    if sentiment_score <= -0.33
                                    else "neutral"
                                )
                            ),
                            "confidence": 0.65,
                            "basis": "premarket_momentum",
                        }

                # Get overnight news count
                news = finnhub_adapter.get_news([symbol], limit=10)
                estimate.overnight_news_count = len(news) if news else 0

            except Exception as e:
                logger.warning(
                    "Failed to get pre-market data",
                    extra={"symbol": sanitize_for_log(symbol), "error": str(e)},
                )

        estimates.append(estimate)

    return PremarketResponse(
        config_id=config_id,
        market_status="closed",
        data_source="finnhub_premarket",
        estimates=estimates,
        disclaimer="Pre-market estimates are predictive and may not reflect market open conditions",
        next_market_open=market_status.next_open,
    )


# Helper functions


def _get_next_market_open(from_dt: datetime) -> datetime | None:
    """Get the next market open time.

    Args:
        from_dt: Starting datetime (in NYC timezone)

    Returns:
        Next market open datetime or None
    """
    check_dt = from_dt

    # Look up to 10 days ahead (handles long weekends + holidays)
    for _ in range(10):
        # Move to next day if past market hours today
        if check_dt.time() >= MARKET_CLOSE_TIME or check_dt == from_dt:
            check_dt = check_dt + timedelta(days=1)
            check_dt = check_dt.replace(
                hour=MARKET_OPEN_TIME.hour,
                minute=MARKET_OPEN_TIME.minute,
                second=0,
                microsecond=0,
            )

        # Skip weekends
        while check_dt.weekday() >= 5:
            check_dt = check_dt + timedelta(days=1)

        # Check for holidays
        day_key = (check_dt.month, check_dt.day)
        if day_key not in NYSE_HOLIDAYS_2025:
            return check_dt

        check_dt = check_dt + timedelta(days=1)

    return None

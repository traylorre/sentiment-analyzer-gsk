"""Volatility endpoints for Feature 006.

Implements volatility visualization (T058-T059):
- GET /api/v2/configurations/{id}/volatility - ATR volatility data
- GET /api/v2/configurations/{id}/correlation - Sentiment-volatility correlation

For On-Call Engineers:
    ATR calculations use OHLC data from Tiingo/Finnhub.
    If calculations are missing:
    1. Check OHLC data availability for the ticker
    2. Verify enough historical data exists (14+ days)
    3. Check API adapters for rate limits

Security Notes:
    - OHLC data is public market data
    - Calculations are performed server-side
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
from src.lambdas.shared.volatility import calculate_atr_result

logger = logging.getLogger(__name__)


# Response schemas


class ATRData(BaseModel):
    """ATR volatility data."""

    value: float = Field(..., ge=0.0)
    percent: float = Field(..., ge=0.0)
    period: int = Field(default=14)
    trend: str = Field(..., pattern="^(increasing|decreasing|stable)$")
    trend_arrow: str = Field(..., pattern="^[↑↓→]$")
    previous_value: float = Field(..., ge=0.0)


class TickerVolatility(BaseModel):
    """Volatility data for a single ticker."""

    symbol: str
    atr: ATRData
    includes_extended_hours: bool
    updated_at: str


class VolatilityResponse(BaseModel):
    """Response for GET /api/v2/configurations/{id}/volatility."""

    config_id: str
    tickers: list[TickerVolatility]


class CorrelationData(BaseModel):
    """Sentiment-volatility correlation data."""

    sentiment_trend: str = Field(..., pattern="^[↑↓→]$")
    volatility_trend: str = Field(..., pattern="^[↑↓→]$")
    interpretation: str
    description: str


class TickerCorrelation(BaseModel):
    """Correlation data for a single ticker."""

    symbol: str
    correlation: CorrelationData


class CorrelationResponse(BaseModel):
    """Response for GET /api/v2/configurations/{id}/correlation."""

    config_id: str
    tickers: list[TickerCorrelation]


# Constants

TREND_ARROW_MAP = {
    "increasing": "↑",
    "decreasing": "↓",
    "stable": "→",
}

INTERPRETATION_DESCRIPTIONS = {
    "positive_divergence": "Sentiment improving while volatility decreasing",
    "negative_divergence": "Sentiment declining while volatility increasing",
    "positive_convergence": "Both sentiment and volatility increasing",
    "negative_convergence": "Both sentiment and volatility decreasing",
    "stable": "Both sentiment and volatility stable",
}


# Service functions


def get_volatility_by_configuration(
    config_id: str,
    tickers: list[str],
    include_extended_hours: bool = False,
    atr_period: int = 14,
    tiingo_adapter: Any | None = None,
    finnhub_adapter: Any | None = None,
) -> VolatilityResponse:
    """Get ATR volatility data for configuration tickers.

    Args:
        config_id: Configuration ID
        tickers: List of ticker symbols
        include_extended_hours: Include pre/post market data
        atr_period: ATR calculation period (default 14)
        tiingo_adapter: TiingoAdapter for OHLC data
        finnhub_adapter: FinnhubAdapter for OHLC data

    Returns:
        VolatilityResponse with ATR data
    """
    now = datetime.now(UTC)
    ticker_volatilities = []

    # Need at least atr_period + 1 days of data
    days_needed = atr_period + 5
    start_date = now - timedelta(days=days_needed)

    for symbol in tickers:
        try:
            # Try Tiingo first, fall back to Finnhub
            ohlc_data = None

            if tiingo_adapter:
                try:
                    ohlc_data = tiingo_adapter.get_ohlc(
                        symbol,
                        start_date=start_date,
                        end_date=now,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to get Tiingo OHLC",
                        extra={
                            "symbol": sanitize_for_log(symbol),
                            **get_safe_error_info(e),
                        },
                    )

            if not ohlc_data and finnhub_adapter:
                try:
                    ohlc_data = finnhub_adapter.get_ohlc(
                        symbol,
                        start_date=start_date,
                        end_date=now,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to get Finnhub OHLC",
                        extra={
                            "symbol": sanitize_for_log(symbol),
                            **get_safe_error_info(e),
                        },
                    )

            calculated = False
            if ohlc_data and len(ohlc_data) >= atr_period:
                # Calculate ATR
                atr_result = calculate_atr_result(symbol, ohlc_data, period=atr_period)

                if atr_result is not None:
                    # Get previous ATR for trend calculation
                    if len(ohlc_data) > atr_period:
                        previous_ohlc = ohlc_data[:-1]
                        previous_result = calculate_atr_result(
                            symbol, previous_ohlc, period=atr_period
                        )
                        previous_value = (
                            previous_result.atr if previous_result else atr_result.atr
                        )
                    else:
                        previous_value = atr_result.atr

                    # Determine trend
                    trend = _determine_trend(atr_result.atr, previous_value)

                    # Calculate ATR percent (ATR / current price * 100)
                    current_price = ohlc_data[-1].close
                    atr_percent = (
                        (atr_result.atr / current_price) * 100
                        if current_price > 0
                        else 0.0
                    )

                    ticker_volatilities.append(
                        TickerVolatility(
                            symbol=symbol,
                            atr=ATRData(
                                value=round(atr_result.atr, 2),
                                percent=round(atr_percent, 2),
                                period=atr_period,
                                trend=trend,
                                trend_arrow=TREND_ARROW_MAP[trend],
                                previous_value=round(previous_value, 2),
                            ),
                            includes_extended_hours=include_extended_hours,
                            updated_at=now.isoformat().replace("+00:00", "Z"),
                        )
                    )
                    calculated = True

            if not calculated:
                # Insufficient data or failed calculation, return placeholder
                ticker_volatilities.append(
                    TickerVolatility(
                        symbol=symbol,
                        atr=ATRData(
                            value=0.0,
                            percent=0.0,
                            period=atr_period,
                            trend="stable",
                            trend_arrow="→",
                            previous_value=0.0,
                        ),
                        includes_extended_hours=include_extended_hours,
                        updated_at=now.isoformat().replace("+00:00", "Z"),
                    )
                )

        except Exception as e:
            logger.error(
                "Failed to calculate volatility",
                extra={
                    "symbol": sanitize_for_log(symbol),
                    **get_safe_error_info(e),
                },
            )
            # Add placeholder on error
            ticker_volatilities.append(
                TickerVolatility(
                    symbol=symbol,
                    atr=ATRData(
                        value=0.0,
                        percent=0.0,
                        period=atr_period,
                        trend="stable",
                        trend_arrow="→",
                        previous_value=0.0,
                    ),
                    includes_extended_hours=include_extended_hours,
                    updated_at=now.isoformat().replace("+00:00", "Z"),
                )
            )

    logger.info(
        "Retrieved volatility data",
        extra={
            "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
            "ticker_count": len(tickers),
        },
    )

    return VolatilityResponse(
        config_id=config_id,
        tickers=ticker_volatilities,
    )


def get_correlation_data(
    config_id: str,
    tickers: list[str],
    sentiment_trends: dict[str, str] | None = None,
    volatility_trends: dict[str, str] | None = None,
) -> CorrelationResponse:
    """Get sentiment-volatility correlation data.

    Args:
        config_id: Configuration ID
        tickers: List of ticker symbols
        sentiment_trends: Dict of symbol -> trend arrow
        volatility_trends: Dict of symbol -> trend arrow

    Returns:
        CorrelationResponse with correlation data
    """
    # Warn if trends are not provided - this causes all tickers to show "stable" which is misleading
    if sentiment_trends is None:
        logger.warning(
            "get_correlation_data called without sentiment_trends - all tickers will show stable trend",
            extra={"config_id": sanitize_for_log(config_id[:8] if config_id else "")},
        )
    if volatility_trends is None:
        logger.warning(
            "get_correlation_data called without volatility_trends - all tickers will show stable trend",
            extra={"config_id": sanitize_for_log(config_id[:8] if config_id else "")},
        )

    ticker_correlations = []

    for symbol in tickers:
        # Get trends (default to stable if not provided)
        # NOTE: Default "→" is a fallback pattern - if you see this in logs, caller should provide real data
        sentiment_arrow = (sentiment_trends or {}).get(symbol, "→")
        volatility_arrow = (volatility_trends or {}).get(symbol, "→")

        # Determine interpretation
        interpretation = _get_interpretation(sentiment_arrow, volatility_arrow)
        description = INTERPRETATION_DESCRIPTIONS.get(
            interpretation,
            "Analyzing sentiment and volatility trends",
        )

        ticker_correlations.append(
            TickerCorrelation(
                symbol=symbol,
                correlation=CorrelationData(
                    sentiment_trend=sentiment_arrow,
                    volatility_trend=volatility_arrow,
                    interpretation=interpretation,
                    description=description,
                ),
            )
        )

    logger.debug(
        "Generated correlation data",
        extra={
            "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
            "ticker_count": len(tickers),
        },
    )

    return CorrelationResponse(
        config_id=config_id,
        tickers=ticker_correlations,
    )


# Helper functions


def _determine_trend(current: float, previous: float, threshold: float = 0.05) -> str:
    """Determine trend direction.

    Args:
        current: Current ATR value
        previous: Previous ATR value
        threshold: Percentage change threshold for trend

    Returns:
        Trend string: increasing, decreasing, or stable
    """
    if previous == 0:
        return "stable"

    pct_change = (current - previous) / previous

    if pct_change > threshold:
        return "increasing"
    elif pct_change < -threshold:
        return "decreasing"
    else:
        return "stable"


def _get_interpretation(
    sentiment_arrow: str,
    volatility_arrow: str,
) -> str:
    """Get correlation interpretation based on trend arrows.

    Args:
        sentiment_arrow: Sentiment trend arrow (↑, ↓, →)
        volatility_arrow: Volatility trend arrow (↑, ↓, →)

    Returns:
        Interpretation string
    """
    # Map arrows to direction
    sentiment_dir = {"↑": 1, "↓": -1, "→": 0}.get(sentiment_arrow, 0)
    volatility_dir = {"↑": 1, "↓": -1, "→": 0}.get(volatility_arrow, 0)

    # Divergence: opposite directions
    if sentiment_dir > 0 and volatility_dir < 0:
        return "positive_divergence"
    elif sentiment_dir < 0 and volatility_dir > 0:
        return "negative_divergence"

    # Convergence: same direction
    if sentiment_dir > 0 and volatility_dir > 0:
        return "positive_convergence"
    elif sentiment_dir < 0 and volatility_dir < 0:
        return "negative_convergence"

    # Stable
    return "stable"

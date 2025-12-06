"""Volatility calculator using Average True Range (ATR).

ATR measures market volatility by analyzing the range of price
movements over a specified period. It's the industry standard
for technical analysis.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from src.lambdas.shared.adapters.base import OHLCCandle
from src.lambdas.shared.logging_utils import sanitize_for_log

logger = logging.getLogger(__name__)


@dataclass
class ATRResult:
    """Result of ATR volatility calculation."""

    ticker: str
    atr: float  # Average True Range in dollars
    atr_percent: float  # ATR as percentage of closing price
    period: int  # Number of periods used
    calculated_at: datetime
    candle_count: int  # Number of candles used

    # Trend direction based on ATR change
    trend: Literal["increasing", "decreasing", "stable"]
    trend_arrow: Literal["↑", "↓", "→"]

    # Thresholds for classification
    volatility_level: Literal["low", "medium", "high"]


def calculate_true_range(
    high: float, low: float, previous_close: float | None
) -> float:
    """Calculate True Range for a single candle.

    True Range is the greatest of:
    - Current high - current low
    - |Current high - previous close|
    - |Current low - previous close|

    Args:
        high: Current period high price
        low: Current period low price
        previous_close: Previous period close price (None for first candle)

    Returns:
        True Range value
    """
    if previous_close is None:
        # First candle: just use high-low range
        return high - low

    return max(
        high - low,
        abs(high - previous_close),
        abs(low - previous_close),
    )


def calculate_atr(
    candles: list[OHLCCandle],
    period: int = 14,
) -> float | None:
    """Calculate Average True Range from OHLC candles.

    Uses Simple Moving Average (SMA) of True Range.

    Args:
        candles: List of OHLC candles (oldest first)
        period: Number of periods for averaging (default: 14)

    Returns:
        ATR value or None if insufficient data
    """
    if len(candles) < period:
        logger.warning(
            f"Insufficient candles for ATR: got {len(candles)}, need {period}"
        )
        return None

    # Calculate True Range for each candle
    true_ranges: list[float] = []

    for i, candle in enumerate(candles):
        previous_close = candles[i - 1].close if i > 0 else None
        tr = calculate_true_range(candle.high, candle.low, previous_close)
        true_ranges.append(tr)

    # Calculate ATR as SMA of last 'period' True Ranges
    recent_trs = true_ranges[-period:]
    return sum(recent_trs) / len(recent_trs)


def calculate_atr_result(
    ticker: str,
    candles: list[OHLCCandle],
    period: int = 14,
    high_volatility_threshold: float = 0.03,  # 3% ATR = high
    low_volatility_threshold: float = 0.01,  # 1% ATR = low
) -> ATRResult | None:
    """Calculate comprehensive ATR result with trend analysis.

    Args:
        ticker: Stock symbol
        candles: List of OHLC candles (oldest first)
        period: Number of periods for ATR calculation
        high_volatility_threshold: ATR% above this is high volatility
        low_volatility_threshold: ATR% below this is low volatility

    Returns:
        ATRResult with volatility metrics or None if insufficient data
    """
    if len(candles) < period:
        logger.warning(
            "Insufficient candles for ticker",
            extra={
                "ticker": sanitize_for_log(ticker),
                "candle_count": len(candles),
                "period_required": period,
            },
        )
        return None

    # Calculate current ATR
    atr = calculate_atr(candles, period)
    if atr is None:
        return None

    # Get current price for percentage calculation
    current_price = candles[-1].close
    if current_price <= 0:
        logger.warning(
            "Invalid closing price for ticker",
            extra={
                "ticker": sanitize_for_log(ticker),
                "current_price": current_price,
            },
        )
        return None

    atr_percent = atr / current_price

    # Determine volatility level
    if atr_percent >= high_volatility_threshold:
        volatility_level: Literal["low", "medium", "high"] = "high"
    elif atr_percent <= low_volatility_threshold:
        volatility_level = "low"
    else:
        volatility_level = "medium"

    # Calculate trend by comparing recent ATR to older ATR
    # Use half-period lookback
    trend: Literal["increasing", "decreasing", "stable"]
    trend_arrow: Literal["↑", "↓", "→"]

    if len(candles) >= period * 2:
        # Calculate ATR from period ago
        older_candles = candles[:-period]
        older_atr = calculate_atr(older_candles, period)

        if older_atr and older_atr > 0:
            change_ratio = atr / older_atr
            if change_ratio > 1.1:  # 10% increase
                trend = "increasing"
                trend_arrow = "↑"
            elif change_ratio < 0.9:  # 10% decrease
                trend = "decreasing"
                trend_arrow = "↓"
            else:
                trend = "stable"
                trend_arrow = "→"
        else:
            trend = "stable"
            trend_arrow = "→"
    else:
        # Not enough data for trend analysis
        trend = "stable"
        trend_arrow = "→"

    return ATRResult(
        ticker=ticker,
        atr=round(atr, 4),
        atr_percent=round(atr_percent, 6),
        period=period,
        calculated_at=datetime.now(UTC),
        candle_count=len(candles),
        trend=trend,
        trend_arrow=trend_arrow,
        volatility_level=volatility_level,
    )


def classify_volatility(
    atr_percent: float,
    high_threshold: float = 0.03,
    low_threshold: float = 0.01,
) -> Literal["low", "medium", "high"]:
    """Classify volatility level based on ATR percentage.

    Args:
        atr_percent: ATR as percentage of price
        high_threshold: Threshold for high volatility
        low_threshold: Threshold for low volatility

    Returns:
        Volatility classification
    """
    if atr_percent >= high_threshold:
        return "high"
    elif atr_percent <= low_threshold:
        return "low"
    else:
        return "medium"

# OHLC Data Generator for ATR Testing
#
# Generates synthetic OHLC price data with predictable ATR values
# for testing volatility calculations.

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class OHLCBar:
    """Represents a single OHLC price bar."""

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    @property
    def true_range(self) -> float:
        """Calculate True Range for this bar.

        True Range is the maximum of:
        1. High - Low (current bar range)
        2. |High - Previous Close| (gap up)
        3. |Low - Previous Close| (gap down)

        Note: For the first bar, only High - Low is used.
        """
        return self.high - self.low

    def true_range_with_previous(self, previous_close: float) -> float:
        """Calculate True Range using previous close."""
        return max(
            self.high - self.low,
            abs(self.high - previous_close),
            abs(self.low - previous_close),
        )


def generate_ohlc_data(
    seed: int,
    ticker: str,
    days: int = 14,
    base_price: float | None = None,
    volatility_percent: float = 2.0,
    start_date: datetime | None = None,
) -> list[OHLCBar]:
    """Generate synthetic OHLC data for ATR testing.

    Args:
        seed: Random seed for deterministic generation
        ticker: Stock ticker (affects base price if not specified)
        days: Number of trading days to generate
        base_price: Starting price (default: derived from seed)
        volatility_percent: Daily volatility as percentage (default: 2%)
        start_date: Most recent date (default: today UTC)

    Returns:
        List of OHLCBar, newest first
    """
    rng = random.Random(seed + hash(ticker))
    base_date = start_date or datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Default base price varies by seed
    if base_price is None:
        base_price = 100 + (seed % 100)

    current_price = base_price
    bars = []

    for i in range(days):
        date = base_date - timedelta(days=i)

        # Daily movement based on volatility
        daily_move = current_price * volatility_percent / 100
        change = (rng.random() * 2 - 1) * daily_move

        open_price = current_price
        close_price = current_price + change

        # Generate realistic high/low
        intraday_range = abs(change) + current_price * rng.random() * 0.005
        high = max(open_price, close_price) + intraday_range * rng.random()
        low = min(open_price, close_price) - intraday_range * rng.random()

        # Ensure low <= open, close <= high
        low = min(low, open_price, close_price)
        high = max(high, open_price, close_price)

        volume = 1000000 + rng.randint(0, 500000)

        bar = OHLCBar(
            date=date,
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close_price, 2),
            volume=volume,
        )
        bars.append(bar)

        # Next day starts at previous close
        current_price = close_price

    return bars


def calculate_atr(bars: list[OHLCBar], period: int = 14) -> float:
    """Calculate Average True Range from OHLC bars.

    Args:
        bars: List of OHLCBar (newest first)
        period: ATR period (default: 14)

    Returns:
        ATR value

    Raises:
        ValueError: If not enough bars for calculation
    """
    if len(bars) < period + 1:
        raise ValueError(
            f"Need at least {period + 1} bars for ATR-{period}, got {len(bars)}"
        )

    # Reverse to oldest first for calculation
    bars = list(reversed(bars))

    # Calculate True Range for each bar
    true_ranges = []
    for i in range(1, len(bars)):
        tr = bars[i].true_range_with_previous(bars[i - 1].close)
        true_ranges.append(tr)

    # Simple Moving Average of True Range
    # Use the most recent 'period' true ranges
    recent_tr = true_ranges[-period:]
    return sum(recent_tr) / len(recent_tr)


def generate_ohlc_with_target_atr(
    seed: int,
    ticker: str,
    target_atr: float,
    days: int = 14,
    base_price: float = 100.0,
    start_date: datetime | None = None,
) -> list[OHLCBar]:
    """Generate OHLC data targeting a specific ATR value.

    Useful for testing specific volatility scenarios.

    Args:
        seed: Random seed for deterministic generation
        ticker: Stock ticker
        target_atr: Desired ATR value
        days: Number of trading days
        base_price: Starting price
        start_date: Most recent date

    Returns:
        List of OHLCBar with ATR approximately equal to target_atr
    """
    # ATR ≈ daily_range, so volatility_percent ≈ (target_atr / base_price) * 100
    volatility_percent = (target_atr / base_price) * 100

    return generate_ohlc_data(
        seed=seed,
        ticker=ticker,
        days=days,
        base_price=base_price,
        volatility_percent=volatility_percent,
        start_date=start_date,
    )


def to_tiingo_format(bars: list[OHLCBar]) -> list[dict]:
    """Convert OHLCBar list to Tiingo API response format.

    Args:
        bars: List of OHLCBar

    Returns:
        List of dicts in Tiingo API format
    """
    return [
        {
            "date": bar.date.isoformat().replace("+00:00", "Z"),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "adjOpen": bar.open,
            "adjHigh": bar.high,
            "adjLow": bar.low,
            "adjClose": bar.close,
            "adjVolume": bar.volume,
            "divCash": 0.0,
            "splitFactor": 1.0,
        }
        for bar in bars
    ]

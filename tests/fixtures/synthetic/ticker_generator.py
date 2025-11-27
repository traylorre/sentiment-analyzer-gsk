"""Synthetic ticker/OHLC data generator for deterministic E2E tests.

Generates realistic but deterministic price data based on seed values.
Used by test oracle to compute expected outcomes from same inputs.
"""

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.lambdas.shared.adapters.base import OHLCCandle


@dataclass
class TickerGeneratorConfig:
    """Configuration for ticker data generation."""

    seed: int = 42
    base_price: float = 100.0
    volatility: float = 0.02  # Daily volatility as percentage
    trend: float = 0.0  # Daily drift (-0.01 to 0.01)
    gap_probability: float = 0.1  # Probability of price gap
    gap_max_percent: float = 0.05  # Maximum gap size


@dataclass
class TickerGenerator:
    """Generates deterministic OHLC price data for testing.

    Uses seeded random number generator for reproducibility.
    Same seed + config always produces identical data.
    """

    config: TickerGeneratorConfig = field(default_factory=TickerGeneratorConfig)
    _rng: random.Random = field(init=False)

    def __post_init__(self):
        """Initialize random generator with seed."""
        self._rng = random.Random(self.config.seed)

    def reset(self, seed: int | None = None) -> None:
        """Reset generator with optional new seed."""
        if seed is not None:
            self.config.seed = seed
        self._rng = random.Random(self.config.seed)

    def generate_candles(
        self,
        ticker: str,
        days: int = 30,
        end_date: datetime | None = None,
        interval: str = "1d",
    ) -> list[OHLCCandle]:
        """Generate OHLC candles for a ticker.

        Args:
            ticker: Stock symbol
            days: Number of days to generate
            end_date: End date (defaults to now UTC)
            interval: Candle interval (1d, 1h, etc.)

        Returns:
            List of OHLCCandle objects sorted by date ascending
        """
        if end_date is None:
            end_date = datetime.now(UTC).replace(
                hour=16, minute=0, second=0, microsecond=0
            )

        candles = []
        price = self.config.base_price

        for i in range(days):
            # Calculate date going backwards
            date = end_date - timedelta(days=days - 1 - i)

            # Skip weekends
            if date.weekday() >= 5:
                continue

            # Apply gap if probability triggers
            if self._rng.random() < self.config.gap_probability:
                gap_direction = 1 if self._rng.random() > 0.5 else -1
                gap_size = self._rng.uniform(0.01, self.config.gap_max_percent)
                price *= 1 + (gap_direction * gap_size)

            # Generate OHLC with realistic patterns
            candle = self._generate_candle(ticker, date, price)
            candles.append(candle)

            # Update price for next day (close becomes next open)
            price = candle.close

            # Apply daily trend/drift
            price *= 1 + self.config.trend

        return candles

    def _generate_candle(
        self, ticker: str, date: datetime, open_price: float
    ) -> OHLCCandle:
        """Generate a single OHLC candle.

        Args:
            ticker: Stock symbol (not stored in OHLCCandle per model spec)
            date: Candle date
            open_price: Opening price

        Returns:
            OHLCCandle with realistic high/low/close
        """
        # Daily return with volatility
        daily_return = self._rng.gauss(0, self.config.volatility)
        close_price = open_price * (1 + daily_return)

        # High is max of open/close plus some wick
        high_wick = abs(self._rng.gauss(0, self.config.volatility / 2))
        high = max(open_price, close_price) * (1 + high_wick)

        # Low is min of open/close minus some wick
        low_wick = abs(self._rng.gauss(0, self.config.volatility / 2))
        low = min(open_price, close_price) * (1 - low_wick)

        # Volume based on volatility (higher vol = higher volume)
        base_volume = 1_000_000
        volume_multiplier = 1 + abs(daily_return) * 10
        volume = int(base_volume * volume_multiplier * self._rng.uniform(0.8, 1.2))

        # Note: OHLCCandle doesn't have a ticker field per model definition
        return OHLCCandle(
            date=date,
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close_price, 2),
            volume=volume,
        )

    def generate_volatile_period(
        self,
        ticker: str,
        days: int = 10,
        volatility_multiplier: float = 3.0,
        end_date: datetime | None = None,
    ) -> list[OHLCCandle]:
        """Generate a period of high volatility data.

        Useful for testing volatility alerts and ATR calculations.

        Args:
            ticker: Stock symbol
            days: Number of days
            volatility_multiplier: Multiplier for base volatility
            end_date: End date

        Returns:
            List of high-volatility OHLCCandles
        """
        original_volatility = self.config.volatility
        self.config.volatility *= volatility_multiplier

        candles = self.generate_candles(ticker, days, end_date)

        self.config.volatility = original_volatility
        return candles

    def generate_trending_period(
        self,
        ticker: str,
        days: int = 20,
        trend_direction: str = "up",
        trend_strength: float = 0.01,
        end_date: datetime | None = None,
    ) -> list[OHLCCandle]:
        """Generate a trending price period.

        Useful for testing trend detection.

        Args:
            ticker: Stock symbol
            days: Number of days
            trend_direction: 'up' or 'down'
            trend_strength: Daily trend percentage
            end_date: End date

        Returns:
            List of trending OHLCCandles
        """
        original_trend = self.config.trend
        self.config.trend = (
            trend_strength if trend_direction == "up" else -trend_strength
        )

        candles = self.generate_candles(ticker, days, end_date)

        self.config.trend = original_trend
        return candles


def create_ticker_generator(
    seed: int = 42,
    base_price: float = 100.0,
    volatility: float = 0.02,
) -> TickerGenerator:
    """Factory function to create a ticker generator.

    Args:
        seed: Random seed for reproducibility
        base_price: Starting price
        volatility: Daily volatility percentage

    Returns:
        Configured TickerGenerator
    """
    config = TickerGeneratorConfig(
        seed=seed,
        base_price=base_price,
        volatility=volatility,
    )
    return TickerGenerator(config=config)

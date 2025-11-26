"""Synthetic sentiment score generator for deterministic E2E tests.

Generates realistic sentiment distributions based on seed values.
Used by test oracle to compute expected outcomes from same inputs.
"""

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from src.lambdas.shared.adapters.base import SentimentData


@dataclass
class SentimentGeneratorConfig:
    """Configuration for sentiment data generation."""

    seed: int = 42
    base_sentiment: float = 0.0  # -1 to 1 range
    sentiment_volatility: float = 0.3  # How much sentiment varies
    buzz_base: float = 50.0  # Base buzz score
    buzz_volatility: float = 20.0  # Buzz variation
    positive_bias: float = 0.0  # Shift towards positive (-1 to 1)


@dataclass
class SentimentGenerator:
    """Generates deterministic sentiment data for testing.

    Uses seeded random number generator for reproducibility.
    Same seed + config always produces identical data.
    """

    config: SentimentGeneratorConfig = field(default_factory=SentimentGeneratorConfig)
    _rng: random.Random = field(init=False)

    def __post_init__(self):
        """Initialize random generator with seed."""
        self._rng = random.Random(self.config.seed)

    def reset(self, seed: int | None = None) -> None:
        """Reset generator with optional new seed."""
        if seed is not None:
            self.config.seed = seed
        self._rng = random.Random(self.config.seed)

    def generate_sentiment(
        self,
        ticker: str,
        timestamp: datetime | None = None,
        source: Literal["tiingo", "finnhub"] = "finnhub",
    ) -> SentimentData:
        """Generate a single sentiment data point.

        Args:
            ticker: Stock symbol
            timestamp: Data timestamp (defaults to now UTC)
            source: Data source (default: finnhub since tiingo doesn't provide sentiment)

        Returns:
            SentimentData with realistic values
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        # Generate sentiment score with noise
        base = self.config.base_sentiment + self.config.positive_bias
        noise = self._rng.gauss(0, self.config.sentiment_volatility)
        sentiment_score = max(-1.0, min(1.0, base + noise))

        # Generate buzz score (normalized to 0-1)
        buzz_noise = self._rng.gauss(0, self.config.buzz_volatility / 100)
        buzz_score = max(0.0, min(1.0, self.config.buzz_base / 100 + buzz_noise))

        # Generate article counts based on buzz
        articles_count = max(1, int(buzz_score * 100 / 5))

        # Generate bullish/bearish percentages based on sentiment
        if sentiment_score > 0:
            bullish_percent = 0.5 + (sentiment_score * 0.4)
            bearish_percent = 1.0 - bullish_percent
        else:
            bearish_percent = 0.5 + (abs(sentiment_score) * 0.4)
            bullish_percent = 1.0 - bearish_percent

        return SentimentData(
            ticker=ticker,
            source=source,
            fetched_at=timestamp,
            sentiment_score=round(sentiment_score, 4),
            bullish_percent=round(bullish_percent, 4),
            bearish_percent=round(bearish_percent, 4),
            articles_count=articles_count,
            buzz_score=round(buzz_score, 4),
        )

    def generate_sentiment_series(
        self,
        ticker: str,
        days: int = 30,
        end_date: datetime | None = None,
        samples_per_day: int = 1,
    ) -> list[SentimentData]:
        """Generate a time series of sentiment data.

        Args:
            ticker: Stock symbol
            days: Number of days
            end_date: End date (defaults to now UTC)
            samples_per_day: Number of samples per day

        Returns:
            List of SentimentData sorted by timestamp ascending
        """
        if end_date is None:
            end_date = datetime.now(UTC)

        sentiment_series = []

        for day_offset in range(days):
            date = end_date - timedelta(days=days - 1 - day_offset)

            for sample in range(samples_per_day):
                # Spread samples throughout the day
                hour = 9 + (7 * sample // samples_per_day)  # Between 9 AM and 4 PM
                timestamp = date.replace(hour=hour, minute=0, second=0, microsecond=0)

                sentiment = self.generate_sentiment(ticker, timestamp)
                sentiment_series.append(sentiment)

        return sentiment_series

    def generate_bullish_period(
        self,
        ticker: str,
        days: int = 10,
        end_date: datetime | None = None,
    ) -> list[SentimentData]:
        """Generate a period of bullish sentiment.

        Args:
            ticker: Stock symbol
            days: Number of days
            end_date: End date

        Returns:
            List of bullish SentimentData
        """
        original_bias = self.config.positive_bias
        self.config.positive_bias = 0.5

        series = self.generate_sentiment_series(ticker, days, end_date)

        self.config.positive_bias = original_bias
        return series

    def generate_bearish_period(
        self,
        ticker: str,
        days: int = 10,
        end_date: datetime | None = None,
    ) -> list[SentimentData]:
        """Generate a period of bearish sentiment.

        Args:
            ticker: Stock symbol
            days: Number of days
            end_date: End date

        Returns:
            List of bearish SentimentData
        """
        original_bias = self.config.positive_bias
        self.config.positive_bias = -0.5

        series = self.generate_sentiment_series(ticker, days, end_date)

        self.config.positive_bias = original_bias
        return series

    def generate_high_buzz_event(
        self,
        ticker: str,
        buzz_multiplier: float = 5.0,
    ) -> SentimentData:
        """Generate a high-buzz sentiment event.

        Useful for testing alert triggers.

        Args:
            ticker: Stock symbol
            buzz_multiplier: Multiplier for base buzz

        Returns:
            SentimentData with elevated buzz
        """
        original_buzz = self.config.buzz_base
        self.config.buzz_base *= buzz_multiplier

        sentiment = self.generate_sentiment(ticker)

        self.config.buzz_base = original_buzz
        return sentiment

    def classify_sentiment(
        self, score: float, threshold: float = 0.2
    ) -> Literal["positive", "negative", "neutral"]:
        """Classify a sentiment score.

        Args:
            score: Sentiment score (-1 to 1)
            threshold: Classification threshold

        Returns:
            Sentiment classification
        """
        if score >= threshold:
            return "positive"
        elif score <= -threshold:
            return "negative"
        else:
            return "neutral"


def create_sentiment_generator(
    seed: int = 42,
    base_sentiment: float = 0.0,
    sentiment_volatility: float = 0.3,
) -> SentimentGenerator:
    """Factory function to create a sentiment generator.

    Args:
        seed: Random seed for reproducibility
        base_sentiment: Base sentiment value
        sentiment_volatility: Sentiment variation

    Returns:
        Configured SentimentGenerator
    """
    config = SentimentGeneratorConfig(
        seed=seed,
        base_sentiment=base_sentiment,
        sentiment_volatility=sentiment_volatility,
    )
    return SentimentGenerator(config=config)

"""Test oracle that computes expected outcomes from synthetic data.

The test oracle generates the same synthetic data as the generators
and computes expected values, so tests can assert actual == expected.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from src.lambdas.shared.adapters.base import NewsArticle, OHLCCandle, SentimentData
from src.lambdas.shared.volatility import (
    ATRResult,
    calculate_atr,
    calculate_atr_result,
)
from tests.fixtures.synthetic.news_generator import (
    NewsGenerator,
    create_news_generator,
)
from tests.fixtures.synthetic.sentiment_generator import (
    SentimentGenerator,
    create_sentiment_generator,
)
from tests.fixtures.synthetic.ticker_generator import (
    TickerGenerator,
    create_ticker_generator,
)


@dataclass
class OracleExpectation:
    """Expected value from oracle computation with tolerance.

    Represents what the oracle expects for a given metric, including
    acceptable tolerance for floating point comparisons.
    """

    metric_name: str
    expected_value: float
    tolerance: float = 0.01
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_within_tolerance(self, actual_value: float) -> bool:
        """Check if actual value is within tolerance of expected.

        Args:
            actual_value: The actual value from API response

        Returns:
            True if within tolerance, False otherwise
        """
        return abs(actual_value - self.expected_value) <= self.tolerance

    def difference(self, actual_value: float) -> float:
        """Calculate difference between actual and expected.

        Args:
            actual_value: The actual value from API response

        Returns:
            Absolute difference
        """
        return abs(actual_value - self.expected_value)


@dataclass
class ValidationResult:
    """Result of validating API response against oracle expectation.

    Provides detailed information about validation outcome for
    diagnostic purposes.
    """

    expectation: OracleExpectation
    actual_value: float
    passed: bool
    difference: float
    message: str = ""

    @classmethod
    def from_comparison(
        cls,
        expectation: OracleExpectation,
        actual_value: float,
    ) -> "ValidationResult":
        """Create ValidationResult from comparing expectation to actual.

        Args:
            expectation: The oracle expectation
            actual_value: The actual value from API

        Returns:
            ValidationResult with computed fields
        """
        passed = expectation.is_within_tolerance(actual_value)
        difference = expectation.difference(actual_value)

        if passed:
            message = (
                f"{expectation.metric_name}: {actual_value:.4f} matches "
                f"expected {expectation.expected_value:.4f} "
                f"(diff: {difference:.4f}, tolerance: {expectation.tolerance})"
            )
        else:
            message = (
                f"{expectation.metric_name}: {actual_value:.4f} differs from "
                f"expected {expectation.expected_value:.4f} by {difference:.4f} "
                f"(exceeds tolerance: {expectation.tolerance})"
            )

        return cls(
            expectation=expectation,
            actual_value=actual_value,
            passed=passed,
            difference=difference,
            message=message,
        )


@dataclass
class TestScenario:
    """A complete test scenario with all generated data."""

    ticker: str
    seed: int
    candles: list[OHLCCandle]
    sentiment_series: list[SentimentData]
    news_articles: list[NewsArticle]
    expected_atr: float | None
    expected_atr_result: ATRResult | None
    expected_volatility_level: Literal["low", "medium", "high"] | None


class SyntheticTestOracle:
    """Computes expected outcomes from synthetic data.

    Uses the same seed and generators to produce deterministic
    expected values that tests can assert against.
    """

    def __init__(self, seed: int = 42):
        """Initialize oracle with seed.

        Args:
            seed: Random seed for all generators
        """
        self.seed = seed
        self._ticker_gen: TickerGenerator | None = None
        self._sentiment_gen: SentimentGenerator | None = None
        self._news_gen: NewsGenerator | None = None

    def _get_ticker_generator(self) -> TickerGenerator:
        """Get or create ticker generator with reset seed."""
        if self._ticker_gen is None:
            self._ticker_gen = create_ticker_generator(seed=self.seed)
        else:
            self._ticker_gen.reset(self.seed)
        return self._ticker_gen

    def _get_sentiment_generator(self) -> SentimentGenerator:
        """Get or create sentiment generator with reset seed."""
        if self._sentiment_gen is None:
            self._sentiment_gen = create_sentiment_generator(seed=self.seed)
        else:
            self._sentiment_gen.reset(self.seed)
        return self._sentiment_gen

    def _get_news_generator(self) -> NewsGenerator:
        """Get or create news generator with reset seed."""
        if self._news_gen is None:
            self._news_gen = create_news_generator(seed=self.seed)
        else:
            self._news_gen.reset(self.seed)
        return self._news_gen

    def compute_expected_atr(
        self,
        ticker: str,
        days: int = 30,
        period: int = 14,
        end_date: datetime | None = None,
    ) -> float | None:
        """Compute expected ATR from synthetic data.

        Args:
            ticker: Stock symbol
            days: Number of days of data
            period: ATR period
            end_date: End date

        Returns:
            Expected ATR value or None if insufficient data
        """
        gen = self._get_ticker_generator()
        candles = gen.generate_candles(ticker, days, end_date)
        return calculate_atr(candles, period)

    def compute_expected_atr_result(
        self,
        ticker: str,
        days: int = 30,
        period: int = 14,
        end_date: datetime | None = None,
    ) -> ATRResult | None:
        """Compute expected ATRResult from synthetic data.

        Args:
            ticker: Stock symbol
            days: Number of days of data
            period: ATR period
            end_date: End date

        Returns:
            Expected ATRResult or None if insufficient data
        """
        gen = self._get_ticker_generator()
        candles = gen.generate_candles(ticker, days, end_date)
        return calculate_atr_result(ticker, candles, period)

    def compute_expected_volatility_level(
        self,
        ticker: str,
        days: int = 30,
        period: int = 14,
        end_date: datetime | None = None,
    ) -> Literal["low", "medium", "high"] | None:
        """Compute expected volatility level.

        Args:
            ticker: Stock symbol
            days: Number of days of data
            period: ATR period
            end_date: End date

        Returns:
            Expected volatility level
        """
        atr_result = self.compute_expected_atr_result(ticker, days, period, end_date)
        if atr_result is None:
            return None
        return atr_result.volatility_level

    def compute_expected_avg_sentiment(
        self,
        ticker: str,
        days: int = 30,
        end_date: datetime | None = None,
    ) -> float:
        """Compute expected average sentiment score.

        Args:
            ticker: Stock symbol
            days: Number of days
            end_date: End date

        Returns:
            Expected average sentiment score
        """
        gen = self._get_sentiment_generator()
        series = gen.generate_sentiment_series(ticker, days, end_date)
        if not series:
            return 0.0
        return sum(s.sentiment_score for s in series) / len(series)

    def compute_expected_sentiment_trend(
        self,
        ticker: str,
        days: int = 14,
        end_date: datetime | None = None,
    ) -> Literal["improving", "declining", "stable"]:
        """Compute expected sentiment trend.

        Compares first half average to second half average.

        Args:
            ticker: Stock symbol
            days: Number of days
            end_date: End date

        Returns:
            Expected trend classification
        """
        gen = self._get_sentiment_generator()
        series = gen.generate_sentiment_series(ticker, days, end_date)

        if len(series) < 4:
            return "stable"

        mid = len(series) // 2
        first_half = series[:mid]
        second_half = series[mid:]

        first_avg = sum(s.sentiment_score for s in first_half) / len(first_half)
        second_avg = sum(s.sentiment_score for s in second_half) / len(second_half)

        diff = second_avg - first_avg
        threshold = 0.1

        if diff > threshold:
            return "improving"
        elif diff < -threshold:
            return "declining"
        else:
            return "stable"

    def compute_expected_news_sentiment_distribution(
        self,
        tickers: list[str],
        count: int = 20,
        days_back: int = 7,
    ) -> dict[str, int]:
        """Compute expected news sentiment distribution.

        Args:
            tickers: List of stock symbols
            count: Number of articles
            days_back: Days to span

        Returns:
            Dict with counts of positive/negative/neutral
        """
        gen = self._get_news_generator()
        # Generate articles to advance RNG state, but we compute distribution differently
        _ = gen.generate_articles(tickers, count, days_back)

        distribution = {"positive": 0, "negative": 0, "neutral": 0}

        # Re-run generator to classify (same seed = same articles)
        gen.reset(self.seed)
        for _ in range(count):
            sentiment = gen._select_sentiment()
            distribution[sentiment] += 1

        return distribution

    def generate_test_scenario(
        self,
        ticker: str,
        days: int = 30,
        news_count: int = 15,
        end_date: datetime | None = None,
    ) -> TestScenario:
        """Generate a complete test scenario with all data.

        Args:
            ticker: Stock symbol
            days: Number of days
            news_count: Number of news articles
            end_date: End date

        Returns:
            Complete TestScenario with data and expected values
        """
        if end_date is None:
            end_date = datetime.now(UTC)

        # Generate all synthetic data (each generator gets fresh seed)
        ticker_gen = self._get_ticker_generator()
        candles = ticker_gen.generate_candles(ticker, days, end_date)

        sentiment_gen = self._get_sentiment_generator()
        sentiment_series = sentiment_gen.generate_sentiment_series(
            ticker, days, end_date
        )

        news_gen = self._get_news_generator()
        news_articles = news_gen.generate_articles([ticker], news_count, days)

        # Compute expected values
        expected_atr = calculate_atr(candles, 14)
        expected_atr_result = calculate_atr_result(ticker, candles, 14)
        expected_volatility_level = (
            expected_atr_result.volatility_level if expected_atr_result else None
        )

        return TestScenario(
            ticker=ticker,
            seed=self.seed,
            candles=candles,
            sentiment_series=sentiment_series,
            news_articles=news_articles,
            expected_atr=expected_atr,
            expected_atr_result=expected_atr_result,
            expected_volatility_level=expected_volatility_level,
        )


def create_test_oracle(seed: int = 42) -> SyntheticTestOracle:
    """Factory function to create a test oracle.

    Args:
        seed: Random seed for reproducibility

    Returns:
        Configured SyntheticTestOracle
    """
    return SyntheticTestOracle(seed=seed)


# Alias for backwards compatibility
TestOracle = SyntheticTestOracle

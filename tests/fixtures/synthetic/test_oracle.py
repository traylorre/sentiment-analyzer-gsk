"""Test oracle that computes expected outcomes from synthetic data.

The test oracle generates the same synthetic data as the generators
and computes expected values, so tests can assert actual == expected.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

# Import for type hints (avoid circular import with TYPE_CHECKING)
from typing import TYPE_CHECKING, Any, Literal

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

if TYPE_CHECKING:
    from tests.fixtures.synthetic.config_generator import SyntheticConfiguration


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

    def compute_expected_api_sentiment(
        self,
        config: "SyntheticConfiguration",
        news_articles: list[NewsArticle],
    ) -> OracleExpectation:
        """Compute expected sentiment as returned by API.

        Uses weighted averaging across tickers, matching the production
        sentiment calculation pipeline.

        Args:
            config: Configuration with ticker weights
            news_articles: News articles to compute sentiment from

        Returns:
            OracleExpectation with expected sentiment score
        """
        if not news_articles:
            return OracleExpectation(
                metric_name="sentiment_score",
                expected_value=0.0,
                tolerance=0.01,
                metadata={"reason": "no_articles", "article_count": 0},
            )

        # Group articles by ticker and compute average sentiment per ticker
        ticker_sentiments: dict[str, list[float]] = {}
        for article in news_articles:
            for ticker in article.tickers:
                if ticker not in ticker_sentiments:
                    ticker_sentiments[ticker] = []
                # Use embedded sentiment if available, otherwise estimate from content
                sentiment = getattr(article, "sentiment_score", None)
                if sentiment is None:
                    # Fallback: estimate from article properties
                    sentiment = self._estimate_article_sentiment(article)
                ticker_sentiments[ticker].append(sentiment)

        # Build ticker weight map from config
        ticker_weights = {t.symbol: t.weight for t in config.tickers}

        # Compute weighted average
        total_weight = 0.0
        weighted_sum = 0.0

        for ticker, sentiments in ticker_sentiments.items():
            if ticker in ticker_weights and sentiments:
                avg_sentiment = sum(sentiments) / len(sentiments)
                weight = ticker_weights[ticker]
                weighted_sum += avg_sentiment * weight
                total_weight += weight

        if total_weight == 0:
            expected_score = 0.0
        else:
            expected_score = weighted_sum / total_weight

        # Clamp to valid range
        expected_score = max(-1.0, min(1.0, expected_score))

        return OracleExpectation(
            metric_name="sentiment_score",
            expected_value=expected_score,
            tolerance=0.01,
            metadata={
                "ticker_count": len(ticker_sentiments),
                "article_count": len(news_articles),
                "weighted": total_weight > 0,
            },
        )

    def _estimate_article_sentiment(self, article: NewsArticle) -> float:
        """Estimate sentiment from article properties.

        Used as fallback when sentiment_score is not embedded.

        Args:
            article: NewsArticle to estimate sentiment for

        Returns:
            Estimated sentiment score in [-1.0, 1.0]
        """
        # Check for embedded expected sentiment (from synthetic generator)
        if hasattr(article, "_expected_sentiment"):
            return article._expected_sentiment

        # Simple heuristic based on title keywords
        title_lower = article.title.lower()
        positive_words = ["surge", "gain", "rise", "profit", "growth", "beat"]
        negative_words = ["fall", "drop", "loss", "miss", "decline", "crash"]

        positive_count = sum(1 for word in positive_words if word in title_lower)
        negative_count = sum(1 for word in negative_words if word in title_lower)

        if positive_count > negative_count:
            return 0.3  # Mild positive
        elif negative_count > positive_count:
            return -0.3  # Mild negative
        else:
            return 0.0  # Neutral

    def validate_api_response(
        self,
        response: dict[str, Any],
        expected: OracleExpectation,
        tolerance: float | None = None,
    ) -> ValidationResult:
        """Validate API response against oracle expectation.

        Args:
            response: Parsed JSON response from API
            expected: Oracle-computed expectation
            tolerance: Optional override for tolerance (default uses expectation's)

        Returns:
            ValidationResult with validation outcome
        """
        if tolerance is not None:
            # Create new expectation with overridden tolerance
            expected = OracleExpectation(
                metric_name=expected.metric_name,
                expected_value=expected.expected_value,
                tolerance=tolerance,
                metadata=expected.metadata,
            )

        # Extract actual sentiment from response
        actual_value = self._extract_sentiment_from_response(response)

        if actual_value is None:
            return ValidationResult(
                expectation=expected,
                actual_value=0.0,
                passed=False,
                difference=abs(expected.expected_value),
                message=(
                    f"Could not extract {expected.metric_name} from API response. "
                    f"Response keys: {list(response.keys()) if response else 'empty'}"
                ),
            )

        return ValidationResult.from_comparison(expected, actual_value)

    def _extract_sentiment_from_response(
        self, response: dict[str, Any]
    ) -> float | None:
        """Extract sentiment score from API response.

        Handles various response formats.

        Args:
            response: Parsed JSON response

        Returns:
            Sentiment score or None if not found
        """
        if not response:
            return None

        # Direct sentiment_score field
        if "sentiment_score" in response:
            return float(response["sentiment_score"])

        # Nested in 'data' field
        if "data" in response and isinstance(response["data"], dict):
            if "sentiment_score" in response["data"]:
                return float(response["data"]["sentiment_score"])

        # List of sentiments - average them
        if "sentiments" in response and isinstance(response["sentiments"], list):
            scores = [
                s.get("score", s.get("sentiment_score"))
                for s in response["sentiments"]
                if isinstance(s, dict)
            ]
            valid_scores = [s for s in scores if s is not None]
            if valid_scores:
                return sum(valid_scores) / len(valid_scores)

        # Single ticker result
        if isinstance(response, list) and response:
            first = response[0]
            if isinstance(first, dict):
                score = first.get("sentiment_score") or first.get("score")
                if score is not None:
                    return float(score)

        # Aggregate score field
        if "aggregate_score" in response:
            return float(response["aggregate_score"])

        if "average_sentiment" in response:
            return float(response["average_sentiment"])

        return None

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

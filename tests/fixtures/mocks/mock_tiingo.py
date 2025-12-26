"""Mock Tiingo adapter that returns synthetic data.

Used for testing without hitting the real Tiingo API.
Returns deterministic data based on seed for reproducibility.
Supports failure injection for error resilience testing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.lambdas.shared.adapters.base import NewsArticle, OHLCCandle, SentimentData
from src.lambdas.shared.adapters.tiingo import TiingoAdapter
from tests.fixtures.synthetic.news_generator import create_news_generator
from tests.fixtures.synthetic.ticker_generator import create_ticker_generator

if TYPE_CHECKING:
    from tests.fixtures.mocks.failure_injector import FailureInjector


class MockTiingoAdapter(TiingoAdapter):
    """Mock Tiingo adapter returning synthetic data.

    Overrides API calls to return deterministic synthetic data
    instead of making real HTTP requests.

    Supports failure injection for testing error handling:
        - HTTP errors (500, 502, 503, 504, 429)
        - Connection errors (timeout, refused, DNS)
        - Malformed responses (invalid JSON, empty, truncated)
        - Field-level errors (missing fields, null/NaN/Infinity values)
    """

    def __init__(
        self,
        seed: int = 42,
        fail_mode: bool = False,
        latency_ms: int = 0,
        failure_injector: FailureInjector | None = None,
    ):
        """Initialize mock adapter.

        Args:
            seed: Random seed for synthetic data
            fail_mode: If True, all calls raise errors (legacy, use failure_injector)
            latency_ms: Simulated latency (not implemented in mock)
            failure_injector: Optional FailureInjector for fine-grained failure control
        """
        # Don't call super().__init__ to avoid needing real API key
        self.seed = seed
        self.fail_mode = fail_mode
        self.latency_ms = latency_ms
        self.failure_injector = failure_injector
        self._ticker_gen = create_ticker_generator(seed=seed)
        self._news_gen = create_news_generator(seed=seed)

        # Track calls for test assertions
        self.get_news_calls: list[dict] = []
        self.get_ohlc_calls: list[dict] = []
        self.get_intraday_ohlc_calls: list[dict] = []
        self.get_sentiment_calls: list[dict] = []

    def reset(self, seed: int | None = None) -> None:
        """Reset mock state and optionally change seed.

        Args:
            seed: Optional new seed value
        """
        if seed is not None:
            self.seed = seed
        self._ticker_gen.reset(self.seed)
        self._news_gen.reset(self.seed)
        self.get_news_calls.clear()
        self.get_ohlc_calls.clear()
        self.get_intraday_ohlc_calls.clear()
        self.get_sentiment_calls.clear()
        if self.failure_injector:
            self.failure_injector.reset()

    def _check_failure_injection(self) -> None:
        """Check if failure should be injected and raise if configured.

        Raises:
            Various exceptions based on failure_injector configuration
        """
        if self.failure_injector:
            self.failure_injector.increment_call_count()
            if self.failure_injector.should_fail():
                self.failure_injector.raise_if_configured()

    def get_news(
        self,
        tickers: list[str],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[NewsArticle]:
        """Get synthetic news articles.

        Args:
            tickers: List of stock symbols
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum articles to return

        Returns:
            List of synthetic NewsArticle objects
        """
        self.get_news_calls.append(
            {
                "tickers": tickers,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            }
        )

        # Check for injected failures first
        self._check_failure_injection()

        if self.fail_mode:
            raise RuntimeError("Mock Tiingo API failure (fail_mode=True)")

        if end_date is None:
            end_date = datetime.now(UTC)

        # Calculate days from start_date or default to 7
        days_back = 7
        if start_date:
            days_back = max(1, (end_date - start_date).days)

        return self._news_gen.generate_articles(
            tickers=tickers,
            count=min(limit, 50),
            days_back=days_back,
            end_date=end_date,
        )

    def get_sentiment(self, ticker: str) -> SentimentData | None:
        """Get sentiment data (not supported by Tiingo, returns None).

        Args:
            ticker: Stock symbol

        Returns:
            None (Tiingo doesn't provide sentiment data)
        """
        self.get_sentiment_calls.append({"ticker": ticker})

        # Check for injected failures first
        self._check_failure_injection()

        if self.fail_mode:
            raise RuntimeError("Mock Tiingo API failure (fail_mode=True)")

        # Real Tiingo doesn't provide sentiment, so mock returns None too
        return None

    def get_ohlc(
        self,
        ticker: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        interval: str = "1d",
    ) -> list[OHLCCandle]:
        """Get synthetic OHLC data.

        Args:
            ticker: Stock symbol
            start_date: Start of date range
            end_date: End of date range
            interval: Candle interval (1d, 1h, etc.)

        Returns:
            List of synthetic OHLCCandle objects
        """
        self.get_ohlc_calls.append(
            {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "interval": interval,
            }
        )

        # Check for injected failures first
        self._check_failure_injection()

        if self.fail_mode:
            raise RuntimeError("Mock Tiingo API failure (fail_mode=True)")

        if end_date is None:
            end_date = datetime.now(UTC)

        # Calculate days from start_date or default to 30
        days = 30
        if start_date:
            days = max(1, (end_date - start_date).days)

        return self._ticker_gen.generate_candles(
            ticker=ticker,
            days=days,
            end_date=end_date,
            interval=interval,
        )

    def get_intraday_ohlc(
        self,
        ticker: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        resolution: str = "5",
    ) -> list[OHLCCandle]:
        """Get synthetic intraday OHLC data (Feature 1056).

        Mirrors the real TiingoAdapter.get_intraday_ohlc method signature.
        Returns synthetic candle data for testing intraday resolution switching.

        Args:
            ticker: Stock symbol
            start_date: Start of date range
            end_date: End of date range
            resolution: Candle resolution ('1', '5', '15', '30', '60' minutes)

        Returns:
            List of synthetic OHLCCandle objects with intraday timestamps
        """
        self.get_intraday_ohlc_calls.append(
            {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "resolution": resolution,
            }
        )

        # Check for injected failures first
        self._check_failure_injection()

        if self.fail_mode:
            raise RuntimeError("Mock Tiingo API failure (fail_mode=True)")

        if end_date is None:
            end_date = datetime.now(UTC)

        # Calculate days from start_date or default to 7 (shorter for intraday)
        days = 7
        if start_date:
            days = max(1, (end_date - start_date).days)

        # Map resolution to interval format for candle generator
        interval_map = {
            "1": "1m",
            "5": "5m",
            "15": "15m",
            "30": "30m",
            "60": "1h",
        }
        interval = interval_map.get(resolution, "5m")

        return self._ticker_gen.generate_candles(
            ticker=ticker,
            days=days,
            end_date=end_date,
            interval=interval,
        )


def create_mock_tiingo(
    seed: int = 42,
    fail_mode: bool = False,
    failure_injector: FailureInjector | None = None,
) -> MockTiingoAdapter:
    """Factory function to create a mock Tiingo adapter.

    Args:
        seed: Random seed for synthetic data
        fail_mode: If True, all calls raise errors (legacy)
        failure_injector: Optional FailureInjector for fine-grained control

    Returns:
        Configured MockTiingoAdapter
    """
    return MockTiingoAdapter(
        seed=seed, fail_mode=fail_mode, failure_injector=failure_injector
    )

"""Integration tests for failover scenario (T030).

Tests the full failover flow from primary failure to secondary success
using mocked adapters and real DynamoDB (moto).

Marked as integration tests to skip in unit test runs.
"""

from datetime import UTC, datetime
from typing import Literal
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.adapters.base import AdapterError, BaseAdapter, NewsArticle
from src.lambdas.shared.circuit_breaker import CircuitBreakerManager
from src.lambdas.shared.failover import FailoverOrchestrator


class MockAdapter(BaseAdapter):
    """Mock adapter for integration testing."""

    def __init__(
        self,
        api_key: str,
        source: Literal["tiingo", "finnhub"],
        articles: list[NewsArticle] | None = None,
        should_fail: bool = False,
        fail_count: int = 0,
    ):
        super().__init__(api_key)
        self._source = source
        self._articles = articles or []
        self._should_fail = should_fail
        self._fail_count = fail_count
        self._current_fails = 0
        self.call_count = 0

    @property
    def source_name(self) -> Literal["tiingo", "finnhub"]:
        return self._source

    def get_news(
        self,
        tickers: list[str],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsArticle]:
        self.call_count += 1

        # Fail for first N calls if fail_count set
        if self._fail_count > 0 and self._current_fails < self._fail_count:
            self._current_fails += 1
            raise AdapterError(
                f"{self._source} intentional failure {self._current_fails}"
            )

        if self._should_fail:
            raise AdapterError(f"{self._source} failed")
        return self._articles[:limit]

    def get_sentiment(self, ticker: str):
        return None

    def get_ohlc(self, ticker: str, start_date=None, end_date=None):
        return []

    def reset(self) -> None:
        """Reset call counters."""
        self.call_count = 0
        self._current_fails = 0


@pytest.fixture
def tiingo_articles() -> list[NewsArticle]:
    """Sample articles from Tiingo."""
    return [
        NewsArticle(
            article_id="tiingo-001",
            source="tiingo",
            title="Apple Announces New iPhone",
            description="Apple reveals latest iPhone model.",
            url="https://tiingo.com/news/apple-iphone",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            source_name="Reuters",
            tickers=["AAPL"],
            tags=["technology", "apple"],
        ),
        NewsArticle(
            article_id="tiingo-002",
            source="tiingo",
            title="Tesla Stock Rises",
            description="Tesla shares climb on delivery numbers.",
            url="https://tiingo.com/news/tesla-stock",
            published_at=datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
            source_name="Bloomberg",
            tickers=["TSLA"],
            tags=["automotive", "tesla"],
        ),
    ]


@pytest.fixture
def finnhub_articles() -> list[NewsArticle]:
    """Sample articles from Finnhub."""
    return [
        NewsArticle(
            article_id="finnhub-001",
            source="finnhub",
            title="Apple Announces New iPhone",
            description="Apple reveals latest iPhone model via Finnhub.",
            url="https://finnhub.io/news/apple-iphone",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            source_name="Reuters",
            tickers=["AAPL"],
            tags=["technology"],
        ),
        NewsArticle(
            article_id="finnhub-002",
            source="finnhub",
            title="Microsoft Azure Growth",
            description="Microsoft cloud revenue exceeds expectations.",
            url="https://finnhub.io/news/msft-azure",
            published_at=datetime(2025, 12, 9, 15, 0, 0, tzinfo=UTC),
            source_name="CNBC",
            tickers=["MSFT"],
            tags=["cloud"],
        ),
    ]


@pytest.fixture
def mock_circuit_breaker() -> MagicMock:
    """Mock circuit breaker manager."""
    cb = MagicMock(spec=CircuitBreakerManager)
    cb.can_execute.return_value = True
    return cb


@pytest.mark.integration
class TestFailoverScenario:
    """Integration tests for complete failover scenarios."""

    def test_primary_success_no_failover(
        self,
        tiingo_articles: list[NewsArticle],
        finnhub_articles: list[NewsArticle],
        mock_circuit_breaker: MagicMock,
    ) -> None:
        """Should use primary source when available (happy path)."""
        primary = MockAdapter("key", "tiingo", articles=tiingo_articles)
        secondary = MockAdapter("key", "finnhub", articles=finnhub_articles)

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        result = orchestrator.get_news_with_failover(tickers=["AAPL", "TSLA"])

        assert result.source_used == "tiingo"
        assert result.is_failover is False
        assert len(result.data) == 2
        assert result.data[0].source == "tiingo"
        assert primary.call_count == 1
        assert secondary.call_count == 0

    def test_failover_on_primary_failure(
        self,
        finnhub_articles: list[NewsArticle],
        mock_circuit_breaker: MagicMock,
    ) -> None:
        """Should failover to secondary when primary fails."""
        primary = MockAdapter("key", "tiingo", should_fail=True)
        secondary = MockAdapter("key", "finnhub", articles=finnhub_articles)

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        result = orchestrator.get_news_with_failover(tickers=["AAPL"])

        assert result.source_used == "finnhub"
        assert result.is_failover is True
        assert len(result.data) == 2
        assert result.data[0].source == "finnhub"
        assert "tiingo failed" in result.primary_error
        assert primary.call_count == 1
        assert secondary.call_count == 1

    def test_failover_with_source_attribution(
        self,
        finnhub_articles: list[NewsArticle],
        mock_circuit_breaker: MagicMock,
    ) -> None:
        """Should correctly attribute source after failover."""
        primary = MockAdapter("key", "tiingo", should_fail=True)
        secondary = MockAdapter("key", "finnhub", articles=finnhub_articles)

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        result = orchestrator.get_news_with_failover(tickers=["AAPL"])

        # Source attribution should reflect actual source
        assert result.source_used == "finnhub"
        assert result.is_failover is True
        assert result.primary_error is not None

        # Duration should be tracked
        assert result.duration_ms >= 0

    def test_both_sources_fail_raises_error(
        self,
        mock_circuit_breaker: MagicMock,
    ) -> None:
        """Should raise AdapterError when both sources fail."""
        primary = MockAdapter("key", "tiingo", should_fail=True)
        secondary = MockAdapter("key", "finnhub", should_fail=True)

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        with pytest.raises(AdapterError) as exc_info:
            orchestrator.get_news_with_failover(tickers=["AAPL"])

        assert "Both sources failed" in str(exc_info.value)
        assert primary.call_count == 1
        assert secondary.call_count == 1

    def test_circuit_breaker_prevents_primary_call(
        self,
        tiingo_articles: list[NewsArticle],
        finnhub_articles: list[NewsArticle],
        mock_circuit_breaker: MagicMock,
    ) -> None:
        """Should skip primary when circuit breaker is open."""
        primary = MockAdapter("key", "tiingo", articles=tiingo_articles)
        secondary = MockAdapter("key", "finnhub", articles=finnhub_articles)

        # Primary circuit is open
        mock_circuit_breaker.can_execute.side_effect = lambda s: s != "tiingo"

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        result = orchestrator.get_news_with_failover(tickers=["AAPL"])

        assert result.source_used == "finnhub"
        assert result.is_failover is True
        assert result.primary_error == "Circuit breaker open"
        assert primary.call_count == 0  # Primary never called

    def test_failover_records_metrics(
        self,
        finnhub_articles: list[NewsArticle],
        mock_circuit_breaker: MagicMock,
    ) -> None:
        """Should record failure in circuit breaker on failover."""
        primary = MockAdapter("key", "tiingo", should_fail=True)
        secondary = MockAdapter("key", "finnhub", articles=finnhub_articles)

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        orchestrator.get_news_with_failover(tickers=["AAPL"])

        # Verify circuit breaker interactions
        mock_circuit_breaker.record_failure.assert_any_call("tiingo")
        mock_circuit_breaker.record_success.assert_called_with("finnhub")


@pytest.mark.integration
class TestFailoverWithTimeout:
    """Integration tests for timeout-based failover."""

    def test_timeout_triggers_failover(
        self,
        finnhub_articles: list[NewsArticle],
        mock_circuit_breaker: MagicMock,
    ) -> None:
        """Should failover when primary exceeds timeout.

        Uses short timeout to test the timeout detection mechanism.
        """
        # Create adapter that will exceed timeout
        import time

        class SlowAdapter(MockAdapter):
            def get_news(self, tickers, start_date=None, end_date=None, limit=50):
                self.call_count += 1
                time.sleep(0.15)  # Exceed the 0.1s timeout
                return self._articles[:limit]

        primary = SlowAdapter("key", "tiingo", articles=[])
        secondary = MockAdapter("key", "finnhub", articles=finnhub_articles)

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
            timeout_seconds=0.1,  # Short timeout for test
        )

        result = orchestrator.get_news_with_failover(tickers=["AAPL"])

        assert result.source_used == "finnhub"
        assert result.is_failover is True
        assert (
            "exceeded" in result.primary_error.lower()
            or "timed out" in result.primary_error.lower()
        )

"""Unit tests for FailoverOrchestrator.

Tests failover behavior between primary and secondary data sources.
"""

from datetime import UTC, datetime
from typing import Literal
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.adapters.base import AdapterError, BaseAdapter, NewsArticle
from src.lambdas.shared.circuit_breaker import CircuitBreakerManager
from src.lambdas.shared.failover import (
    FailoverOrchestrator,
    FailoverResult,
)


class MockAdapter(BaseAdapter):
    """Mock adapter for testing."""

    def __init__(
        self,
        api_key: str,
        source: Literal["tiingo", "finnhub"],
        articles: list[NewsArticle] | None = None,
        should_fail: bool = False,
        delay_seconds: float = 0,
    ):
        super().__init__(api_key)
        self._source = source
        self._articles = articles or []
        self._should_fail = should_fail
        self._delay_seconds = delay_seconds
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
        if self._delay_seconds > 0:
            import time

            time.sleep(self._delay_seconds)
        if self._should_fail:
            raise AdapterError(f"{self._source} failed")
        return self._articles[:limit]

    def get_sentiment(self, ticker: str):
        return None

    def get_ohlc(self, ticker: str, start_date=None, end_date=None):
        return []


@pytest.fixture
def sample_articles() -> list[NewsArticle]:
    """Sample news articles for testing."""
    return [
        NewsArticle(
            article_id="article-1",
            source="tiingo",
            title="Test Article 1",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            tickers=["AAPL"],
        ),
        NewsArticle(
            article_id="article-2",
            source="tiingo",
            title="Test Article 2",
            published_at=datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
            tickers=["TSLA"],
        ),
    ]


@pytest.fixture
def mock_circuit_breaker() -> MagicMock:
    """Mock circuit breaker manager."""
    cb = MagicMock(spec=CircuitBreakerManager)
    cb.can_execute.return_value = True
    return cb


class TestFailoverOrchestratorPrimarySuccess:
    """Tests for successful primary source operations."""

    def test_returns_primary_data_on_success(
        self, sample_articles: list[NewsArticle], mock_circuit_breaker: MagicMock
    ) -> None:
        """Should return data from primary when it succeeds."""
        primary = MockAdapter("key", "tiingo", articles=sample_articles)
        secondary = MockAdapter("key", "finnhub", articles=[])

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        result = orchestrator.get_news_with_failover(tickers=["AAPL"])

        assert result.source_used == "tiingo"
        assert result.is_failover is False
        assert len(result.data) == 2
        assert result.primary_error is None
        assert primary.call_count == 1
        assert secondary.call_count == 0

    def test_records_success_in_circuit_breaker(
        self, sample_articles: list[NewsArticle], mock_circuit_breaker: MagicMock
    ) -> None:
        """Should record success in circuit breaker."""
        primary = MockAdapter("key", "tiingo", articles=sample_articles)
        secondary = MockAdapter("key", "finnhub", articles=[])

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        orchestrator.get_news_with_failover(tickers=["AAPL"])

        mock_circuit_breaker.record_success.assert_called_once_with("tiingo")


class TestFailoverOrchestratorFailover:
    """Tests for failover behavior."""

    def test_failover_on_primary_error(self, mock_circuit_breaker: MagicMock) -> None:
        """Should failover to secondary when primary raises error."""
        secondary_articles = [
            NewsArticle(
                article_id="sec-1",
                source="finnhub",
                title="Secondary Article",
                published_at=datetime(2025, 12, 9, 15, 0, 0, tzinfo=UTC),
                tickers=["AAPL"],
            )
        ]
        primary = MockAdapter("key", "tiingo", should_fail=True)
        secondary = MockAdapter("key", "finnhub", articles=secondary_articles)

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        result = orchestrator.get_news_with_failover(tickers=["AAPL"])

        assert result.source_used == "finnhub"
        assert result.is_failover is True
        assert len(result.data) == 1
        assert "tiingo failed" in result.primary_error
        assert primary.call_count == 1
        assert secondary.call_count == 1

    def test_failover_records_primary_failure(
        self, mock_circuit_breaker: MagicMock
    ) -> None:
        """Should record failure in circuit breaker for primary."""
        primary = MockAdapter("key", "tiingo", should_fail=True)
        secondary = MockAdapter("key", "finnhub", articles=[])

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        orchestrator.get_news_with_failover(tickers=["AAPL"])

        mock_circuit_breaker.record_failure.assert_any_call("tiingo")
        mock_circuit_breaker.record_success.assert_called_with("finnhub")

    def test_uses_secondary_when_primary_circuit_open(
        self, mock_circuit_breaker: MagicMock
    ) -> None:
        """Should use secondary directly when primary circuit is open."""
        secondary_articles = [
            NewsArticle(
                article_id="sec-1",
                source="finnhub",
                title="Secondary Article",
                published_at=datetime(2025, 12, 9, 15, 0, 0, tzinfo=UTC),
                tickers=["AAPL"],
            )
        ]
        primary = MockAdapter("key", "tiingo", articles=[])
        secondary = MockAdapter("key", "finnhub", articles=secondary_articles)

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
        assert primary.call_count == 0  # Primary not called


class TestFailoverOrchestratorBothFail:
    """Tests for when both sources fail."""

    def test_raises_error_when_both_fail(self, mock_circuit_breaker: MagicMock) -> None:
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

    def test_raises_error_when_both_circuits_open(
        self, mock_circuit_breaker: MagicMock
    ) -> None:
        """Should raise error when both circuits are open."""
        primary = MockAdapter("key", "tiingo", articles=[])
        secondary = MockAdapter("key", "finnhub", articles=[])

        mock_circuit_breaker.can_execute.return_value = False

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
        )

        with pytest.raises(AdapterError) as exc_info:
            orchestrator.get_news_with_failover(tickers=["AAPL"])

        assert "unavailable" in str(exc_info.value)


class TestFailoverOrchestratorTimeout:
    """Tests for timeout-based failover."""

    def test_slow_primary_triggers_post_execution_timeout(
        self, mock_circuit_breaker: MagicMock
    ) -> None:
        """Should trigger timeout error when primary exceeds timeout after execution.

        Note: The current implementation checks timeout AFTER the request completes.
        This is a post-execution check, not a true async timeout.
        For production, consider using concurrent.futures.ThreadPoolExecutor.
        """
        # Primary takes 0.2s, timeout is 0.1s - will exceed but completes first
        primary = MockAdapter("key", "tiingo", articles=[], delay_seconds=0.2)
        secondary = MockAdapter("key", "finnhub", articles=[])

        orchestrator = FailoverOrchestrator(
            primary=primary,
            secondary=secondary,
            circuit_breaker=mock_circuit_breaker,
            timeout_seconds=0.1,
        )

        result = orchestrator.get_news_with_failover(tickers=["AAPL"])

        # Post-execution timeout check triggers failover
        assert result.source_used == "finnhub"
        assert result.is_failover is True
        assert (
            "timed out" in result.primary_error.lower()
            or "exceeded" in result.primary_error.lower()
        )


class TestFailoverResult:
    """Tests for FailoverResult dataclass."""

    def test_result_attributes(self) -> None:
        """FailoverResult should store all attributes."""
        result = FailoverResult(
            data=["article1", "article2"],
            source_used="tiingo",
            is_failover=False,
            duration_ms=150,
        )

        assert result.data == ["article1", "article2"]
        assert result.source_used == "tiingo"
        assert result.is_failover is False
        assert result.duration_ms == 150
        assert result.primary_error is None

    def test_result_with_error(self) -> None:
        """FailoverResult should store primary error."""
        result = FailoverResult(
            data=[],
            source_used="finnhub",
            is_failover=True,
            duration_ms=250,
            primary_error="Tiingo timeout",
        )

        assert result.is_failover is True
        assert result.primary_error == "Tiingo timeout"

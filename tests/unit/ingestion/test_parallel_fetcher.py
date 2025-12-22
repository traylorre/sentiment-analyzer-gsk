"""Unit tests for parallel source fetching.

Tests ParallelFetcher class that fetches from Tiingo and Finnhub concurrently.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.adapters.base import NewsArticle


@pytest.fixture
def mock_tiingo_adapter():
    """Create mock Tiingo adapter."""
    adapter = MagicMock()
    adapter.source_name = "tiingo"
    return adapter


@pytest.fixture
def mock_finnhub_adapter():
    """Create mock Finnhub adapter."""
    adapter = MagicMock()
    adapter.source_name = "finnhub"
    return adapter


@pytest.fixture
def mock_quota_tracker():
    """Create mock quota tracker."""
    tracker = MagicMock()
    tracker.can_call.return_value = True
    tracker.record_call.return_value = None
    return tracker


@pytest.fixture
def mock_circuit_breaker():
    """Create mock circuit breaker."""
    breaker = MagicMock()
    breaker.can_execute.return_value = True
    breaker.record_success.return_value = None
    breaker.record_failure.return_value = None
    return breaker


@pytest.fixture
def sample_tiingo_articles():
    """Create sample Tiingo articles."""
    return [
        NewsArticle(
            article_id="tiingo-001",
            source="tiingo",
            title="Apple Reports Q4 Earnings Beat",
            description="Apple beats expectations",
            url="https://tiingo.com/news/1",
            published_at=datetime.now(UTC),
            source_name="reuters",
            tickers=["AAPL"],
            tags=["earnings"],
        ),
        NewsArticle(
            article_id="tiingo-002",
            source="tiingo",
            title="Tesla Deliveries Exceed Estimates",
            description="Tesla delivers more than expected",
            url="https://tiingo.com/news/2",
            published_at=datetime.now(UTC),
            source_name="ap",
            tickers=["TSLA"],
            tags=["deliveries"],
        ),
    ]


@pytest.fixture
def sample_finnhub_articles():
    """Create sample Finnhub articles."""
    return [
        NewsArticle(
            article_id="finnhub-001",
            source="finnhub",
            title="Apple reports Q4 earnings beat",  # Same as Tiingo but different case
            description="Apple beats expectations today",
            url="https://finnhub.io/news/1",
            published_at=datetime.now(UTC),
            source_name="reuters",
            tickers=["AAPL"],
            tags=["earnings"],
        ),
        NewsArticle(
            article_id="finnhub-002",
            source="finnhub",
            title="Microsoft Cloud Revenue Grows",
            description="Azure sees strong growth",
            url="https://finnhub.io/news/2",
            published_at=datetime.now(UTC),
            source_name="bloomberg",
            tickers=["MSFT"],
            tags=["cloud"],
        ),
    ]


class TestParallelFetcher:
    """Tests for ParallelFetcher class."""

    def test_parallel_fetch_calls_both_sources(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
        sample_tiingo_articles,
        sample_finnhub_articles,
    ):
        """Parallel fetch calls both Tiingo and Finnhub adapters."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        mock_tiingo_adapter.get_news.return_value = sample_tiingo_articles
        mock_finnhub_adapter.get_news.return_value = sample_finnhub_articles

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        tickers = ["AAPL", "TSLA"]
        results = fetcher.fetch_all_sources(tickers)

        # Both adapters should be called
        mock_tiingo_adapter.get_news.assert_called_once()
        mock_finnhub_adapter.get_news.assert_called_once()

        # Results should contain articles from both sources
        assert "tiingo" in results
        assert "finnhub" in results
        assert len(results["tiingo"]) == 2
        assert len(results["finnhub"]) == 2

    def test_parallel_fetch_handles_one_source_failure(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
        sample_tiingo_articles,
    ):
        """Parallel fetch continues when one source fails."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        mock_tiingo_adapter.get_news.return_value = sample_tiingo_articles
        mock_finnhub_adapter.get_news.side_effect = Exception("Finnhub API error")

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        tickers = ["AAPL"]
        results = fetcher.fetch_all_sources(tickers)

        # Tiingo should succeed
        assert "tiingo" in results
        assert len(results["tiingo"]) == 2

        # Finnhub should have empty list (or error tracked separately)
        assert "finnhub" in results
        assert len(results["finnhub"]) == 0

        # Check errors were captured
        errors = fetcher.get_errors()
        assert len(errors) == 1
        assert errors[0]["source"] == "finnhub"
        assert "Finnhub API error" in errors[0]["error"]

    def test_parallel_fetch_respects_rate_limits(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
        sample_tiingo_articles,
        sample_finnhub_articles,
    ):
        """Parallel fetch skips sources when quota exceeded."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        mock_tiingo_adapter.get_news.return_value = sample_tiingo_articles
        mock_finnhub_adapter.get_news.return_value = sample_finnhub_articles

        # Tiingo quota exceeded
        mock_quota_tracker.can_call.side_effect = lambda s: s != "tiingo"

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        tickers = ["AAPL"]
        results = fetcher.fetch_all_sources(tickers)

        # Tiingo should NOT be called (quota exceeded)
        mock_tiingo_adapter.get_news.assert_not_called()

        # Finnhub should be called
        mock_finnhub_adapter.get_news.assert_called_once()

        # Results should only have Finnhub
        assert results["tiingo"] == []
        assert len(results["finnhub"]) == 2

    def test_parallel_fetch_collects_results_thread_safely(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """Parallel fetch collects results without race conditions."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        # Simulate slow responses to increase chance of race conditions
        def slow_tiingo_response(*args, **kwargs):
            time.sleep(0.05)
            return [
                NewsArticle(
                    article_id=f"tiingo-{i}",
                    source="tiingo",
                    title=f"Tiingo Article {i}",
                    description="Test",
                    url=f"https://tiingo.com/{i}",
                    published_at=datetime.now(UTC),
                    tickers=["AAPL"],
                )
                for i in range(10)
            ]

        def slow_finnhub_response(*args, **kwargs):
            time.sleep(0.03)
            return [
                NewsArticle(
                    article_id=f"finnhub-{i}",
                    source="finnhub",
                    title=f"Finnhub Article {i}",
                    description="Test",
                    url=f"https://finnhub.io/{i}",
                    published_at=datetime.now(UTC),
                    tickers=["AAPL"],
                )
                for i in range(10)
            ]

        mock_tiingo_adapter.get_news.side_effect = slow_tiingo_response
        mock_finnhub_adapter.get_news.side_effect = slow_finnhub_response

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        # Run multiple times to expose potential race conditions
        for _ in range(5):
            results = fetcher.fetch_all_sources(["AAPL"])

            # Both sources should have correct count
            assert len(results["tiingo"]) == 10
            assert len(results["finnhub"]) == 10

    def test_parallel_fetch_respects_circuit_breaker(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        sample_tiingo_articles,
    ):
        """Parallel fetch skips sources when circuit breaker is open."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        mock_tiingo_adapter.get_news.return_value = sample_tiingo_articles

        # Create separate breakers
        tiingo_breaker = MagicMock()
        tiingo_breaker.can_execute.return_value = True

        finnhub_breaker = MagicMock()
        finnhub_breaker.can_execute.return_value = False  # Open circuit

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=tiingo_breaker,
            finnhub_breaker=finnhub_breaker,
            quota_tracker=mock_quota_tracker,
        )

        tickers = ["AAPL"]
        results = fetcher.fetch_all_sources(tickers)

        # Tiingo should be called
        mock_tiingo_adapter.get_news.assert_called_once()

        # Finnhub should NOT be called (circuit open)
        mock_finnhub_adapter.get_news.assert_not_called()

        # Results reflect which sources were called
        assert len(results["tiingo"]) == 2
        assert results["finnhub"] == []

    def test_parallel_fetch_records_success_to_circuit_breaker(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
        sample_tiingo_articles,
        sample_finnhub_articles,
    ):
        """Parallel fetch records success to circuit breakers."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        mock_tiingo_adapter.get_news.return_value = sample_tiingo_articles
        mock_finnhub_adapter.get_news.return_value = sample_finnhub_articles

        tiingo_breaker = MagicMock()
        tiingo_breaker.can_execute.return_value = True
        finnhub_breaker = MagicMock()
        finnhub_breaker.can_execute.return_value = True

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=tiingo_breaker,
            finnhub_breaker=finnhub_breaker,
            quota_tracker=mock_quota_tracker,
        )

        fetcher.fetch_all_sources(["AAPL"])

        # Both breakers should record success
        tiingo_breaker.record_success.assert_called_once()
        finnhub_breaker.record_success.assert_called_once()

    def test_parallel_fetch_records_failure_to_circuit_breaker(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        sample_tiingo_articles,
    ):
        """Parallel fetch records failure to circuit breaker."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        mock_tiingo_adapter.get_news.return_value = sample_tiingo_articles
        mock_finnhub_adapter.get_news.side_effect = Exception("API Error")

        tiingo_breaker = MagicMock()
        tiingo_breaker.can_execute.return_value = True
        finnhub_breaker = MagicMock()
        finnhub_breaker.can_execute.return_value = True

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=tiingo_breaker,
            finnhub_breaker=finnhub_breaker,
            quota_tracker=mock_quota_tracker,
        )

        fetcher.fetch_all_sources(["AAPL"])

        # Tiingo records success
        tiingo_breaker.record_success.assert_called_once()

        # Finnhub records failure
        finnhub_breaker.record_failure.assert_called_once()


class TestParallelFetcherQuotaIntegration:
    """Tests for ParallelFetcher quota integration."""

    def test_pre_fetch_quota_check(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_circuit_breaker,
        sample_tiingo_articles,
    ):
        """Pre-fetch quota check prevents unnecessary API calls."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        quota_tracker = MagicMock()
        # Both sources at critical quota
        quota_tracker.can_call.return_value = False

        mock_tiingo_adapter.get_news.return_value = sample_tiingo_articles

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=quota_tracker,
        )

        tickers = ["AAPL"]
        results = fetcher.fetch_all_sources(tickers)

        # Neither adapter should be called
        mock_tiingo_adapter.get_news.assert_not_called()
        mock_finnhub_adapter.get_news.assert_not_called()

        # Results should be empty
        assert results["tiingo"] == []
        assert results["finnhub"] == []

    def test_quota_recorded_per_source(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_circuit_breaker,
        sample_tiingo_articles,
        sample_finnhub_articles,
    ):
        """Quota is recorded for each source after fetch."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        quota_tracker = MagicMock()
        quota_tracker.can_call.return_value = True

        mock_tiingo_adapter.get_news.return_value = sample_tiingo_articles
        mock_finnhub_adapter.get_news.return_value = sample_finnhub_articles

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=quota_tracker,
        )

        fetcher.fetch_all_sources(["AAPL"])

        # Both sources should record quota
        calls = quota_tracker.record_call.call_args_list
        source_calls = {call[0][0] for call in calls}
        assert "tiingo" in source_calls
        assert "finnhub" in source_calls


class TestParallelFetcherMetrics:
    """Tests for ParallelFetcher metrics collection."""

    def test_get_metrics_returns_fetch_stats(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
        sample_tiingo_articles,
        sample_finnhub_articles,
    ):
        """get_metrics returns statistics about the fetch operation."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        mock_tiingo_adapter.get_news.return_value = sample_tiingo_articles
        mock_finnhub_adapter.get_news.return_value = sample_finnhub_articles

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        fetcher.fetch_all_sources(["AAPL"])
        metrics = fetcher.get_metrics()

        assert "tiingo_count" in metrics
        assert "finnhub_count" in metrics
        assert "total_count" in metrics
        assert "duration_ms" in metrics
        assert metrics["tiingo_count"] == 2
        assert metrics["finnhub_count"] == 2
        assert metrics["total_count"] == 4
        assert metrics["duration_ms"] >= 0

    def test_get_errors_returns_all_failures(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """get_errors returns all failures from fetch operation."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        mock_tiingo_adapter.get_news.side_effect = Exception("Tiingo failed")
        mock_finnhub_adapter.get_news.side_effect = Exception("Finnhub failed")

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        fetcher.fetch_all_sources(["AAPL"])
        errors = fetcher.get_errors()

        assert len(errors) == 2
        sources = {e["source"] for e in errors}
        assert sources == {"tiingo", "finnhub"}

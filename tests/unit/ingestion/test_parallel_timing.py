"""Unit tests for parallel execution timing.

Verifies that parallel fetching is faster than sequential fetching.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.adapters.base import NewsArticle


@pytest.fixture
def mock_tiingo_adapter():
    """Create mock Tiingo adapter with simulated latency."""
    adapter = MagicMock()
    adapter.source_name = "tiingo"
    return adapter


@pytest.fixture
def mock_finnhub_adapter():
    """Create mock Finnhub adapter with simulated latency."""
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


def create_articles(source: str, count: int) -> list[NewsArticle]:
    """Create sample articles for a source."""
    return [
        NewsArticle(
            article_id=f"{source}-{i}",
            source=source,
            title=f"{source.title()} Article {i}",
            description=f"Description {i}",
            url=f"https://{source}.com/article/{i}",
            published_at=datetime.now(UTC),
            tickers=["AAPL"],
        )
        for i in range(count)
    ]


class TestParallelTiming:
    """Tests for parallel execution timing."""

    def test_parallel_execution_faster_than_sequential(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """Parallel execution completes faster than sequential would."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        # Simulate 100ms latency for each source
        latency_ms = 100

        def slow_tiingo(*args, **kwargs):
            time.sleep(latency_ms / 1000)
            return create_articles("tiingo", 5)

        def slow_finnhub(*args, **kwargs):
            time.sleep(latency_ms / 1000)
            return create_articles("finnhub", 5)

        mock_tiingo_adapter.get_news.side_effect = slow_tiingo
        mock_finnhub_adapter.get_news.side_effect = slow_finnhub

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        start = time.time()
        results = fetcher.fetch_all_sources(["AAPL"])
        elapsed_ms = (time.time() - start) * 1000

        # Verify results
        assert len(results["tiingo"]) == 5
        assert len(results["finnhub"]) == 5

        # Parallel should take ~100ms (latency of slowest source)
        # Sequential would take ~200ms (latency of both)
        # Allow 50ms overhead for thread creation
        max_parallel_time = latency_ms + 50
        min_sequential_time = latency_ms * 2 - 20  # With some tolerance

        assert (
            elapsed_ms < min_sequential_time
        ), f"Execution took {elapsed_ms:.0f}ms, appears sequential (>={min_sequential_time}ms)"
        assert (
            elapsed_ms < max_parallel_time
        ), f"Execution took {elapsed_ms:.0f}ms, too slow for parallel (<{max_parallel_time}ms)"

    def test_parallel_execution_with_varying_latencies(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """Parallel execution handles sources with different latencies."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        # Tiingo is fast, Finnhub is slow
        tiingo_latency_ms = 50
        finnhub_latency_ms = 150

        def fast_tiingo(*args, **kwargs):
            time.sleep(tiingo_latency_ms / 1000)
            return create_articles("tiingo", 3)

        def slow_finnhub(*args, **kwargs):
            time.sleep(finnhub_latency_ms / 1000)
            return create_articles("finnhub", 3)

        mock_tiingo_adapter.get_news.side_effect = fast_tiingo
        mock_finnhub_adapter.get_news.side_effect = slow_finnhub

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        start = time.time()
        results = fetcher.fetch_all_sources(["AAPL"])
        elapsed_ms = (time.time() - start) * 1000

        # Should be dominated by slowest source + overhead
        # Parallel: ~150ms, Sequential: ~200ms
        max_parallel_time = finnhub_latency_ms + 50
        assert (
            elapsed_ms < max_parallel_time
        ), f"Execution took {elapsed_ms:.0f}ms, expected <{max_parallel_time}ms"

        # Verify both returned results
        assert len(results["tiingo"]) == 3
        assert len(results["finnhub"]) == 3

    def test_parallel_execution_with_one_source_failure(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """Parallel execution completes quickly even when one source fails."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        latency_ms = 100

        def slow_tiingo(*args, **kwargs):
            time.sleep(latency_ms / 1000)
            return create_articles("tiingo", 5)

        def failing_finnhub(*args, **kwargs):
            time.sleep(20 / 1000)  # Fast failure
            raise Exception("Finnhub error")

        mock_tiingo_adapter.get_news.side_effect = slow_tiingo
        mock_finnhub_adapter.get_news.side_effect = failing_finnhub

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        start = time.time()
        results = fetcher.fetch_all_sources(["AAPL"])
        elapsed_ms = (time.time() - start) * 1000

        # Should still complete in parallel time (not blocked by failure)
        max_time = latency_ms + 50
        assert (
            elapsed_ms < max_time
        ), f"Execution took {elapsed_ms:.0f}ms, failure blocked parallel execution"

        # Tiingo should succeed
        assert len(results["tiingo"]) == 5
        # Finnhub should be empty
        assert results["finnhub"] == []

    def test_duration_ms_metric_is_accurate(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """duration_ms metric accurately reflects actual execution time."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        latency_ms = 75

        def slow_response(*args, **kwargs):
            time.sleep(latency_ms / 1000)
            return create_articles("test", 2)

        mock_tiingo_adapter.get_news.side_effect = slow_response
        mock_finnhub_adapter.get_news.side_effect = slow_response

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        external_start = time.time()
        fetcher.fetch_all_sources(["AAPL"])
        external_elapsed_ms = (time.time() - external_start) * 1000

        metrics = fetcher.get_metrics()

        # Internal duration should match external measurement (within tolerance)
        assert abs(metrics["duration_ms"] - external_elapsed_ms) < 20

    def test_parallel_execution_scales_with_tickers(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """Parallel execution time doesn't increase linearly with tickers."""
        from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

        latency_ms = 50

        def constant_latency_tiingo(*args, **kwargs):
            time.sleep(latency_ms / 1000)
            return create_articles("tiingo", 10)

        def constant_latency_finnhub(*args, **kwargs):
            time.sleep(latency_ms / 1000)
            return create_articles("finnhub", 10)

        mock_tiingo_adapter.get_news.side_effect = constant_latency_tiingo
        mock_finnhub_adapter.get_news.side_effect = constant_latency_finnhub

        fetcher = ParallelFetcher(
            tiingo_adapter=mock_tiingo_adapter,
            finnhub_adapter=mock_finnhub_adapter,
            tiingo_breaker=mock_circuit_breaker,
            finnhub_breaker=mock_circuit_breaker,
            quota_tracker=mock_quota_tracker,
        )

        # Test with different ticker counts
        for ticker_count in [1, 5, 10]:
            tickers = [f"TICK{i}" for i in range(ticker_count)]

            start = time.time()
            fetcher.fetch_all_sources(tickers)
            elapsed_ms = (time.time() - start) * 1000

            # Should still be parallel time regardless of ticker count
            # (assuming adapters handle all tickers in one call)
            max_time = latency_ms + 50
            assert (
                elapsed_ms < max_time
            ), f"{ticker_count} tickers took {elapsed_ms:.0f}ms, expected <{max_time}ms"

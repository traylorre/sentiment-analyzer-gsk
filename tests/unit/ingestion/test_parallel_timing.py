"""Unit tests for parallel execution.

Concurrency is proved by synchronisation: each source waits for the other inside its
fetch, which only a concurrent fetch can satisfy. An elapsed-time ceiling cannot tell a
parallel run on a loaded host from a sequential run on an idle one.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

import threading
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


# Generous liveness bound: a concurrent fetch meets in microseconds, a sequential one never does
RENDEZVOUS_TIMEOUT_S = 5.0


def rendezvous(barrier, outcome, source, articles):
    """Adapter side effect that waits for the other source inside its own fetch."""

    def get_news(*args, **kwargs):
        try:
            barrier.wait(timeout=RENDEZVOUS_TIMEOUT_S)
            outcome[source] = "met"
        except threading.BrokenBarrierError:
            outcome[source] = "alone"
        return articles

    return get_news


def make_fetcher(tiingo, finnhub, breaker, tracker):
    from src.lambdas.ingestion.parallel_fetcher import ParallelFetcher

    return ParallelFetcher(
        tiingo_adapter=tiingo,
        finnhub_adapter=finnhub,
        tiingo_breaker=breaker,
        finnhub_breaker=breaker,
        quota_tracker=tracker,
    )


class TestParallelExecution:
    """Tests that sources are fetched concurrently."""

    def test_sources_fetch_concurrently(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """Both sources are inside their fetch at the same time."""
        barrier = threading.Barrier(2)
        outcome = {}
        mock_tiingo_adapter.get_news.side_effect = rendezvous(
            barrier, outcome, "tiingo", create_articles("tiingo", 5)
        )
        mock_finnhub_adapter.get_news.side_effect = rendezvous(
            barrier, outcome, "finnhub", create_articles("finnhub", 5)
        )
        fetcher = make_fetcher(
            mock_tiingo_adapter,
            mock_finnhub_adapter,
            mock_circuit_breaker,
            mock_quota_tracker,
        )

        results = fetcher.fetch_all_sources(["AAPL"])

        assert outcome == {"tiingo": "met", "finnhub": "met"}, (
            f"sources did not overlap, so the fetch ran sequentially: {outcome}"
        )
        assert len(results["tiingo"]) == 5
        assert len(results["finnhub"]) == 5

    def test_fast_source_completes_while_slow_source_is_in_flight(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """A slow source does not hold back a fast one."""
        barrier = threading.Barrier(2)
        tiingo_returned = threading.Event()
        outcome = {}
        tiingo_fetch = rendezvous(
            barrier, outcome, "tiingo", create_articles("tiingo", 3)
        )

        def fast_tiingo(*args, **kwargs):
            articles = tiingo_fetch(*args, **kwargs)
            tiingo_returned.set()
            return articles

        def slow_finnhub(*args, **kwargs):
            articles = rendezvous(
                barrier, outcome, "finnhub", create_articles("finnhub", 3)
            )()
            outcome["tiingo_done_first"] = tiingo_returned.wait(
                timeout=RENDEZVOUS_TIMEOUT_S
            )
            return articles

        mock_tiingo_adapter.get_news.side_effect = fast_tiingo
        mock_finnhub_adapter.get_news.side_effect = slow_finnhub
        fetcher = make_fetcher(
            mock_tiingo_adapter,
            mock_finnhub_adapter,
            mock_circuit_breaker,
            mock_quota_tracker,
        )

        results = fetcher.fetch_all_sources(["AAPL"])

        assert outcome == {
            "tiingo": "met",
            "finnhub": "met",
            "tiingo_done_first": True,
        }, f"the fast source did not finish while the slow one was in flight: {outcome}"
        assert len(results["tiingo"]) == 3
        assert len(results["finnhub"]) == 3

    @patch("src.lambdas.ingestion.parallel_fetcher.emit_metric")
    def test_failing_source_does_not_block_the_other(
        self,
        mock_emit_metric,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """A source that fails mid-fetch does not hold back the source still running."""
        finnhub_failed = threading.Event()
        outcome = {}

        def tiingo_outlasting_finnhub(*args, **kwargs):
            outcome["saw_finnhub_fail"] = finnhub_failed.wait(
                timeout=RENDEZVOUS_TIMEOUT_S
            )
            return create_articles("tiingo", 5)

        def failing_finnhub(*args, **kwargs):
            finnhub_failed.set()
            raise Exception("Finnhub error")

        mock_tiingo_adapter.get_news.side_effect = tiingo_outlasting_finnhub
        mock_finnhub_adapter.get_news.side_effect = failing_finnhub
        fetcher = make_fetcher(
            mock_tiingo_adapter,
            mock_finnhub_adapter,
            mock_circuit_breaker,
            mock_quota_tracker,
        )

        results = fetcher.fetch_all_sources(["AAPL"])

        assert outcome == {"saw_finnhub_fail": True}, (
            "Tiingo was not in flight when Finnhub failed, so the fetch ran sequentially"
        )
        assert len(results["tiingo"]) == 5
        assert results["finnhub"] == []

    def test_duration_ms_metric_is_accurate(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
        monkeypatch,
    ):
        """duration_ms is the difference between the fetch's start and end readings."""
        import src.lambdas.ingestion.parallel_fetcher as fetcher_module

        readings = iter([1000.0, 1000.25])
        monkeypatch.setattr(
            fetcher_module, "time", SimpleNamespace(time=lambda: next(readings))
        )
        mock_tiingo_adapter.get_news.return_value = create_articles("tiingo", 2)
        mock_finnhub_adapter.get_news.return_value = create_articles("finnhub", 2)
        fetcher = make_fetcher(
            mock_tiingo_adapter,
            mock_finnhub_adapter,
            mock_circuit_breaker,
            mock_quota_tracker,
        )

        fetcher.fetch_all_sources(["AAPL"])

        assert fetcher.get_metrics()["duration_ms"] == 250.0

    def test_one_call_per_source_whatever_the_ticker_count(
        self,
        mock_tiingo_adapter,
        mock_finnhub_adapter,
        mock_quota_tracker,
        mock_circuit_breaker,
    ):
        """Each source is called once with every ticker, concurrently, at any ticker count."""
        fetcher = make_fetcher(
            mock_tiingo_adapter,
            mock_finnhub_adapter,
            mock_circuit_breaker,
            mock_quota_tracker,
        )

        for ticker_count in [1, 5, 10]:
            tickers = [f"TICK{i}" for i in range(ticker_count)]
            barrier = threading.Barrier(2)
            outcome = {}
            mock_tiingo_adapter.get_news.reset_mock()
            mock_finnhub_adapter.get_news.reset_mock()
            mock_tiingo_adapter.get_news.side_effect = rendezvous(
                barrier, outcome, "tiingo", create_articles("tiingo", 10)
            )
            mock_finnhub_adapter.get_news.side_effect = rendezvous(
                barrier, outcome, "finnhub", create_articles("finnhub", 10)
            )

            fetcher.fetch_all_sources(tickers)

            assert outcome == {"tiingo": "met", "finnhub": "met"}, (
                f"{ticker_count} tickers: sources did not overlap: {outcome}"
            )
            for adapter in (mock_tiingo_adapter, mock_finnhub_adapter):
                adapter.get_news.assert_called_once()
                assert adapter.get_news.call_args.kwargs["tickers"] == tickers

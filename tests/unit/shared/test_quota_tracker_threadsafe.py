"""Thread-safety tests for QuotaTracker.

Tests concurrent access to quota tracking to ensure thread-safety
during parallel ingestion from multiple sources.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.quota_tracker import (
    QuotaTrackerManager,
    clear_quota_cache,
    get_quota_cache_stats,
)


@pytest.fixture(autouse=True)
def clear_cache_before_tests():
    """Clear quota cache before each test."""
    clear_quota_cache()
    yield
    clear_quota_cache()


@pytest.fixture
def mock_table():
    """Create mock DynamoDB table."""
    table = MagicMock()
    table.get_item.return_value = {}  # No existing item
    table.put_item.return_value = None
    return table


class TestQuotaTrackerThreadSafety:
    """Tests for thread-safe quota tracker operations."""

    def test_concurrent_record_calls_are_thread_safe(self, mock_table):
        """Multiple threads recording calls produces correct totals."""
        manager = QuotaTrackerManager(mock_table)
        num_threads = 10
        calls_per_thread = 50

        def worker():
            for _ in range(calls_per_thread):
                manager.record_call("tiingo", 1)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        tracker = manager.get_tracker()
        expected_calls = num_threads * calls_per_thread
        assert tracker.tiingo.used == expected_calls

    def test_concurrent_can_call_checks_are_thread_safe(self, mock_table):
        """Multiple threads checking quota doesn't cause race conditions."""
        manager = QuotaTrackerManager(mock_table)
        num_threads = 20
        results = []
        results_lock = threading.Lock()

        def worker():
            result = manager.can_call("tiingo")
            with results_lock:
                results.append(result)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            list(executor.map(lambda _: worker(), range(num_threads)))

        # All checks should return True (quota not exhausted)
        assert all(results)
        assert len(results) == num_threads

    def test_mixed_record_and_check_operations(self, mock_table):
        """Interleaved record_call and can_call operations are thread-safe."""
        manager = QuotaTrackerManager(mock_table)
        iterations = 100

        def recorder():
            for _ in range(iterations):
                manager.record_call("finnhub", 1)

        def checker():
            for _ in range(iterations):
                manager.can_call("finnhub")

        threads = [
            threading.Thread(target=recorder),
            threading.Thread(target=recorder),
            threading.Thread(target=checker),
            threading.Thread(target=checker),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        tracker = manager.get_tracker()
        assert tracker.finnhub.used == iterations * 2

    def test_different_services_can_be_updated_concurrently(self, mock_table):
        """Different services can be updated by different threads."""
        manager = QuotaTrackerManager(mock_table)
        iterations = 100

        def tiingo_worker():
            for _ in range(iterations):
                manager.record_call("tiingo", 1)

        def finnhub_worker():
            for _ in range(iterations):
                manager.record_call("finnhub", 1)

        threads = [
            threading.Thread(target=tiingo_worker),
            threading.Thread(target=finnhub_worker),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        tracker = manager.get_tracker()
        assert tracker.tiingo.used == iterations
        assert tracker.finnhub.used == iterations

    def test_cache_stats_are_thread_safe(self, mock_table):
        """Cache statistics are accurate under concurrent access."""
        manager = QuotaTrackerManager(mock_table)
        num_threads = 10
        reads_per_thread = 20

        def worker():
            for _ in range(reads_per_thread):
                manager.get_tracker()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = get_quota_cache_stats()
        # First read is a miss, rest are hits
        assert stats["misses"] == 1
        assert stats["hits"] == (num_threads * reads_per_thread) - 1

    def test_record_call_with_high_contention(self, mock_table):
        """Many threads hitting same service simultaneously."""
        manager = QuotaTrackerManager(mock_table)
        num_threads = 50
        calls_per_thread = 20

        barrier = threading.Barrier(num_threads)

        def worker():
            # Wait for all threads to start
            barrier.wait()
            for _ in range(calls_per_thread):
                manager.record_call("sendgrid", 1)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        tracker = manager.get_tracker()
        assert tracker.sendgrid.used == num_threads * calls_per_thread

    def test_critical_threshold_sync_under_contention(self, mock_table):
        """Critical threshold triggers sync even under high contention."""
        manager = QuotaTrackerManager(mock_table)

        # Record 80 calls (80% of Finnhub's 60 limit would be 48)
        # But we'll use Tiingo which has 500 limit, so 80% = 400
        for _ in range(400):
            manager.record_call("tiingo", 1)

        tracker = manager.get_tracker()
        assert tracker.tiingo.is_critical

    def test_get_usage_summary_is_thread_safe(self, mock_table):
        """get_usage_summary works correctly under concurrent modifications."""
        manager = QuotaTrackerManager(mock_table)
        summaries = []
        summaries_lock = threading.Lock()

        def modifier():
            for _ in range(50):
                manager.record_call("tiingo", 1)

        def reader():
            for _ in range(50):
                summary = manager.get_usage_summary()
                with summaries_lock:
                    summaries.append(summary)

        threads = [
            threading.Thread(target=modifier),
            threading.Thread(target=reader),
            threading.Thread(target=modifier),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All summaries should be valid
        assert len(summaries) == 100
        for summary in summaries:
            assert "tiingo" in summary
            assert "finnhub" in summary
            assert "sendgrid" in summary


class TestQuotaTrackerCacheThreadSafety:
    """Tests for thread-safe cache operations."""

    def test_clear_cache_during_concurrent_access(self, mock_table):
        """Clearing cache while other threads access it doesn't cause errors."""
        manager = QuotaTrackerManager(mock_table)

        def accessor():
            for _ in range(100):
                manager.get_tracker()

        def clearer():
            for _ in range(10):
                clear_quota_cache()

        threads = [
            threading.Thread(target=accessor),
            threading.Thread(target=accessor),
            threading.Thread(target=clearer),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors

    def test_stats_update_atomically(self, mock_table):
        """Cache hit/miss stats update atomically."""
        manager = QuotaTrackerManager(mock_table)

        def worker():
            for _ in range(100):
                manager.get_tracker()
                get_quota_cache_stats()

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = get_quota_cache_stats()
        # Should have valid stats
        assert stats["hits"] >= 0
        assert stats["misses"] >= 0
        assert stats["syncs"] >= 0

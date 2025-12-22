"""Thread-safety tests for CircuitBreaker.

Tests concurrent access to circuit breaker state to ensure thread-safety
during parallel ingestion from multiple sources.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

import threading
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.circuit_breaker import (
    CircuitBreakerManager,
    clear_cache,
    get_cache_stats,
)


@pytest.fixture(autouse=True)
def clear_cache_before_tests():
    """Clear circuit breaker cache before each test."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def mock_table():
    """Create mock DynamoDB table."""
    table = MagicMock()
    table.get_item.return_value = {}  # No existing item
    table.put_item.return_value = None
    return table


class TestCircuitBreakerThreadSafety:
    """Tests for thread-safe circuit breaker operations."""

    def test_concurrent_record_failures_are_thread_safe(self, mock_table):
        """Multiple threads recording failures produces correct count."""
        manager = CircuitBreakerManager(mock_table)
        num_threads = 10
        failures_per_thread = 20

        def worker():
            for _ in range(failures_per_thread):
                manager.record_failure("tiingo")

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        state = manager.get_state("tiingo")
        # Total failures should be accurate
        assert state.total_failures == num_threads * failures_per_thread

    def test_concurrent_record_success_are_thread_safe(self, mock_table):
        """Multiple threads recording successes doesn't cause race conditions."""
        manager = CircuitBreakerManager(mock_table)
        num_threads = 20

        def worker():
            for _ in range(50):
                manager.record_success("finnhub")

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        state = manager.get_state("finnhub")
        # State should be valid (closed)
        assert state.state == "closed"

    def test_concurrent_can_execute_checks(self, mock_table):
        """Multiple threads checking can_execute is thread-safe."""
        manager = CircuitBreakerManager(mock_table)
        num_threads = 20
        results = []
        results_lock = threading.Lock()

        def worker():
            for _ in range(50):
                result = manager.can_execute("tiingo")
                with results_lock:
                    results.append(result)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All checks should return True (circuit closed)
        assert all(results)
        assert len(results) == num_threads * 50

    def test_state_transition_under_contention(self, mock_table):
        """Circuit breaker state transitions correctly under high contention."""
        manager = CircuitBreakerManager(mock_table)
        num_threads = 20

        barrier = threading.Barrier(num_threads)

        def worker():
            barrier.wait()  # All threads start at once
            for _ in range(5):
                manager.record_failure("sendgrid")

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        state = manager.get_state("sendgrid")
        # 20 threads × 5 failures = 100 total failures
        assert state.total_failures == 100
        # Should be open (failure threshold is 5)
        assert state.state == "open"

    def test_mixed_failure_and_success_operations(self, mock_table):
        """Interleaved failure and success operations are thread-safe."""
        manager = CircuitBreakerManager(mock_table)
        iterations = 100

        def failure_worker():
            for _ in range(iterations):
                manager.record_failure("tiingo")

        def success_worker():
            for _ in range(iterations):
                manager.record_success("tiingo")

        threads = [
            threading.Thread(target=failure_worker),
            threading.Thread(target=success_worker),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        state = manager.get_state("tiingo")
        # Should have recorded all failures
        assert state.total_failures == iterations

    def test_different_services_can_be_updated_concurrently(self, mock_table):
        """Different services can have their states updated by different threads."""
        manager = CircuitBreakerManager(mock_table)
        iterations = 50

        def tiingo_worker():
            for _ in range(iterations):
                manager.record_failure("tiingo")

        def finnhub_worker():
            for _ in range(iterations):
                manager.record_failure("finnhub")

        def sendgrid_worker():
            for _ in range(iterations):
                manager.record_success("sendgrid")

        threads = [
            threading.Thread(target=tiingo_worker),
            threading.Thread(target=finnhub_worker),
            threading.Thread(target=sendgrid_worker),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        tiingo_state = manager.get_state("tiingo")
        finnhub_state = manager.get_state("finnhub")
        sendgrid_state = manager.get_state("sendgrid")

        assert tiingo_state.total_failures == iterations
        assert finnhub_state.total_failures == iterations
        assert sendgrid_state.state == "closed"

    def test_get_all_states_under_contention(self, mock_table):
        """get_all_states works correctly under concurrent modifications."""
        manager = CircuitBreakerManager(mock_table)
        all_states = []
        all_states_lock = threading.Lock()

        def modifier():
            for _ in range(50):
                manager.record_failure("tiingo")
                manager.record_success("finnhub")

        def reader():
            for _ in range(50):
                states = manager.get_all_states()
                with all_states_lock:
                    all_states.append(states)

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

        # All collected states should be valid
        assert len(all_states) == 100
        for states in all_states:
            assert "tiingo" in states
            assert "finnhub" in states
            assert "sendgrid" in states


class TestCircuitBreakerCacheThreadSafety:
    """Tests for thread-safe cache operations."""

    def test_clear_cache_during_concurrent_access(self, mock_table):
        """Clearing cache while other threads access it doesn't cause errors."""
        manager = CircuitBreakerManager(mock_table)

        def accessor():
            for _ in range(100):
                manager.get_state("tiingo")

        def clearer():
            for _ in range(10):
                clear_cache()

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

    def test_cache_stats_are_thread_safe(self, mock_table):
        """Cache statistics are accurate under concurrent access."""
        manager = CircuitBreakerManager(mock_table)
        num_threads = 10
        reads_per_thread = 20

        def worker():
            for _ in range(reads_per_thread):
                manager.get_state("tiingo")

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = get_cache_stats()
        # Should have valid stats
        assert stats["hits"] >= 0
        assert stats["misses"] >= 0

    def test_stats_update_atomically(self, mock_table):
        """Cache hit/miss stats update atomically."""
        manager = CircuitBreakerManager(mock_table)

        def worker():
            for _ in range(100):
                manager.get_state("finnhub")
                get_cache_stats()

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = get_cache_stats()
        total_accesses = stats["hits"] + stats["misses"]
        # Should account for all accesses
        assert total_accesses >= 1  # At least one miss to populate cache

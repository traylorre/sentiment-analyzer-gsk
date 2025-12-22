"""Unit tests for threading utilities.

Tests thread-safety of queue, counter, and dictionary primitives
using concurrent execution to expose race conditions.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.lib.threading_utils import (
    ThreadSafeCounter,
    ThreadSafeDict,
    ThreadSafeQueue,
    create_lock,
    create_rlock,
    thread_safe_operation,
)


class TestThreadSafeQueue:
    """Tests for ThreadSafeQueue class."""

    def test_put_and_get_single_item(self):
        """Single item put and get works correctly."""
        q: ThreadSafeQueue[int] = ThreadSafeQueue()
        q.put(42)
        assert q.get() == 42

    def test_put_nowait_and_get_nowait(self):
        """Non-blocking put and get work correctly."""
        q: ThreadSafeQueue[str] = ThreadSafeQueue()
        q.put_nowait("test")
        assert q.get_nowait() == "test"

    def test_get_nowait_raises_on_empty(self):
        """get_nowait raises Empty on empty queue."""
        q: ThreadSafeQueue[int] = ThreadSafeQueue()
        with pytest.raises(queue.Empty):
            q.get_nowait()

    def test_get_all_drains_queue(self):
        """get_all returns all items and empties queue."""
        q: ThreadSafeQueue[int] = ThreadSafeQueue()
        for i in range(5):
            q.put(i)

        items = q.get_all()
        assert items == [0, 1, 2, 3, 4]
        assert q.empty()

    def test_get_all_on_empty_queue(self):
        """get_all returns empty list on empty queue."""
        q: ThreadSafeQueue[int] = ThreadSafeQueue()
        items = q.get_all()
        assert items == []

    def test_total_put_tracks_count(self):
        """total_put tracks all items ever put."""
        q: ThreadSafeQueue[int] = ThreadSafeQueue()
        q.put(1)
        q.put(2)
        q.get()  # Remove one
        assert q.total_put == 2  # Still shows 2 total put

    def test_qsize_and_empty(self):
        """qsize and empty work correctly."""
        q: ThreadSafeQueue[int] = ThreadSafeQueue()
        assert q.empty()
        assert q.qsize() == 0

        q.put(1)
        assert not q.empty()
        assert q.qsize() == 1

    def test_concurrent_puts_are_thread_safe(self):
        """Multiple threads can put items without race conditions."""
        q: ThreadSafeQueue[int] = ThreadSafeQueue()
        num_threads = 10
        items_per_thread = 100

        def worker(thread_id: int):
            for i in range(items_per_thread):
                q.put(thread_id * 1000 + i)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            list(executor.map(worker, range(num_threads)))

        # Should have all items
        items = q.get_all()
        assert len(items) == num_threads * items_per_thread
        assert q.total_put == num_threads * items_per_thread

    def test_concurrent_put_and_get_are_thread_safe(self):
        """Producers and consumers can run concurrently."""
        q: ThreadSafeQueue[int] = ThreadSafeQueue()
        results: list[int] = []
        results_lock = threading.Lock()
        producer_done = threading.Event()

        def producer():
            for i in range(100):
                q.put(i)
            producer_done.set()

        def consumer():
            while not producer_done.is_set() or not q.empty():
                try:
                    item = q.get(timeout=0.1)
                    with results_lock:
                        results.append(item)
                except queue.Empty:
                    continue

        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)

        producer_thread.start()
        consumer_thread.start()

        producer_thread.join()
        consumer_thread.join()

        # Consumer should have gotten all items
        assert sorted(results) == list(range(100))


class TestThreadSafeCounter:
    """Tests for ThreadSafeCounter class."""

    def test_initial_value(self):
        """Counter starts with correct initial value."""
        counter = ThreadSafeCounter()
        assert counter.value == 0

        counter_with_initial = ThreadSafeCounter(initial=10)
        assert counter_with_initial.value == 10

    def test_increment(self):
        """Increment works correctly."""
        counter = ThreadSafeCounter()
        assert counter.increment() == 1
        assert counter.increment(5) == 6
        assert counter.value == 6

    def test_decrement(self):
        """Decrement works correctly."""
        counter = ThreadSafeCounter(initial=10)
        assert counter.decrement() == 9
        assert counter.decrement(5) == 4
        assert counter.value == 4

    def test_concurrent_increments_are_thread_safe(self):
        """Multiple threads incrementing same counter produces correct result."""
        counter = ThreadSafeCounter()
        num_threads = 10
        increments_per_thread = 1000

        def worker():
            for _ in range(increments_per_thread):
                counter.increment()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exact total
        assert counter.value == num_threads * increments_per_thread

    def test_concurrent_increment_and_decrement(self):
        """Mixed increment/decrement from multiple threads is correct."""
        counter = ThreadSafeCounter(initial=5000)
        iterations = 1000

        def incrementer():
            for _ in range(iterations):
                counter.increment()

        def decrementer():
            for _ in range(iterations):
                counter.decrement()

        threads = [
            threading.Thread(target=incrementer),
            threading.Thread(target=incrementer),
            threading.Thread(target=decrementer),
            threading.Thread(target=decrementer),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 2 threads incrementing, 2 decrementing = net 0 change
        assert counter.value == 5000


class TestThreadSafeDict:
    """Tests for ThreadSafeDict class."""

    def test_get_set(self):
        """Basic get and set work correctly."""
        d = ThreadSafeDict()
        d.set("key1", "value1")
        assert d.get("key1") == "value1"
        assert d.get("missing", "default") == "default"

    def test_increment(self):
        """Increment works for numeric values."""
        d = ThreadSafeDict()
        assert d.increment("count") == 1
        assert d.increment("count", 5) == 6
        assert d.get("count") == 6

    def test_get_all(self):
        """get_all returns copy of all data."""
        d = ThreadSafeDict()
        d.set("a", 1)
        d.set("b", 2)

        all_data = d.get_all()
        assert all_data == {"a": 1, "b": 2}

        # Modifying copy doesn't affect original
        all_data["c"] = 3
        assert d.get("c") is None

    def test_keys(self):
        """keys returns all keys."""
        d = ThreadSafeDict()
        d.set("x", 1)
        d.set("y", 2)
        assert sorted(d.keys()) == ["x", "y"]

    def test_concurrent_increments_are_thread_safe(self):
        """Multiple threads incrementing same key produces correct result."""
        d = ThreadSafeDict()
        num_threads = 10
        increments_per_thread = 100

        def worker():
            for _ in range(increments_per_thread):
                d.increment("shared_counter")

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert d.get("shared_counter") == num_threads * increments_per_thread

    def test_concurrent_different_keys(self):
        """Different threads can work on different keys."""
        d = ThreadSafeDict()
        num_threads = 10
        iterations = 100

        def worker(key: str):
            for _ in range(iterations):
                d.increment(key)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            list(executor.map(worker, [f"key_{i}" for i in range(num_threads)]))

        # Each key should have correct count
        for i in range(num_threads):
            assert d.get(f"key_{i}") == iterations


class TestLockHelpers:
    """Tests for lock helper functions."""

    def test_create_lock(self):
        """create_lock returns threading.Lock."""
        lock = create_lock()
        assert isinstance(lock, type(threading.Lock()))

    def test_create_rlock(self):
        """create_rlock returns reentrant lock."""
        rlock = create_rlock()
        # RLock can be acquired multiple times by same thread
        rlock.acquire()
        rlock.acquire()  # Would deadlock with regular Lock
        rlock.release()
        rlock.release()

    def test_thread_safe_operation_context_manager(self):
        """thread_safe_operation provides mutual exclusion."""
        lock = create_lock()
        shared_value = [0]  # Use list to avoid nonlocal issues
        iterations = 1000

        def worker():
            for _ in range(iterations):
                with thread_safe_operation(lock):
                    current = shared_value[0]
                    time.sleep(0.00001)  # Tiny delay to expose race conditions
                    shared_value[0] = current + 1

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Without lock, this would be less due to race conditions
        assert shared_value[0] == 5 * iterations

    def test_thread_safe_operation_releases_on_exception(self):
        """Lock is released even when exception occurs."""
        lock = create_lock()

        with pytest.raises(ValueError):
            with thread_safe_operation(lock):
                raise ValueError("test error")

        # Lock should be released - this acquire should succeed immediately
        acquired = lock.acquire(blocking=False)
        assert acquired
        lock.release()

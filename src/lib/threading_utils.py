"""Thread-safety utilities for parallel execution.

Provides thread-safe primitives for concurrent ingestion from multiple sources.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

import queue
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

T = TypeVar("T")


class ThreadSafeQueue:
    """Thread-safe queue wrapper with batch operations and statistics.

    Used for collecting results from parallel worker threads without
    race conditions.

    Usage:
        results_queue = ThreadSafeQueue()

        # In worker threads:
        results_queue.put(article)

        # After workers complete:
        articles = results_queue.get_all()
    """

    def __init__(self, maxsize: int = 0) -> None:
        """Initialize thread-safe queue.

        Args:
            maxsize: Maximum queue size (0 = unlimited)
        """
        self._queue: queue.Queue[T] = queue.Queue(maxsize=maxsize)
        self._put_count = 0
        self._lock = threading.Lock()

    def put(self, item: T, block: bool = True, timeout: float | None = None) -> None:
        """Add item to queue.

        Args:
            item: Item to add
            block: Block if queue is full
            timeout: Timeout for blocking
        """
        self._queue.put(item, block=block, timeout=timeout)
        with self._lock:
            self._put_count += 1

    def put_nowait(self, item: T) -> None:
        """Add item without blocking."""
        self._queue.put_nowait(item)
        with self._lock:
            self._put_count += 1

    def get(self, block: bool = True, timeout: float | None = None) -> T:
        """Get item from queue.

        Args:
            block: Block if queue is empty
            timeout: Timeout for blocking

        Returns:
            Item from queue

        Raises:
            queue.Empty: If queue is empty and non-blocking
        """
        return self._queue.get(block=block, timeout=timeout)

    def get_nowait(self) -> T:
        """Get item without blocking."""
        return self._queue.get_nowait()

    def get_all(self) -> list[T]:
        """Get all items from queue (drains the queue).

        Returns:
            List of all items in queue
        """
        items = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def qsize(self) -> int:
        """Get approximate queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()

    @property
    def total_put(self) -> int:
        """Total items put into queue (even if already removed)."""
        with self._lock:
            return self._put_count


class ThreadSafeCounter:
    """Thread-safe counter for tracking metrics across threads.

    Usage:
        counter = ThreadSafeCounter()

        # In worker threads:
        counter.increment()
        counter.increment(5)

        # After workers complete:
        total = counter.value
    """

    def __init__(self, initial: int = 0) -> None:
        """Initialize counter.

        Args:
            initial: Initial counter value
        """
        self._value = initial
        self._lock = threading.Lock()

    def increment(self, amount: int = 1) -> int:
        """Increment counter and return new value.

        Args:
            amount: Amount to increment by

        Returns:
            New counter value after increment
        """
        with self._lock:
            self._value += amount
            return self._value

    def decrement(self, amount: int = 1) -> int:
        """Decrement counter and return new value.

        Args:
            amount: Amount to decrement by

        Returns:
            New counter value after decrement
        """
        with self._lock:
            self._value -= amount
            return self._value

    @property
    def value(self) -> int:
        """Get current counter value."""
        with self._lock:
            return self._value


class ThreadSafeDict:
    """Thread-safe dictionary wrapper.

    Usage:
        metrics = ThreadSafeDict()

        # In worker threads:
        metrics.set("tiingo_count", 10)
        metrics.increment("tiingo_count", 5)

        # After workers complete:
        all_metrics = metrics.get_all()
    """

    def __init__(self) -> None:
        """Initialize thread-safe dictionary."""
        self._data: dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key.

        Args:
            key: Dictionary key
            default: Default value if key not found

        Returns:
            Value for key or default
        """
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value for key.

        Args:
            key: Dictionary key
            value: Value to set
        """
        with self._lock:
            self._data[key] = value

    def increment(self, key: str, amount: int = 1, default: int = 0) -> int:
        """Increment numeric value for key.

        Args:
            key: Dictionary key
            amount: Amount to increment
            default: Default value if key doesn't exist

        Returns:
            New value after increment
        """
        with self._lock:
            current = self._data.get(key, default)
            new_value = current + amount
            self._data[key] = new_value
            return new_value

    def get_all(self) -> dict[str, Any]:
        """Get a copy of all data.

        Returns:
            Copy of all key-value pairs
        """
        with self._lock:
            return dict(self._data)

    def keys(self) -> list[str]:
        """Get all keys."""
        with self._lock:
            return list(self._data.keys())


@contextmanager
def thread_safe_operation(lock: threading.Lock) -> Iterator[None]:
    """Context manager for thread-safe operations.

    Usage:
        lock = threading.Lock()

        with thread_safe_operation(lock):
            # Critical section
            shared_state.update(...)

    Args:
        lock: Threading lock to acquire

    Yields:
        None (lock is held during with block)
    """
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def create_lock() -> threading.Lock:
    """Factory function to create a threading lock.

    Returns:
        New threading.Lock instance
    """
    return threading.Lock()


def create_rlock() -> threading.RLock:
    """Factory function to create a reentrant lock.

    Reentrant locks can be acquired multiple times by the same thread.

    Returns:
        New threading.RLock instance
    """
    return threading.RLock()

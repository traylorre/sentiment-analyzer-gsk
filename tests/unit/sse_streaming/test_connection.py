"""Unit tests for ConnectionManager.

Tests thread-safe connection tracking per FR-008 (100 connection limit).
"""

import threading
import time

from src.lambdas.sse_streaming.connection import ConnectionManager, SSEConnection


class TestSSEConnection:
    """Tests for SSEConnection dataclass."""

    def test_connection_generates_uuid(self):
        """Connection should generate unique UUID on creation."""
        conn1 = SSEConnection()
        conn2 = SSEConnection()

        assert conn1.connection_id != conn2.connection_id
        assert conn1.connection_id.startswith("")  # UUID format

    def test_connection_default_values(self):
        """Connection should have sensible defaults."""
        conn = SSEConnection()

        assert conn.user_id is None
        assert conn.config_id is None
        assert conn.ticker_filters == []
        assert conn.last_event_id is None
        assert conn.connected_at is not None

    def test_connection_with_values(self):
        """Connection should accept custom values."""
        conn = SSEConnection(
            user_id="user123",
            config_id="config456",
            ticker_filters=["AAPL", "MSFT"],
        )

        assert conn.user_id == "user123"
        assert conn.config_id == "config456"
        assert conn.ticker_filters == ["AAPL", "MSFT"]

    def test_matches_ticker_no_filters(self):
        """Connection with no filters should match all tickers."""
        conn = SSEConnection()

        assert conn.matches_ticker("AAPL") is True
        assert conn.matches_ticker("ANY") is True

    def test_matches_ticker_with_filters(self):
        """Connection with filters should only match configured tickers."""
        conn = SSEConnection(ticker_filters=["AAPL", "MSFT"])

        assert conn.matches_ticker("AAPL") is True
        assert conn.matches_ticker("MSFT") is True
        assert conn.matches_ticker("GOOGL") is False


class TestConnectionManager:
    """Tests for ConnectionManager."""

    def test_manager_default_max_connections(self):
        """Manager should default to 100 max connections."""
        manager = ConnectionManager()
        assert manager.max_connections == 100

    def test_manager_custom_max_connections(self):
        """Manager should accept custom max connections."""
        manager = ConnectionManager(max_connections=50)
        assert manager.max_connections == 50

    def test_acquire_returns_connection(self):
        """Acquire should return a valid connection."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire()

        assert conn is not None
        assert isinstance(conn, SSEConnection)
        assert manager.count == 1

    def test_acquire_with_user_id(self):
        """Acquire should set user_id on connection."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire(user_id="user123")

        assert conn is not None
        assert conn.user_id == "user123"

    def test_acquire_with_config_id_and_filters(self):
        """Acquire should set config_id and ticker_filters."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire(
            user_id="user123",
            config_id="config456",
            ticker_filters=["AAPL", "MSFT"],
        )

        assert conn is not None
        assert conn.config_id == "config456"
        assert conn.ticker_filters == ["AAPL", "MSFT"]

    def test_acquire_returns_none_at_limit(self):
        """Acquire should return None when limit reached."""
        manager = ConnectionManager(max_connections=2)

        conn1 = manager.acquire()
        conn2 = manager.acquire()
        conn3 = manager.acquire()

        assert conn1 is not None
        assert conn2 is not None
        assert conn3 is None
        assert manager.count == 2

    def test_release_decrements_count(self):
        """Release should decrement connection count."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire()
        assert manager.count == 1

        result = manager.release(conn.connection_id)

        assert result is True
        assert manager.count == 0

    def test_release_unknown_connection(self):
        """Release should return False for unknown connection."""
        manager = ConnectionManager(max_connections=10)

        result = manager.release("unknown-id")

        assert result is False

    def test_acquire_after_release(self):
        """Should be able to acquire after release frees slot."""
        manager = ConnectionManager(max_connections=1)

        conn1 = manager.acquire()
        assert manager.acquire() is None  # At limit

        manager.release(conn1.connection_id)
        conn2 = manager.acquire()

        assert conn2 is not None

    def test_get_connection(self):
        """Get should return connection by ID."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire(user_id="user123")

        retrieved = manager.get(conn.connection_id)

        assert retrieved is not None
        assert retrieved.user_id == "user123"

    def test_get_unknown_connection(self):
        """Get should return None for unknown ID."""
        manager = ConnectionManager(max_connections=10)

        retrieved = manager.get("unknown-id")

        assert retrieved is None

    def test_update_last_event_id(self):
        """Should update last event ID on connection."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire()

        result = manager.update_last_event_id(conn.connection_id, "evt_123")

        assert result is True
        assert manager.get(conn.connection_id).last_event_id == "evt_123"

    def test_update_last_event_id_unknown(self):
        """Update should return False for unknown connection."""
        manager = ConnectionManager(max_connections=10)

        result = manager.update_last_event_id("unknown-id", "evt_123")

        assert result is False

    def test_get_status(self):
        """Get status should return correct values."""
        manager = ConnectionManager(max_connections=10)
        manager.acquire()
        manager.acquire()

        status = manager.get_status()

        assert status["connections"] == 2
        assert status["max_connections"] == 10
        assert status["available"] == 8
        assert status["uptime_seconds"] >= 0

    def test_available_property(self):
        """Available should return remaining slots."""
        manager = ConnectionManager(max_connections=5)

        assert manager.available == 5

        manager.acquire()
        manager.acquire()

        assert manager.available == 3

    def test_uptime_increases(self):
        """Uptime should increase over time."""
        manager = ConnectionManager(max_connections=10)
        initial_uptime = manager.uptime_seconds

        time.sleep(0.1)  # Wait briefly

        assert manager.uptime_seconds >= initial_uptime


class TestConnectionManagerThreadSafety:
    """Thread safety tests for ConnectionManager."""

    def test_concurrent_acquire(self):
        """Concurrent acquires should not exceed limit."""
        manager = ConnectionManager(max_connections=50)
        results = []
        errors = []

        def acquire_connection():
            try:
                conn = manager.acquire()
                results.append(conn is not None)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=acquire_connection) for _ in range(100)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert manager.count == 50  # Should not exceed limit
        assert sum(results) == 50  # Exactly 50 should succeed

    def test_concurrent_acquire_release(self):
        """Concurrent acquire/release should maintain consistency."""
        manager = ConnectionManager(max_connections=10)
        connection_ids = []
        lock = threading.Lock()

        def acquire_and_release():
            conn = manager.acquire()
            if conn:
                with lock:
                    connection_ids.append(conn.connection_id)
                time.sleep(0.01)  # Brief hold
                manager.release(conn.connection_id)

        threads = [threading.Thread(target=acquire_and_release) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # After all threads complete, count should be 0
        assert manager.count == 0

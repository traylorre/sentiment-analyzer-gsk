"""Unit tests for connection limit enforcement.

Tests the 503 Service Unavailable response when connection limit (100) is reached.
Per FR-008: Maximum 100 concurrent connections per Lambda instance.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.lambdas.sse_streaming.connection import ConnectionManager
from src.lambdas.sse_streaming.handler import app


class TestConnectionLimitEnforcement:
    """Tests for connection limit enforcement."""

    def test_returns_503_when_limit_reached(self):
        """Test that 503 is returned when connection limit reached."""
        # Create a mock connection manager at capacity
        mock_manager = MagicMock(spec=ConnectionManager)
        mock_manager.acquire.return_value = None  # Connection denied
        mock_manager.max_connections = 100

        with patch(
            "src.lambdas.sse_streaming.handler.connection_manager", mock_manager
        ):
            client = TestClient(app)
            response = client.get("/api/v2/stream")

            assert response.status_code == 503

    def test_503_response_includes_retry_after_header(self):
        """Test that 503 response includes Retry-After header."""
        mock_manager = MagicMock(spec=ConnectionManager)
        mock_manager.acquire.return_value = None
        mock_manager.max_connections = 100

        with patch(
            "src.lambdas.sse_streaming.handler.connection_manager", mock_manager
        ):
            client = TestClient(app)
            response = client.get("/api/v2/stream")

            assert response.status_code == 503
            assert "Retry-After" in response.headers
            assert response.headers["Retry-After"] == "30"

    def test_503_response_body_format(self):
        """Test that 503 response body has correct format."""
        mock_manager = MagicMock(spec=ConnectionManager)
        mock_manager.acquire.return_value = None
        mock_manager.max_connections = 100

        with patch(
            "src.lambdas.sse_streaming.handler.connection_manager", mock_manager
        ):
            client = TestClient(app)
            response = client.get("/api/v2/stream")

            assert response.status_code == 503
            data = response.json()
            assert "detail" in data
            assert "max_connections" in data
            assert data["max_connections"] == 100
            assert "retry_after" in data
            assert data["retry_after"] == 30

    def test_503_message_indicates_limit(self):
        """Test that 503 message indicates connection limit."""
        mock_manager = MagicMock(spec=ConnectionManager)
        mock_manager.acquire.return_value = None
        mock_manager.max_connections = 100

        with patch(
            "src.lambdas.sse_streaming.handler.connection_manager", mock_manager
        ):
            client = TestClient(app)
            response = client.get("/api/v2/stream")

            data = response.json()
            assert (
                "limit" in data["detail"].lower()
                or "connection" in data["detail"].lower()
            )


class TestConnectionManagerLimit:
    """Tests for ConnectionManager limit behavior."""

    def test_acquire_returns_none_at_limit(self):
        """Test acquire returns None when at max connections."""
        manager = ConnectionManager(max_connections=2)

        # Fill to capacity
        conn1 = manager.acquire()
        conn2 = manager.acquire()

        # Should fail
        conn3 = manager.acquire()

        assert conn1 is not None
        assert conn2 is not None
        assert conn3 is None

    def test_acquire_succeeds_after_release(self):
        """Test acquire succeeds after a connection is released."""
        manager = ConnectionManager(max_connections=1)

        # Fill to capacity
        conn1 = manager.acquire()
        assert conn1 is not None

        # At limit
        conn2 = manager.acquire()
        assert conn2 is None

        # Release
        manager.release(conn1.connection_id)

        # Should succeed now
        conn3 = manager.acquire()
        assert conn3 is not None

    def test_status_shows_zero_available_at_limit(self):
        """Test status shows 0 available when at limit."""
        manager = ConnectionManager(max_connections=3)

        # Fill to capacity
        for _ in range(3):
            manager.acquire()

        status = manager.get_status()

        assert status["connections"] == 3
        assert status["max_connections"] == 3
        assert status["available"] == 0

    def test_default_limit_is_100(self):
        """Test default connection limit is 100."""
        manager = ConnectionManager()
        assert manager.max_connections == 100

    def test_custom_limit_is_respected(self):
        """Test custom connection limit is respected."""
        manager = ConnectionManager(max_connections=50)
        assert manager.max_connections == 50

        # Fill to custom capacity
        for _ in range(50):
            assert manager.acquire() is not None

        # Should fail at 51
        assert manager.acquire() is None


class TestConcurrentConnectionHandling:
    """Tests for thread-safe connection handling."""

    def test_count_tracks_connections_accurately(self):
        """Test connection count is accurate."""
        manager = ConnectionManager(max_connections=10)

        # Acquire 5 connections
        connections = []
        for _ in range(5):
            conn = manager.acquire()
            connections.append(conn)

        assert manager.count == 5

        # Release 2
        manager.release(connections[0].connection_id)
        manager.release(connections[1].connection_id)

        assert manager.count == 3

    def test_release_nonexistent_connection_is_safe(self):
        """Test releasing non-existent connection doesn't crash."""
        manager = ConnectionManager(max_connections=10)

        # Should not raise
        manager.release("nonexistent-id")
        manager.release("another-fake-id")

        assert manager.count == 0

    def test_double_release_is_safe(self):
        """Test double-releasing a connection is safe."""
        manager = ConnectionManager(max_connections=10)

        conn = manager.acquire()
        conn_id = conn.connection_id

        # Release twice
        manager.release(conn_id)
        manager.release(conn_id)

        assert manager.count == 0


class TestMetricsOnConnectionLimit:
    """Tests for metrics emission on connection limit."""

    def test_emits_failure_metric_on_503(self):
        """Test that failure metric is emitted when limit reached."""
        mock_manager = MagicMock(spec=ConnectionManager)
        mock_manager.acquire.return_value = None
        mock_manager.max_connections = 100

        mock_emitter = MagicMock()

        with (
            patch("src.lambdas.sse_streaming.handler.connection_manager", mock_manager),
            patch("src.lambdas.sse_streaming.handler.metrics_emitter", mock_emitter),
        ):
            client = TestClient(app)
            response = client.get("/api/v2/stream")

            assert response.status_code == 503
            mock_emitter.emit_connection_acquire_failure.assert_called_once()

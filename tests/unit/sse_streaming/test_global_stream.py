"""Unit tests for global SSE stream endpoint.

Tests /api/v2/stream endpoint per FR-004 and FR-014.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestGlobalStreamEndpoint:
    """Tests for GET /api/v2/stream endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client for SSE Lambda."""
        from src.lambdas.sse_streaming.handler import app

        return TestClient(app)

    def test_health_endpoint(self, client):
        """Health endpoint should return healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_stream_status_endpoint(self, client):
        """Stream status should return connection info."""
        response = client.get("/api/v2/stream/status")

        assert response.status_code == 200
        data = response.json()
        assert "connections" in data
        assert "max_connections" in data
        assert "available" in data
        assert "uptime_seconds" in data

    def test_stream_status_shows_correct_max(self, client):
        """Stream status should show correct max connections."""
        response = client.get("/api/v2/stream/status")

        data = response.json()
        # Default is 100
        assert data["max_connections"] == 100


class TestStreamEndpointIntegration:
    """Integration tests for stream endpoint (mocked)."""

    @pytest.fixture
    def mock_polling_service(self):
        """Mock the polling service."""
        with patch("src.lambdas.sse_streaming.stream.PollingService") as mock:
            instance = MagicMock()
            mock.return_value = instance
            yield instance

    def test_stream_endpoint_exists(self):
        """Verify stream endpoint is registered in app."""
        from src.lambdas.sse_streaming.handler import app

        routes = [route.path for route in app.routes]
        # Stream endpoint will be added in T015
        # For now, verify base routes exist
        assert "/health" in routes
        assert "/api/v2/stream/status" in routes


class TestGlobalStreamConnectionLimit:
    """Tests for connection limit handling on global stream."""

    @pytest.fixture
    def client(self):
        """Create test client for SSE Lambda."""
        from src.lambdas.sse_streaming.handler import app

        return TestClient(app)

    def test_global_stream_returns_503_when_limit_reached(self, client):
        """Test that global stream returns 503 when connection limit reached."""
        from src.lambdas.sse_streaming.handler import connection_manager

        # Mock connection_manager.acquire to return None (limit reached)
        with patch.object(connection_manager, "acquire", return_value=None):
            response = client.get("/api/v2/stream")

            assert response.status_code == 503
            data = response.json()
            assert "Connection limit reached" in data["detail"]
            assert "max_connections" in data
            assert data["retry_after"] == 30
            assert response.headers.get("Retry-After") == "30"

    def test_global_stream_emits_failure_metric_on_limit(self, client):
        """Test that connection limit emits failure metric."""
        from src.lambdas.sse_streaming.handler import (
            connection_manager,
            metrics_emitter,
        )

        with patch.object(connection_manager, "acquire", return_value=None):
            with patch.object(
                metrics_emitter, "emit_connection_acquire_failure"
            ) as mock_emit:
                client.get("/api/v2/stream")

                mock_emit.assert_called_once()


class TestConfigStreamConnectionLimit:
    """Tests for connection limit handling on config stream."""

    @pytest.fixture
    def client(self):
        """Create test client for SSE Lambda."""
        from src.lambdas.sse_streaming.handler import app

        return TestClient(app)

    def test_config_stream_returns_503_when_limit_reached(self, client):
        """Test that config stream returns 503 when connection limit reached."""
        from src.lambdas.sse_streaming.handler import (
            config_lookup_service,
            connection_manager,
        )

        # Mock successful auth and config lookup, but connection limit reached
        with patch.object(
            config_lookup_service, "validate_user_access", return_value=(True, ["AAPL"])
        ):
            with patch.object(connection_manager, "acquire", return_value=None):
                response = client.get(
                    "/api/v2/configurations/test-config/stream",
                    headers={"X-User-ID": "user-123"},
                )

                assert response.status_code == 503
                data = response.json()
                assert "Connection limit reached" in data["detail"]


class TestGlobalExceptionHandler:
    """Tests for global exception handler."""

    @pytest.fixture
    def client(self):
        """Create test client for SSE Lambda."""
        from src.lambdas.sse_streaming.handler import app

        return TestClient(app, raise_server_exceptions=False)

    def test_exception_handler_returns_500(self, client):
        """Test that unhandled exceptions return 500."""
        from src.lambdas.sse_streaming.handler import connection_manager

        # Cause an exception in the stream status endpoint
        with patch.object(
            connection_manager, "get_status", side_effect=RuntimeError("Test error")
        ):
            response = client.get("/api/v2/stream/status")

            assert response.status_code == 500
            data = response.json()
            assert data["detail"] == "Internal server error"


class TestGlobalStreamTickersQueryParam:
    """Tests for tickers query parameter on /api/v2/stream (Phase 6 T051)."""

    @pytest.fixture
    def client(self):
        """Create test client for SSE Lambda."""
        from src.lambdas.sse_streaming.handler import app

        return TestClient(app)

    def test_stream_accepts_tickers_param(self, client):
        """Test that stream endpoint accepts tickers query param."""
        from src.lambdas.sse_streaming.handler import connection_manager

        # Mock to verify param is parsed
        with patch.object(connection_manager, "acquire", return_value=None):
            response = client.get("/api/v2/stream?tickers=AAPL,MSFT,GOOGL")
            # 503 expected since acquire returns None
            assert response.status_code == 503

    def test_stream_passes_ticker_filters_to_connection_manager(self, client):
        """Test that ticker filters are passed to connection_manager.acquire()."""
        from src.lambdas.sse_streaming.handler import connection_manager

        # Capture the kwargs passed to acquire
        with patch.object(connection_manager, "acquire", return_value=None) as mock_acq:
            client.get("/api/v2/stream?tickers=AAPL,MSFT")
            mock_acq.assert_called_once()
            kwargs = mock_acq.call_args.kwargs
            assert kwargs.get("ticker_filters") == ["AAPL", "MSFT"]

    def test_stream_ticker_filters_case_insensitive(self, client):
        """Test that ticker filters are normalized to uppercase."""
        from src.lambdas.sse_streaming.handler import connection_manager

        with patch.object(connection_manager, "acquire", return_value=None) as mock_acq:
            client.get("/api/v2/stream?tickers=aapl,Msft,googl")
            kwargs = mock_acq.call_args.kwargs
            # All should be uppercase
            assert kwargs.get("ticker_filters") == ["AAPL", "MSFT", "GOOGL"]

    def test_stream_empty_tickers_param_means_all(self, client):
        """Test that empty/missing tickers param means all tickers."""
        from src.lambdas.sse_streaming.handler import connection_manager

        with patch.object(connection_manager, "acquire", return_value=None) as mock_acq:
            client.get("/api/v2/stream")  # No tickers param
            kwargs = mock_acq.call_args.kwargs
            assert kwargs.get("ticker_filters") == []  # Empty = all

    def test_stream_tickers_with_resolutions(self, client):
        """Test that tickers and resolutions can be used together."""
        from src.lambdas.sse_streaming.handler import connection_manager

        with patch.object(connection_manager, "acquire", return_value=None) as mock_acq:
            client.get("/api/v2/stream?tickers=AAPL,MSFT&resolutions=1m,5m")
            kwargs = mock_acq.call_args.kwargs
            assert kwargs.get("ticker_filters") == ["AAPL", "MSFT"]
            assert kwargs.get("resolution_filters") == ["1m", "5m"]

    def test_stream_tickers_whitespace_handling(self, client):
        """Test that whitespace in tickers is handled correctly."""
        from src.lambdas.sse_streaming.handler import connection_manager

        with patch.object(connection_manager, "acquire", return_value=None) as mock_acq:
            client.get("/api/v2/stream?tickers=%20AAPL%20,%20MSFT%20")
            kwargs = mock_acq.call_args.kwargs
            # Whitespace should be stripped
            assert kwargs.get("ticker_filters") == ["AAPL", "MSFT"]

    def test_stream_tickers_empty_items_filtered(self, client):
        """Test that empty ticker items are filtered out."""
        from src.lambdas.sse_streaming.handler import connection_manager

        with patch.object(connection_manager, "acquire", return_value=None) as mock_acq:
            client.get("/api/v2/stream?tickers=AAPL,,MSFT,")
            kwargs = mock_acq.call_args.kwargs
            # Empty items should be excluded
            assert kwargs.get("ticker_filters") == ["AAPL", "MSFT"]

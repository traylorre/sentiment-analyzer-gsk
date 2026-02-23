"""Unit tests for global SSE stream endpoint.

Tests /api/v2/stream and /api/v2/stream/status endpoints per FR-004 and FR-014.

Uses direct handler invocation for testing.
Note: /health and /debug endpoints no longer exist and tests for them have been removed.
"""

import json
from unittest.mock import MagicMock, patch

from src.lambdas.sse_streaming.handler import handler
from tests.conftest import make_function_url_event, parse_streaming_response


class TestGlobalStreamEndpoint:
    """Tests for GET /api/v2/stream/status endpoint."""

    def test_stream_status_endpoint(self):
        """Stream status should return connection info."""
        event = make_function_url_event(path="/api/v2/stream/status")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 200
        data = json.loads(body)
        assert "connections" in data
        assert "max_connections" in data
        assert "available" in data
        assert "uptime_seconds" in data

    def test_stream_status_shows_correct_max(self):
        """Stream status should show correct max connections."""
        event = make_function_url_event(path="/api/v2/stream/status")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        data = json.loads(body)
        # Default is 100
        assert data["max_connections"] == 100


class TestStreamEndpointIntegration:
    """Integration tests for stream endpoint (mocked)."""

    def test_stream_status_route_exists(self):
        """Verify /api/v2/stream/status is handled by the handler."""
        event = make_function_url_event(path="/api/v2/stream/status")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        # Should return 200, not 404
        assert metadata["statusCode"] == 200

    def test_stream_route_exists(self):
        """Verify /api/v2/stream is handled by the handler."""
        # Mock connection_manager to return None so we get a deterministic 503
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(path="/api/v2/stream")
                gen = handler(event, None)
                metadata, body = parse_streaming_response(gen)

                # 503 (limit reached) means the route exists and was matched
                assert metadata["statusCode"] == 503


class TestGlobalStreamConnectionLimit:
    """Tests for connection limit handling on global stream."""

    def test_global_stream_returns_503_when_limit_reached(self):
        """Test that global stream returns 503 when connection limit reached."""
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(path="/api/v2/stream")
                gen = handler(event, None)
                metadata, body = parse_streaming_response(gen)

                assert metadata["statusCode"] == 503
                data = json.loads(body)
                assert "Connection limit reached" in data["detail"]
                assert metadata["headers"].get("Retry-After") == "30"

    def test_global_stream_emits_failure_metric_on_limit(self):
        """Test that connection limit emits failure metric."""
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        mock_emitter = MagicMock()

        with (
            patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr),
            patch("src.lambdas.sse_streaming.handler.metrics_emitter", mock_emitter),
        ):
            event = make_function_url_event(path="/api/v2/stream")
            gen = handler(event, None)
            # Consume the generator to trigger the metric emission
            list(gen)

            mock_emitter.emit_connection_acquire_failure.assert_called_once()


class TestConfigStreamConnectionLimit:
    """Tests for connection limit handling on config stream."""

    def test_config_stream_returns_503_when_limit_reached(self):
        """Test that config stream returns 503 when connection limit reached."""
        mock_lookup = MagicMock()
        mock_lookup.validate_user_access.return_value = (True, ["AAPL"])

        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with (
            patch(
                "src.lambdas.sse_streaming.handler.config_lookup_service", mock_lookup
            ),
            patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr),
            patch("src.lambdas.sse_streaming.handler.metrics_emitter"),
        ):
            event = make_function_url_event(
                path="/api/v2/configurations/test-config/stream",
                headers={"X-User-ID": "user-123"},
            )
            gen = handler(event, None)
            metadata, body = parse_streaming_response(gen)

            assert metadata["statusCode"] == 503
            data = json.loads(body)
            assert "Connection limit reached" in data["detail"]


class TestGlobalExceptionHandler:
    """Tests for unhandled exception handling in the handler."""

    def test_exception_handler_returns_500(self):
        """Test that unhandled exceptions return 500."""
        mock_mgr = MagicMock()
        mock_mgr.get_status.side_effect = RuntimeError("Test error")

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            event = make_function_url_event(path="/api/v2/stream/status")
            gen = handler(event, None)
            metadata, body = parse_streaming_response(gen)

            assert metadata["statusCode"] == 500
            data = json.loads(body)
            assert data["detail"] == "Internal server error"


class TestGlobalStreamTickersQueryParam:
    """Tests for tickers query parameter on /api/v2/stream (Phase 6 T051)."""

    def test_stream_accepts_tickers_param(self):
        """Test that stream endpoint accepts tickers query param."""
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(
                    path="/api/v2/stream",
                    query_params={"tickers": "AAPL,MSFT,GOOGL"},
                )
                gen = handler(event, None)
                metadata, body = parse_streaming_response(gen)

                # 503 expected since acquire returns None
                assert metadata["statusCode"] == 503

    def test_stream_passes_ticker_filters_to_connection_manager(self):
        """Test that ticker filters are passed to connection_manager.acquire()."""
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(
                    path="/api/v2/stream",
                    query_params={"tickers": "AAPL,MSFT"},
                )
                gen = handler(event, None)
                list(gen)  # Consume generator

                mock_mgr.acquire.assert_called_once()
                kwargs = mock_mgr.acquire.call_args.kwargs
                assert kwargs.get("ticker_filters") == ["AAPL", "MSFT"]

    def test_stream_ticker_filters_case_insensitive(self):
        """Test that ticker filters are normalized to uppercase."""
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(
                    path="/api/v2/stream",
                    query_params={"tickers": "aapl,Msft,googl"},
                )
                gen = handler(event, None)
                list(gen)  # Consume generator

                kwargs = mock_mgr.acquire.call_args.kwargs
                # All should be uppercase
                assert kwargs.get("ticker_filters") == ["AAPL", "MSFT", "GOOGL"]

    def test_stream_empty_tickers_param_means_all(self):
        """Test that empty/missing tickers param means all tickers."""
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(path="/api/v2/stream")  # No tickers
                gen = handler(event, None)
                list(gen)  # Consume generator

                kwargs = mock_mgr.acquire.call_args.kwargs
                assert kwargs.get("ticker_filters") == []  # Empty = all

    def test_stream_tickers_with_resolutions(self):
        """Test that tickers and resolutions can be used together."""
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(
                    path="/api/v2/stream",
                    query_params={"tickers": "AAPL,MSFT", "resolutions": "1m,5m"},
                )
                gen = handler(event, None)
                list(gen)  # Consume generator

                kwargs = mock_mgr.acquire.call_args.kwargs
                assert kwargs.get("ticker_filters") == ["AAPL", "MSFT"]
                assert kwargs.get("resolution_filters") == ["1m", "5m"]

    def test_stream_tickers_whitespace_handling(self):
        """Test that whitespace in tickers is handled correctly."""
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(
                    path="/api/v2/stream",
                    query_params={"tickers": " AAPL , MSFT "},
                )
                gen = handler(event, None)
                list(gen)  # Consume generator

                kwargs = mock_mgr.acquire.call_args.kwargs
                # Whitespace should be stripped
                assert kwargs.get("ticker_filters") == ["AAPL", "MSFT"]

    def test_stream_tickers_empty_items_filtered(self):
        """Test that empty ticker items are filtered out."""
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(
                    path="/api/v2/stream",
                    query_params={"tickers": "AAPL,,MSFT,"},
                )
                gen = handler(event, None)
                list(gen)  # Consume generator

                kwargs = mock_mgr.acquire.call_args.kwargs
                # Empty items should be excluded
                assert kwargs.get("ticker_filters") == ["AAPL", "MSFT"]

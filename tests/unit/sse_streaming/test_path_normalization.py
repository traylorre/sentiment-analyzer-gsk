"""Unit tests for path normalization in the SSE streaming handler.

Tests that the handler's inline path normalization (re.sub(r"/+", "/", path))
correctly handles double-slash paths from Lambda Web Adapter (Fix 141).

Migrated from PathNormalizationMiddleware + Starlette tests to direct handler
invocation (001-fastapi-purge). The middleware no longer exists; path normalization
is now inline in the handler function.
"""

import json
from unittest.mock import MagicMock, patch

from src.lambdas.sse_streaming.handler import handler
from tests.conftest import make_function_url_event, parse_streaming_response


class TestPathNormalization:
    """Tests for inline path normalization in the handler."""

    def test_api_v2_stream_status_single_slash(self):
        """Normal /api/v2/stream/status should work."""
        event = make_function_url_event(path="/api/v2/stream/status")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 200
        data = json.loads(body)
        # StreamStatus model uses 'connections' field
        assert "connections" in data

    def test_api_path_internal_double_slash(self):
        """Internal double slashes /api//v2/stream/status should be normalized."""
        event = make_function_url_event(path="/api//v2/stream/status")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 200
        data = json.loads(body)
        assert "connections" in data

    def test_multiple_internal_double_slashes(self):
        """Multiple internal double slashes should be normalized."""
        # /api//v2//stream//status -> /api/v2/stream/status
        event = make_function_url_event(path="/api//v2//stream//status")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 200
        data = json.loads(body)
        assert "connections" in data

    def test_leading_double_slash_normalized(self):
        """Leading double slashes //api/v2/stream/status should be normalized."""
        event = make_function_url_event(path="//api/v2/stream/status")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 200
        data = json.loads(body)
        assert "connections" in data

    def test_triple_slash_normalized(self):
        """Triple slashes ///api///v2///stream///status should be normalized."""
        event = make_function_url_event(path="///api///v2///stream///status")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 200
        data = json.loads(body)
        assert "connections" in data

    def test_single_slash_unchanged(self):
        """Single slashes should not be modified — /api/v2/stream/status works normally."""
        event = make_function_url_event(path="/api/v2/stream/status")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 200

    def test_nonexistent_path_still_404(self):
        """Normalization should not make nonexistent paths return 200."""
        event = make_function_url_event(path="/nonexistent/path")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 404

    def test_root_path_404(self):
        """Root path / should return 404 (no root handler)."""
        event = make_function_url_event(path="/")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 404


class TestPathNormalizationWithStreaming:
    """Tests for path normalization on streaming endpoints."""

    def test_double_slash_global_stream_normalizes(self):
        """Double slashes in /api//v2//stream should normalize and route correctly."""
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(path="/api//v2//stream")
                gen = handler(event, None)
                metadata, body = parse_streaming_response(gen)

                # 503 means the route was matched (connection limit hit)
                assert metadata["statusCode"] == 503

    def test_double_slash_config_stream_normalizes(self):
        """Double slashes in config stream path should normalize and route correctly."""
        event = make_function_url_event(
            path="//api//v2//configurations//test-config//stream"
        )
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        # 401 means the route was matched (auth required)
        assert metadata["statusCode"] == 401

    def test_nonexistent_double_slash_path_still_404(self):
        """Double slashes on a nonexistent path should still return 404."""
        event = make_function_url_event(path="//nonexistent//path")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 404

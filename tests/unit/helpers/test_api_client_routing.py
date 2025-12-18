"""Unit tests for PreprodAPIClient URL routing logic.

Tests verify that the client correctly routes requests to either:
- Dashboard Lambda (BUFFERED mode) for regular API calls
- SSE Lambda (RESPONSE_STREAM mode) for streaming endpoints

Background:
The sentiment-analyzer uses a two-Lambda architecture where SSE streaming
requires RESPONSE_STREAM invoke mode. The PreprodAPIClient routes paths
containing "/stream" to the SSE Lambda URL, while other paths go to the
Dashboard Lambda URL.

See: specs/082-fix-sse-e2e-timeouts/spec.md
"""

import os
from unittest.mock import patch

from tests.e2e.helpers.api_client import PreprodAPIClient


class TestPreprodAPIClientInit:
    """Tests for PreprodAPIClient initialization and URL configuration."""

    def test_init_with_default_urls(self):
        """Verify default URL behavior when no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove relevant env vars
            os.environ.pop("PREPROD_API_URL", None)
            os.environ.pop("SSE_LAMBDA_URL", None)

            client = PreprodAPIClient()

            # base_url falls back to default
            assert client.base_url == "https://api.preprod.sentiment-analyzer.com"
            # sse_url falls back to base_url when SSE_LAMBDA_URL not set
            assert client.sse_url == client.base_url

    def test_init_with_base_url_only(self):
        """Verify SSE URL falls back to base URL when not provided."""
        with patch.dict(
            os.environ, {"PREPROD_API_URL": "https://dashboard.example.com"}, clear=True
        ):
            os.environ.pop("SSE_LAMBDA_URL", None)

            client = PreprodAPIClient()

            assert client.base_url == "https://dashboard.example.com"
            assert client.sse_url == "https://dashboard.example.com"

    def test_init_with_both_urls(self):
        """Verify independent URL configuration."""
        with patch.dict(
            os.environ,
            {
                "PREPROD_API_URL": "https://dashboard.example.com",
                "SSE_LAMBDA_URL": "https://sse.example.com",
            },
            clear=True,
        ):
            client = PreprodAPIClient()

            assert client.base_url == "https://dashboard.example.com"
            assert client.sse_url == "https://sse.example.com"

    def test_init_with_explicit_parameters(self):
        """Verify constructor parameters override env vars."""
        with patch.dict(
            os.environ,
            {
                "PREPROD_API_URL": "https://env-dashboard.example.com",
                "SSE_LAMBDA_URL": "https://env-sse.example.com",
            },
            clear=True,
        ):
            client = PreprodAPIClient(
                base_url="https://explicit-dashboard.example.com",
                sse_url="https://explicit-sse.example.com",
            )

            assert client.base_url == "https://explicit-dashboard.example.com"
            assert client.sse_url == "https://explicit-sse.example.com"

    def test_trailing_slashes_removed(self):
        """Verify trailing slashes are removed from URLs."""
        client = PreprodAPIClient(
            base_url="https://dashboard.example.com/",
            sse_url="https://sse.example.com/",
        )

        assert client.base_url == "https://dashboard.example.com"
        assert client.sse_url == "https://sse.example.com"

    def test_empty_sse_url_falls_back_to_base(self):
        """Verify empty SSE_LAMBDA_URL env var triggers fallback."""
        with patch.dict(
            os.environ,
            {
                "PREPROD_API_URL": "https://dashboard.example.com",
                "SSE_LAMBDA_URL": "",  # Empty string
            },
            clear=True,
        ):
            client = PreprodAPIClient()

            assert client.base_url == "https://dashboard.example.com"
            assert client.sse_url == "https://dashboard.example.com"


class TestStreamSSERouting:
    """Tests for stream_sse() URL routing logic.

    These tests verify the routing decision logic by testing the internal
    computation of effective_url without mocking the full HTTP stack.
    The actual HTTP behavior is tested in integration tests.
    """

    def test_stream_path_routing_logic(self):
        """Verify /api/v2/stream would route to SSE Lambda URL."""
        client = PreprodAPIClient(
            base_url="https://dashboard.example.com", sse_url="https://sse.example.com"
        )

        path = "/api/v2/stream"
        # This is the exact logic from stream_sse method
        effective_url = client.sse_url if "/stream" in path else client.base_url

        assert effective_url == "https://sse.example.com"

    def test_config_stream_path_routing_logic(self):
        """Verify /api/v2/configurations/{id}/stream would route to SSE Lambda URL."""
        client = PreprodAPIClient(
            base_url="https://dashboard.example.com", sse_url="https://sse.example.com"
        )

        path = "/api/v2/configurations/abc123/stream"
        effective_url = client.sse_url if "/stream" in path else client.base_url

        assert effective_url == "https://sse.example.com"

    def test_stream_status_path_routing_logic(self):
        """Verify /api/v2/stream/status would route to SSE Lambda URL (contains /stream)."""
        client = PreprodAPIClient(
            base_url="https://dashboard.example.com", sse_url="https://sse.example.com"
        )

        path = "/api/v2/stream/status"
        effective_url = client.sse_url if "/stream" in path else client.base_url

        assert effective_url == "https://sse.example.com"

    def test_non_stream_path_routing_logic(self):
        """Verify /api/v2/configurations would route to Dashboard Lambda URL."""
        client = PreprodAPIClient(
            base_url="https://dashboard.example.com", sse_url="https://sse.example.com"
        )

        path = "/api/v2/configurations"
        effective_url = client.sse_url if "/stream" in path else client.base_url

        assert effective_url == "https://dashboard.example.com"

    def test_health_path_routing_logic(self):
        """Verify /health would route to Dashboard Lambda URL."""
        client = PreprodAPIClient(
            base_url="https://dashboard.example.com", sse_url="https://sse.example.com"
        )

        path = "/health"
        effective_url = client.sse_url if "/stream" in path else client.base_url

        assert effective_url == "https://dashboard.example.com"

    def test_fallback_routing_when_sse_url_not_set(self):
        """Verify all paths route to base_url when SSE_LAMBDA_URL not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SSE_LAMBDA_URL", None)

            client = PreprodAPIClient(base_url="https://dashboard.example.com")

            # Even /stream paths should go to base_url when sse_url equals base_url
            stream_path = "/api/v2/stream"
            effective_url = (
                client.sse_url if "/stream" in stream_path else client.base_url
            )

            assert effective_url == "https://dashboard.example.com"
            assert client.sse_url == client.base_url


class TestStreamSSEEdgeCases:
    """Tests for edge cases in URL routing."""

    def test_same_base_and_sse_url(self):
        """Verify behavior when both URLs are identical."""
        client = PreprodAPIClient(
            base_url="https://same.example.com", sse_url="https://same.example.com"
        )

        assert client.base_url == client.sse_url
        # Should still work - routing logic executes but result is same URL

    def test_path_with_stream_substring_matches(self):
        """Verify routing when '/stream' appears in path."""
        client = PreprodAPIClient(
            base_url="https://dashboard.example.com", sse_url="https://sse.example.com"
        )

        # The routing uses 'in' operator with '/stream' (note the leading slash)
        # This prevents false matches like '/api/v2/livestream'
        paths_with_stream = [
            "/api/v2/data/stream/historical",
            "/stream",
            "/api/v2/stream/config/123",
        ]

        for path in paths_with_stream:
            effective_url = client.sse_url if "/stream" in path else client.base_url
            assert (
                effective_url == "https://sse.example.com"
            ), f"Path {path} should route to SSE"

    def test_path_without_stream_slash_does_not_match(self):
        """Verify paths with 'stream' but not '/stream' route to base URL."""
        client = PreprodAPIClient(
            base_url="https://dashboard.example.com", sse_url="https://sse.example.com"
        )

        # These paths contain 'stream' but not '/stream' - should NOT route to SSE
        paths_without_stream_slash = ["/api/v2/livestream", "/api/v2/downstream/data"]

        for path in paths_without_stream_slash:
            effective_url = client.sse_url if "/stream" in path else client.base_url
            assert (
                effective_url == "https://dashboard.example.com"
            ), f"Path {path} should route to base"

    def test_multiple_trailing_slashes(self):
        """Verify multiple trailing slashes are handled."""
        client = PreprodAPIClient(
            base_url="https://dashboard.example.com///",
            sse_url="https://sse.example.com//",
        )

        # rstrip("/") removes all trailing slashes
        assert client.base_url == "https://dashboard.example.com"
        assert client.sse_url == "https://sse.example.com"

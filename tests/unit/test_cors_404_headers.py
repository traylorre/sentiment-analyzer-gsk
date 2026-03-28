"""Unit tests for CORS on env-gated 404 responses (Feature 1268).

Tests the _make_not_found_response() function which conditionally adds
CORS headers to 404 responses when the requesting origin is in the
allowed origins list (_CORS_ALLOWED_ORIGINS).

Approach: Reload handler module with CORS_ORIGINS set to control
_CORS_ALLOWED_ORIGINS (parsed at module level).
"""

import importlib
import json
import os
from unittest.mock import patch

import pytest

# Set env before any handler import
os.environ.setdefault("DYNAMODB_TABLE", "test-sentiment-items")
os.environ.setdefault("SENTIMENTS_TABLE", "test-sentiment-items")
os.environ.setdefault("USERS_TABLE", "test-sentiment-users")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CHAOS_EXPERIMENTS_TABLE", "test-chaos-experiments")

ALLOWED_ORIGIN = "https://example.com"
SECOND_ORIGIN = "https://app.example.com"
CORS_ORIGINS_VALUE = f"{ALLOWED_ORIGIN},{SECOND_ORIGIN}"


def _reload_handler_with_cors(cors_origins: str = CORS_ORIGINS_VALUE):
    """Reload handler module with specific CORS_ORIGINS."""
    with patch.dict(os.environ, {"CORS_ORIGINS": cors_origins}):
        import src.lambdas.dashboard.handler as handler_module

        importlib.reload(handler_module)
        return handler_module


class TestMakeNotFoundResponse:
    """Unit tests for _make_not_found_response (Feature 1268)."""

    @pytest.fixture(autouse=True)
    def setup_handler(self):
        """Reload handler with CORS origins before each test, restore after."""
        self.handler = _reload_handler_with_cors()
        yield
        # Restore original environment
        _reload_handler_with_cors("")

    def test_valid_origin_includes_cors_headers(self):
        """CORS headers present when origin is in allowed list."""
        response = self.handler._make_not_found_response(ALLOWED_ORIGIN)
        assert response.headers.get("Access-Control-Allow-Origin") == ALLOWED_ORIGIN
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"
        assert "GET" in response.headers.get("Access-Control-Allow-Methods", "")
        assert "Content-Type" in response.headers.get(
            "Access-Control-Allow-Headers", ""
        )

    def test_invalid_origin_omits_cors_origin(self):
        """Access-Control-Allow-Origin omitted for unknown origin."""
        response = self.handler._make_not_found_response("https://evil.com")
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_none_origin_omits_cors_origin(self):
        """Access-Control-Allow-Origin omitted when origin is None."""
        response = self.handler._make_not_found_response(None)
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_empty_origin_omits_cors_origin(self):
        """Access-Control-Allow-Origin omitted for empty string origin."""
        response = self.handler._make_not_found_response("")
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_response_body_is_not_found(self):
        """Response body is always {"detail": "Not found"}."""
        response = self.handler._make_not_found_response(ALLOWED_ORIGIN)
        body = json.loads(response.body)
        assert body == {"detail": "Not found"}

    def test_response_status_is_404(self):
        """Response status code is always 404."""
        response = self.handler._make_not_found_response(ALLOWED_ORIGIN)
        assert response.status_code == 404

    def test_vary_origin_always_present(self):
        """Vary: Origin header is always present regardless of origin."""
        # With valid origin
        response = self.handler._make_not_found_response(ALLOWED_ORIGIN)
        assert response.headers.get("Vary") == "Origin"

        # With no origin
        response = self.handler._make_not_found_response(None)
        assert response.headers.get("Vary") == "Origin"

        # With invalid origin
        response = self.handler._make_not_found_response("https://evil.com")
        assert response.headers.get("Vary") == "Origin"

    def test_no_wildcard_origin(self):
        """Access-Control-Allow-Origin never uses wildcard *."""
        response = self.handler._make_not_found_response(ALLOWED_ORIGIN)
        assert response.headers.get("Access-Control-Allow-Origin") != "*"

    def test_credentials_header_with_valid_origin(self):
        """Access-Control-Allow-Credentials is 'true' when origin valid."""
        response = self.handler._make_not_found_response(ALLOWED_ORIGIN)
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"

    def test_multiple_allowed_origins(self):
        """Only the requesting origin is reflected, not all allowed origins."""
        response = self.handler._make_not_found_response(SECOND_ORIGIN)
        assert response.headers.get("Access-Control-Allow-Origin") == SECOND_ORIGIN
        # Verify the other origin is NOT in the header
        assert ALLOWED_ORIGIN not in response.headers.get(
            "Access-Control-Allow-Origin", ""
        )

    def test_whitespace_in_cors_origins_handled(self):
        """Origins with whitespace around commas are still matched."""
        handler = _reload_handler_with_cors("  https://a.com , https://b.com  ")
        response = handler._make_not_found_response("https://a.com")
        assert response.headers.get("Access-Control-Allow-Origin") == "https://a.com"
        response = handler._make_not_found_response("https://b.com")
        assert response.headers.get("Access-Control-Allow-Origin") == "https://b.com"

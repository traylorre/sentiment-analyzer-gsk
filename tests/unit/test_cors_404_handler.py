"""Unit tests for catch-all @app.not_found handler (Feature 1311).

Tests the handle_not_found() handler which intercepts ALL unmatched routes
and returns 404 with conditional CORS headers via _make_not_found_response().

Unlike test_cors_404_headers.py (which tests _make_not_found_response directly)
and test_cors_404_integration.py (which tests env-gated registered routes),
these tests hit truly unmatched routes that have NO registered handler —
the exact scenario that was broken before Feature 1311.

Approach: Reload handler module with CORS_ORIGINS set, then invoke
lambda_handler with events targeting nonexistent paths.
"""

import importlib
import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Set env before any handler import
os.environ.setdefault("DYNAMODB_TABLE", "test-sentiment-items")
os.environ.setdefault("SENTIMENTS_TABLE", "test-sentiment-items")
os.environ.setdefault("USERS_TABLE", "test-sentiment-users")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CHAOS_EXPERIMENTS_TABLE", "test-chaos-experiments")

from tests.conftest import get_response_header, make_event

ALLOWED_ORIGIN = "https://main.d29tlmksqcx494.amplifyapp.com"


def _reload_handler(cors_origins: str = ALLOWED_ORIGIN):
    """Reload handler module with specific CORS_ORIGINS."""
    with patch.dict(os.environ, {"CORS_ORIGINS": cors_origins}):
        import src.lambdas.dashboard.handler as handler_module

        importlib.reload(handler_module)
        return handler_module


@pytest.fixture
def mock_lambda_context():
    ctx = MagicMock()
    ctx.function_name = "test-dashboard"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


@pytest.mark.unit
class TestCatchAllNotFoundHandler:
    """Unit tests for @app.not_found catch-all handler (Feature 1311).

    These test truly unmatched routes — paths with NO registered handler.
    Before Feature 1311, these returned Powertools' bare 404 without CORS.
    """

    @pytest.fixture(autouse=True)
    def setup_handler(self):
        """Reload handler with CORS origins before each test, restore after."""
        self.handler = _reload_handler(ALLOWED_ORIGIN)
        yield
        _reload_handler("")

    def test_unmatched_route_returns_404_with_cors(self, mock_lambda_context):
        """Truly unmatched route returns 404 with CORS for allowed origin."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/nonexistent-cors-test",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 404
        assert (
            get_response_header(response, "Access-Control-Allow-Origin")
            == ALLOWED_ORIGIN
        )
        assert (
            get_response_header(response, "Access-Control-Allow-Credentials") == "true"
        )
        assert get_response_header(response, "Vary") == "Origin"

    def test_unmatched_route_no_cors_for_unknown_origin(self, mock_lambda_context):
        """Truly unmatched route returns 404 WITHOUT CORS for unknown origin."""
        bad_origin = "https://evil.attacker.example.com"
        event = make_event(
            method="GET",
            path="/api/v2/tickers/nonexistent-cors-test",
            headers={"origin": bad_origin},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 404
        allow_origin = get_response_header(response, "Access-Control-Allow-Origin")
        assert allow_origin != bad_origin
        assert get_response_header(response, "Vary") == "Origin"

    def test_unmatched_route_no_origin_header(self, mock_lambda_context):
        """Truly unmatched route returns 404 without CORS when no Origin sent."""
        event = make_event(
            method="GET",
            path="/totally/random/nonexistent/path",
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 404
        assert get_response_header(response, "Access-Control-Allow-Origin") == ""
        assert get_response_header(response, "Vary") == "Origin"

    def test_unmatched_route_body_is_valid_json(self, mock_lambda_context):
        """Unmatched route 404 body is {"detail": "Not found"}."""
        event = make_event(
            method="GET",
            path="/does-not-exist",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        body = json.loads(response["body"])
        assert body == {"detail": "Not found"}

    def test_unmatched_route_vary_origin_always_present(self, mock_lambda_context):
        """Vary: Origin is present on all unmatched routes regardless of origin."""
        # With allowed origin
        event = make_event(
            method="GET",
            path="/nonexistent-1",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)
        assert get_response_header(response, "Vary") == "Origin"

        # With unknown origin
        event = make_event(
            method="GET",
            path="/nonexistent-2",
            headers={"origin": "https://unknown.com"},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)
        assert get_response_header(response, "Vary") == "Origin"

        # With no origin
        event = make_event(
            method="GET",
            path="/nonexistent-3",
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)
        assert get_response_header(response, "Vary") == "Origin"

    def test_unmatched_route_allows_methods(self, mock_lambda_context):
        """CORS Allow-Methods header includes standard HTTP methods."""
        event = make_event(
            method="GET",
            path="/nonexistent",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        methods = get_response_header(response, "Access-Control-Allow-Methods")
        for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]:
            assert method in methods, f"{method} missing from Allow-Methods"

    def test_unmatched_route_allows_required_headers(self, mock_lambda_context):
        """CORS Allow-Headers includes Content-Type and Authorization."""
        event = make_event(
            method="GET",
            path="/nonexistent",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        allowed = get_response_header(response, "Access-Control-Allow-Headers")
        assert "Content-Type" in allowed
        assert "Authorization" in allowed

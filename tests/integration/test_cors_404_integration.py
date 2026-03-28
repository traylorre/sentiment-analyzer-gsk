"""Integration tests for CORS on env-gated 404 responses (Feature 1268).

These test the full handler invocation path:
handler.py -> Powertools resolver -> route handler -> _make_not_found_response

Note: These do NOT test through API Gateway. API Gateway behavior
(AWS_PROXY pass-through) is verified by E2E tests in preprod.
"""

import importlib
import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Set env before imports
os.environ.setdefault("DYNAMODB_TABLE", "test-sentiment-items")
os.environ.setdefault("SENTIMENTS_TABLE", "test-sentiment-items")
os.environ.setdefault("USERS_TABLE", "test-sentiment-users")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CHAOS_EXPERIMENTS_TABLE", "test-chaos-experiments")

from tests.conftest import make_event


def _reload_handler(env: str, cors_origins: str = ""):
    """Reload handler with specific ENVIRONMENT and CORS_ORIGINS."""
    env_overrides = {"ENVIRONMENT": env}
    if cors_origins:
        env_overrides["CORS_ORIGINS"] = cors_origins
    else:
        env_overrides["CORS_ORIGINS"] = ""
    with patch.dict(os.environ, env_overrides):
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


@pytest.mark.integration
class TestEnvGated404CorsIntegration:
    """Integration tests for CORS on env-gated 404 responses (Feature 1268).

    These test the full handler invocation path:
    handler.py -> Powertools resolver -> route handler -> _make_not_found_response

    Note: These do NOT test through API Gateway. API Gateway behavior
    (AWS_PROXY pass-through) is verified by E2E tests in preprod.
    """

    @pytest.fixture(autouse=True)
    def restore_handler(self):
        """Restore handler to test environment after each test."""
        yield
        _reload_handler("test")

    def test_chaos_endpoint_404_cors_through_handler(self, mock_lambda_context):
        """Full handler path returns 404 with CORS for valid origin."""
        test_origin = "https://dashboard.example.com"
        handler = _reload_handler("preprod", cors_origins=test_origin)
        event = make_event(
            method="GET",
            path="/chaos/experiments",
            headers={"origin": test_origin},
        )
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404
        headers = response.get("headers", {})
        assert headers.get("Access-Control-Allow-Origin") == test_origin
        assert headers.get("Access-Control-Allow-Credentials") == "true"
        assert headers.get("Vary") == "Origin"
        body = json.loads(response["body"])
        assert body["detail"] == "Not found"

    def test_dashboard_root_404_cors_through_handler(self, mock_lambda_context):
        """Dashboard root / returns 404 with CORS in non-dev."""
        test_origin = "https://dashboard.example.com"
        handler = _reload_handler("preprod", cors_origins=test_origin)
        event = make_event(
            method="GET",
            path="/",
            headers={"origin": test_origin},
        )
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404
        headers = response.get("headers", {})
        assert headers.get("Access-Control-Allow-Origin") == test_origin

    def test_static_file_404_cors_through_handler(self, mock_lambda_context):
        """Static file route returns 404 with CORS in non-dev."""
        test_origin = "https://dashboard.example.com"
        handler = _reload_handler("preprod", cors_origins=test_origin)
        event = make_event(
            method="GET",
            path="/static/app.js",
            headers={"origin": test_origin},
        )
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404
        headers = response.get("headers", {})
        assert headers.get("Access-Control-Allow-Origin") == test_origin

    def test_no_cors_when_origins_env_empty(self, mock_lambda_context):
        """No CORS headers when CORS_ORIGINS env var is empty."""
        handler = _reload_handler("preprod", cors_origins="")
        event = make_event(
            method="GET",
            path="/chaos/experiments",
            headers={"origin": "https://some-origin.example.com"},
        )
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404
        headers = response.get("headers", {})
        assert "Access-Control-Allow-Origin" not in headers
        assert headers.get("Vary") == "Origin"

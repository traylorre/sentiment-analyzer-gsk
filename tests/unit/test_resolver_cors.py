"""Unit tests for CORS post-processing on all responses (Feature 1314).

Tests the _inject_cors_headers() function and its integration in lambda_handler().
Verifies that ALL successful API responses include CORS headers when the
requesting origin is in the allowed origins list.

Unlike test_cors_404_headers.py (which tests _make_not_found_response directly)
and test_cors_404_handler.py (which tests the @app.not_found catch-all),
these tests verify CORS on MATCHED routes — the exact scenario that was
broken before Feature 1314 (successful responses had zero CORS headers).

Approach: Reload handler module with CORS_ORIGINS set, then invoke
lambda_handler with events targeting real registered routes.
"""

import importlib
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
SECOND_ORIGIN = "https://localhost:3000"
CORS_ORIGINS_VALUE = f"{ALLOWED_ORIGIN},{SECOND_ORIGIN}"


def _reload_handler(cors_origins: str = CORS_ORIGINS_VALUE):
    """Reload handler module with specific CORS_ORIGINS."""
    with patch.dict(os.environ, {"CORS_ORIGINS": cors_origins}):
        import src.lambdas.dashboard.handler as handler_module

        importlib.reload(handler_module)
        return handler_module


@pytest.fixture
def mock_lambda_context():
    """Minimal Lambda context mock."""
    ctx = MagicMock()
    ctx.function_name = "test-dashboard"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


@pytest.mark.unit
class TestResolverCors:
    """Unit tests for CORS post-processing on matched routes (Feature 1314).

    These test successful API responses (200) on registered routes.
    Before Feature 1314, these responses had ZERO CORS headers and browsers
    silently blocked every response body.
    """

    @pytest.fixture(autouse=True)
    def setup_handler(self):
        """Reload handler with CORS origins before each test, restore after."""
        self.handler = _reload_handler(CORS_ORIGINS_VALUE)
        yield
        _reload_handler("")

    def test_allowed_origin_gets_cors_headers(self, mock_lambda_context):
        """Matched route response includes full CORS headers for allowed origin."""
        event = make_event(
            method="GET",
            path="/api/v2/runtime",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        assert (
            get_response_header(response, "Access-Control-Allow-Origin")
            == ALLOWED_ORIGIN
        )
        assert (
            get_response_header(response, "Access-Control-Allow-Credentials") == "true"
        )
        assert "GET" in get_response_header(response, "Access-Control-Allow-Methods")
        assert "Content-Type" in get_response_header(
            response, "Access-Control-Allow-Headers"
        )

    def test_disallowed_origin_no_cors_allow(self, mock_lambda_context):
        """Matched route omits ACAO for unknown origin (Vary still present)."""
        event = make_event(
            method="GET",
            path="/api/v2/runtime",
            headers={"origin": "https://evil.attacker.example.com"},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        assert get_response_header(response, "Access-Control-Allow-Origin") == ""
        assert get_response_header(response, "Vary") == "Origin"

    def test_missing_origin_no_cors_allow(self, mock_lambda_context):
        """Matched route omits ACAO when no Origin header sent."""
        event = make_event(
            method="GET",
            path="/api/v2/runtime",
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        assert get_response_header(response, "Access-Control-Allow-Origin") == ""
        assert get_response_header(response, "Vary") == "Origin"

    def test_vary_origin_always_present(self, mock_lambda_context):
        """Vary: Origin present on all responses regardless of origin match."""
        # With allowed origin
        event = make_event(
            method="GET",
            path="/api/v2/runtime",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)
        assert get_response_header(response, "Vary") == "Origin"

        # With no origin
        event = make_event(method="GET", path="/api/v2/runtime")
        response = self.handler.lambda_handler(event, mock_lambda_context)
        assert get_response_header(response, "Vary") == "Origin"

        # With bad origin
        event = make_event(
            method="GET",
            path="/api/v2/runtime",
            headers={"origin": "https://evil.com"},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)
        assert get_response_header(response, "Vary") == "Origin"

    def test_second_allowed_origin_reflected(self, mock_lambda_context):
        """Multi-origin: second origin reflected correctly, not first."""
        event = make_event(
            method="GET",
            path="/api/v2/runtime",
            headers={"origin": SECOND_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        acao = get_response_header(response, "Access-Control-Allow-Origin")
        assert acao == SECOND_ORIGIN
        assert ALLOWED_ORIGIN not in acao

    def test_no_wildcard_origin(self, mock_lambda_context):
        """Access-Control-Allow-Origin NEVER uses wildcard *."""
        event = make_event(
            method="GET",
            path="/api/v2/runtime",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        acao = get_response_header(response, "Access-Control-Allow-Origin")
        assert acao != "*"

    def test_not_found_cors_not_duplicated(self, mock_lambda_context):
        """404 from @app.not_found already has CORS; post-processor skips (idempotent)."""
        event = make_event(
            method="GET",
            path="/api/v2/nonexistent/route/for/cors/test",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 404
        # CORS headers should be present (from @app.not_found)
        assert (
            get_response_header(response, "Access-Control-Allow-Origin")
            == ALLOWED_ORIGIN
        )
        # Should NOT have duplicate values (idempotency check)
        mv_headers = response.get("multiValueHeaders") or {}
        for key, val in mv_headers.items():
            if key.lower() == "access-control-allow-origin":
                # Should be a single-element list, not duplicated
                if isinstance(val, list):
                    assert len(val) == 1, (
                        f"ACAO duplicated: {val} (post-processor should skip "
                        f"when @app.not_found already set CORS headers)"
                    )

    def test_multivalue_headers_format(self, mock_lambda_context):
        """CORS headers use list values in multiValueHeaders (v1 proxy format)."""
        event = make_event(
            method="GET",
            path="/api/v2/runtime",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        mv_headers = response.get("multiValueHeaders") or {}
        # Find ACAO in multiValueHeaders
        acao_values = None
        for key, val in mv_headers.items():
            if key.lower() == "access-control-allow-origin":
                acao_values = val
                break

        assert (
            acao_values is not None
        ), "Access-Control-Allow-Origin not found in multiValueHeaders"
        assert isinstance(
            acao_values, list
        ), f"ACAO value should be a list, got {type(acao_values)}"
        assert acao_values == [ALLOWED_ORIGIN]

    def test_api_index_route_gets_cors(self, mock_lambda_context):
        """Registered route /api (200 in test env) includes CORS headers."""
        event = make_event(
            method="GET",
            path="/api",
            headers={"origin": ALLOWED_ORIGIN},
        )
        response = self.handler.lambda_handler(event, mock_lambda_context)

        # In test env, /api returns 200 with endpoint listing
        assert response["statusCode"] == 200
        assert (
            get_response_header(response, "Access-Control-Allow-Origin")
            == ALLOWED_ORIGIN
        )


@pytest.mark.unit
class TestInjectCorsHeadersDirect:
    """Direct unit tests for _inject_cors_headers() function."""

    @pytest.fixture(autouse=True)
    def setup_handler(self):
        """Reload handler with CORS origins before each test, restore after."""
        self.handler = _reload_handler(CORS_ORIGINS_VALUE)
        yield
        _reload_handler("")

    def test_adds_cors_to_empty_response(self):
        """Adds CORS headers to a bare response dict."""
        response = {"statusCode": 200, "body": "{}"}
        event = {"headers": {"origin": ALLOWED_ORIGIN}}

        result = self.handler._inject_cors_headers(response, event)

        assert result is response  # mutated in place
        mv = result["multiValueHeaders"]
        assert mv["Access-Control-Allow-Origin"] == [ALLOWED_ORIGIN]
        assert mv["Access-Control-Allow-Credentials"] == ["true"]
        assert mv["Vary"] == ["Origin"]

    def test_skips_when_acao_already_in_multivalue_headers(self):
        """Idempotent: skips when ACAO already present in multiValueHeaders."""
        response = {
            "statusCode": 404,
            "body": "{}",
            "multiValueHeaders": {
                "Access-Control-Allow-Origin": [ALLOWED_ORIGIN],
                "Vary": ["Origin"],
            },
        }
        event = {"headers": {"origin": ALLOWED_ORIGIN}}

        result = self.handler._inject_cors_headers(response, event)

        # Should not have been modified (ACAO already present)
        assert result["multiValueHeaders"]["Access-Control-Allow-Origin"] == [
            ALLOWED_ORIGIN
        ]
        # Should not have added credentials (idempotent skip)
        assert "Access-Control-Allow-Credentials" not in result["multiValueHeaders"]

    def test_skips_when_acao_already_in_headers(self):
        """Idempotent: skips when ACAO present in singular headers dict."""
        response = {
            "statusCode": 404,
            "body": "{}",
            "headers": {
                "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
                "Vary": "Origin",
            },
        }
        event = {"headers": {"origin": ALLOWED_ORIGIN}}

        result = self.handler._inject_cors_headers(response, event)

        # Should not have added multiValueHeaders CORS entries
        mv = result.get("multiValueHeaders", {})
        assert "Access-Control-Allow-Origin" not in mv

    def test_handles_missing_headers_in_event(self):
        """Gracefully handles event with no headers dict."""
        response = {"statusCode": 200, "body": "{}"}
        event = {}

        result = self.handler._inject_cors_headers(response, event)

        # Should add Vary but no ACAO (no origin to match)
        mv = result["multiValueHeaders"]
        assert mv["Vary"] == ["Origin"]
        assert "Access-Control-Allow-Origin" not in mv

    def test_case_insensitive_origin_header_lookup(self):
        """Origin header lookup is case-insensitive."""
        response = {"statusCode": 200, "body": "{}"}
        event = {"headers": {"Origin": ALLOWED_ORIGIN}}  # Capital O

        result = self.handler._inject_cors_headers(response, event)

        mv = result["multiValueHeaders"]
        assert mv["Access-Control-Allow-Origin"] == [ALLOWED_ORIGIN]

    def test_unmatched_origin_gets_vary_only(self):
        """Unmatched origin gets Vary: Origin but no ACAO."""
        response = {"statusCode": 200, "body": "{}"}
        event = {"headers": {"origin": "https://evil.com"}}

        result = self.handler._inject_cors_headers(response, event)

        mv = result["multiValueHeaders"]
        assert mv["Vary"] == ["Origin"]
        assert "Access-Control-Allow-Origin" not in mv

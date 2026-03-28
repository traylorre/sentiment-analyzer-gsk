"""Integration tests for CORS header behavior (Feature 1267).

These tests verify the deployed API Gateway returns correct CORS headers
when queried with various Origin headers. They require a deployed preprod
API Gateway endpoint.

Tests validate:
- Origin echoing (no wildcard) on OPTIONS responses
- Access-Control-Allow-Credentials: true present
- Vary: Origin header present
- Localhost origins work in preprod
- Unauthorized origins are echoed on OPTIONS (MOCK behavior)
- Lambda middleware rejects unauthorized origins on data requests
- 401/403 error responses include correct CORS headers

For On-Call Engineers:
    If tests fail:
    1. Verify preprod API is deployed: check API Gateway console
    2. Verify the Feature 1267 Terraform changes have been applied
    3. Check API Gateway deployment was triggered after config change
"""

import os

import pytest
import requests

# Preprod API endpoint - set via environment variable
API_ENDPOINT = os.getenv(
    "PREPROD_API_ENDPOINT",
    "",
)

# Known allowed origin (Amplify frontend)
ALLOWED_ORIGIN = "https://main.d29tlmksqcx494.amplifyapp.com"

# Skip all tests if no API endpoint is configured
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not API_ENDPOINT,
        reason="PREPROD_API_ENDPOINT not set; skipping CORS integration tests",
    ),
]


def _options_request(
    path: str = "/",
    origin: str = ALLOWED_ORIGIN,
    timeout: int = 10,
) -> requests.Response:
    """Send an OPTIONS preflight request with the given Origin header."""
    return requests.options(
        f"{API_ENDPOINT}{path}",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
        timeout=timeout,
    )


def _get_request(
    path: str = "/health",
    origin: str = ALLOWED_ORIGIN,
    auth_token: str | None = None,
    timeout: int = 10,
) -> requests.Response:
    """Send a GET request with the given Origin header."""
    headers = {"Origin": origin}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return requests.get(
        f"{API_ENDPOINT}{path}",
        headers=headers,
        timeout=timeout,
    )


# =============================================================================
# Phase 3: User Story 1 - Authenticated Dashboard User Makes API Calls
# =============================================================================


class TestOptionsEchoesOrigin:
    """Verify OPTIONS preflight responses echo the requesting origin."""

    def test_options_echoes_allowed_origin(self) -> None:
        """T015: OPTIONS with allowed origin echoes it back (not wildcard)."""
        resp = _options_request(origin=ALLOWED_ORIGIN)
        assert resp.status_code == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == ALLOWED_ORIGIN

    def test_options_includes_credentials(self) -> None:
        """T016: OPTIONS response includes Access-Control-Allow-Credentials: true."""
        resp = _options_request(origin=ALLOWED_ORIGIN)
        assert resp.status_code == 200
        assert resp.headers.get("Access-Control-Allow-Credentials") == "true"

    def test_options_includes_vary_origin(self) -> None:
        """T017: OPTIONS response includes Vary: Origin header."""
        resp = _options_request(origin=ALLOWED_ORIGIN)
        assert resp.status_code == 200
        vary = resp.headers.get("Vary", "")
        assert "Origin" in vary, f"Expected 'Origin' in Vary header, got: {vary}"


# =============================================================================
# Phase 4: User Story 2 - Local Developer Testing
# =============================================================================


class TestLocalhostOrigins:
    """Verify localhost origins work correctly in preprod."""

    def test_options_echoes_localhost_origin(self) -> None:
        """T018: OPTIONS with localhost:3000 echoes it back."""
        resp = _options_request(origin="http://localhost:3000")
        assert resp.status_code == 200
        assert (
            resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
        )

    def test_options_echoes_localhost_alt_port(self) -> None:
        """T019: OPTIONS with localhost:8080 echoes it back."""
        resp = _options_request(origin="http://localhost:8080")
        assert resp.status_code == 200
        assert (
            resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:8080"
        )


# =============================================================================
# Phase 5: User Story 3 - Unauthorized Origin Rejection
# =============================================================================


class TestUnauthorizedOriginRejection:
    """Verify unauthorized origins cannot exfiltrate data."""

    def test_options_echoes_any_origin_mock_behavior(self) -> None:
        """T020: OPTIONS echoes even evil origins (expected MOCK behavior).

        This is expected because API Gateway MOCK integrations cannot perform
        conditional logic. The security boundary is at the Lambda middleware
        layer, not the OPTIONS preflight.
        """
        resp = _options_request(origin="https://evil.example.com")
        assert resp.status_code == 200
        # MOCK integration echoes any origin - this is by design
        assert (
            resp.headers.get("Access-Control-Allow-Origin")
            == "https://evil.example.com"
        )

    @pytest.mark.skipif(
        not os.getenv("PREPROD_AUTH_TOKEN"),
        reason="PREPROD_AUTH_TOKEN not set; cannot test authenticated endpoints",
    )
    def test_get_rejects_unauthorized_origin(self) -> None:
        """T021: GET with evil origin - Lambda rejects in response headers."""
        auth_token = os.getenv("PREPROD_AUTH_TOKEN", "")
        resp = _get_request(
            path="/api/v2/configurations",
            origin="https://evil.example.com",
            auth_token=auth_token,
        )
        # Lambda middleware should NOT echo the evil origin
        allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
        assert (
            allow_origin != "https://evil.example.com"
        ), "Lambda should reject unauthorized origins in data responses"

    @pytest.mark.skipif(
        not os.getenv("PREPROD_AUTH_TOKEN"),
        reason="PREPROD_AUTH_TOKEN not set; cannot test authenticated endpoints",
    )
    def test_get_accepts_authorized_origin(self) -> None:
        """T022: GET with authorized origin - Lambda echoes it."""
        auth_token = os.getenv("PREPROD_AUTH_TOKEN", "")
        resp = _get_request(
            path="/api/v2/configurations",
            origin=ALLOWED_ORIGIN,
            auth_token=auth_token,
        )
        allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
        assert (
            allow_origin == ALLOWED_ORIGIN
        ), f"Expected Lambda to echo authorized origin, got: {allow_origin}"


# =============================================================================
# Phase 6: User Story 4 - Infrastructure Consistency
# =============================================================================


class TestErrorResponseCORS:
    """Verify error responses include correct CORS headers."""

    def test_401_error_echoes_origin(self) -> None:
        """T024: 401 Unauthorized response echoes the Origin header.

        Sending a request without valid auth to a protected endpoint
        triggers a 401 from API Gateway (Cognito authorizer). The gateway
        response should still echo the origin for CORS to work.
        """
        resp = _get_request(
            path="/api/v2/configurations",
            origin=ALLOWED_ORIGIN,
            auth_token=None,  # No auth - triggers 401
        )
        assert resp.status_code == 401
        allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
        assert (
            allow_origin == ALLOWED_ORIGIN
        ), f"Expected 401 response to echo origin, got: {allow_origin}"

    def test_403_error_echoes_origin(self) -> None:
        """T025: 403 Forbidden response echoes the Origin header.

        Sending a request with an invalid auth token triggers a 403
        from API Gateway. The gateway response should echo the origin.
        """
        resp = _get_request(
            path="/api/v2/configurations",
            origin=ALLOWED_ORIGIN,
            auth_token="invalid-token-triggers-403",
        )
        # API Gateway returns 401 for invalid tokens, not 403
        # Accept either 401 or 403 as both should echo origin
        assert resp.status_code in (401, 403)
        allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
        assert (
            allow_origin == ALLOWED_ORIGIN
        ), f"Expected error response to echo origin, got: {allow_origin}"

"""E2E: Verify CORS headers on error responses via API Gateway (Feature 1268).

Feature 1296: Uses public route /api/v2/tickers/{proxy+} to bypass Cognito
authorizer. No auth header needed — public routes have endpoint_auth=NONE.
Lambda returns 404 for nonexistent ticker paths with CORS headers.

Requires deployed preprod environment with:
- API Gateway endpoint (PREPROD_API_GATEWAY_URL or PREPROD_API_URL)
- CORS origins configured in Terraform (cors_allowed_origins)
"""

import os

import httpx
import pytest

PREPROD_API_URL = os.environ.get(
    "PREPROD_API_GATEWAY_URL", os.environ.get("PREPROD_API_URL", "")
)
# Preprod CORS origin — must match what's in Terraform cors_allowed_origins
PREPROD_CORS_ORIGIN = os.environ.get(
    "PREPROD_CORS_ORIGIN",
    "https://main.d29tlmksqcx494.amplifyapp.com",
)

# Public route with {proxy+} — bypasses Cognito authorizer
# /api/v2/tickers has has_proxy=true, endpoint_auth="NONE" in main.tf
NONEXISTENT_PUBLIC_PATH = "/api/v2/tickers/nonexistent-cors-test"


@pytest.mark.preprod
class TestEnvGated404CorsE2E:
    """E2E: Verify CORS headers on 404 responses through API Gateway.

    Uses a public route (no Cognito auth) to reach Lambda, which returns
    404 with application-level CORS headers for nonexistent paths.
    """

    @pytest.fixture(autouse=True)
    def skip_if_no_url(self):
        if not PREPROD_API_URL:
            pytest.skip("PREPROD_API_URL / PREPROD_API_GATEWAY_URL not set")

    def test_404_response_has_cors_headers(self):
        """Hit nonexistent public route, verify CORS headers present on 404."""
        response = httpx.get(
            f"{PREPROD_API_URL}{NONEXISTENT_PUBLIC_PATH}",
            headers={"Origin": PREPROD_CORS_ORIGIN},
            timeout=10,
        )
        assert (
            response.status_code == 404
        ), f"Expected 404 for nonexistent route, got {response.status_code}"
        assert (
            response.headers.get("access-control-allow-origin") is not None
        ), "Missing Access-Control-Allow-Origin on 404 response"
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_404_response_no_cors_for_unknown_origin(self):
        """Hit nonexistent public route with unknown origin, verify no allow-origin."""
        bad_origin = "https://evil.attacker.example.com"
        response = httpx.get(
            f"{PREPROD_API_URL}{NONEXISTENT_PUBLIC_PATH}",
            headers={"Origin": bad_origin},
            timeout=10,
        )
        assert (
            response.status_code == 404
        ), f"Expected 404 for nonexistent route, got {response.status_code}"
        allow_origin = response.headers.get("access-control-allow-origin", "")
        assert (
            allow_origin != bad_origin
        ), f"Should not echo unknown origin: {allow_origin}"

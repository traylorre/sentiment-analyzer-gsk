"""E2E: Verify CORS headers on error responses via API Gateway (Feature 1268).

Feature 1291: Updated to route through API Gateway instead of Lambda Function URL.
Lambda Function URLs use AWS_IAM auth (Feature 1256) which rejects unauthenticated
HTTP requests with 403 before reaching application code. Production traffic flows
through API Gateway, so these tests now match the production architecture.

Requires deployed preprod environment with:
- API Gateway endpoint (PREPROD_API_GATEWAY_URL)
- JWT secret for authenticated requests (PREPROD_TEST_JWT_SECRET)
- CORS origins configured in Terraform (cors_allowed_origins)
"""

import os
import uuid

import httpx
import pytest

from tests.e2e.conftest import create_test_jwt

PREPROD_API_GATEWAY_URL = os.environ.get("PREPROD_API_GATEWAY_URL", "")
PREPROD_TEST_JWT_SECRET = os.environ.get(
    "PREPROD_TEST_JWT_SECRET", "test-jwt-secret-for-e2e-only-not-production"
)
# Preprod CORS origin — must match what's in Terraform cors_allowed_origins
PREPROD_CORS_ORIGIN = os.environ.get(
    "PREPROD_CORS_ORIGIN",
    "https://main.d29tlmksqcx494.amplifyapp.com",
)


@pytest.mark.preprod
class TestEnvGated404CorsE2E:
    """E2E: Verify CORS headers on 404 responses through API Gateway.

    Tests authenticated requests to nonexistent routes, verifying that
    Lambda's application-level CORS headers are preserved through API Gateway.
    """

    @pytest.fixture(autouse=True)
    def skip_if_no_url(self):
        if not PREPROD_API_GATEWAY_URL:
            pytest.skip("PREPROD_API_GATEWAY_URL not set")

    def _make_auth_headers(self, origin: str) -> dict[str, str]:
        """Create headers with JWT auth and Origin for CORS testing."""
        token = create_test_jwt(
            user_id=str(uuid.uuid4()),
            secret=PREPROD_TEST_JWT_SECRET,
        )
        return {
            "Authorization": f"Bearer {token}",
            "Origin": origin,
        }

    def test_404_response_has_cors_headers(self):
        """Hit nonexistent route via API Gateway, verify CORS headers present on 404."""
        headers = self._make_auth_headers(PREPROD_CORS_ORIGIN)
        response = httpx.get(
            f"{PREPROD_API_GATEWAY_URL}/api/v2/nonexistent-cors-test-route",
            headers=headers,
            timeout=10,
        )
        assert (
            response.status_code == 404
        ), f"Expected 404 for nonexistent route, got {response.status_code}"
        # Verify Lambda-level CORS headers are preserved through API Gateway
        assert (
            response.headers.get("access-control-allow-origin") is not None
        ), "Missing Access-Control-Allow-Origin on 404 response"
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_404_response_no_cors_for_unknown_origin(self):
        """Hit nonexistent route with unknown origin, verify no CORS allow-origin."""
        bad_origin = "https://evil.attacker.example.com"
        headers = self._make_auth_headers(bad_origin)
        response = httpx.get(
            f"{PREPROD_API_GATEWAY_URL}/api/v2/nonexistent-cors-test-route",
            headers=headers,
            timeout=10,
        )
        assert (
            response.status_code == 404
        ), f"Expected 404 for nonexistent route, got {response.status_code}"
        # CORS origin header should NOT be present for unknown origins
        allow_origin = response.headers.get("access-control-allow-origin", "")
        assert (
            allow_origin != bad_origin
        ), f"Should not echo unknown origin: {allow_origin}"

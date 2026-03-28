"""E2E: Verify CORS headers on env-gated 404 in preprod (Feature 1268).

Requires deployed preprod environment with CORS_ORIGINS configured.
May be deferred to gameday if preprod is not available.

These tests make real HTTP calls to the preprod API Gateway endpoint
with explicit Origin headers to verify CORS header presence/absence.
"""

import os

import httpx
import pytest

PREPROD_API_URL = os.environ.get("PREPROD_API_URL", "")
# Preprod CORS origins (should match Terraform var.cors_allowed_origins)
PREPROD_CORS_ORIGIN = os.environ.get(
    "PREPROD_CORS_ORIGIN", "https://preprod.sentiment-analyzer.example.com"
)


@pytest.mark.preprod
class TestEnvGated404CorsE2E:
    """E2E: Verify CORS headers on env-gated 404 in preprod.

    Requires deployed preprod environment. May be deferred to gameday.
    """

    @pytest.fixture(autouse=True)
    def skip_if_no_url(self):
        if not PREPROD_API_URL:
            pytest.skip("PREPROD_API_URL not set")

    def test_chaos_endpoint_404_has_cors(self):
        """Hit chaos endpoint in preprod, verify CORS headers present."""
        response = httpx.get(
            f"{PREPROD_API_URL}/chaos/experiments",
            headers={"Origin": PREPROD_CORS_ORIGIN},
            timeout=10,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"
        # Verify CORS headers are present for valid origin
        assert (
            response.headers.get("access-control-allow-origin") == PREPROD_CORS_ORIGIN
        )
        assert response.headers.get("vary") == "Origin"
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_chaos_endpoint_404_no_cors_bad_origin(self):
        """Hit chaos endpoint with unknown origin, verify no CORS origin."""
        bad_origin = "https://evil.attacker.example.com"
        response = httpx.get(
            f"{PREPROD_API_URL}/chaos/experiments",
            headers={"Origin": bad_origin},
            timeout=10,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"
        # Verify CORS origin header is NOT present for unknown origin
        assert "access-control-allow-origin" not in response.headers
        # Vary: Origin should still be present
        assert response.headers.get("vary") == "Origin"

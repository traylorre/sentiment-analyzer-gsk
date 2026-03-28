"""E2E test for production CORS headers (Feature 1269).

Verifies that the API returns correct CORS headers for configured
production origins and rejects unknown origins.

Requires:
- AWS_ENV=prod
- PROD_API_GATEWAY_URL set to the production API endpoint

AR3-FINDING-5: If OPTIONS fails with 401/403, check API Gateway CORS
configuration (Feature 1253). API Gateway may require separate CORS
setup from Lambda Function URLs.
"""

import os

import pytest
import requests

from tests.e2e.conftest import SkipInfo

skip = SkipInfo(
    condition=os.getenv("AWS_ENV") != "prod",
    reason="Requires prod deployment",
    remediation="Run with AWS_ENV=prod and PROD_API_GATEWAY_URL set",
)


@pytest.mark.skipif(skip.condition, reason=skip.reason)
class TestCorsProdHeaders:
    """Verify production CORS headers are correctly configured."""

    @pytest.fixture
    def api_url(self) -> str:
        """Get production API URL from environment."""
        url = os.environ.get("PROD_API_GATEWAY_URL")
        if not url:
            pytest.skip("PROD_API_GATEWAY_URL not set")
        return url

    def test_preflight_returns_allowed_origin(self, api_url: str) -> None:
        """OPTIONS preflight returns Access-Control-Allow-Origin for configured origin."""
        response = requests.options(
            f"{api_url}/api/v2/health",
            headers={
                "Origin": "https://traylorre.github.io",
                "Access-Control-Request-Method": "GET",
            },
            timeout=10,
        )
        assert response.headers.get("Access-Control-Allow-Origin") == (
            "https://traylorre.github.io"
        ), (
            f"Expected ACAO header for configured origin. "
            f"Got: {response.headers.get('Access-Control-Allow-Origin')}"
        )

    def test_preflight_rejects_unknown_origin(self, api_url: str) -> None:
        """OPTIONS preflight does NOT return ACAO for unknown origin."""
        response = requests.options(
            f"{api_url}/api/v2/health",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
            timeout=10,
        )
        acao = response.headers.get("Access-Control-Allow-Origin", "")
        assert "evil.com" not in acao, (
            f"API returned ACAO for unknown origin 'evil.com': {acao}. "
            "Production should only allow configured origins."
        )

    def test_credentials_header_present(self, api_url: str) -> None:
        """Access-Control-Allow-Credentials is true for configured origin."""
        response = requests.options(
            f"{api_url}/api/v2/health",
            headers={
                "Origin": "https://traylorre.github.io",
                "Access-Control-Request-Method": "GET",
            },
            timeout=10,
        )
        assert response.headers.get("Access-Control-Allow-Credentials") == "true", (
            "Access-Control-Allow-Credentials should be 'true' for configured origin. "
            f"Got: {response.headers.get('Access-Control-Allow-Credentials')}"
        )

    def test_get_request_includes_cors_headers(self, api_url: str) -> None:
        """GET request (not just preflight) includes CORS headers."""
        response = requests.get(
            f"{api_url}/api/v2/health",
            headers={
                "Origin": "https://traylorre.github.io",
            },
            timeout=10,
        )
        acao = response.headers.get("Access-Control-Allow-Origin")
        assert (
            acao == "https://traylorre.github.io"
        ), f"GET response missing ACAO header for configured origin. Got: {acao}"

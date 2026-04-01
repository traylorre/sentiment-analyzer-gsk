"""E2E tests for Lambda Function URL restriction (Feature 1256).

Tests verify that direct access to the SSE Lambda Function URL returns 403
(auth_type=AWS_IAM), while API Gateway and CloudFront paths continue to work.

Feature 1300: Dashboard Function URL removed — only SSE Function URL tests remain.
Dashboard Lambda is accessed exclusively via API Gateway (lambda:InvokeFunction).

Requires:
- SSE_FUNCTION_URL: Direct Lambda Function URL for SSE
- PREPROD_API_URL: API Gateway URL (should work)
- SSE_CLOUDFRONT_URL: CloudFront URL (should work)
"""

import os

import httpx
import pytest

from tests.e2e.conftest import SkipInfo

skip = SkipInfo(
    condition=os.getenv("AWS_ENV") != "preprod",
    reason="Requires preprod with Function URL auth=AWS_IAM",
    remediation="Run with AWS_ENV=preprod and Function URL env vars set",
)


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestDirectSSEFunctionURLBlocked:
    """Direct SSE Function URL access returns 403 (auth_type=AWS_IAM)."""

    @pytest.mark.asyncio
    async def test_sse_function_url_returns_403(self) -> None:
        """SC-002: Direct curl to SSE Function URL -> 403."""
        url = os.environ.get("SSE_FUNCTION_URL", "")
        if not url:
            pytest.skip("SSE_FUNCTION_URL not set")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/api/v2/stream/status")
        assert (
            response.status_code == 403
        ), f"Expected 403 (auth_type=AWS_IAM), got {response.status_code}"


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestProtectedPathsStillWork:
    """API Gateway and CloudFront paths still work."""

    @pytest.mark.asyncio
    async def test_api_gateway_health_works(self) -> None:
        """SC-003: API Gateway health check returns 200."""
        url = os.environ.get("PREPROD_API_URL", "")
        if not url:
            pytest.skip("PREPROD_API_URL not set")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cloudfront_sse_status_works(self) -> None:
        """SC-004: CloudFront SSE stream/status returns 200."""
        url = os.environ.get("SSE_CLOUDFRONT_URL", "")
        if not url:
            pytest.skip("SSE_CLOUDFRONT_URL not set")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/api/v2/stream/status")
        assert response.status_code == 200

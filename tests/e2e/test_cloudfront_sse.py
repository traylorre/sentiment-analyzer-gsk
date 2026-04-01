"""E2E tests for CloudFront SSE streaming (Feature 1255).

Tests verify SSE events arrive via CloudFront, WAF blocks malicious
requests, and normal streaming traffic passes through.

Requires:
- SSE_CLOUDFRONT_URL pointing to CloudFront distribution
- WAF WebACL associated with CloudFront
"""

import os

import httpx
import pytest

from tests.e2e.conftest import SkipInfo

skip = SkipInfo(
    condition=os.getenv("AWS_ENV") != "preprod",
    reason="Requires preprod CloudFront distribution with WAF",
    remediation="Run with AWS_ENV=preprod and SSE_CLOUDFRONT_URL set",
)


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestSSEViaCloudFront:
    """US1: SSE traffic routes through CloudFront."""

    @pytest.fixture
    def sse_url(self) -> str:
        url = os.environ.get("SSE_CLOUDFRONT_URL", "").rstrip("/")
        if not url:
            pytest.skip("SSE_CLOUDFRONT_URL not set — CloudFront not yet deployed")
        return url

    @pytest.mark.asyncio
    async def test_stream_status_via_cloudfront(self, sse_url: str) -> None:
        """Scenario 3: /stream/status returns JSON via CloudFront."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{sse_url}/api/v2/stream/status")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_cloudfront_no_cache_header(self, sse_url: str) -> None:
        """SC-004: CloudFront does NOT cache SSE responses."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{sse_url}/api/v2/stream/status",
                headers={"Accept": "application/json"},
            )
        # X-Cache header should be Miss (not cached)
        x_cache = response.headers.get("x-cache", "")
        assert "Hit" not in x_cache, f"SSE should not be cached, got X-Cache: {x_cache}"


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestWAFProtectsSSE:
    """US2: WAF blocks malicious requests to SSE endpoints."""

    @pytest.fixture
    def sse_url(self) -> str:
        url = os.environ.get("SSE_CLOUDFRONT_URL", "").rstrip("/")
        if not url:
            pytest.skip("SSE_CLOUDFRONT_URL not set — CloudFront not yet deployed")
        return url

    @pytest.mark.asyncio
    async def test_sqli_on_sse_blocked(self, sse_url: str) -> None:
        """Scenario 6: SQLi on SSE endpoint blocked by WAF."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{sse_url}/api/v2/stream/status",
                params={"q": "' OR '1'='1"},
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_normal_sse_request_passes(self, sse_url: str) -> None:
        """Normal SSE request passes through WAF."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{sse_url}/api/v2/stream/status")
        assert response.status_code == 200

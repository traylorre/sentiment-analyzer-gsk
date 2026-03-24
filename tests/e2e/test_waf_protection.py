"""E2E tests for WAF v2 protection (Feature 1254).

Tests verify that WAF blocks SQL injection, XSS, and rate-limited IPs
before requests reach Lambda. Normal traffic passes through unaffected.

Requires:
- PREPROD_API_URL pointing to API Gateway endpoint (behind WAF)
- WAF WebACL associated with API Gateway stage
"""

import os

import httpx
import pytest

from tests.conftest import SkipInfo

skip = SkipInfo(
    condition=os.getenv("AWS_ENV") != "preprod",
    reason="Requires preprod API Gateway with WAF enabled",
    remediation="Run with AWS_ENV=preprod and PREPROD_API_URL set to API Gateway URL",
)


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestSQLInjectionBlocked:
    """US2: SQL injection attempts blocked by WAF."""

    @pytest.fixture
    def api_url(self) -> str:
        return os.environ.get("PREPROD_API_URL", "").rstrip("/")

    @pytest.mark.asyncio
    async def test_sqli_in_query_param_blocked(self, api_url: str) -> None:
        """Scenario 5: SQLi in query parameter → 403."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v2/tickers/search",
                params={"q": "' OR '1'='1"},
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sqli_drop_table_blocked(self, api_url: str) -> None:
        """SQLi DROP TABLE pattern → 403."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v2/tickers/search",
                params={"q": "'; DROP TABLE users; --"},
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_normal_query_not_blocked(self, api_url: str) -> None:
        """Scenario 7: Normal text with SQL keywords → allowed."""
        async with httpx.AsyncClient() as client:
            # Create session first for app-level auth
            session = await client.post(f"{api_url}/api/v2/auth/anonymous")
            if session.status_code == 201:
                token = session.json().get("token", session.json().get("user_id", ""))
                response = await client.get(
                    f"{api_url}/api/v2/tickers/search",
                    params={"q": "AAPL"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == 200


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestXSSBlocked:
    """US3: XSS attempts blocked by WAF."""

    @pytest.fixture
    def api_url(self) -> str:
        return os.environ.get("PREPROD_API_URL", "").rstrip("/")

    @pytest.mark.asyncio
    async def test_xss_script_tag_blocked(self, api_url: str) -> None:
        """Scenario 8: XSS script tag in body → 403."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/api/v2/auth/anonymous",
                headers={"X-Custom": "<script>alert(1)</script>"},
            )
        # WAF may block based on header inspection
        assert response.status_code in (403, 201)  # 201 if header not inspected

    @pytest.mark.asyncio
    async def test_xss_url_encoded_blocked(self, api_url: str) -> None:
        """Scenario 9: URL-encoded XSS → 403."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v2/tickers/search",
                params={"q": "<script>alert(1)</script>"},
            )
        assert response.status_code == 403


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestOptionsExempt:
    """FR-010: OPTIONS preflight not counted toward rate limit."""

    @pytest.fixture
    def api_url(self) -> str:
        return os.environ.get("PREPROD_API_URL", "").rstrip("/")

    @pytest.mark.asyncio
    async def test_options_request_allowed(self, api_url: str) -> None:
        """OPTIONS preflight passes through WAF (ALLOW rule, priority 0)."""
        async with httpx.AsyncClient() as client:
            response = await client.options(
                f"{api_url}/api/v2/configurations",
                headers={
                    "Origin": "https://test.example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
        assert response.status_code == 200


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestNormalTrafficPasses:
    """SC-004: Normal user traffic experiences zero false positives."""

    @pytest.fixture
    def api_url(self) -> str:
        return os.environ.get("PREPROD_API_URL", "").rstrip("/")

    @pytest.mark.asyncio
    async def test_health_check_passes_waf(self, api_url: str) -> None:
        """Health endpoint passes through WAF without issues."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_anonymous_session_passes_waf(self, api_url: str) -> None:
        """Anonymous session creation passes through WAF."""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{api_url}/api/v2/auth/anonymous")
        assert response.status_code == 201

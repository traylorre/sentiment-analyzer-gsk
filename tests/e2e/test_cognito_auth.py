"""E2E tests for API Gateway Cognito auth (Feature 1253).

Tests verify that protected endpoints return 401 from API Gateway without
a valid Cognito JWT, public endpoints remain accessible, CORS headers are
present on 401 responses, and anonymous UUID tokens work on public routes.

Requires:
- PREPROD_API_URL pointing to API Gateway endpoint (with /v1 stage)
- Cognito auth enabled on the API Gateway
- Public route overrides deployed
"""

import os

import httpx
import pytest

from tests.e2e.conftest import SkipInfo

skip = SkipInfo(
    condition=os.getenv("AWS_ENV") != "preprod",
    reason="Requires preprod API Gateway with Cognito auth enabled",
    remediation="Run with AWS_ENV=preprod and PREPROD_API_URL set to API Gateway URL",
)


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestProtectedEndpoints:
    """US1: Protected endpoints reject invalid tokens at API Gateway."""

    @pytest.fixture
    def api_url(self) -> str:
        url = os.environ.get("PREPROD_API_URL", "").rstrip("/")
        if not url:
            pytest.skip("PREPROD_API_URL not set")
        return url

    @pytest.mark.asyncio
    async def test_configurations_without_token_returns_401(self, api_url: str) -> None:
        """Scenario 1: GET /configurations without token → 401."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/api/v2/configurations")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_configurations_with_uuid_token_returns_401(
        self, api_url: str
    ) -> None:
        """Scenario 4: UUID anonymous token on protected endpoint → 401."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v2/configurations",
                headers={
                    "Authorization": "Bearer 12345678-1234-1234-1234-123456789abc"
                },
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_orphaned_endpoint_returns_401(self, api_url: str) -> None:
        """Scenario 5: Orphaned endpoint without JWT → 401 (falls to {proxy+})."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/api/v2/sentiment")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_alerts_without_token_returns_401(self, api_url: str) -> None:
        """Alerts endpoint requires Cognito JWT."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/api/v2/alerts")
        assert response.status_code == 401


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestPublicEndpoints:
    """US2: Public endpoints remain accessible without Cognito JWT."""

    @pytest.fixture
    def api_url(self) -> str:
        url = os.environ.get("PREPROD_API_URL", "").rstrip("/")
        if not url:
            pytest.skip("PREPROD_API_URL not set")
        return url

    @pytest.mark.asyncio
    async def test_health_without_token_returns_200(self, api_url: str) -> None:
        """Scenario 8: GET /health without auth → 200."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_anonymous_session_creation(self, api_url: str) -> None:
        """Scenario 6: POST /auth/anonymous without auth → 201."""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{api_url}/api/v2/auth/anonymous")
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_runtime_without_token_returns_200(self, api_url: str) -> None:
        """Runtime config accessible without JWT (app initialization)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/api/v2/runtime")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_tickers_search_with_uuid_token(self, api_url: str) -> None:
        """Scenario 7: Ticker search with UUID token → 200 (public, app-level auth)."""
        # Create anonymous session first to get a UUID token
        async with httpx.AsyncClient() as client:
            session_resp = await client.post(f"{api_url}/api/v2/auth/anonymous")
            if session_resp.status_code == 201:
                token = session_resp.json().get(
                    "token", session_resp.json().get("user_id", "")
                )
                response = await client.get(
                    f"{api_url}/api/v2/tickers/search",
                    params={"q": "AAPL"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == 200


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestCORSOnErrorResponses:
    """US4: 401 responses include CORS headers."""

    @pytest.fixture
    def api_url(self) -> str:
        url = os.environ.get("PREPROD_API_URL", "").rstrip("/")
        if not url:
            pytest.skip("PREPROD_API_URL not set")
        return url

    @pytest.mark.asyncio
    async def test_401_includes_cors_allow_origin(self, api_url: str) -> None:
        """Scenario 15: 401 includes Access-Control-Allow-Origin."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v2/configurations",
                headers={"Origin": "https://test.example.com"},
            )
        assert response.status_code == 401
        assert "access-control-allow-origin" in {k.lower() for k in response.headers}

    @pytest.mark.asyncio
    async def test_401_includes_cors_allow_credentials(self, api_url: str) -> None:
        """Scenario 15: 401 includes Access-Control-Allow-Credentials: true."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v2/configurations",
                headers={"Origin": "https://test.example.com"},
            )
        assert response.status_code == 401
        cred_header = response.headers.get("access-control-allow-credentials", "")
        assert cred_header == "true"

    @pytest.mark.asyncio
    async def test_401_uses_explicit_allow_headers(self, api_url: str) -> None:
        """CORS Allow-Headers must be explicit list, not wildcard '*'."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v2/configurations",
                headers={"Origin": "https://test.example.com"},
            )
        assert response.status_code == 401
        allow_headers = response.headers.get("access-control-allow-headers", "")
        assert allow_headers != "*", "Must use explicit header list, not wildcard"
        assert "Authorization" in allow_headers

    @pytest.mark.asyncio
    async def test_options_preflight_returns_200(self, api_url: str) -> None:
        """Scenario 16: OPTIONS preflight → 200 with CORS, no Cognito check."""
        async with httpx.AsyncClient() as client:
            response = await client.options(
                f"{api_url}/api/v2/configurations",
                headers={
                    "Origin": "https://test.example.com",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                },
            )
        assert response.status_code == 200
        assert "access-control-allow-methods" in {k.lower() for k in response.headers}


@pytest.mark.skipif(skip.condition, reason=skip.reason)
@pytest.mark.preprod
class TestAnonymousSessions:
    """US5: Existing anonymous sessions continue working."""

    @pytest.fixture
    def api_url(self) -> str:
        url = os.environ.get("PREPROD_API_URL", "").rstrip("/")
        if not url:
            pytest.skip("PREPROD_API_URL not set")
        return url

    @pytest.mark.asyncio
    async def test_uuid_token_on_public_endpoint_works(self, api_url: str) -> None:
        """Scenario 17: Anonymous UUID token on public endpoint → works."""
        async with httpx.AsyncClient() as client:
            # Create anonymous session
            session_resp = await client.post(f"{api_url}/api/v2/auth/anonymous")
            if session_resp.status_code == 201:
                token = session_resp.json().get(
                    "token", session_resp.json().get("user_id", "")
                )
                # Access public endpoint with UUID token
                response = await client.get(
                    f"{api_url}/api/v2/market/status",
                    headers={"Authorization": f"Bearer {token}"},
                )
                # Public route — passes through to Lambda, app-level auth validates UUID
                assert response.status_code in (200, 404)  # 404 if market is closed

    @pytest.mark.asyncio
    async def test_uuid_token_on_protected_endpoint_returns_401(
        self, api_url: str
    ) -> None:
        """Scenario 18: Anonymous UUID token on protected endpoint → 401."""
        async with httpx.AsyncClient() as client:
            session_resp = await client.post(f"{api_url}/api/v2/auth/anonymous")
            if session_resp.status_code == 201:
                token = session_resp.json().get(
                    "token", session_resp.json().get("user_id", "")
                )
                response = await client.get(
                    f"{api_url}/api/v2/configurations",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == 401

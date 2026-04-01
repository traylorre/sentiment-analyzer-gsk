"""E2E tests for admin dashboard lockdown on preprod (Feature 1249).

Verifies that admin routes return 404, health/runtime are stripped,
and refresh/status requires auth on the deployed preprod environment.

Feature 1291/1292: Rewritten to use PreprodAPIClient invoke transport.
Raw requests to Function URL blocked by AWS_IAM auth (Feature 1256).
"""

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.preprod, pytest.mark.e2e]


class TestAdminLockdownPreprod:
    """Preprod regression tests for admin dashboard lockdown."""

    @pytest.mark.asyncio
    async def test_root_returns_404(self, api_client: PreprodAPIClient):
        """GET / should return 404 in preprod."""
        resp = await api_client.get("/")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chaos_returns_404(self, api_client: PreprodAPIClient):
        """GET /chaos should return 404 in preprod."""
        resp = await api_client.get("/chaos")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_static_returns_404(self, api_client: PreprodAPIClient):
        """GET /static/app.js should return 404 in preprod."""
        resp = await api_client.get("/static/app.js")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_api_index_returns_404(self, api_client: PreprodAPIClient):
        """GET /api should return 404 in preprod."""
        resp = await api_client.get("/api")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_health_stripped(self, api_client: PreprodAPIClient):
        """GET /health should return 200 with only status key."""
        resp = await api_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "table" not in data, "Health response leaks table name"
        assert "environment" not in data, "Health response leaks environment"

    @pytest.mark.asyncio
    async def test_runtime_stripped(self, api_client: PreprodAPIClient):
        """GET /api/v2/runtime should not expose SSE URL or real env."""
        resp = await api_client.get("/api/v2/runtime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sse_url"] is None, "Runtime response leaks SSE Lambda URL"
        assert data["environment"] == "production"

    @pytest.mark.asyncio
    async def test_refresh_status_requires_auth(self, api_client: PreprodAPIClient):
        """GET /configurations/{id}/refresh/status without token -> 401."""
        resp = await api_client.get(
            "/api/v2/configurations/fake-id/refresh/status",
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_api_v2_still_works(self, api_client: PreprodAPIClient):
        """POST /api/v2/auth/anonymous should still return 201."""
        resp = await api_client.post(
            "/api/v2/auth/anonymous",
            json={},
        )
        assert resp.status_code == 201

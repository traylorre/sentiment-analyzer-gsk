"""E2E tests for chaos endpoint lockdown on preprod (Feature 1250).

Verifies all chaos endpoints return 404 in preprod environment.

Feature 1291/1292: Rewritten to use PreprodAPIClient invoke transport.
Raw requests to Function URL blocked by AWS_IAM auth (Feature 1256).
"""

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.preprod, pytest.mark.e2e]


class TestChaosLockdownPreprod:
    """Preprod regression tests for chaos endpoint lockdown."""

    @pytest.mark.asyncio
    async def test_chaos_create_returns_404(self, api_client: PreprodAPIClient):
        """POST /chaos/experiments should return 404 in preprod."""
        resp = await api_client.post(
            "/chaos/experiments",
            json={
                "scenario_type": "ingestion_failure",
                "blast_radius": 50,
                "duration_seconds": 30,
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chaos_list_returns_404(self, api_client: PreprodAPIClient):
        """GET /chaos/experiments should return 404 in preprod."""
        resp = await api_client.get("/chaos/experiments")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chaos_start_returns_404(self, api_client: PreprodAPIClient):
        """POST /chaos/experiments/fake/start should return 404 in preprod."""
        resp = await api_client.post("/chaos/experiments/fake-id/start")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chaos_stop_returns_404(self, api_client: PreprodAPIClient):
        """POST /chaos/experiments/fake/stop should return 404 in preprod."""
        resp = await api_client.post("/chaos/experiments/fake-id/stop")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chaos_delete_returns_404(self, api_client: PreprodAPIClient):
        """DELETE /chaos/experiments/fake should return 404 in preprod."""
        resp = await api_client.delete("/chaos/experiments/fake-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chaos_report_returns_404(self, api_client: PreprodAPIClient):
        """GET /chaos/experiments/fake/report should return 404 in preprod."""
        resp = await api_client.get("/chaos/experiments/fake-id/report")
        assert resp.status_code == 404

"""E2E tests for admin dashboard lockdown on preprod (Feature 1249).

Verifies that admin routes return 404, health/runtime are stripped,
and refresh/status requires auth on the deployed preprod environment.
"""

import os

import pytest
import requests

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")


@pytest.mark.preprod
class TestAdminLockdownPreprod:
    """Preprod regression tests for admin dashboard lockdown."""

    @pytest.fixture(autouse=True)
    def _skip_without_url(self):
        if not DASHBOARD_URL:
            pytest.skip("DASHBOARD_URL not set — not running against preprod")

    def test_root_returns_404(self):
        """GET / should return 404 in preprod."""
        resp = requests.get(f"{DASHBOARD_URL}/", timeout=30)
        assert resp.status_code == 404

    def test_chaos_returns_404(self):
        """GET /chaos should return 404 in preprod."""
        resp = requests.get(f"{DASHBOARD_URL}/chaos", timeout=30)
        assert resp.status_code == 404

    def test_static_returns_404(self):
        """GET /static/app.js should return 404 in preprod."""
        resp = requests.get(f"{DASHBOARD_URL}/static/app.js", timeout=30)
        assert resp.status_code == 404

    def test_api_index_returns_404(self):
        """GET /api should return 404 in preprod."""
        resp = requests.get(f"{DASHBOARD_URL}/api", timeout=30)
        assert resp.status_code == 404

    def test_health_stripped(self):
        """GET /health should return 200 with only status key."""
        resp = requests.get(f"{DASHBOARD_URL}/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "table" not in data, "Health response leaks table name"
        assert "environment" not in data, "Health response leaks environment"

    def test_runtime_stripped(self):
        """GET /api/v2/runtime should not expose SSE URL or real env."""
        resp = requests.get(f"{DASHBOARD_URL}/api/v2/runtime", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sse_url"] is None, "Runtime response leaks SSE Lambda URL"
        assert data["environment"] == "production"

    def test_refresh_status_requires_auth(self):
        """GET /configurations/{id}/refresh/status without token → 401."""
        resp = requests.get(
            f"{DASHBOARD_URL}/api/v2/configurations/fake-id/refresh/status",
            timeout=30,
        )
        assert resp.status_code == 401

    def test_api_v2_still_works(self):
        """POST /api/v2/auth/anonymous should still return 201."""
        resp = requests.post(
            f"{DASHBOARD_URL}/api/v2/auth/anonymous",
            json={},
            timeout=30,
        )
        assert resp.status_code == 201

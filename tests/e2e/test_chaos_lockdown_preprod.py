"""E2E tests for chaos endpoint lockdown on preprod (Feature 1250).

Verifies all chaos endpoints return 404 in preprod environment.
"""

import os

import pytest
import requests

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")


@pytest.mark.preprod
class TestChaosLockdownPreprod:
    """Preprod regression tests for chaos endpoint lockdown."""

    @pytest.fixture(autouse=True)
    def _skip_without_url(self):
        if not DASHBOARD_URL:
            pytest.skip("DASHBOARD_URL not set — not running against preprod")

    def test_chaos_create_returns_404(self):
        """POST /chaos/experiments should return 404 in preprod."""
        resp = requests.post(
            f"{DASHBOARD_URL}/chaos/experiments",
            json={
                "scenario_type": "ingestion_failure",
                "blast_radius": 50,
                "duration_seconds": 30,
            },
            timeout=30,
        )
        assert resp.status_code == 404

    def test_chaos_list_returns_404(self):
        """GET /chaos/experiments should return 404 in preprod."""
        resp = requests.get(f"{DASHBOARD_URL}/chaos/experiments", timeout=30)
        assert resp.status_code == 404

    def test_chaos_start_returns_404(self):
        """POST /chaos/experiments/fake/start should return 404 in preprod."""
        resp = requests.post(
            f"{DASHBOARD_URL}/chaos/experiments/fake-id/start", timeout=30
        )
        assert resp.status_code == 404

    def test_chaos_stop_returns_404(self):
        """POST /chaos/experiments/fake/stop should return 404 in preprod."""
        resp = requests.post(
            f"{DASHBOARD_URL}/chaos/experiments/fake-id/stop", timeout=30
        )
        assert resp.status_code == 404

    def test_chaos_delete_returns_404(self):
        """DELETE /chaos/experiments/fake should return 404 in preprod."""
        resp = requests.delete(f"{DASHBOARD_URL}/chaos/experiments/fake-id", timeout=30)
        assert resp.status_code == 404

    def test_chaos_report_returns_404(self):
        """GET /chaos/experiments/fake/report should return 404 in preprod."""
        resp = requests.get(
            f"{DASHBOARD_URL}/chaos/experiments/fake-id/report", timeout=30
        )
        assert resp.status_code == 404

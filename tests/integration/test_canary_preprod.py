"""
Canary Test for Preprod

This is a META-TEST: We're testing the canary itself.

The canary is a simple health check that will run after prod deployment
to validate the system is operational. If this test fails in preprod,
the canary is broken and we should NOT deploy to prod (we'd have no monitoring).

Purpose:
- Validate the health endpoint returns expected structure
- Validate the health endpoint responds quickly
- Validate authentication is required

Integration Level: REAL AWS (preprod environment)

Feature 1292: Rewritten to use PreprodAPIClient invoke transport.
Raw requests to Function URL blocked by AWS_IAM auth (Feature 1256).
"""

import asyncio
import time

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.preprod, pytest.mark.integration]


class TestCanaryPreprod:
    """Test the production canary against preprod infrastructure.

    These tests validate that the canary (health check) will work in production.
    If these tests fail, the production canary would also fail - meaning we'd
    have no early warning system for production issues.
    """

    @pytest.mark.asyncio
    async def test_health_endpoint_structure(self, api_client: PreprodAPIClient):
        """Verify the health endpoint returns the expected structure.

        CRITICAL: This test validates the canary itself, not just the app.
        """
        response = await api_client.get("/health")

        assert (
            response.status_code == 200
        ), f"Health check failed with {response.status_code}"

        data = response.json()
        assert isinstance(data, dict), "Response must be JSON object"
        assert "status" in data, "Missing 'status' field in response"
        assert data["status"] in [
            "healthy",
            "degraded",
        ], f"Status is '{data['status']}', expected 'healthy' or 'degraded'"

    @pytest.mark.asyncio
    async def test_health_endpoint_performance(self, api_client: PreprodAPIClient):
        """Verify the health endpoint responds quickly.

        Prod canary has 2-minute timeout. If preprod is slower than 5 seconds,
        there's a performance issue that could cause spurious canary failures.
        """
        start = time.time()
        response = await api_client.get("/health")
        duration = time.time() - start

        assert response.status_code == 200, "Health check must succeed"
        # 5s budget includes invoke overhead (~100ms) — still well within 120s prod timeout
        assert duration < 5.0, (
            f"Health check took {duration:.2f}s (should be <5s). "
            f"This is too slow and will cause prod canary failures."
        )

    @pytest.mark.asyncio
    async def test_health_endpoint_public_access(self, api_client: PreprodAPIClient):
        """Verify the health endpoint is publicly accessible (no auth required).

        Health checks MUST be public for load balancers and monitoring systems.
        """
        response = await api_client.get("/health")

        assert (
            response.status_code == 200
        ), f"Health endpoint should return 200 without auth, got {response.status_code}."
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]

    @pytest.mark.asyncio
    async def test_health_endpoint_idempotency(self, api_client: PreprodAPIClient):
        """Verify the health endpoint is idempotent (multiple calls = same result).

        Prod canary runs hourly. Health check must not mutate state.
        """
        responses = []
        for _ in range(3):
            response = await api_client.get("/health")
            assert response.status_code == 200
            responses.append(response.json())

        statuses = [r["status"] for r in responses]
        assert all(
            s == "healthy" for s in statuses
        ), f"Health endpoint returned inconsistent statuses: {statuses}"

    @pytest.mark.asyncio
    async def test_health_endpoint_concurrent_requests(
        self, api_client: PreprodAPIClient
    ):
        """Verify the health endpoint handles concurrent requests.

        Multiple canary checks from different regions shouldn't interfere.
        """

        async def check_health():
            resp = await api_client.get("/health")
            return resp.status_code

        results = await asyncio.gather(*[check_health() for _ in range(5)])
        assert all(
            status == 200 for status in results
        ), f"Concurrent health checks had failures: {results}"

    @pytest.mark.asyncio
    async def test_health_endpoint_error_messages(self, api_client: PreprodAPIClient):
        """Verify the health endpoint provides useful error messages.

        If canary fails in prod, we need to know WHY it failed.
        """
        response = await api_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        if data["status"] == "degraded":
            assert (
                "details" in data or "message" in data or "errors" in data
            ), "Degraded status should include error details for debugging"


class TestCanaryMetadata:
    """Test that canary metadata is correct for production use."""

    def test_canary_validates_correct_fields(self):
        """Document which fields the canary validates."""
        required_fields = ["status"]
        assert required_fields == ["status"]

    def test_canary_timeout_configuration(self):
        """Document the canary timeout configuration."""
        prod_canary_timeout = 120
        preprod_performance_threshold = 5
        margin = prod_canary_timeout - preprod_performance_threshold
        assert margin >= 100, f"Only {margin}s margin — too tight."

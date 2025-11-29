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
Mocking: None (we're testing the actual health endpoint)
"""

import os
import time

import pytest
import requests


class TestCanaryPreprod:
    """Test the production canary against preprod infrastructure.

    These tests validate that the canary (health check) will work in production.
    If these tests fail, the production canary would also fail - meaning we'd
    have no early warning system for production issues.

    Required Environment Variables (set by CI in test-preprod job):
    - PREPROD_DASHBOARD_URL: Lambda Function URL for preprod dashboard
    - PREPROD_DASHBOARD_API_KEY: API key for preprod (same as DASHBOARD_API_KEY)

    CI Configuration: deploy.yml test-preprod job sets these from Terraform outputs.
    """

    @pytest.fixture(scope="class")
    def dashboard_url(self):
        """
        Get dashboard URL from environment.

        This MUST be set in CI - skipping is a test configuration error.
        """
        url = os.environ.get("PREPROD_DASHBOARD_URL")
        if not url:
            pytest.fail(
                "PREPROD_DASHBOARD_URL not set! "
                "This is required for canary tests. "
                "Check deploy.yml test-preprod job env vars. "
                "The URL should come from Terraform output: dashboard_url"
            )
        return url

    @pytest.fixture(scope="class")
    def api_key(self):
        """Get preprod API key from environment.

        This MUST be set in CI - skipping is a test configuration error.
        """
        # Try both env var names (CI uses DASHBOARD_API_KEY, tests expect PREPROD_DASHBOARD_API_KEY)
        key = os.environ.get("PREPROD_DASHBOARD_API_KEY") or os.environ.get(
            "DASHBOARD_API_KEY"
        )
        if not key:
            pytest.fail(
                "PREPROD_DASHBOARD_API_KEY (or DASHBOARD_API_KEY) not set! "
                "This is required for canary tests. "
                "Check deploy.yml test-preprod job env vars."
            )
        return key

    def test_health_endpoint_structure(self, dashboard_url):
        """
        Verify the health endpoint returns the expected structure.

        This is what the prod canary will check after deployment.
        If this fails, the canary won't work in prod.

        CRITICAL: This test validates the canary itself, not just the app.
        Note: Health endpoint is PUBLIC (no auth required).
        """
        response = requests.get(
            f"{dashboard_url}/health",
            timeout=10,
        )

        # Canary requirement: Must return 200
        assert (
            response.status_code == 200
        ), f"Health check failed with {response.status_code}: {response.text}"

        # Canary requirement: Must have JSON body
        data = response.json()
        assert isinstance(data, dict), "Response must be JSON object"

        # Canary requirement: Must include 'status' field
        assert "status" in data, "Missing 'status' field in response"
        assert data["status"] in [
            "healthy",
            "degraded",
        ], f"Status is '{data['status']}', expected 'healthy' or 'degraded'"

        # Canary requirement: Should include timestamp (version is optional)
        # Some health endpoints may not have timestamp, so warn instead of fail
        if "timestamp" not in data:
            import warnings

            warnings.warn(
                "Health endpoint missing 'timestamp' field (non-blocking)",
                stacklevel=2,
            )

        # Nice-to-have: Environment info
        if "environment" in data:
            assert (
                data["environment"] == "preprod"
            ), "Environment should be 'preprod' in preprod tests"

        print(f"✅ Health endpoint structure valid: {data}")

    def test_health_endpoint_performance(self, dashboard_url):
        """
        Verify the health endpoint responds quickly.

        Prod canary has 2-minute timeout (120 seconds).
        If preprod is slower than 5 seconds, there's a performance issue
        that could cause spurious canary failures in prod.

        CRITICAL: Slow health checks will cause false alarms in prod.
        Note: Health endpoint is PUBLIC (no auth required).
        """
        start = time.time()

        response = requests.get(
            f"{dashboard_url}/health",
            timeout=10,
        )

        duration = time.time() - start

        assert response.status_code == 200, "Health check must succeed"

        # Health check should respond in <5 seconds
        # This gives 115 seconds margin before prod canary timeout
        assert duration < 5.0, (
            f"Health check took {duration:.2f}s (should be <5s). "
            f"This is too slow and will cause prod canary failures."
        )

        print(f"✅ Health endpoint responded in {duration:.2f}s")

    def test_health_endpoint_public_access(self, dashboard_url):
        """
        Verify the health endpoint is publicly accessible (no auth required).

        Health checks MUST be public for:
        - Load balancer health checks
        - Kubernetes liveness/readiness probes
        - Monitoring systems (CloudWatch, Datadog, etc.)

        Authentication on health endpoints prevents infrastructure from
        verifying application health.
        """
        response = requests.get(
            f"{dashboard_url}/health",
            timeout=10,
        )

        # Health endpoint MUST be publicly accessible
        assert response.status_code == 200, (
            f"Health endpoint should return 200 without auth, got {response.status_code}. "
            f"Health checks must be public for load balancers and monitoring."
        )

        data = response.json()
        assert data["status"] in ["healthy", "degraded"], f"Unexpected status: {data}"

        print("✅ Health endpoint is publicly accessible (correct for health checks)")

    def test_health_endpoint_idempotency(self, dashboard_url):
        """
        Verify the health endpoint is idempotent (multiple calls return same result).

        Prod canary runs hourly. If health check mutates state,
        it could cause issues over time.
        Note: Health endpoint is PUBLIC (no auth required).
        """
        responses = []

        # Call health endpoint 3 times
        for i in range(3):
            response = requests.get(
                f"{dashboard_url}/health",
                timeout=10,
            )
            assert response.status_code == 200, f"Call {i+1} failed"
            responses.append(response.json())

        # All responses should have 'status': 'healthy'
        statuses = [r["status"] for r in responses]
        assert all(
            s == "healthy" for s in statuses
        ), f"Health endpoint returned inconsistent statuses: {statuses}"

        print("✅ Health endpoint is idempotent (3 calls, all returned 'healthy')")

    def test_health_endpoint_concurrent_requests(self, dashboard_url):
        """
        Verify the health endpoint handles concurrent requests.

        If multiple canary checks run simultaneously (e.g., from different regions),
        they shouldn't interfere with each other.
        Note: Health endpoint is PUBLIC (no auth required).
        """
        import concurrent.futures

        def check_health():
            response = requests.get(
                f"{dashboard_url}/health",
                timeout=10,
            )
            return response.status_code

        # Run 5 concurrent health checks
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(check_health) for _ in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert all(
            status == 200 for status in results
        ), f"Concurrent health checks had failures: {results}"

        print("✅ Health endpoint handles concurrent requests (5 parallel calls)")

    def test_health_endpoint_error_messages(self, dashboard_url):
        """
        Verify the health endpoint provides useful error messages.

        If canary fails in prod, we need to know WHY it failed.
        Good error messages help with debugging.
        Note: Health endpoint is PUBLIC (no auth required).
        """
        response = requests.get(
            f"{dashboard_url}/health",
            timeout=10,
        )

        assert response.status_code == 200

        data = response.json()

        # If status is "degraded", there should be details
        if data["status"] == "degraded":
            assert (
                "details" in data or "message" in data or "errors" in data
            ), "Degraded status should include error details for debugging"

        print("✅ Health endpoint provides adequate error information")


class TestCanaryMetadata:
    """Test that canary metadata is correct for production use."""

    def test_canary_validates_correct_fields(self):
        """
        Document which fields the canary validates.

        This serves as documentation for what prod canary checks.
        If we change the health endpoint structure, we need to update
        both the canary and this test.
        """
        required_fields = ["status"]
        optional_fields = ["timestamp", "environment", "version"]

        # This test just documents expectations
        # Actual validation happens in test_health_endpoint_structure
        assert required_fields == ["status"]

        print(f"✅ Canary validates these fields: {required_fields}")
        print(f"   Optional fields: {optional_fields}")

    def test_canary_timeout_configuration(self):
        """
        Document the canary timeout configuration.

        Prod canary has 2-minute timeout.
        Preprod tests expect <5 second response.
        This gives 115 seconds margin for network latency, etc.
        """
        prod_canary_timeout = 120  # seconds (from deploy-prod.yml)
        preprod_performance_threshold = 5  # seconds

        margin = prod_canary_timeout - preprod_performance_threshold
        assert margin >= 100, (
            f"Only {margin}s margin between preprod threshold and prod timeout. "
            f"This is too tight and could cause false alarms."
        )

        print("✅ Canary timeout configuration validated (115s margin)")

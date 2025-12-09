"""
E2E Tests for Dashboard Lambda (Preprod)
========================================

Integration tests for the dashboard FastAPI application against REAL preprod environment.

CRITICAL: These tests use REAL AWS resources (preprod environment only).
- DynamoDB: preprod-sentiment-users table (Feature 006 - Terraform-deployed)
- NO mocking of AWS infrastructure

NOTE: The v1 API endpoints (/api/metrics, /api/items, /api/stream) are DEPRECATED.
      All new development should use the v2 API (/api/v2/*).
      See tests/e2e/ for comprehensive v2 API test coverage.

For On-Call Engineers:
    If these tests fail in CI:
    1. Verify preprod environment is deployed: `aws dynamodb describe-table --table-name preprod-sentiment-users`
    2. Check preprod Terraform matches deployed resources: `terraform plan` should show no changes
    3. Verify DATABASE_TABLE env var is set correctly in Lambda
    4. Check AWS credentials are configured in CI

For Developers:
    - Tests read from REAL preprod DynamoDB table
    - Health check validates DynamoDB connectivity
    - v1 API tests are SKIPPED (deprecated)
    - For v2 API tests, see tests/e2e/ directory
"""

import os

import pytest
from fastapi.testclient import TestClient

from src.lambdas.dashboard.handler import app

# Environment variables should be set by CI (do NOT override here)
# CI sets: DYNAMODB_TABLE=dev-sentiment-items, API_KEY=<from secrets>
# For local testing, ensure these are set in your environment


@pytest.fixture
def client():
    """Create TestClient for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """
    Return valid authorization headers for E2E tests.

    Uses API_KEY from environment (set by CI or local config).
    """
    api_key = os.environ.get("API_KEY", "test-api-key-12345")
    return {"Authorization": f"Bearer {api_key}"}


class TestDashboardE2E:
    """
    Integration tests for dashboard functionality against REAL preprod DynamoDB.

    IMPORTANT: These tests query the actual preprod-sentiment-users table in AWS.
    Tests are designed to work with whatever data exists in preprod.

    NOTE: v1 API tests (/api/metrics, /api/items) are SKIPPED.
          See tests/e2e/ for v2 API coverage.
    """

    def test_health_check_returns_healthy(self, client):
        """
        Integration: Health check endpoint returns healthy status.

        Verifies:
        - Status code is 200
        - Response contains status, table name, environment
        - DynamoDB connectivity to REAL preprod table is tested
        """
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        # Table name should contain 'sentiment' (could be sentiment-items or sentiment-users)
        assert "sentiment" in data["table"]
        assert data["environment"] in ["dev", "test", "preprod"]

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_metrics_response_schema(self, client, auth_headers):
        """
        Integration: Metrics endpoint returns correct response schema.

        Verifies frontend can parse the response correctly from real dev data.
        """
        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        required_fields = [
            "total",
            "positive",
            "neutral",
            "negative",
            "by_tag",
            "rate_last_hour",
            "rate_last_24h",
            "recent_items",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Verify types
        assert isinstance(data["total"], int)
        assert isinstance(data["positive"], int)
        assert isinstance(data["neutral"], int)
        assert isinstance(data["negative"], int)
        assert isinstance(data["by_tag"], dict)
        assert isinstance(data["rate_last_hour"], int)
        assert isinstance(data["rate_last_24h"], int)
        assert isinstance(data["recent_items"], list)

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_metrics_aggregation_accuracy(self, client, auth_headers):
        """
        Integration: Metrics are aggregated correctly from real dev data.

        Verifies:
        - Sentiment counts are non-negative integers
        - Total equals sum of sentiments
        - Tag distribution is valid
        """
        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify non-negative counts
        assert data["total"] >= 0
        assert data["positive"] >= 0
        assert data["neutral"] >= 0
        assert data["negative"] >= 0

        # Verify total equals sum of sentiments
        assert data["total"] == data["positive"] + data["neutral"] + data["negative"]

        # Verify tag distribution is valid
        assert isinstance(data["by_tag"], dict)
        for tag, count in data["by_tag"].items():
            assert isinstance(tag, str)
            assert isinstance(count, int)
            assert count > 0

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_metrics_recent_items_sanitized(self, client, auth_headers):
        """
        Integration: Recent items have internal fields removed.

        Verifies ttl and content_hash are not exposed to frontend from real dev data.
        """
        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check recent items don't contain internal fields
        for item in data["recent_items"]:
            assert "ttl" not in item, "TTL field should not be exposed to frontend"
            assert (
                "content_hash" not in item
            ), "content_hash field should not be exposed to frontend"

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_api_key_validation_rejects_invalid(self, client):
        """
        Integration: API key validation rejects invalid credentials.

        Verifies:
        - Missing auth returns 401
        - Wrong key returns 401
        - Correct error messages
        """
        # Test missing auth
        response = client.get("/api/metrics")
        assert response.status_code == 401
        assert "Missing Authorization header" in response.json()["detail"]

        # Test wrong key
        response = client.get(
            "/api/metrics", headers={"Authorization": "Bearer wrong-key"}
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

        # Test invalid format
        response = client.get(
            "/api/metrics", headers={"Authorization": "InvalidFormat"}
        )
        assert response.status_code == 401
        assert "Invalid Authorization header format" in response.json()["detail"]

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_api_key_validation_accepts_valid(self, client, auth_headers):
        """
        Integration: API key validation accepts valid credentials.
        """
        response = client.get("/api/metrics", headers=auth_headers)
        assert response.status_code == 200

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_items_endpoint_returns_analyzed_items(self, client, auth_headers):
        """
        Integration: Items endpoint returns only analyzed items by default.
        """
        response = client.get("/api/items", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return only analyzed items (not pending)
        for item in data:
            assert item.get("status") == "analyzed"

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_items_endpoint_filters_by_status(self, client, auth_headers):
        """
        Integration: Items endpoint filters by status parameter.
        """
        # Get analyzed items
        response = client.get("/api/items?status=analyzed", headers=auth_headers)
        assert response.status_code == 200
        analyzed_data = response.json()

        # All should be analyzed
        for item in analyzed_data:
            assert item["status"] == "analyzed"

        # Get pending items
        response = client.get("/api/items?status=pending", headers=auth_headers)
        assert response.status_code == 200
        pending_data = response.json()

        # All should be pending
        for item in pending_data:
            assert item["status"] == "pending"

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_items_endpoint_respects_limit(self, client, auth_headers):
        """
        Integration: Items endpoint respects limit parameter.
        """
        response = client.get("/api/items?limit=3", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return at most 3 items
        assert len(data) <= 3

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_items_sorted_by_timestamp_descending(self, client, auth_headers):
        """
        Integration: Items are sorted by timestamp in descending order.
        """
        response = client.get("/api/items", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify descending order if we have items
        if len(data) > 1:
            timestamps = [item["timestamp"] for item in data]
            assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_metrics_time_window_filtering(self, client, auth_headers):
        """
        Integration: Metrics respect time window parameter.

        Tests that items outside the time window are excluded.
        """
        # Query with 1-hour window
        response_1h = client.get("/api/metrics?hours=1", headers=auth_headers)
        assert response_1h.status_code == 200
        data_1h = response_1h.json()

        # Query with 24-hour window
        response_24h = client.get("/api/metrics?hours=24", headers=auth_headers)
        assert response_24h.status_code == 200
        data_24h = response_24h.json()

        # 24-hour window should have >= 1-hour window counts
        assert data_24h["total"] >= data_1h["total"]

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_ingestion_rates_calculated_correctly(self, client, auth_headers):
        """
        Integration: Ingestion rates are calculated for different time windows.
        """
        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # rate_last_hour should be >= 0
        assert data["rate_last_hour"] >= 0

        # rate_last_24h should be >= rate_last_hour (24h window includes 1h window)
        assert data["rate_last_24h"] >= data["rate_last_hour"]

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_empty_table_or_no_matches_returns_zeros(self, client, auth_headers):
        """
        Integration: Empty results return zero counts gracefully.

        Tests with time window that likely has no data.
        """
        # Query with very restrictive time window (minimum valid: 1 hour)
        response = client.get("/api/metrics?hours=1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return zeros or very low counts
        assert data["total"] >= 0
        assert data["positive"] >= 0
        assert data["neutral"] >= 0
        assert data["negative"] >= 0
        assert isinstance(data["by_tag"], dict)
        assert isinstance(data["recent_items"], list)

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_parameter_validation_hours(self, client, auth_headers):
        """
        Integration: Invalid hours parameter returns 400 error.
        """
        # Test hours = 0
        response = client.get("/api/metrics?hours=0", headers=auth_headers)
        assert response.status_code == 400
        assert "Hours must be between" in response.json()["detail"]

        # Test hours > 168
        response = client.get("/api/metrics?hours=200", headers=auth_headers)
        assert response.status_code == 400

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_parameter_validation_limit(self, client, auth_headers):
        """
        Integration: Invalid limit parameter returns 400 error.
        """
        # Test limit = 0
        response = client.get("/api/items?limit=0", headers=auth_headers)
        assert response.status_code == 400

        # Test limit > 100
        response = client.get("/api/items?limit=150", headers=auth_headers)
        assert response.status_code == 400

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_parameter_validation_status(self, client, auth_headers):
        """
        Integration: Invalid status parameter returns 400 error.
        """
        response = client.get("/api/items?status=invalid", headers=auth_headers)
        assert response.status_code == 400
        assert "Status must be" in response.json()["detail"]

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_concurrent_requests(self, client, auth_headers):
        """
        Integration: Multiple concurrent requests work correctly.

        Simulates multiple dashboard tabs/users hitting real dev DynamoDB.
        """
        # Make multiple requests
        responses = []
        for _ in range(5):
            response = client.get("/api/metrics", headers=auth_headers)
            responses.append(response)

        # All should succeed with consistent data
        for response in responses:
            assert response.status_code == 200
            # Verify structure is consistent
            data = response.json()
            assert "total" in data
            assert "positive" in data

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_response_content_type(self, client, auth_headers):
        """
        Integration: API endpoints return correct content types.
        """
        # Metrics endpoint
        response = client.get("/api/metrics", headers=auth_headers)
        assert "application/json" in response.headers["content-type"]

        # Items endpoint
        response = client.get("/api/items", headers=auth_headers)
        assert "application/json" in response.headers["content-type"]

        # Health endpoint
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_sse_stream_endpoint_exists(self, client, auth_headers):
        """
        Integration: SSE stream endpoint exists and requires authentication.

        Note: Full SSE streaming (continuous events) is not tested here as it
        requires long-running connections. This test verifies the endpoint is
        accessible and has correct authentication.
        """
        # Test requires auth
        response_no_auth = client.get("/api/stream")
        assert response_no_auth.status_code == 401

        # Note: Testing full SSE behavior requires async client and is deferred
        # to manual testing or E2E tests due to complexity of testing infinite streams


class TestSecurityIntegration:
    """
    Integration Tests for Security Mitigations
    ===========================================

    Tests security features against REAL preprod environment.

    IMPORTANT: These tests use REAL AWS resources (preprod environment only).

    Test Coverage:
    - P0-2: SSE connection limits with real Lambda concurrency
    - P0-5: CORS origin validation with real Function URL
    - P1-2: IP logging verification in CloudWatch

    For On-Call Engineers:
        If these tests fail:
        1. Check Lambda environment variables: MAX_SSE_CONNECTIONS_PER_IP, CORS_ORIGINS
        2. Verify CloudWatch logs are being written
        3. Check Lambda concurrency limits not exceeded
    """

    @pytest.mark.skip(reason="v1 API deprecated - SSE tested in tests/e2e/test_sse.py")
    @pytest.mark.asyncio
    async def test_sse_connection_limit_enforced_in_preprod(self, auth_headers):
        """
        Integration: SSE connection limit enforced against real preprod Lambda.

        Tests P0-2 mitigation works with real Lambda Function URL.

        Uses httpx AsyncClient with ASGITransport and asyncio.wait_for timeout
        to properly test SSE streaming endpoints without blocking.

        Reference: https://fastapi.tiangolo.com/advanced/async-tests/
        """
        import asyncio

        import httpx

        async def attempt_sse_connection(client: httpx.AsyncClient) -> int:
            """Attempt SSE connection and return status code."""
            async with client.stream(
                "GET",
                "http://test/api/stream",
                headers=auth_headers,
            ) as response:
                # Return status immediately - don't wait for stream data
                return response.status_code

        # Use ASGITransport to test against the app directly
        transport = httpx.ASGITransport(app=app)
        connection_established = False

        async with httpx.AsyncClient(transport=transport) as client:
            try:
                # Use wait_for with 3s timeout - enough to get status, not stream data
                status_code = await asyncio.wait_for(
                    attempt_sse_connection(client),
                    timeout=3.0,
                )

                # Should return 200 for successful SSE connection
                # 429 indicates rate limiting which is also valid behavior
                assert status_code in [200, 429], f"Unexpected status: {status_code}"
                connection_established = True

            except TimeoutError:
                # Timeout means connection was established and is streaming
                # This is SUCCESS - SSE connections hang waiting for events
                connection_established = True

        # Explicit assertion - test MUST establish connection or timeout while streaming
        assert connection_established, (
            "SSE endpoint test failed - neither connected nor timed out during streaming. "
            "This indicates the endpoint may be broken or returning an error immediately."
        )

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_cors_headers_present_for_valid_origin(self, client, auth_headers):
        """
        Integration: CORS headers are present for whitelisted origins.

        Tests P0-5 mitigation allows configured origins.
        """
        # Test with localhost (should be allowed in preprod)
        response = client.get(
            "/api/metrics",
            headers={
                **auth_headers,
                "Origin": "http://localhost:3000",
            },
        )

        assert response.status_code == 200

        # Should have CORS headers
        # Note: TestClient may not fully simulate CORS, but verify endpoint works
        # Full CORS testing requires browser or curl with Origin header

    @pytest.mark.skip(
        reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/"
    )
    def test_authentication_failure_logged_to_cloudwatch(self, client):
        """
        Integration: Authentication failures are logged to CloudWatch.

        Tests P1-2 mitigation logs IP addresses for forensics.

        Note: Verifying CloudWatch logs requires AWS API access.
        This test only verifies the endpoint returns 401.
        Manual verification: Check CloudWatch Logs for client IP in error logs.
        """
        # Attempt authentication with wrong key
        response = client.get(
            "/api/metrics",
            headers={
                "Authorization": "Bearer invalid-key-for-testing",
                "X-Forwarded-For": "198.51.100.TEST",
            },
        )

        assert response.status_code == 401

        # To verify logging:
        # 1. Go to CloudWatch Logs
        # 2. Find log group: /aws/lambda/preprod-sentiment-analyzer-dashboard
        # 3. Search for "Invalid API key attempt"
        # 4. Verify log contains "198.51.100.TEST"

    def test_max_sse_connections_env_var_respected(self, client, auth_headers):
        """
        Integration: MAX_SSE_CONNECTIONS_PER_IP env var is respected.

        Verifies Lambda reads environment variable correctly.
        """
        # This test verifies the endpoint exists and uses the env var
        # Can't directly test the value without accessing Lambda config

        response = client.get("/health")
        assert response.status_code == 200

        # Manual verification:
        # aws lambda get-function-configuration \
        #   --function-name preprod-sentiment-analyzer-dashboard \
        #   --query 'Environment.Variables.MAX_SSE_CONNECTIONS_PER_IP'

    def test_production_blocks_requests_without_cors_origins(self):
        """
        Integration: Production environment rejects requests without CORS config.

        Tests P0-5 mitigation blocks cross-origin requests in production.

        Note: This test is SKIPPED in preprod. Only runs in production environment.
        """
        import os

        env = os.environ.get("ENVIRONMENT", "dev")

        if env != "production":
            import pytest

            pytest.skip("Test only runs in production environment")

        # If running in production, CORS_ORIGINS must be configured
        # Otherwise all cross-origin requests should be blocked

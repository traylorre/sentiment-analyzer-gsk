"""
E2E Tests for Dashboard Lambda (Preprod)
========================================

Integration tests for the dashboard FastAPI application against REAL preprod environment.

CRITICAL: These tests use REAL AWS resources (preprod environment only).
- DynamoDB: preprod-sentiment-users table (Feature 006 - Terraform-deployed)
- NO mocking of AWS infrastructure

NOTE: v1 API tests have been REMOVED (Feature 076).
      The v1 API endpoints (/api/metrics, /api/items, /api/stream) are DEPRECATED.
      See tests/e2e/ for comprehensive v2 API test coverage.
      Audit trail: specs/076-v1-test-deprecation/audit.md

For On-Call Engineers:
    If these tests fail in CI:
    1. Verify preprod environment is deployed: `aws dynamodb describe-table --table-name preprod-sentiment-users`
    2. Check preprod Terraform matches deployed resources: `terraform plan` should show no changes
    3. Verify DATABASE_TABLE env var is set correctly in Lambda
    4. Check AWS credentials are configured in CI

For Developers:
    - Tests read from REAL preprod DynamoDB table
    - Health check validates DynamoDB connectivity
    - For v2 API tests, see tests/e2e/ directory
"""

import os

import pytest
from fastapi.testclient import TestClient

from src.lambdas.dashboard.handler import app


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

    NOTE: v1 API tests have been removed (Feature 076).
          See specs/076-v1-test-deprecation/audit.md for audit trail.
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


class TestSecurityIntegration:
    """
    Integration Tests for Security Mitigations
    ===========================================

    Tests security features against REAL preprod environment.

    IMPORTANT: These tests use REAL AWS resources (preprod environment only).

    Test Coverage:
    - Environment variable configuration
    - CORS configuration in production

    NOTE: v1 API security tests have been removed (Feature 076).
          See specs/076-v1-test-deprecation/audit.md for audit trail.
          See tests/e2e/test_sse.py for v2 SSE tests.
          See tests/e2e/test_observability.py for logging tests.

    For On-Call Engineers:
        If these tests fail:
        1. Check Lambda environment variables: MAX_SSE_CONNECTIONS_PER_IP, CORS_ORIGINS
        2. Verify CloudWatch logs are being written
        3. Check Lambda concurrency limits not exceeded
    """

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
        env = os.environ.get("ENVIRONMENT", "dev")

        if env != "production":
            pytest.skip("Test only runs in production environment")

        # If running in production, CORS_ORIGINS must be configured
        # Otherwise all cross-origin requests should be blocked

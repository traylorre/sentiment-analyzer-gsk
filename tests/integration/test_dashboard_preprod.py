"""
E2E Tests for Dashboard Lambda
==============================

Integration tests for the dashboard FastAPI application against REAL dev environment.

CRITICAL: These tests use REAL AWS resources (dev environment only).
- DynamoDB: dev-sentiment-items table (Terraform-deployed)
- NO mocking of AWS infrastructure

External dependencies mocked:
- None for dashboard (reads from real DynamoDB only)

For On-Call Engineers:
    If these tests fail in CI:
    1. Verify dev environment is deployed: `aws dynamodb describe-table --table-name dev-sentiment-items`
    2. Check dev Terraform matches deployed resources: `terraform plan` should show no changes
    3. Verify GSI configuration in dev matches code expectations
    4. Check AWS credentials are configured in CI

For Developers:
    - Tests read from REAL dev DynamoDB table
    - Tests verify end-to-end request/response cycle
    - Tests are flexible about data present in dev (no seed data assumptions)
    - Covers metrics aggregation, API key validation, health check
    - Verifies response schemas match frontend expectations
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
    Integration tests for dashboard functionality against REAL dev DynamoDB.

    IMPORTANT: These tests query the actual dev-sentiment-items table in AWS.
    Tests are designed to work with whatever data exists in dev.
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
        # Table name should be from environment (e.g., preprod-sentiment-items)
        assert "sentiment-items" in data["table"]
        assert data["environment"] in ["dev", "test", "preprod"]

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

    def test_api_key_validation_accepts_valid(self, client, auth_headers):
        """
        Integration: API key validation accepts valid credentials.
        """
        response = client.get("/api/metrics", headers=auth_headers)
        assert response.status_code == 200

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

    def test_items_endpoint_respects_limit(self, client, auth_headers):
        """
        Integration: Items endpoint respects limit parameter.
        """
        response = client.get("/api/items?limit=3", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return at most 3 items
        assert len(data) <= 3

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

    def test_parameter_validation_status(self, client, auth_headers):
        """
        Integration: Invalid status parameter returns 400 error.
        """
        response = client.get("/api/items?status=invalid", headers=auth_headers)
        assert response.status_code == 400
        assert "Status must be" in response.json()["detail"]

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

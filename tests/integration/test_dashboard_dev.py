"""
Dashboard E2E Tests - Dev Environment
======================================

End-to-end tests for dev environment with ALL AWS resources mocked.

IMPORTANT: These tests use moto to mock ALL AWS infrastructure.
- Purpose: Fast feedback during development
- Run on: Every PR, every merge, Dependabot PRs
- Cost: $0 (no real AWS resources)

For actual integration testing against real AWS, see test_dashboard_preprod.py
which runs in preprod environment on manual trigger.

For Developers:
    - All AWS resources mocked with moto
    - Fast execution (no real AWS API calls)
    - Tests verify application logic and data flow
    - Safe to run locally and in CI
"""

import os

import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from src.lambdas.dashboard.handler import app


@pytest.fixture
def env_vars():
    """Set test environment variables."""
    os.environ["API_KEY"] = "test-api-key-12345"
    os.environ["DYNAMODB_TABLE"] = "test-sentiment-items"
    os.environ["ENVIRONMENT"] = "test"
    yield
    # Cleanup
    for key in ["API_KEY", "DYNAMODB_TABLE", "ENVIRONMENT"]:
        os.environ.pop(key, None)


@pytest.fixture
def client():
    """Create TestClient for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Return valid authorization headers."""
    return {"Authorization": "Bearer test-api-key-12345"}


class TestDashboardDevE2E:
    """Dev environment E2E tests with mocked AWS."""

    @mock_aws
    def test_health_check(self, env_vars, client):
        """E2E: Health check returns healthy status."""
        # Create mock DynamoDB table
        import boto3

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-sentiment-items",
            KeySchema=[
                {"AttributeName": "source_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "source_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["table"] == "test-sentiment-items"

    @mock_aws
    def test_metrics_endpoint_schema(self, env_vars, client, auth_headers):
        """E2E: Metrics endpoint returns correct schema."""
        # Create mock table
        import boto3

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-sentiment-items",
            KeySchema=[
                {"AttributeName": "source_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "source_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
                {"AttributeName": "sentiment", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "by_sentiment",
                    "KeySchema": [
                        {"AttributeName": "sentiment", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "by_status",
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify schema
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
            assert field in data

    @mock_aws
    def test_api_key_validation(self, env_vars, client):
        """E2E: API key validation rejects invalid credentials."""
        import boto3

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-sentiment-items",
            KeySchema=[
                {"AttributeName": "source_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "source_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Missing auth
        response = client.get("/api/metrics")
        assert response.status_code == 401

        # Wrong key
        response = client.get(
            "/api/metrics", headers={"Authorization": "Bearer wrong-key"}
        )
        assert response.status_code == 401

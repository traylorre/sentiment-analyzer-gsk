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

import json
import os

import pytest
from moto import mock_aws

from src.lambdas.dashboard.handler import lambda_handler
from tests.conftest import make_event


@pytest.fixture
def env_vars():
    """Set test environment variables.

    Feature 1039: API_KEY removed, now uses session-based auth.
    """
    os.environ["DATABASE_TABLE"] = "test-sentiment-items"
    os.environ["ENVIRONMENT"] = "test"
    yield
    # Cleanup
    for key in ["DATABASE_TABLE", "ENVIRONMENT"]:
        os.environ.pop(key, None)


@pytest.fixture
def auth_headers():
    """Return valid authorization headers.

    Feature 1146: Bearer-only authentication (X-User-ID fallback removed).
    Anonymous sessions use Bearer token with UUID.
    """
    return {"Authorization": "Bearer 550e8400-e29b-41d4-a716-446655440000"}


class TestDashboardDevE2E:
    """Dev environment E2E tests with mocked AWS."""

    @mock_aws
    def test_health_check(self, env_vars, mock_lambda_context):
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

        response = lambda_handler(
            make_event(method="GET", path="/health"),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["status"] == "healthy"
        assert data["table"] == "test-sentiment-items"

    @mock_aws
    def test_sentiment_endpoint_schema(
        self, env_vars, mock_lambda_context, auth_headers
    ):
        """E2E: Sentiment endpoint returns correct schema."""
        # Create mock table with by_tag GSI required for v2 API
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
                {"AttributeName": "tag", "AttributeType": "S"},
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
                {
                    "IndexName": "by_tag",
                    "KeySchema": [
                        {"AttributeName": "tag", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/sentiment",
                query_params={"tags": "test"},
                headers=auth_headers,
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        # Verify schema
        required_fields = [
            "tags",
            "overall",
            "total_count",
        ]
        for field in required_fields:
            assert field in data

    @mock_aws
    def test_session_auth_validation(self, env_vars, mock_lambda_context):
        """E2E: Session auth validation rejects missing/invalid credentials.

        Feature 1039: API key auth removed, now uses session-based auth.
        """
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
        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/sentiment",
                query_params={"tags": "test"},
            ),
            mock_lambda_context,
        )
        assert response["statusCode"] == 401

        # Invalid token (not a valid JWT/UUID)
        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/sentiment",
                query_params={"tags": "test"},
                headers={"Authorization": "Bearer invalid-token"},
            ),
            mock_lambda_context,
        )
        assert response["statusCode"] == 401

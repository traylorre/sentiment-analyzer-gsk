"""
Analysis E2E Tests - Dev Environment
=====================================

End-to-end tests for dev environment with ALL AWS resources mocked.

IMPORTANT: These tests use moto to mock ALL AWS infrastructure.
- Purpose: Fast feedback during development
- Run on: Every PR, every merge, Dependabot PRs
- Cost: $0 (no real AWS resources)

Mocking Strategy:
- AWS resources (DynamoDB, SNS): moto
- ML inference (transformers): unittest.mock

For actual integration testing against real AWS, see test_analysis_preprod.py.
"""

import json
import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.lambdas.analysis.handler import lambda_handler


@pytest.fixture
def env_vars():
    """Set test environment variables."""
    os.environ["DYNAMODB_TABLE"] = "test-sentiment-items"
    os.environ["MODEL_PATH"] = "/opt/model"
    os.environ["ENVIRONMENT"] = "test"
    yield
    for key in ["DYNAMODB_TABLE", "MODEL_PATH", "ENVIRONMENT"]:
        os.environ.pop(key, None)


@pytest.fixture
def mock_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.aws_request_id = "test-request-123"
    context.function_name = "test-sentiment-analysis"
    context.memory_limit_in_mb = 1024
    return context


def create_sns_event(source_id: str, timestamp: str, text: str) -> dict:
    """Create SNS event for testing."""
    message = {
        "source_id": source_id,
        "source_type": "newsapi",
        "text_for_analysis": text,
        "model_version": "v1.0.0",
        "matched_tags": ["AI"],
        "timestamp": timestamp,
    }

    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "Sns": {
                    "Message": json.dumps(message),
                    "Timestamp": datetime.now(UTC).isoformat(),
                },
            }
        ]
    }


class TestAnalysisDevE2E:
    """Dev environment E2E tests with mocked AWS."""

    @mock_aws
    def test_full_analysis_flow(self, env_vars, mock_context):
        """E2E: Complete analysis flow with mocked AWS."""
        # Create mock DynamoDB table
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

        table = dynamodb.Table("test-sentiment-items")

        # Insert pending item
        source_id = "newsapi#test123"
        timestamp = "2025-11-20T10:00:00.000Z"
        table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "status": "pending",
                "text_for_analysis": "Great news about AI!",
                "source_type": "newsapi",
                "matched_tags": ["AI"],
            }
        )

        # Create SNS event
        event = create_sns_event(
            source_id=source_id,
            timestamp=timestamp,
            text="Great news about AI!",
        )

        # Execute with mocked ML
        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch("src.lambdas.analysis.handler.get_model_load_time_ms") as mock_load,
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            mock_analyze.return_value = ("positive", 0.95)
            mock_load.return_value = 0

            result = lambda_handler(event, mock_context)

        # Verify success
        assert result["statusCode"] == 200
        assert result["body"]["sentiment"] == "positive"
        assert result["body"]["updated"] is True

        # Verify DynamoDB update
        response = table.get_item(Key={"source_id": source_id, "timestamp": timestamp})
        assert response["Item"]["status"] == "analyzed"
        assert response["Item"]["sentiment"] == "positive"

    @mock_aws
    def test_idempotency(self, env_vars, mock_context):
        """E2E: Duplicate messages don't re-analyze."""
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

        table = dynamodb.Table("test-sentiment-items")

        source_id = "newsapi#idempotent"
        timestamp = "2025-11-20T11:00:00.000Z"
        table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "status": "pending",
                "text_for_analysis": "Test",
                "source_type": "newsapi",
                "matched_tags": ["test"],
            }
        )

        event = create_sns_event(source_id=source_id, timestamp=timestamp, text="Test")

        # First invocation
        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch("src.lambdas.analysis.handler.get_model_load_time_ms") as mock_load,
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            mock_analyze.return_value = ("positive", 0.85)
            mock_load.return_value = 0
            result1 = lambda_handler(event, mock_context)

        assert result1["body"]["updated"] is True

        # Second invocation (duplicate)
        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch("src.lambdas.analysis.handler.get_model_load_time_ms") as mock_load,
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            mock_analyze.return_value = ("negative", 0.90)
            mock_load.return_value = 0
            result2 = lambda_handler(event, mock_context)

        # Should not update
        assert result2["body"]["updated"] is False

        # Original result preserved
        response = table.get_item(Key={"source_id": source_id, "timestamp": timestamp})
        assert response["Item"]["sentiment"] == "positive"

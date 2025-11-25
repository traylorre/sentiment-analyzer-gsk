"""
Unit Tests for Metrics Lambda Handler
=====================================

Tests the metrics handler with mocked AWS services.

For On-Call Engineers:
    These tests verify:
    - Stuck items detection via by_status GSI query
    - CloudWatch metric emission (StuckItems)
    - Error handling

For Developers:
    - Uses moto to mock DynamoDB and CloudWatch
    - Tests both success and error scenarios
    - Verifies metrics are emitted correctly
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.lambdas.metrics.handler import (
    METRIC_NAME,
    METRIC_NAMESPACE,
    STUCK_THRESHOLD_MINUTES,
    emit_stuck_items_metric,
    get_stuck_items_count,
    lambda_handler,
)


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_REGION"] = "us-east-1"


@pytest.fixture
def env_vars(aws_credentials):
    """Set up environment variables for testing."""
    os.environ["DYNAMODB_TABLE"] = "test-sentiment-items"
    os.environ["ENVIRONMENT"] = "test"
    yield
    # Cleanup
    for key in ["DYNAMODB_TABLE", "ENVIRONMENT"]:
        os.environ.pop(key, None)


@pytest.fixture
def dynamodb_table(aws_credentials):
    """Create a mock DynamoDB table with by_status GSI."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        table = dynamodb.create_table(
            TableName="test-sentiment-items",
            KeySchema=[
                {"AttributeName": "source_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "source_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "by_status",
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "KEYS_ONLY"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                }
            ],
            ProvisionedThroughput={
                "ReadCapacityUnits": 5,
                "WriteCapacityUnits": 5,
            },
        )

        # Wait for table to be active
        table.meta.client.get_waiter("table_exists").wait(
            TableName="test-sentiment-items"
        )

        yield table


@pytest.fixture
def mock_context():
    """Create a mock Lambda context."""
    context = MagicMock()
    context.aws_request_id = "test-request-id"
    context.function_name = "test-sentiment-metrics"
    return context


class TestGetStuckItemsCount:
    """Tests for get_stuck_items_count function."""

    def test_no_stuck_items(self, dynamodb_table, env_vars):
        """Test when there are no stuck items."""
        # Add a recent pending item (not stuck)
        now = datetime.now(UTC)
        dynamodb_table.put_item(
            Item={
                "source_id": "test-1",
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "pending",
            }
        )

        count = get_stuck_items_count("test-sentiment-items")
        assert count == 0

    def test_with_stuck_items(self, dynamodb_table, env_vars):
        """Test detection of stuck items older than threshold."""
        now = datetime.now(UTC)
        old_time = now - timedelta(minutes=10)  # 10 minutes ago (stuck)

        # Add stuck item
        dynamodb_table.put_item(
            Item={
                "source_id": "stuck-1",
                "timestamp": old_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "pending",
            }
        )

        # Add recent item (not stuck)
        dynamodb_table.put_item(
            Item={
                "source_id": "recent-1",
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "pending",
            }
        )

        count = get_stuck_items_count("test-sentiment-items")
        assert count == 1

    def test_completed_items_not_counted(self, dynamodb_table, env_vars):
        """Test that completed items are not counted as stuck."""
        old_time = datetime.now(UTC) - timedelta(minutes=10)

        # Add old but completed item
        dynamodb_table.put_item(
            Item={
                "source_id": "completed-1",
                "timestamp": old_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "completed",
            }
        )

        count = get_stuck_items_count("test-sentiment-items")
        assert count == 0

    def test_multiple_stuck_items(self, dynamodb_table, env_vars):
        """Test counting multiple stuck items."""
        old_time = datetime.now(UTC) - timedelta(minutes=10)

        for i in range(5):
            dynamodb_table.put_item(
                Item={
                    "source_id": f"stuck-{i}",
                    "timestamp": (old_time - timedelta(minutes=i)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "status": "pending",
                }
            )

        count = get_stuck_items_count("test-sentiment-items")
        assert count == 5

    def test_custom_threshold(self, dynamodb_table, env_vars):
        """Test with custom threshold value."""
        now = datetime.now(UTC)

        # Item 3 minutes old
        dynamodb_table.put_item(
            Item={
                "source_id": "test-1",
                "timestamp": (now - timedelta(minutes=3)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "status": "pending",
            }
        )

        # With default 5 minute threshold, should not be stuck
        count = get_stuck_items_count("test-sentiment-items", threshold_minutes=5)
        assert count == 0

        # With 2 minute threshold, should be stuck
        count = get_stuck_items_count("test-sentiment-items", threshold_minutes=2)
        assert count == 1


class TestEmitStuckItemsMetric:
    """Tests for emit_stuck_items_metric function."""

    @mock_aws
    def test_emit_metric_success(self, aws_credentials):
        """Test successful metric emission."""
        with patch("src.lambdas.metrics.handler.emit_metric") as mock_emit:
            emit_stuck_items_metric(5, "test")

            mock_emit.assert_called_once_with(
                metric_name=METRIC_NAME,
                value=5,
                unit="Count",
                dimensions={"Environment": "test"},
                namespace=METRIC_NAMESPACE,
            )

    @mock_aws
    def test_emit_metric_zero(self, aws_credentials):
        """Test emitting zero stuck items."""
        with patch("src.lambdas.metrics.handler.emit_metric") as mock_emit:
            emit_stuck_items_metric(0, "prod")

            mock_emit.assert_called_once_with(
                metric_name=METRIC_NAME,
                value=0,
                unit="Count",
                dimensions={"Environment": "prod"},
                namespace=METRIC_NAMESPACE,
            )


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    def test_handler_success(self, dynamodb_table, env_vars, mock_context):
        """Test successful handler execution."""
        # Add a stuck item
        old_time = datetime.now(UTC) - timedelta(minutes=10)
        dynamodb_table.put_item(
            Item={
                "source_id": "stuck-1",
                "timestamp": old_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "pending",
            }
        )

        with patch("src.lambdas.metrics.handler.emit_metric"):
            result = lambda_handler({"source": "aws.events"}, mock_context)

        assert result["statusCode"] == 200
        assert result["body"]["stuck_items"] == 1
        assert result["body"]["environment"] == "test"
        assert "duration_ms" in result["body"]

    def test_handler_no_stuck_items(self, dynamodb_table, env_vars, mock_context):
        """Test handler with no stuck items."""
        with patch("src.lambdas.metrics.handler.emit_metric"):
            result = lambda_handler({"source": "aws.events"}, mock_context)

        assert result["statusCode"] == 200
        assert result["body"]["stuck_items"] == 0

    def test_handler_missing_table_env(self, aws_credentials, mock_context):
        """Test handler fails gracefully with missing DYNAMODB_TABLE."""
        os.environ.pop("DYNAMODB_TABLE", None)
        os.environ["ENVIRONMENT"] = "test"

        result = lambda_handler({}, mock_context)

        assert result["statusCode"] == 500
        assert "DYNAMODB_TABLE not set" in result["body"]

    def test_handler_emits_error_metric_on_failure(self, env_vars, mock_context):
        """Test handler emits error metric on failure."""
        with (
            patch(
                "src.lambdas.metrics.handler.get_stuck_items_count",
                side_effect=Exception("DynamoDB error"),
            ),
            patch("src.lambdas.metrics.handler.emit_metric") as mock_emit,
        ):
            result = lambda_handler({}, mock_context)

        assert result["statusCode"] == 500
        assert "DynamoDB error" in result["body"]

        # Should have tried to emit error metric
        mock_emit.assert_called_with(
            metric_name="MetricsLambdaErrors",
            value=1,
            unit="Count",
            dimensions={"Environment": "test"},
            namespace=METRIC_NAMESPACE,
        )


class TestConstants:
    """Tests for module constants."""

    def test_stuck_threshold_default(self):
        """Test default stuck threshold is 5 minutes."""
        assert STUCK_THRESHOLD_MINUTES == 5

    def test_metric_namespace(self):
        """Test metric namespace is correct."""
        assert METRIC_NAMESPACE == "SentimentAnalyzer"

    def test_metric_name(self):
        """Test metric name is correct."""
        assert METRIC_NAME == "StuckItems"

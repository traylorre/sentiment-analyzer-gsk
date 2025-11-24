"""
Analysis E2E Test
=================

Integration tests for the analysis flow against REAL dev environment.

CRITICAL: These tests use REAL AWS resources (dev environment only).
- DynamoDB: dev-sentiment-items table (Terraform-deployed)
- SNS: dev-sentiment-topic (Terraform-deployed)
- NO mocking of AWS infrastructure

External dependencies mocked:
- ML inference (transformers pipeline - prohibitively expensive and non-deterministic)
  Mocking allows us to test data flow without 2GB model download and GPU requirements.

For On-Call Engineers:
    If these tests fail in CI:
    1. Verify dev environment is deployed: `aws dynamodb describe-table --table-name dev-sentiment-items`
    2. Check SNS topic exists: `aws sns list-topics | grep dev-sentiment-topic`
    3. Verify DynamoDB schema matches table definition
    4. Check AWS credentials are configured in CI

    See SC-04 and SC-06 in ON_CALL_SOP.md for analysis issues.

For Developers:
    - Tests use REAL dev DynamoDB and SNS
    - ML inference is mocked (documented exception for cost/performance)
    - Verifies complete data flow through the system
    - Tests idempotency (duplicate handling)
    - Validates schema compliance
"""

import json
import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest

from src.lambdas.analysis.handler import lambda_handler

# Environment variables should be set by CI (do NOT override here)
# CI sets: DYNAMODB_TABLE=dev-sentiment-items, ENVIRONMENT=dev, etc.


@pytest.fixture
def env_vars():
    """
    Verify required environment variables are set.

    Does NOT override CI-provided values.
    """
    required_vars = ["DYNAMODB_TABLE", "ENVIRONMENT"]
    for var in required_vars:
        assert var in os.environ, f"Missing required env var: {var}"
    yield


@pytest.fixture
def mock_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.aws_request_id = "e2e-test-request-123"
    context.function_name = "test-sentiment-analysis"
    context.memory_limit_in_mb = 1024
    return context


@pytest.fixture
def dynamodb_table():
    """
    Get reference to REAL dev DynamoDB table.

    Returns the actual Terraform-deployed table.
    """
    table_name = os.environ.get("DYNAMODB_TABLE", "dev-sentiment-items")
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    return dynamodb.Table(table_name)


def create_sns_event(
    source_id: str,
    timestamp: str,
    text: str,
    model_version: str = "v1.0.0",
    matched_tags: list[str] | None = None,
) -> dict:
    """
    Create an SNS event for testing.

    Args:
        source_id: DynamoDB partition key
        timestamp: DynamoDB sort key
        text: Text for analysis
        model_version: Model version
        matched_tags: Tags that matched

    Returns:
        SNS event dict
    """
    if matched_tags is None:
        matched_tags = ["AI"]

    message = {
        "source_id": source_id,
        "source_type": "newsapi",
        "text_for_analysis": text,
        "model_version": model_version,
        "matched_tags": matched_tags,
        "timestamp": timestamp,
    }

    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "EventVersion": "1.0",
                "EventSubscriptionArn": "arn:aws:sns:us-east-1:123456789012:test-topic:...",
                "Sns": {
                    "Type": "Notification",
                    "MessageId": f"msg-{source_id}",
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                    "Subject": None,
                    "Message": json.dumps(message),
                    "Timestamp": datetime.now(UTC).isoformat(),
                    "MessageAttributes": {},
                },
            }
        ]
    }


class TestAnalysisE2E:
    """
    Integration tests for analysis flow against REAL dev AWS.

    IMPORTANT: These tests interact with actual dev-sentiment-items table.
    Test data is inserted/verified in real DynamoDB.
    """

    def test_full_analysis_flow(self, env_vars, mock_context, dynamodb_table):
        """
        Integration: Complete analysis flow from SNS to DynamoDB update.

        This is the primary integration test that verifies:
        1. SNS message is parsed correctly
        2. Inference runs (mocked ML, real AWS for everything else)
        3. DynamoDB item in REAL dev table is updated with results
        """
        # Use unique source_id to avoid conflicts with other test runs
        test_id = f"integration-test-{datetime.now(UTC).timestamp()}"
        source_id = f"newsapi#{test_id}"
        timestamp = datetime.now(UTC).isoformat()

        # Insert pending item into REAL dev table
        dynamodb_table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "status": "pending",
                "text_for_analysis": "This is an amazing breakthrough in AI technology!",
                "source_type": "newsapi",
                "matched_tags": ["AI", "technology"],
            }
        )

        # Create SNS event
        event = create_sns_event(
            source_id=source_id,
            timestamp=timestamp,
            text="This is an amazing breakthrough in AI technology!",
            model_version="v1.0.0",
            matched_tags=["AI", "technology"],
        )

        # Execute with mocked ML inference (only exception to no-mocking rule)
        try:
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = ("positive", 0.94)
                mock_load_time.return_value = 0

                result = lambda_handler(event, mock_context)

            # Verify success
            assert result["statusCode"] == 200
            assert result["body"]["sentiment"] == "positive"
            assert result["body"]["score"] == 0.94
            assert result["body"]["updated"] is True

            # Verify DynamoDB update in REAL dev table
            response = dynamodb_table.get_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )

            item = response["Item"]
            assert item["status"] == "analyzed"
            assert item["sentiment"] == "positive"
            assert float(item["score"]) == 0.94
            assert item["model_version"] == "v1.0.0"

        finally:
            # Cleanup: Remove test item from REAL dev table
            dynamodb_table.delete_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )

    def test_idempotency_prevents_reanalysis(
        self, env_vars, mock_context, dynamodb_table
    ):
        """
        Integration: Duplicate SNS messages don't re-analyze items.

        Verifies the conditional update prevents overwriting results in REAL dev table.
        """
        # Use unique source_id
        test_id = f"integration-idempotent-{datetime.now(UTC).timestamp()}"
        source_id = f"newsapi#{test_id}"
        timestamp = datetime.now(UTC).isoformat()

        # Insert pending item
        dynamodb_table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "status": "pending",
                "text_for_analysis": "Test article",
                "source_type": "newsapi",
                "matched_tags": ["AI"],
            }
        )

        event = create_sns_event(
            source_id=source_id, timestamp=timestamp, text="Test article"
        )

        try:
            # First invocation
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = ("positive", 0.85)
                mock_load_time.return_value = 0

                result1 = lambda_handler(event, mock_context)

            assert result1["body"]["updated"] is True

            # Second invocation (duplicate message)
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = ("negative", 0.90)  # Different result
                mock_load_time.return_value = 0

                result2 = lambda_handler(event, mock_context)

            # Should not update
            assert result2["body"]["updated"] is False

            # Original result preserved in REAL dev table
            response = dynamodb_table.get_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )
            assert response["Item"]["sentiment"] == "positive"  # Original

        finally:
            # Cleanup
            dynamodb_table.delete_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )

    def test_neutral_sentiment_classification(
        self, env_vars, mock_context, dynamodb_table
    ):
        """
        Integration: Neutral sentiment is stored correctly in REAL dev table.

        Neutral indicates low model confidence (score < 0.6).
        """
        test_id = f"integration-neutral-{datetime.now(UTC).timestamp()}"
        source_id = f"newsapi#{test_id}"
        timestamp = datetime.now(UTC).isoformat()

        dynamodb_table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "status": "pending",
                "text_for_analysis": "The weather is okay today.",
                "source_type": "newsapi",
                "matched_tags": ["weather"],
            }
        )

        event = create_sns_event(
            source_id=source_id,
            timestamp=timestamp,
            text="The weather is okay today.",
        )

        try:
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = ("neutral", 0.52)
                mock_load_time.return_value = 0

                result = lambda_handler(event, mock_context)

            assert result["body"]["sentiment"] == "neutral"
            assert result["body"]["score"] == 0.52

            # Verify in REAL dev table
            response = dynamodb_table.get_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )
            assert response["Item"]["sentiment"] == "neutral"

        finally:
            dynamodb_table.delete_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )

    def test_negative_sentiment_classification(
        self, env_vars, mock_context, dynamodb_table
    ):
        """
        Integration: Negative sentiment is stored correctly in REAL dev table.
        """
        test_id = f"integration-negative-{datetime.now(UTC).timestamp()}"
        source_id = f"newsapi#{test_id}"
        timestamp = datetime.now(UTC).isoformat()

        dynamodb_table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "status": "pending",
                "text_for_analysis": "This is terrible news about the economy.",
                "source_type": "newsapi",
                "matched_tags": ["economy"],
            }
        )

        event = create_sns_event(
            source_id=source_id,
            timestamp=timestamp,
            text="This is terrible news about the economy.",
        )

        try:
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = ("negative", 0.88)
                mock_load_time.return_value = 0

                result = lambda_handler(event, mock_context)

            assert result["body"]["sentiment"] == "negative"

            # Verify in REAL dev table
            response = dynamodb_table.get_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )
            assert response["Item"]["sentiment"] == "negative"

        finally:
            dynamodb_table.delete_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )

    def test_model_version_stored(self, env_vars, mock_context, dynamodb_table):
        """
        Integration: Model version is correctly stored in REAL dev table.

        This is important for tracking which model analyzed each item.
        """
        test_id = f"integration-version-{datetime.now(UTC).timestamp()}"
        source_id = f"newsapi#{test_id}"
        timestamp = datetime.now(UTC).isoformat()

        dynamodb_table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "status": "pending",
                "text_for_analysis": "Test",
                "source_type": "newsapi",
                "matched_tags": ["test"],
            }
        )

        event = create_sns_event(
            source_id=source_id,
            timestamp=timestamp,
            text="Test",
            model_version="v2.0.0",  # Different version
        )

        try:
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = ("positive", 0.80)
                mock_load_time.return_value = 0

                result = lambda_handler(event, mock_context)

            assert result["body"]["model_version"] == "v2.0.0"

            # Verify in REAL dev table
            response = dynamodb_table.get_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )
            assert response["Item"]["model_version"] == "v2.0.0"

        finally:
            dynamodb_table.delete_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )

    def test_score_precision(self, env_vars, mock_context, dynamodb_table):
        """
        Integration: Score is stored with correct precision in REAL dev table.

        Score should be rounded to 4 decimal places.
        """
        test_id = f"integration-precision-{datetime.now(UTC).timestamp()}"
        source_id = f"newsapi#{test_id}"
        timestamp = datetime.now(UTC).isoformat()

        dynamodb_table.put_item(
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

        try:
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = (
                    "positive",
                    0.9234567890,
                )  # Many decimals
                mock_load_time.return_value = 0

                result = lambda_handler(event, mock_context)

            # Should be rounded to 4 decimals
            assert result["body"]["score"] == 0.9235

            # Verify in REAL dev table
            response = dynamodb_table.get_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )
            assert float(response["Item"]["score"]) == 0.9235

        finally:
            dynamodb_table.delete_item(
                Key={"source_id": source_id, "timestamp": timestamp}
            )

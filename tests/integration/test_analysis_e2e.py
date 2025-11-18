"""
Analysis E2E Test
=================

End-to-end test for the analysis flow: SNS → Inference → DynamoDB.

For On-Call Engineers:
    This test verifies the complete analysis pipeline:
    1. SNS message triggers Lambda
    2. Model runs inference on text
    3. DynamoDB item updated with sentiment/score
    4. Idempotency prevents duplicate processing

    If this test fails in CI:
    - Check moto mock versions match production AWS behavior
    - Verify DynamoDB schema matches table definition
    - Check SNS message format matches ingestion output

    See SC-04 and SC-06 in ON_CALL_SOP.md for analysis issues.

For Developers:
    - Uses moto to mock DynamoDB and CloudWatch
    - Mocks sentiment module (no actual model loading)
    - Verifies complete data flow through the system
    - Tests idempotency (duplicate handling)
    - Validates schema compliance
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.lambdas.analysis.handler import lambda_handler


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def env_vars(aws_credentials):
    """Set up environment variables for testing."""
    os.environ["DYNAMODB_TABLE"] = "test-sentiment-items"
    os.environ["MODEL_PATH"] = "/opt/model"
    os.environ["ENVIRONMENT"] = "test"

    yield

    # Cleanup
    for key in ["DYNAMODB_TABLE", "MODEL_PATH", "ENVIRONMENT"]:
        os.environ.pop(key, None)


@pytest.fixture
def mock_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.aws_request_id = "e2e-test-request-123"
    context.function_name = "test-sentiment-analysis"
    context.memory_limit_in_mb = 1024
    return context


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
                    "Timestamp": datetime.now(timezone.utc).isoformat(),
                    "MessageAttributes": {},
                },
            }
        ]
    }


class TestAnalysisE2E:
    """End-to-end tests for analysis flow."""

    @mock_aws
    def test_full_analysis_flow(self, env_vars, mock_context):
        """
        Test complete analysis flow from SNS to DynamoDB update.

        This is the primary E2E test that verifies:
        1. SNS message is parsed correctly
        2. Inference runs on text
        3. DynamoDB item is updated with results
        """
        # Setup DynamoDB with pending item
        table = self._setup_dynamodb_with_item(
            source_id="newsapi#e2e123",
            timestamp="2025-11-17T14:30:00.000Z",
            status="pending",
            text="This is an amazing breakthrough in AI technology!",
        )

        # Create SNS event
        event = create_sns_event(
            source_id="newsapi#e2e123",
            timestamp="2025-11-17T14:30:00.000Z",
            text="This is an amazing breakthrough in AI technology!",
            model_version="v1.0.0",
            matched_tags=["AI", "technology"],
        )

        # Execute with mocked model
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

        # Verify DynamoDB update
        response = table.get_item(
            Key={
                "source_id": "newsapi#e2e123",
                "timestamp": "2025-11-17T14:30:00.000Z",
            }
        )

        item = response["Item"]
        assert item["status"] == "analyzed"
        assert item["sentiment"] == "positive"
        assert float(item["score"]) == 0.94
        assert item["model_version"] == "v1.0.0"

    @mock_aws
    def test_idempotency_prevents_reanalysis(self, env_vars, mock_context):
        """
        Test that duplicate SNS messages don't re-analyze items.

        This verifies the conditional update prevents overwriting results.
        """
        # Setup DynamoDB with pending item
        table = self._setup_dynamodb_with_item(
            source_id="newsapi#idempotent123",
            timestamp="2025-11-17T15:00:00.000Z",
            status="pending",
            text="Test article",
        )

        event = create_sns_event(
            source_id="newsapi#idempotent123",
            timestamp="2025-11-17T15:00:00.000Z",
            text="Test article",
        )

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

        # Original result preserved
        response = table.get_item(
            Key={
                "source_id": "newsapi#idempotent123",
                "timestamp": "2025-11-17T15:00:00.000Z",
            }
        )
        assert response["Item"]["sentiment"] == "positive"  # Original

    @mock_aws
    def test_neutral_sentiment_classification(self, env_vars, mock_context):
        """
        Test neutral sentiment is stored correctly.

        Neutral indicates low model confidence (score < 0.6).
        """
        table = self._setup_dynamodb_with_item(
            source_id="newsapi#neutral123",
            timestamp="2025-11-17T16:00:00.000Z",
            status="pending",
            text="The weather is okay today.",
        )

        event = create_sns_event(
            source_id="newsapi#neutral123",
            timestamp="2025-11-17T16:00:00.000Z",
            text="The weather is okay today.",
        )

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

        # Verify in DynamoDB
        response = table.get_item(
            Key={
                "source_id": "newsapi#neutral123",
                "timestamp": "2025-11-17T16:00:00.000Z",
            }
        )
        assert response["Item"]["sentiment"] == "neutral"

    @mock_aws
    def test_negative_sentiment_classification(self, env_vars, mock_context):
        """
        Test negative sentiment is stored correctly.
        """
        table = self._setup_dynamodb_with_item(
            source_id="newsapi#negative123",
            timestamp="2025-11-17T17:00:00.000Z",
            status="pending",
            text="This is terrible news about the economy.",
        )

        event = create_sns_event(
            source_id="newsapi#negative123",
            timestamp="2025-11-17T17:00:00.000Z",
            text="This is terrible news about the economy.",
        )

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

        # Verify in DynamoDB
        response = table.get_item(
            Key={
                "source_id": "newsapi#negative123",
                "timestamp": "2025-11-17T17:00:00.000Z",
            }
        )
        assert response["Item"]["sentiment"] == "negative"

    @mock_aws
    def test_multiple_items_processed_independently(self, env_vars, mock_context):
        """
        Test that multiple items are processed independently.

        Each SNS message should only affect its target item.
        """
        # Setup multiple pending items
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

        # Insert two items
        table.put_item(
            Item={
                "source_id": "newsapi#item1",
                "timestamp": "2025-11-17T10:00:00.000Z",
                "status": "pending",
            }
        )
        table.put_item(
            Item={
                "source_id": "newsapi#item2",
                "timestamp": "2025-11-17T11:00:00.000Z",
                "status": "pending",
            }
        )

        # Process first item
        event1 = create_sns_event(
            source_id="newsapi#item1",
            timestamp="2025-11-17T10:00:00.000Z",
            text="Positive news",
        )

        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch(
                "src.lambdas.analysis.handler.get_model_load_time_ms"
            ) as mock_load_time,
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            mock_analyze.return_value = ("positive", 0.90)
            mock_load_time.return_value = 0

            lambda_handler(event1, mock_context)

        # Verify item1 updated, item2 still pending
        item1 = table.get_item(
            Key={
                "source_id": "newsapi#item1",
                "timestamp": "2025-11-17T10:00:00.000Z",
            }
        )["Item"]
        item2 = table.get_item(
            Key={
                "source_id": "newsapi#item2",
                "timestamp": "2025-11-17T11:00:00.000Z",
            }
        )["Item"]

        assert item1["status"] == "analyzed"
        assert item2["status"] == "pending"

    @mock_aws
    def test_model_version_stored(self, env_vars, mock_context):
        """
        Test that model version is correctly stored.

        This is important for tracking which model analyzed each item.
        """
        table = self._setup_dynamodb_with_item(
            source_id="newsapi#version123",
            timestamp="2025-11-17T18:00:00.000Z",
            status="pending",
            text="Test",
        )

        event = create_sns_event(
            source_id="newsapi#version123",
            timestamp="2025-11-17T18:00:00.000Z",
            text="Test",
            model_version="v2.0.0",  # Different version
        )

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

        # Verify in DynamoDB
        response = table.get_item(
            Key={
                "source_id": "newsapi#version123",
                "timestamp": "2025-11-17T18:00:00.000Z",
            }
        )
        assert response["Item"]["model_version"] == "v2.0.0"

    @mock_aws
    def test_score_precision(self, env_vars, mock_context):
        """
        Test that score is stored with correct precision.

        Score should be rounded to 4 decimal places.
        """
        table = self._setup_dynamodb_with_item(
            source_id="newsapi#precision123",
            timestamp="2025-11-17T19:00:00.000Z",
            status="pending",
            text="Test",
        )

        event = create_sns_event(
            source_id="newsapi#precision123",
            timestamp="2025-11-17T19:00:00.000Z",
            text="Test",
        )

        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch(
                "src.lambdas.analysis.handler.get_model_load_time_ms"
            ) as mock_load_time,
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            mock_analyze.return_value = ("positive", 0.9234567890)  # Many decimals
            mock_load_time.return_value = 0

            result = lambda_handler(event, mock_context)

        # Should be rounded to 4 decimals
        assert result["body"]["score"] == 0.9235

        # Verify in DynamoDB
        response = table.get_item(
            Key={
                "source_id": "newsapi#precision123",
                "timestamp": "2025-11-17T19:00:00.000Z",
            }
        )
        assert float(response["Item"]["score"]) == 0.9235

    def _setup_dynamodb_with_item(
        self,
        source_id: str,
        timestamp: str,
        status: str,
        text: str = "Test text",
    ):
        """
        Set up DynamoDB table with a single item.

        Args:
            source_id: Item partition key
            timestamp: Item sort key
            status: Item status (pending/analyzed)
            text: Text for analysis

        Returns:
            DynamoDB table resource
        """
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
        table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "status": status,
                "text_for_analysis": text,
                "source_type": "newsapi",
                "matched_tags": ["AI"],
            }
        )

        return table


class TestAnalysisErrorScenarios:
    """Tests for error scenarios in analysis flow."""

    @mock_aws
    def test_item_not_found(self, env_vars, mock_context):
        """
        Test handling when item doesn't exist in DynamoDB.

        This can happen if ingestion failed or item was deleted.
        """
        # Setup empty table
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

        event = create_sns_event(
            source_id="newsapi#nonexistent",
            timestamp="2025-11-17T20:00:00.000Z",
            text="Test",
        )

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

        # Should still "succeed" but not update (conditional check fails)
        assert result["statusCode"] == 200
        assert result["body"]["updated"] is False

    @mock_aws
    def test_empty_text_handling(self, env_vars, mock_context):
        """
        Test handling of empty text for analysis.
        """
        table = TestAnalysisE2E()._setup_dynamodb_with_item(
            source_id="newsapi#empty123",
            timestamp="2025-11-17T21:00:00.000Z",
            status="pending",
            text="",
        )

        event = create_sns_event(
            source_id="newsapi#empty123",
            timestamp="2025-11-17T21:00:00.000Z",
            text="",  # Empty
        )

        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch(
                "src.lambdas.analysis.handler.get_model_load_time_ms"
            ) as mock_load_time,
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            # Model returns neutral for empty text
            mock_analyze.return_value = ("neutral", 0.5)
            mock_load_time.return_value = 0

            result = lambda_handler(event, mock_context)

        assert result["statusCode"] == 200
        assert result["body"]["sentiment"] == "neutral"


class TestAnalysisMetrics:
    """Tests for metrics emission during analysis."""

    @mock_aws
    def test_metrics_emitted_on_success(self, env_vars, mock_context):
        """
        Test that correct metrics are emitted on successful analysis.
        """
        TestAnalysisE2E()._setup_dynamodb_with_item(
            source_id="newsapi#metrics123",
            timestamp="2025-11-17T22:00:00.000Z",
            status="pending",
            text="Great news!",
        )

        event = create_sns_event(
            source_id="newsapi#metrics123",
            timestamp="2025-11-17T22:00:00.000Z",
            text="Great news!",
        )

        emitted_metrics = []

        def mock_batch(metrics, **kwargs):
            emitted_metrics.extend(metrics)

        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch(
                "src.lambdas.analysis.handler.get_model_load_time_ms"
            ) as mock_load_time,
            patch("src.lib.metrics.emit_metric"),
            patch("src.lambdas.analysis.handler.emit_metrics_batch", mock_batch),
        ):
            mock_analyze.return_value = ("positive", 0.90)
            mock_load_time.return_value = 0

            lambda_handler(event, mock_context)

        metric_names = [m["name"] for m in emitted_metrics]
        assert "SentimentAnalysisCount" in metric_names
        assert "InferenceLatencyMs" in metric_names
        assert "PositiveSentimentCount" in metric_names
        assert "ItemsAnalyzed" in metric_names

    @mock_aws
    def test_cold_start_metric(self, env_vars, mock_context):
        """
        Test that model load time metric is emitted on cold start.
        """
        TestAnalysisE2E()._setup_dynamodb_with_item(
            source_id="newsapi#coldstart123",
            timestamp="2025-11-17T23:00:00.000Z",
            status="pending",
            text="Test",
        )

        event = create_sns_event(
            source_id="newsapi#coldstart123",
            timestamp="2025-11-17T23:00:00.000Z",
            text="Test",
        )

        emitted = []

        def mock_emit(name, value, **kwargs):
            emitted.append({"name": name, "value": value})

        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch(
                "src.lambdas.analysis.handler.get_model_load_time_ms"
            ) as mock_load_time,
            patch("src.lambdas.analysis.handler.emit_metric", mock_emit),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            mock_analyze.return_value = ("positive", 0.80)
            mock_load_time.return_value = 2500  # Cold start

            lambda_handler(event, mock_context)

        metric_names = [m["name"] for m in emitted]
        assert "ModelLoadTimeMs" in metric_names

        # Find the metric and check value
        load_metric = next(m for m in emitted if m["name"] == "ModelLoadTimeMs")
        assert load_metric["value"] == 2500

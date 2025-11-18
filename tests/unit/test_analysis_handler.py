"""
Unit Tests for Analysis Lambda Handler
======================================

Tests the analysis handler with mocked model and AWS services.

For On-Call Engineers:
    These tests verify:
    - SNS message parsing
    - Sentiment inference flow
    - DynamoDB conditional updates
    - Idempotency (duplicate handling)
    - Error handling and metrics

For Developers:
    - Uses moto to mock DynamoDB and CloudWatch
    - Mocks sentiment module to avoid loading actual model
    - Test both success and error scenarios
    - Verify metrics are emitted correctly
"""

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.lambdas.analysis.handler import (
    _emit_analysis_metrics,
    _update_item_with_sentiment,
    lambda_handler,
)


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
    context.aws_request_id = "test-request-123"
    context.function_name = "test-sentiment-analysis"
    context.memory_limit_in_mb = 1024
    return context


@pytest.fixture
def sns_event():
    """Sample SNS event from ingestion Lambda."""
    message = {
        "source_id": "newsapi#abc123def456",
        "source_type": "newsapi",
        "text_for_analysis": "This is a great article about AI breakthroughs!",
        "model_version": "v1.0.0",
        "matched_tags": ["AI", "technology"],
        "timestamp": "2025-11-17T14:30:15.000Z",
    }

    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "EventVersion": "1.0",
                "EventSubscriptionArn": "arn:aws:sns:us-east-1:123456789012:test-topic:...",
                "Sns": {
                    "Type": "Notification",
                    "MessageId": "test-message-id",
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                    "Subject": None,
                    "Message": json.dumps(message),
                    "Timestamp": "2025-11-17T14:30:16.000Z",
                    "MessageAttributes": {},
                },
            }
        ]
    }


@pytest.fixture
def dynamodb_table(env_vars):
    """Create mock DynamoDB table with a pending item."""
    with mock_aws():
        # Create table
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
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Insert pending item
        table.put_item(
            Item={
                "source_id": "newsapi#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
                "source_type": "newsapi",
                "source_url": "https://example.com/article",
                "text_snippet": "This is a great article...",
                "text_for_analysis": "This is a great article about AI breakthroughs!",
                "status": "pending",
                "matched_tags": ["AI", "technology"],
                "ttl_timestamp": 1737139200,
                "metadata": {
                    "title": "AI Breakthrough",
                    "author": "Test Author",
                    "published_at": "2025-11-17T14:00:00Z",
                    "source_name": "Test News",
                },
            }
        )

        yield table


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    @mock_aws
    def test_handler_success(self, env_vars, sns_event, mock_context):
        """Test successful analysis flow."""
        # Setup DynamoDB
        self._setup_dynamodb_with_pending_item()

        with patch("src.lambdas.analysis.handler.load_model"), \
             patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze, \
             patch("src.lambdas.analysis.handler.get_model_load_time_ms") as mock_load_time, \
             patch("src.lib.metrics.emit_metric"), \
             patch("src.lib.metrics.emit_metrics_batch"):

            mock_analyze.return_value = ("positive", 0.92)
            mock_load_time.return_value = 0  # Warm start

            result = lambda_handler(sns_event, mock_context)

        assert result["statusCode"] == 200
        assert result["body"]["source_id"] == "newsapi#abc123def456"
        assert result["body"]["sentiment"] == "positive"
        assert result["body"]["score"] == 0.92
        assert result["body"]["model_version"] == "v1.0.0"
        assert result["body"]["updated"] is True
        assert "inference_time_ms" in result["body"]

    @mock_aws
    def test_handler_updates_dynamodb(self, env_vars, sns_event, mock_context):
        """Test that DynamoDB item is updated correctly."""
        # Setup DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = self._setup_dynamodb_with_pending_item()

        with patch("src.lambdas.analysis.handler.load_model"), \
             patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze, \
             patch("src.lambdas.analysis.handler.get_model_load_time_ms") as mock_load_time, \
             patch("src.lib.metrics.emit_metric"), \
             patch("src.lib.metrics.emit_metrics_batch"):

            mock_analyze.return_value = ("negative", 0.78)
            mock_load_time.return_value = 0

            lambda_handler(sns_event, mock_context)

        # Verify item was updated
        table = dynamodb.Table("test-sentiment-items")
        response = table.get_item(
            Key={
                "source_id": "newsapi#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
            }
        )

        item = response["Item"]
        assert item["status"] == "analyzed"
        assert item["sentiment"] == "negative"
        assert float(item["score"]) == 0.78
        assert item["model_version"] == "v1.0.0"

    @mock_aws
    def test_handler_idempotency(self, env_vars, sns_event, mock_context):
        """Test that duplicate messages don't re-analyze."""
        # Setup DynamoDB with already-analyzed item
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
                "source_id": "newsapi#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
                "status": "analyzed",  # Already analyzed
                "sentiment": "positive",
                "score": 0.85,
            }
        )

        with patch("src.lambdas.analysis.handler.load_model"), \
             patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze, \
             patch("src.lambdas.analysis.handler.get_model_load_time_ms") as mock_load_time, \
             patch("src.lib.metrics.emit_metric"), \
             patch("src.lib.metrics.emit_metrics_batch"):

            mock_analyze.return_value = ("negative", 0.90)  # Different result
            mock_load_time.return_value = 0

            result = lambda_handler(sns_event, mock_context)

        # Should succeed but not update
        assert result["statusCode"] == 200
        assert result["body"]["updated"] is False

        # Original sentiment should be preserved
        response = table.get_item(
            Key={
                "source_id": "newsapi#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
            }
        )
        assert response["Item"]["sentiment"] == "positive"  # Original

    @mock_aws
    def test_handler_neutral_sentiment(self, env_vars, sns_event, mock_context):
        """Test neutral sentiment classification."""
        self._setup_dynamodb_with_pending_item()

        with patch("src.lambdas.analysis.handler.load_model"), \
             patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze, \
             patch("src.lambdas.analysis.handler.get_model_load_time_ms") as mock_load_time, \
             patch("src.lib.metrics.emit_metric"), \
             patch("src.lib.metrics.emit_metrics_batch"):

            mock_analyze.return_value = ("neutral", 0.55)
            mock_load_time.return_value = 0

            result = lambda_handler(sns_event, mock_context)

        assert result["body"]["sentiment"] == "neutral"
        assert result["body"]["score"] == 0.55

    def test_handler_invalid_message_format(self, env_vars, mock_context):
        """Test error handling for invalid SNS message."""
        # Missing required field
        invalid_event = {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps({
                            "source_id": "newsapi#abc123",
                            # Missing timestamp, text_for_analysis, model_version
                        })
                    }
                }
            ]
        }

        with patch("src.lib.metrics.emit_metric"):
            result = lambda_handler(invalid_event, mock_context)

        assert result["statusCode"] == 400
        assert result["body"]["code"] == "VALIDATION_ERROR"

    @mock_aws
    def test_handler_model_load_error(self, env_vars, sns_event, mock_context):
        """Test error handling when model fails to load."""
        self._setup_dynamodb_with_pending_item()

        from src.lambdas.analysis.sentiment import ModelLoadError

        with patch("src.lambdas.analysis.handler.load_model") as mock_load, \
             patch("src.lib.metrics.emit_metric"):

            mock_load.side_effect = ModelLoadError("Model not found")

            result = lambda_handler(sns_event, mock_context)

        assert result["statusCode"] == 500
        assert result["body"]["code"] == "MODEL_ERROR"

    @mock_aws
    def test_handler_inference_error(self, env_vars, sns_event, mock_context):
        """Test error handling when inference fails."""
        self._setup_dynamodb_with_pending_item()

        from src.lambdas.analysis.sentiment import InferenceError

        with patch("src.lambdas.analysis.handler.load_model"), \
             patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze, \
             patch("src.lambdas.analysis.handler.get_model_load_time_ms") as mock_load_time, \
             patch("src.lib.metrics.emit_metric"):

            mock_analyze.side_effect = InferenceError("CUDA error")
            mock_load_time.return_value = 0

            result = lambda_handler(sns_event, mock_context)

        assert result["statusCode"] == 500
        assert result["body"]["code"] == "MODEL_ERROR"

    @mock_aws
    def test_handler_emits_model_load_metric(self, env_vars, sns_event, mock_context):
        """Test that model load time metric is emitted on cold start."""
        self._setup_dynamodb_with_pending_item()

        emitted_metrics = []

        def mock_emit(name, value, **kwargs):
            emitted_metrics.append({"name": name, "value": value})

        with patch("src.lambdas.analysis.handler.load_model"), \
             patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze, \
             patch("src.lambdas.analysis.handler.get_model_load_time_ms") as mock_load_time, \
             patch("src.lambdas.analysis.handler.emit_metric", mock_emit), \
             patch("src.lib.metrics.emit_metrics_batch"):

            mock_analyze.return_value = ("positive", 0.90)
            mock_load_time.return_value = 2500  # Cold start

            lambda_handler(sns_event, mock_context)

        # Should have model load metric
        metric_names = [m["name"] for m in emitted_metrics]
        assert "ModelLoadTimeMs" in metric_names

    def _setup_dynamodb_with_pending_item(self):
        """Set up DynamoDB table with a pending item."""
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
                "source_id": "newsapi#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
                "status": "pending",
                "text_for_analysis": "Test text",
            }
        )

        return table


class TestUpdateItemWithSentiment:
    """Tests for _update_item_with_sentiment function."""

    @mock_aws
    def test_update_pending_item(self, env_vars):
        """Test updating a pending item."""
        # Setup
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
                "source_id": "newsapi#test123",
                "timestamp": "2025-11-17T10:00:00Z",
                "status": "pending",
            }
        )

        with patch("src.lib.metrics.emit_metric"):
            result = _update_item_with_sentiment(
                table=table,
                source_id="newsapi#test123",
                timestamp="2025-11-17T10:00:00Z",
                sentiment="positive",
                score=0.88,
                model_version="v1.0.0",
            )

        assert result is True

        # Verify update
        response = table.get_item(
            Key={
                "source_id": "newsapi#test123",
                "timestamp": "2025-11-17T10:00:00Z",
            }
        )
        item = response["Item"]
        assert item["status"] == "analyzed"
        assert item["sentiment"] == "positive"

    @mock_aws
    def test_skip_already_analyzed(self, env_vars):
        """Test skipping already analyzed item."""
        # Setup
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
                "source_id": "newsapi#test123",
                "timestamp": "2025-11-17T10:00:00Z",
                "status": "analyzed",  # Already analyzed
                "sentiment": "negative",
            }
        )

        with patch("src.lib.metrics.emit_metric"):
            result = _update_item_with_sentiment(
                table=table,
                source_id="newsapi#test123",
                timestamp="2025-11-17T10:00:00Z",
                sentiment="positive",  # Different
                score=0.95,
                model_version="v1.0.0",
            )

        assert result is False

        # Original should be preserved
        response = table.get_item(
            Key={
                "source_id": "newsapi#test123",
                "timestamp": "2025-11-17T10:00:00Z",
            }
        )
        assert response["Item"]["sentiment"] == "negative"


class TestEmitAnalysisMetrics:
    """Tests for _emit_analysis_metrics function."""

    def test_emits_correct_metrics(self):
        """Test that correct metrics are emitted."""
        emitted = []

        def mock_batch(metrics, **kwargs):
            emitted.extend(metrics)

        with patch("src.lambdas.analysis.handler.emit_metrics_batch", mock_batch):
            _emit_analysis_metrics(
                sentiment="positive",
                inference_time_ms=125.5,
                updated=True,
            )

        metric_names = [m["name"] for m in emitted]
        assert "SentimentAnalysisCount" in metric_names
        assert "InferenceLatencyMs" in metric_names
        assert "PositiveSentimentCount" in metric_names
        assert "ItemsAnalyzed" in metric_names

    def test_emits_sentiment_specific_metric(self):
        """Test sentiment-specific metric names."""
        emitted = []

        def mock_batch(metrics, **kwargs):
            emitted.extend(metrics)

        with patch("src.lambdas.analysis.handler.emit_metrics_batch", mock_batch):
            _emit_analysis_metrics(
                sentiment="negative",
                inference_time_ms=100,
                updated=True,
            )

        metric_names = [m["name"] for m in emitted]
        assert "NegativeSentimentCount" in metric_names

    def test_skips_items_analyzed_when_not_updated(self):
        """Test ItemsAnalyzed metric skipped for duplicates."""
        emitted = []

        def mock_batch(metrics, **kwargs):
            emitted.extend(metrics)

        with patch("src.lambdas.analysis.handler.emit_metrics_batch", mock_batch):
            _emit_analysis_metrics(
                sentiment="positive",
                inference_time_ms=100,
                updated=False,  # Not updated
            )

        metric_names = [m["name"] for m in emitted]
        assert "ItemsAnalyzed" not in metric_names


class TestSNSMessageParsing:
    """Tests for SNS message parsing."""

    @mock_aws
    def test_parses_all_fields(self, env_vars, mock_context):
        """Test all message fields are parsed correctly."""
        # Setup
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
                "source_id": "newsapi#custom123",
                "timestamp": "2025-11-17T12:00:00.000Z",
                "status": "pending",
            }
        )

        message = {
            "source_id": "newsapi#custom123",
            "source_type": "newsapi",
            "text_for_analysis": "Custom text for testing",
            "model_version": "v2.0.0",
            "matched_tags": ["custom"],
            "timestamp": "2025-11-17T12:00:00.000Z",
        }

        event = {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps(message)
                    }
                }
            ]
        }

        with patch("src.lambdas.analysis.handler.load_model"), \
             patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze, \
             patch("src.lambdas.analysis.handler.get_model_load_time_ms") as mock_load_time, \
             patch("src.lib.metrics.emit_metric"), \
             patch("src.lib.metrics.emit_metrics_batch"):

            mock_analyze.return_value = ("positive", 0.85)
            mock_load_time.return_value = 0

            result = lambda_handler(event, mock_context)

        # Verify parsed correctly
        assert result["body"]["source_id"] == "newsapi#custom123"
        assert result["body"]["model_version"] == "v2.0.0"

        # Verify text was passed to analyze
        mock_analyze.assert_called_once_with("Custom text for testing")

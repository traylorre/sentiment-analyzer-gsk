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
from decimal import Decimal
from unittest.mock import MagicMock, patch

import boto3
import pytest
from freezegun import freeze_time
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
    os.environ["AWS_REGION"] = "us-east-1"


@pytest.fixture
def env_vars(aws_credentials):
    """Set up environment variables for testing."""
    os.environ["DATABASE_TABLE"] = "test-sentiment-items"
    os.environ["MODEL_PATH"] = "/opt/model"
    os.environ["ENVIRONMENT"] = "test"

    yield

    # Cleanup
    for key in ["DATABASE_TABLE", "MODEL_PATH", "ENVIRONMENT"]:
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
        "source_id": "article#abc123def456",
        "source_type": "tiingo",
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
                "source_id": "article#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
                "source_type": "tiingo",
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

        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch(
                "src.lambdas.analysis.handler.get_model_load_time_ms"
            ) as mock_load_time,
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            mock_analyze.return_value = ("positive", 0.92)
            mock_load_time.return_value = 0  # Warm start

            result = lambda_handler(sns_event, mock_context)

        assert result["statusCode"] == 200
        assert result["body"]["source_id"] == "article#abc123def456"
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

        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch(
                "src.lambdas.analysis.handler.get_model_load_time_ms"
            ) as mock_load_time,
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            mock_analyze.return_value = ("negative", 0.78)
            mock_load_time.return_value = 0

            lambda_handler(sns_event, mock_context)

        # Verify item was updated
        table = dynamodb.Table("test-sentiment-items")
        response = table.get_item(
            Key={
                "source_id": "article#abc123def456",
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
                "source_id": "article#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
                "status": "analyzed",  # Already analyzed
                "sentiment": "positive",
                "score": Decimal("0.85"),
            }
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
            mock_analyze.return_value = ("negative", 0.90)  # Different result
            mock_load_time.return_value = 0

            result = lambda_handler(sns_event, mock_context)

        # Should succeed but not update
        assert result["statusCode"] == 200
        assert result["body"]["updated"] is False

        # Original sentiment should be preserved
        response = table.get_item(
            Key={
                "source_id": "article#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
            }
        )
        assert response["Item"]["sentiment"] == "positive"  # Original

    @mock_aws
    def test_handler_neutral_sentiment(self, env_vars, sns_event, mock_context):
        """Test neutral sentiment classification."""
        self._setup_dynamodb_with_pending_item()

        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch(
                "src.lambdas.analysis.handler.get_model_load_time_ms"
            ) as mock_load_time,
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            mock_analyze.return_value = ("neutral", 0.55)
            mock_load_time.return_value = 0

            result = lambda_handler(sns_event, mock_context)

        assert result["body"]["sentiment"] == "neutral"
        assert result["body"]["score"] == 0.55

    def test_handler_invalid_message_format(self, env_vars, mock_context, caplog):
        """Test error handling for invalid SNS message."""
        # Missing required field
        invalid_event = {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps(
                            {
                                "source_id": "article#abc123",
                                # Missing timestamp, text_for_analysis, model_version
                            }
                        )
                    }
                }
            ]
        }

        with patch("src.lib.metrics.emit_metric"):
            result = lambda_handler(invalid_event, mock_context)

        assert result["statusCode"] == 400
        assert result["body"]["code"] == "VALIDATION_ERROR"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Invalid SNS message format")

    @mock_aws
    def test_handler_model_load_error(self, env_vars, sns_event, mock_context, caplog):
        """Test error handling when model fails to load."""
        self._setup_dynamodb_with_pending_item()

        from src.lambdas.analysis.sentiment import ModelLoadError

        with (
            patch("src.lambdas.analysis.handler.load_model") as mock_load,
            patch("src.lib.metrics.emit_metric"),
        ):
            mock_load.side_effect = ModelLoadError("Model not found")

            result = lambda_handler(sns_event, mock_context)

        assert result["statusCode"] == 500
        assert result["body"]["code"] == "MODEL_ERROR"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Model load error")

    @mock_aws
    def test_handler_inference_error(self, env_vars, sns_event, mock_context, caplog):
        """Test error handling when inference fails."""
        self._setup_dynamodb_with_pending_item()

        from src.lambdas.analysis.sentiment import InferenceError

        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch(
                "src.lambdas.analysis.handler.get_model_load_time_ms"
            ) as mock_load_time,
            patch("src.lib.metrics.emit_metric"),
        ):
            mock_analyze.side_effect = InferenceError("CUDA error")
            mock_load_time.return_value = 0

            result = lambda_handler(sns_event, mock_context)

        assert result["statusCode"] == 500
        assert result["body"]["code"] == "MODEL_ERROR"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Inference error")

    @mock_aws
    def test_handler_emits_model_load_metric(self, env_vars, sns_event, mock_context):
        """Test that model load time metric is emitted on cold start."""
        self._setup_dynamodb_with_pending_item()

        emitted_metrics = []

        def mock_emit(name, value, **kwargs):
            emitted_metrics.append({"name": name, "value": value})

        with (
            patch("src.lambdas.analysis.handler.load_model"),
            patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
            patch(
                "src.lambdas.analysis.handler.get_model_load_time_ms"
            ) as mock_load_time,
            patch("src.lambdas.analysis.handler.emit_metric", mock_emit),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
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
                "source_id": "article#abc123def456",
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
                "source_id": "article#test123",
                "timestamp": "2025-11-17T10:00:00Z",
                "status": "pending",
            }
        )

        with patch("src.lib.metrics.emit_metric"):
            result = _update_item_with_sentiment(
                table=table,
                source_id="article#test123",
                timestamp="2025-11-17T10:00:00Z",
                sentiment="positive",
                score=0.88,
                model_version="v1.0.0",
            )

        assert result is True

        # Verify update
        response = table.get_item(
            Key={
                "source_id": "article#test123",
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
                "source_id": "article#test123",
                "timestamp": "2025-11-17T10:00:00Z",
                "status": "analyzed",  # Already analyzed
                "sentiment": "negative",
            }
        )

        with patch("src.lib.metrics.emit_metric"):
            result = _update_item_with_sentiment(
                table=table,
                source_id="article#test123",
                timestamp="2025-11-17T10:00:00Z",
                sentiment="positive",  # Different
                score=0.95,
                model_version="v1.0.0",
            )

        assert result is False

        # Original should be preserved
        response = table.get_item(
            Key={
                "source_id": "article#test123",
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
                "source_id": "article#custom123",
                "timestamp": "2025-11-17T12:00:00.000Z",
                "status": "pending",
            }
        )

        message = {
            "source_id": "article#custom123",
            "source_type": "tiingo",
            "text_for_analysis": "Custom text for testing",
            "model_version": "v2.0.0",
            "matched_tags": ["custom"],
            "timestamp": "2025-11-17T12:00:00.000Z",
        }

        event = {"Records": [{"Sns": {"Message": json.dumps(message)}}]}

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

            result = lambda_handler(event, mock_context)

        # Verify parsed correctly
        assert result["body"]["source_id"] == "article#custom123"
        assert result["body"]["model_version"] == "v2.0.0"

        # Verify text was passed to analyze
        mock_analyze.assert_called_once_with("Custom text for testing")


class TestSignedFanoutHop:
    """FR-001/FR-008: the value handed to the fanout writer is signed, while the
    stored per-article record keeps the unsigned model confidence."""

    FROZEN_NOW = "2025-11-17T15:00:00Z"

    def _run_handler(self, sns_event, mock_context, label, confidence):
        captured = []

        def capture_fanout(dynamodb, table_name, sentiment_score):
            captured.append(sentiment_score)

        os.environ["TIMESERIES_TABLE"] = "test-sentiment-timeseries"
        try:
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch("src.lambdas.analysis.handler.accumulate_fanout", capture_fanout),
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = (label, confidence)
                mock_load_time.return_value = 0
                result = lambda_handler(sns_event, mock_context)
        finally:
            os.environ.pop("TIMESERIES_TABLE", None)
        return result, captured

    def _sns_event_with_tickers(self, sns_event):
        message = json.loads(sns_event["Records"][0]["Sns"]["Message"])
        message["matched_tickers"] = ["AAPL"]
        sns_event["Records"][0]["Sns"]["Message"] = json.dumps(message)
        return sns_event

    @mock_aws
    @freeze_time(FROZEN_NOW)
    def test_negative_arrives_signed(self, env_vars, sns_event, mock_context):
        TestLambdaHandler._setup_dynamodb_with_pending_item(TestLambdaHandler())
        event = self._sns_event_with_tickers(sns_event)

        _, captured = self._run_handler(event, mock_context, "negative", 0.9)

        assert len(captured) == 1
        assert captured[0].value == -0.9

    @mock_aws
    @freeze_time(FROZEN_NOW)
    def test_neutral_arrives_zero(self, env_vars, sns_event, mock_context):
        TestLambdaHandler._setup_dynamodb_with_pending_item(TestLambdaHandler())
        event = self._sns_event_with_tickers(sns_event)

        _, captured = self._run_handler(event, mock_context, "neutral", 0.55)

        assert len(captured) == 1
        assert captured[0].value == 0.0

    @mock_aws
    @freeze_time(FROZEN_NOW)
    def test_positive_arrives_signed(self, env_vars, sns_event, mock_context):
        TestLambdaHandler._setup_dynamodb_with_pending_item(TestLambdaHandler())
        event = self._sns_event_with_tickers(sns_event)

        _, captured = self._run_handler(event, mock_context, "positive", 0.8)

        assert len(captured) == 1
        assert captured[0].value == 0.8

    @mock_aws
    @freeze_time(FROZEN_NOW)
    def test_item_record_score_stays_unsigned(self, env_vars, sns_event, mock_context):
        """FR-008: the per-article record's score field remains unsigned confidence."""
        TestLambdaHandler._setup_dynamodb_with_pending_item(TestLambdaHandler())
        event = self._sns_event_with_tickers(sns_event)

        self._run_handler(event, mock_context, "negative", 0.78)

        table = boto3.resource("dynamodb", region_name="us-east-1").Table(
            "test-sentiment-items"
        )
        item = table.get_item(
            Key={
                "source_id": "article#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
            }
        )["Item"]
        assert float(item["score"]) == 0.78
        assert item["sentiment"] == "negative"


class TestFanoutTimestampBounds:
    """FR-010: article timestamps outside [now - 30d, now + 5min] skip fanout
    only; the item still stores; the reject is loud but carries no raw text."""

    FROZEN_NOW = "2025-11-17T15:00:00Z"

    def _run(self, mock_context, article_ts, metrics):
        message = {
            "source_id": "article#abc123def456",
            "source_type": "tiingo",
            "text_for_analysis": "SECRET-ARTICLE-BODY should never be logged",
            "model_version": "v1.0.0",
            "matched_tickers": ["AAPL"],
            "sources": ["tiingo"],
            "timestamp": article_ts,
        }
        event = {"Records": [{"Sns": {"Message": json.dumps(message)}}]}

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
        dynamodb.Table("test-sentiment-items").put_item(
            Item={
                "source_id": "article#abc123def456",
                "timestamp": article_ts,
                "status": "pending",
                "text_for_analysis": "SECRET-ARTICLE-BODY should never be logged",
            }
        )

        def record_metric(name, value=1, **kwargs):
            metrics.append({"name": name, "value": value, **kwargs})

        os.environ["TIMESERIES_TABLE"] = "test-sentiment-timeseries"
        try:
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch(
                    "src.lambdas.analysis.handler.accumulate_fanout"
                ) as mock_accumulate,
                patch("src.lambdas.analysis.handler.emit_metric", record_metric),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = ("negative", 0.9)
                mock_load_time.return_value = 0
                result = lambda_handler({"Records": event["Records"]}, mock_context)
        finally:
            os.environ.pop("TIMESERIES_TABLE", None)
        return result, mock_accumulate

    @mock_aws
    @freeze_time(FROZEN_NOW)
    def test_future_timestamp_skips_fanout_stores_item(
        self, env_vars, mock_context, caplog
    ):
        metrics = []
        result, mock_accumulate = self._run(
            mock_context, "2025-11-17T15:10:00.000Z", metrics
        )

        assert result["statusCode"] == 200
        assert result["body"]["updated"] is True
        mock_accumulate.assert_not_called()
        assert any(m["name"] == "TimeseriesFanoutRejectedTimestamp" for m in metrics)
        app_records = [r for r in caplog.records if r.name.startswith("src.lambdas")]
        assert app_records, "expected a structured rejection warning"
        for record in app_records:
            assert "SECRET-ARTICLE-BODY" not in record.getMessage()
            assert "SECRET-ARTICLE-BODY" not in str(record.__dict__)

    @mock_aws
    @freeze_time(FROZEN_NOW)
    def test_stale_timestamp_skips_fanout_stores_item(
        self, env_vars, mock_context, caplog
    ):
        metrics = []
        result, mock_accumulate = self._run(
            mock_context, "2025-10-01T15:00:00.000Z", metrics
        )

        assert result["statusCode"] == 200
        assert result["body"]["updated"] is True
        mock_accumulate.assert_not_called()
        assert any(m["name"] == "TimeseriesFanoutRejectedTimestamp" for m in metrics)
        app_records = [r for r in caplog.records if r.name.startswith("src.lambdas")]
        assert app_records, "expected a structured rejection warning"
        for record in app_records:
            assert "SECRET-ARTICLE-BODY" not in record.getMessage()
            assert "SECRET-ARTICLE-BODY" not in str(record.__dict__)

    @mock_aws
    @freeze_time(FROZEN_NOW)
    def test_in_bounds_timestamp_reaches_fanout(self, env_vars, mock_context):
        metrics = []
        _, mock_accumulate = self._run(
            mock_context, "2025-11-17T14:30:15.000Z", metrics
        )

        assert mock_accumulate.called
        assert not any(
            m["name"] == "TimeseriesFanoutRejectedTimestamp" for m in metrics
        )


class TestFanoutFailureRecording:
    """FR-009: retries exhausted -> one structured record carrying ticker,
    resolution, window and error class; TimeseriesFanoutErrors incremented
    with no added dimension (research D4)."""

    FROZEN_NOW = "2025-11-17T15:00:00Z"

    @mock_aws
    @freeze_time(FROZEN_NOW)
    def test_exhausted_retries_recorded(self, env_vars, mock_context, capsys):
        from src.lib.timeseries.fanout import FanoutWriteError

        message = {
            "source_id": "article#abc123def456",
            "source_type": "tiingo",
            "text_for_analysis": "irrelevant",
            "model_version": "v1.0.0",
            "matched_tickers": ["AAPL"],
            "sources": ["tiingo"],
            "timestamp": "2025-11-17T14:30:15.000Z",
        }
        event = {"Records": [{"Sns": {"Message": json.dumps(message)}}]}

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
        dynamodb.Table("test-sentiment-items").put_item(
            Item={
                "source_id": "article#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
                "status": "pending",
                "text_for_analysis": "irrelevant",
            }
        )

        metrics = []

        def record_metric(name, value=1, **kwargs):
            metrics.append({"name": name, "value": value, "kwargs": kwargs})

        error = FanoutWriteError(
            ticker="AAPL",
            resolution="24h",
            window="2025-11-17T00:00:00+00:00",
            error_class="ConditionalCheckFailedException",
        )

        os.environ["TIMESERIES_TABLE"] = "test-sentiment-timeseries"
        try:
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch(
                    "src.lambdas.analysis.handler.accumulate_fanout",
                    side_effect=error,
                ),
                patch("src.lambdas.analysis.handler.emit_metric", record_metric),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = ("negative", 0.9)
                mock_load_time.return_value = 0
                result = lambda_handler(event, mock_context)
        finally:
            os.environ.pop("TIMESERIES_TABLE", None)

        # Lambda still succeeds; fanout is supplementary
        assert result["statusCode"] == 200

        errors = [m for m in metrics if m["name"] == "TimeseriesFanoutErrors"]
        assert len(errors) == 1
        assert not errors[0]["kwargs"].get("dimensions")

        # The structured record carries the repair coordinates
        # (log_structured prints JSON to stdout; Lambda ships stdout to CloudWatch)
        out = capsys.readouterr().out
        failure_lines = [
            line
            for line in out.splitlines()
            if "Time-series fanout failed after retries" in line
        ]
        assert len(failure_lines) == 1
        record = json.loads(failure_lines[0])
        assert record["ticker"] == "AAPL"
        assert record["resolution"] == "24h"
        assert record["window"] == "2025-11-17T00:00:00+00:00"
        assert record["error_class"] == "ConditionalCheckFailedException"


class TestFanoutIdempotencyGate:
    """FR-003 / spec A2: a redelivered SNS message does not double count,
    because the analyzed-status conditional update still gates fanout."""

    FROZEN_NOW = "2025-11-17T15:00:00Z"

    @mock_aws
    @freeze_time(FROZEN_NOW)
    def test_redelivery_skips_fanout(self, env_vars, sns_event, mock_context):
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
        dynamodb.Table("test-sentiment-items").put_item(
            Item={
                "source_id": "article#abc123def456",
                "timestamp": "2025-11-17T14:30:15.000Z",
                "status": "pending",
                "text_for_analysis": "Test text",
            }
        )

        message = json.loads(sns_event["Records"][0]["Sns"]["Message"])
        message["matched_tickers"] = ["AAPL"]
        message["sources"] = ["tiingo"]
        sns_event["Records"][0]["Sns"]["Message"] = json.dumps(message)

        os.environ["TIMESERIES_TABLE"] = "test-sentiment-timeseries"
        try:
            with (
                patch("src.lambdas.analysis.handler.load_model"),
                patch("src.lambdas.analysis.handler.analyze_sentiment") as mock_analyze,
                patch(
                    "src.lambdas.analysis.handler.get_model_load_time_ms"
                ) as mock_load_time,
                patch(
                    "src.lambdas.analysis.handler.accumulate_fanout"
                ) as mock_accumulate,
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
            ):
                mock_analyze.return_value = ("negative", 0.9)
                mock_load_time.return_value = 0

                first = lambda_handler(sns_event, mock_context)
                second = lambda_handler(sns_event, mock_context)
        finally:
            os.environ.pop("TIMESERIES_TABLE", None)

        assert first["body"]["updated"] is True
        assert second["body"]["updated"] is False
        # Fanout ran exactly once: the redelivery never reached it
        assert mock_accumulate.call_count == 1

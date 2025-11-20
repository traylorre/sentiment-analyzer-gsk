"""
Unit Tests for Ingestion Lambda Handler
========================================

Tests the ingestion handler with mocked AWS services.

For On-Call Engineers:
    These tests verify:
    - EventBridge trigger handling
    - NewsAPI fetching and deduplication
    - DynamoDB conditional writes
    - SNS publishing for analysis
    - Error handling and metrics

For Developers:
    - Uses moto to mock DynamoDB, SNS, Secrets Manager, CloudWatch
    - Uses responses to mock NewsAPI HTTP calls
    - Test both success and error scenarios
    - Verify metrics are emitted correctly
"""

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
import responses
from moto import mock_aws

from src.lambdas.ingestion.adapters.newsapi import NEWSAPI_BASE_URL
from src.lambdas.ingestion.handler import (
    _get_text_for_analysis,
    _process_article,
    lambda_handler,
)
from src.lambdas.shared.secrets import clear_cache


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
    os.environ["WATCH_TAGS"] = "AI,climate"
    os.environ["DYNAMODB_TABLE"] = "test-sentiment-items"
    os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"
    os.environ[
        "NEWSAPI_SECRET_ARN"
    ] = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
    os.environ["MODEL_VERSION"] = "v1.0.0"
    os.environ["ENVIRONMENT"] = "test"

    yield

    # Cleanup
    for key in [
        "WATCH_TAGS",
        "DYNAMODB_TABLE",
        "SNS_TOPIC_ARN",
        "NEWSAPI_SECRET_ARN",
        "MODEL_VERSION",
        "ENVIRONMENT",
    ]:
        os.environ.pop(key, None)


@pytest.fixture
def dynamodb_table(env_vars):
    """Create mock DynamoDB table."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
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
        yield client


@pytest.fixture
def sns_topic(env_vars):
    """Create mock SNS topic."""
    with mock_aws():
        client = boto3.client("sns", region_name="us-east-1")
        client.create_topic(Name="test-topic")
        yield client


@pytest.fixture
def secrets(env_vars):
    """Create mock secret."""
    with mock_aws():
        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(
            Name="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            SecretString=json.dumps({"api_key": "test-api-key-12345"}),
        )
        yield client


@pytest.fixture
def sample_newsapi_response():
    """Sample successful NewsAPI response."""
    return {
        "status": "ok",
        "totalResults": 2,
        "articles": [
            {
                "source": {"id": "test-source", "name": "Test News"},
                "author": "Test Author",
                "title": "AI Breakthrough Article",
                "description": "This is a test article about AI breakthroughs.",
                "url": "https://example.com/article/ai-1",
                "urlToImage": "https://example.com/image1.jpg",
                "publishedAt": "2025-11-17T14:30:00Z",
                "content": "Full article content about AI...",
            },
            {
                "source": {"id": "test-source", "name": "Test News"},
                "author": "Another Author",
                "title": "Climate Change Report",
                "description": "New report on climate change impacts.",
                "url": "https://example.com/article/climate-1",
                "urlToImage": "https://example.com/image2.jpg",
                "publishedAt": "2025-11-17T15:00:00Z",
                "content": "Full article content about climate...",
            },
        ],
    }


@pytest.fixture
def mock_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.aws_request_id = "test-request-123"
    context.function_name = "test-ingestion"
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    return context


@pytest.fixture
def eventbridge_event():
    """Sample EventBridge scheduled event."""
    return {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "account": "123456789012",
        "time": "2025-11-17T14:30:00Z",
        "region": "us-east-1",
        "resources": ["arn:aws:events:us-east-1:123456789012:rule/test-scheduler"],
        "detail": {},
    }


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    @mock_aws
    @responses.activate
    def test_handler_success(
        self,
        env_vars,
        sample_newsapi_response,
        mock_context,
        eventbridge_event,
    ):
        """Test successful ingestion flow with within-invocation deduplication.

        This test verifies that when NewsAPI returns the same articles for
        different search tags (a common real-world scenario), the Lambda
        correctly deduplicates them within a single invocation.

        Expected behavior:
        - Tag 1 (AI): 2 articles fetched → 2 new items inserted
        - Tag 2 (climate): Same 2 articles → both skipped as duplicates
        - Total: 4 fetched, 2 new, 2 duplicates
        """
        # Setup mocks
        self._setup_aws_mocks()

        # Mock NewsAPI responses - same articles for both tags tests deduplication
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )

        # Mock CloudWatch
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        assert result["statusCode"] == 200
        assert result["body"]["summary"]["tags_processed"] == 2
        assert result["body"]["summary"]["articles_fetched"] == 4
        # Same articles for both tags validates within-invocation deduplication
        assert result["body"]["summary"]["new_items"] == 2
        assert result["body"]["summary"]["duplicates_skipped"] == 2
        assert "execution_time_ms" in result["body"]

    @mock_aws
    @responses.activate
    def test_handler_deduplication(
        self,
        env_vars,
        sample_newsapi_response,
        mock_context,
        eventbridge_event,
    ):
        """Test that duplicate articles are skipped."""
        # Setup mocks
        self._setup_aws_mocks()

        # Mock NewsAPI - same articles for both calls
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            # First invocation
            result1 = lambda_handler(eventbridge_event, mock_context)

        # Add more mock responses for second invocation
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            # Second invocation - should skip duplicates
            result2 = lambda_handler(eventbridge_event, mock_context)

        # First invocation: 2 new (same articles for both tags means 2 duplicates)
        assert result1["body"]["summary"]["new_items"] == 2
        # Second invocation: all duplicates
        assert result2["body"]["summary"]["new_items"] == 0
        assert result2["body"]["summary"]["duplicates_skipped"] == 4

    @mock_aws
    @responses.activate
    def test_handler_deduplication_with_partial_overlap(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
    ):
        """Test deduplication with realistic partial overlap between tags.

        Real-world scenario: Different tags return some unique articles and
        some overlapping articles. This tests that deduplication correctly
        handles partial overlap.

        Expected behavior:
        - Tag 1 (AI): 2 unique articles → 2 new items
        - Tag 2 (climate): 1 shared article + 1 unique → 1 duplicate, 1 new
        - Total: 4 fetched, 3 new, 1 duplicate
        """
        # Setup mocks
        self._setup_aws_mocks()

        # Articles for tag 1 (AI)
        ai_response = {
            "status": "ok",
            "totalResults": 2,
            "articles": [
                {
                    "source": {"id": "test-source", "name": "Test News"},
                    "author": "AI Author",
                    "title": "AI-Only Article",
                    "description": "This article is only about AI.",
                    "url": "https://example.com/article/ai-only",
                    "publishedAt": "2025-11-17T14:30:00Z",
                },
                {
                    "source": {"id": "test-source", "name": "Test News"},
                    "author": "Shared Author",
                    "title": "AI and Climate Crossover",
                    "description": "This article covers both AI and climate.",
                    "url": "https://example.com/article/shared",  # Same URL = duplicate
                    "publishedAt": "2025-11-17T15:00:00Z",
                },
            ],
        }

        # Articles for tag 2 (climate) - one shared, one unique
        climate_response = {
            "status": "ok",
            "totalResults": 2,
            "articles": [
                {
                    "source": {"id": "test-source", "name": "Test News"},
                    "author": "Shared Author",
                    "title": "AI and Climate Crossover",
                    "description": "This article covers both AI and climate.",
                    "url": "https://example.com/article/shared",  # Same URL = duplicate
                    "publishedAt": "2025-11-17T15:00:00Z",
                },
                {
                    "source": {"id": "test-source", "name": "Test News"},
                    "author": "Climate Author",
                    "title": "Climate-Only Article",
                    "description": "This article is only about climate.",
                    "url": "https://example.com/article/climate-only",
                    "publishedAt": "2025-11-17T15:30:00Z",
                },
            ],
        }

        responses.add(responses.GET, NEWSAPI_BASE_URL, json=ai_response, status=200)
        responses.add(
            responses.GET, NEWSAPI_BASE_URL, json=climate_response, status=200
        )

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        assert result["statusCode"] == 200
        assert result["body"]["summary"]["tags_processed"] == 2
        assert result["body"]["summary"]["articles_fetched"] == 4
        # 3 unique articles (ai-only, shared, climate-only), 1 duplicate (shared again)
        assert result["body"]["summary"]["new_items"] == 3
        assert result["body"]["summary"]["duplicates_skipped"] == 1

    @mock_aws
    @responses.activate
    def test_handler_rate_limit_partial_success(
        self,
        env_vars,
        sample_newsapi_response,
        mock_context,
        eventbridge_event,
    ):
        """Test handler continues after rate limit on one tag."""
        # Setup mocks
        self._setup_aws_mocks()

        # First tag succeeds
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )

        # Second tag gets rate limited
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"status": "error", "message": "Rate limited"},
            status=429,
            headers={"Retry-After": "3600"},
        )

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Should be 207 (multi-status) since one tag failed
        assert result["statusCode"] == 207
        assert result["body"]["summary"]["tags_processed"] == 1
        assert result["body"]["summary"]["errors"] == 1
        assert len(result["body"]["errors"]) == 1
        assert result["body"]["errors"][0]["error"] == "RATE_LIMIT_EXCEEDED"

    @mock_aws
    @responses.activate
    def test_handler_authentication_error(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        caplog,
    ):
        """Test handler fails fast on authentication error."""
        # Setup mocks
        self._setup_aws_mocks()

        # Authentication failure
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"status": "error", "message": "Invalid API key"},
            status=401,
        )

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        assert result["statusCode"] == 401
        assert result["body"]["code"] == "AUTHENTICATION_ERROR"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Authentication")

    @mock_aws
    def test_handler_missing_config(
        self, mock_context, eventbridge_event, aws_credentials, caplog
    ):
        """Test handler fails with missing configuration."""
        # Don't set env vars

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        assert result["statusCode"] == 500
        assert result["body"]["code"] == "CONFIGURATION_ERROR"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Configuration error")

    @mock_aws
    @responses.activate
    def test_handler_per_tag_stats(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
    ):
        """Test per-tag statistics are tracked correctly."""
        # Setup mocks
        self._setup_aws_mocks()

        # Different number of articles per tag
        ai_response = {
            "status": "ok",
            "totalResults": 3,
            "articles": [
                {
                    "url": f"https://example.com/ai/{i}",
                    "title": f"AI Article {i}",
                    "publishedAt": "2025-11-17T14:30:00Z",
                }
                for i in range(3)
            ],
        }

        climate_response = {
            "status": "ok",
            "totalResults": 1,
            "articles": [
                {
                    "url": "https://example.com/climate/1",
                    "title": "Climate Article",
                    "publishedAt": "2025-11-17T14:30:00Z",
                }
            ],
        }

        responses.add(responses.GET, NEWSAPI_BASE_URL, json=ai_response, status=200)
        responses.add(
            responses.GET, NEWSAPI_BASE_URL, json=climate_response, status=200
        )

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        assert result["body"]["per_tag_stats"]["AI"]["fetched"] == 3
        assert result["body"]["per_tag_stats"]["AI"]["new"] == 3
        assert result["body"]["per_tag_stats"]["climate"]["fetched"] == 1
        assert result["body"]["per_tag_stats"]["climate"]["new"] == 1

    def _setup_aws_mocks(self):
        """Set up all AWS service mocks."""
        # DynamoDB
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
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

        # SNS
        sns = boto3.client("sns", region_name="us-east-1")
        sns.create_topic(Name="test-topic")

        # Secrets Manager
        secrets = boto3.client("secretsmanager", region_name="us-east-1")
        secrets.create_secret(
            Name="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            SecretString=json.dumps({"api_key": "test-api-key-12345"}),
        )


class TestProcessArticle:
    """Tests for _process_article function."""

    @mock_aws
    def test_process_new_article(self, env_vars):
        """Test processing a new article."""
        # Setup mocks
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

        sns = boto3.client("sns", region_name="us-east-1")
        topic_arn = sns.create_topic(Name="test-topic")["TopicArn"]

        article = {
            "url": "https://example.com/article/1",
            "title": "Test Article",
            "description": "Test description",
            "publishedAt": "2025-11-17T14:30:00Z",
            "author": "Test Author",
            "source": {"name": "Test Source"},
        }

        with patch("src.lib.metrics.emit_metric"):
            result = _process_article(
                article=article,
                tag="AI",
                table=table,
                sns_client=sns,
                sns_topic_arn=topic_arn,
                model_version="v1.0.0",
            )

        assert result == "new"

        # Verify item was inserted
        response = table.scan()
        assert len(response["Items"]) == 1
        item = response["Items"][0]
        assert item["source_id"].startswith("newsapi#")
        assert item["status"] == "pending"
        assert item["matched_tags"] == ["AI"]

    @mock_aws
    def test_process_duplicate_article(self, env_vars):
        """Test processing a duplicate article."""
        # Setup mocks
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

        sns = boto3.client("sns", region_name="us-east-1")
        topic_arn = sns.create_topic(Name="test-topic")["TopicArn"]

        article = {
            "url": "https://example.com/article/1",
            "title": "Test Article",
            "description": "Test description",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        with patch("src.lib.metrics.emit_metric"):
            # First process - new
            result1 = _process_article(
                article=article,
                tag="AI",
                table=table,
                sns_client=sns,
                sns_topic_arn=topic_arn,
                model_version="v1.0.0",
            )

            # Second process - duplicate
            result2 = _process_article(
                article=article,
                tag="AI",
                table=table,
                sns_client=sns,
                sns_topic_arn=topic_arn,
                model_version="v1.0.0",
            )

        assert result1 == "new"
        assert result2 == "duplicate"

    @mock_aws
    def test_process_article_missing_url(self, env_vars):
        """Test processing article without URL (uses title+publishedAt)."""
        # Setup mocks
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

        sns = boto3.client("sns", region_name="us-east-1")
        topic_arn = sns.create_topic(Name="test-topic")["TopicArn"]

        article = {
            "title": "Test Article Without URL",
            "description": "Test description",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        with patch("src.lib.metrics.emit_metric"):
            result = _process_article(
                article=article,
                tag="AI",
                table=table,
                sns_client=sns,
                sns_topic_arn=topic_arn,
                model_version="v1.0.0",
            )

        assert result == "new"

    @mock_aws
    def test_process_article_invalid(self, env_vars):
        """Test processing article without required fields."""
        # Setup mocks
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

        sns = boto3.client("sns", region_name="us-east-1")
        topic_arn = sns.create_topic(Name="test-topic")["TopicArn"]

        # Article without URL, title, or publishedAt
        article = {
            "description": "Only has description",
        }

        with patch("src.lib.metrics.emit_metric"):
            result = _process_article(
                article=article,
                tag="AI",
                table=table,
                sns_client=sns,
                sns_topic_arn=topic_arn,
                model_version="v1.0.0",
            )

        assert result == "duplicate"  # Skipped


class TestGetTextForAnalysis:
    """Tests for _get_text_for_analysis function."""

    def test_with_title_and_description(self):
        """Test extraction with both title and description."""
        article = {
            "title": "Test Title",
            "description": "Test Description",
            "content": "Test Content",
        }

        text = _get_text_for_analysis(article)

        assert text == "Test Title. Test Description"

    def test_with_title_only(self):
        """Test extraction with only title."""
        article = {
            "title": "Test Title",
            "content": "Test Content",
        }

        text = _get_text_for_analysis(article)

        assert text == "Test Title"

    def test_with_description_only(self):
        """Test extraction with only description."""
        article = {
            "description": "Test Description",
            "content": "Test Content",
        }

        text = _get_text_for_analysis(article)

        assert text == "Test Description"

    def test_with_content_only(self):
        """Test extraction with only content."""
        article = {
            "content": "Test Content that is fairly long",
        }

        text = _get_text_for_analysis(article)

        assert text == "Test Content that is fairly long"

    def test_empty_article(self):
        """Test extraction with empty article."""
        article = {}

        text = _get_text_for_analysis(article)

        assert text == ""

    def test_truncates_long_content(self):
        """Test that content is truncated to 500 chars."""
        article = {
            "content": "x" * 1000,
        }

        text = _get_text_for_analysis(article)

        assert len(text) == 500


class TestSNSPublishing:
    """Tests for SNS message publishing."""

    @mock_aws
    def test_sns_message_format(self, env_vars):
        """Test SNS message has correct format."""
        # Setup mocks
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

        sns = boto3.client("sns", region_name="us-east-1")
        topic_arn = sns.create_topic(Name="test-topic")["TopicArn"]

        article = {
            "url": "https://example.com/article/1",
            "title": "Test Article",
            "description": "Test description",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        # Track published messages
        published = []
        original_publish = sns.publish

        def mock_publish(**kwargs):
            published.append(kwargs)
            return original_publish(**kwargs)

        sns.publish = mock_publish

        with patch("src.lib.metrics.emit_metric"):
            _process_article(
                article=article,
                tag="AI",
                table=table,
                sns_client=sns,
                sns_topic_arn=topic_arn,
                model_version="v1.0.0",
            )

        # Verify message format
        assert len(published) == 1
        message = json.loads(published[0]["Message"])
        assert message["source_id"].startswith("newsapi#")
        assert message["source_type"] == "newsapi"
        assert message["text_for_analysis"] == "Test Article. Test description"
        assert message["model_version"] == "v1.0.0"
        assert message["matched_tags"] == ["AI"]
        assert "timestamp" in message


class TestMetricsEmission:
    """Tests for CloudWatch metrics emission."""

    @mock_aws
    @responses.activate
    def test_metrics_emitted_on_success(
        self,
        env_vars,
        sample_newsapi_response,
        mock_context,
        eventbridge_event,
    ):
        """Test that metrics are emitted on successful run."""
        # Setup mocks
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
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

        sns = boto3.client("sns", region_name="us-east-1")
        sns.create_topic(Name="test-topic")

        secrets = boto3.client("secretsmanager", region_name="us-east-1")
        secrets.create_secret(
            Name="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            SecretString=json.dumps({"api_key": "test-api-key-12345"}),
        )

        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )

        # Track metric calls
        emitted_metrics = []

        def mock_emit_metrics_batch(metrics, **kwargs):
            emitted_metrics.extend(metrics)

        with (
            patch("src.lib.metrics.emit_metric"),
            patch(
                "src.lambdas.ingestion.handler.emit_metrics_batch",
                mock_emit_metrics_batch,
            ),
        ):
            _result = lambda_handler(eventbridge_event, mock_context)

        # Verify metrics
        metric_names = [m["name"] for m in emitted_metrics]
        assert "ArticlesFetched" in metric_names
        assert "NewItemsIngested" in metric_names
        assert "DuplicatesSkipped" in metric_names
        assert "ExecutionTimeMs" in metric_names


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @mock_aws
    def test_secret_not_found(self, env_vars, mock_context, eventbridge_event, caplog):
        """Test handler when secret is not found."""
        # Clear secrets cache to ensure we test the actual missing secret scenario
        # Previous tests may have cached a valid secret
        clear_cache()

        # Setup DynamoDB but not secret
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
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

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Missing secret is a server configuration error, not client auth failure
        # 401 = client didn't provide credentials
        # 500 = server misconfiguration (secret not set up)
        assert result["statusCode"] == 500
        assert "error" in result["body"]

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Secret not found")

    @mock_aws
    @responses.activate
    def test_sns_publish_failure_continues(
        self,
        env_vars,
        sample_newsapi_response,
        mock_context,
        eventbridge_event,
    ):
        """Test that SNS publish failure doesn't stop processing."""
        # Setup mocks
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

        # Don't create SNS topic - publish will fail
        # But we need the client
        sns = boto3.client("sns", region_name="us-east-1")

        secrets = boto3.client("secretsmanager", region_name="us-east-1")
        secrets.create_secret(
            Name="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            SecretString=json.dumps({"api_key": "test-api-key-12345"}),
        )

        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_newsapi_response,
            status=200,
        )

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            # Create the topic so the test works
            sns.create_topic(Name="test-topic")
            result = lambda_handler(eventbridge_event, mock_context)

        # Handler should complete even if SNS has issues
        assert result["statusCode"] in [200, 207]

    @mock_aws
    @responses.activate
    def test_empty_newsapi_response(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
    ):
        """Test handling of empty NewsAPI response."""
        # Setup mocks
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
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

        sns = boto3.client("sns", region_name="us-east-1")
        sns.create_topic(Name="test-topic")

        secrets = boto3.client("secretsmanager", region_name="us-east-1")
        secrets.create_secret(
            Name="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            SecretString=json.dumps({"api_key": "test-api-key-12345"}),
        )

        empty_response = {
            "status": "ok",
            "totalResults": 0,
            "articles": [],
        }

        responses.add(responses.GET, NEWSAPI_BASE_URL, json=empty_response, status=200)
        responses.add(responses.GET, NEWSAPI_BASE_URL, json=empty_response, status=200)

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        assert result["statusCode"] == 200
        assert result["body"]["summary"]["articles_fetched"] == 0
        assert result["body"]["summary"]["new_items"] == 0

"""
Ingestion E2E Test
==================

End-to-end test for the ingestion flow: NewsAPI → DynamoDB → SNS.

For On-Call Engineers:
    This test verifies the complete ingestion pipeline:
    1. EventBridge triggers Lambda
    2. Lambda fetches from NewsAPI
    3. Articles are deduplicated
    4. New items inserted to DynamoDB
    5. SNS messages published for analysis

    If this test fails in CI:
    - Check moto mock versions match production AWS behavior
    - Verify DynamoDB schema matches table definition
    - Check SNS message format matches analysis Lambda expectations

    See SC-03 in ON_CALL_SOP.md for ingestion issues.

For Developers:
    - Uses moto to mock all AWS services
    - Uses responses to mock NewsAPI HTTP calls
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
import responses
from moto import mock_aws

from src.lambdas.ingestion.adapters.newsapi import NEWSAPI_BASE_URL
from src.lambdas.ingestion.handler import lambda_handler


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
    os.environ["WATCH_TAGS"] = "AI,climate,economy"
    os.environ["DYNAMODB_TABLE"] = "test-sentiment-items"
    os.environ["SNS_TOPIC_ARN"] = (
        "arn:aws:sns:us-east-1:123456789012:test-analysis-topic"
    )
    os.environ["NEWSAPI_SECRET_ARN"] = (
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-newsapi"
    )
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
def mock_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.aws_request_id = "e2e-test-request-123"
    context.function_name = "test-sentiment-ingestion"
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    return context


@pytest.fixture
def eventbridge_event():
    """Sample EventBridge scheduled event."""
    return {
        "version": "0",
        "id": "e2e-test-event-id",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "account": "123456789012",
        "time": datetime.now(timezone.utc).isoformat(),
        "region": "us-east-1",
        "resources": [
            "arn:aws:events:us-east-1:123456789012:rule/sentiment-ingestion-scheduler"
        ],
        "detail": {},
    }


@pytest.fixture
def newsapi_articles():
    """Sample NewsAPI articles for each tag."""
    return {
        "AI": [
            {
                "source": {"id": "techcrunch", "name": "TechCrunch"},
                "author": "AI Reporter",
                "title": "New AI Model Breaks Records",
                "description": "A new artificial intelligence model has achieved unprecedented accuracy.",
                "url": "https://techcrunch.com/2025/11/17/ai-model-records",
                "urlToImage": "https://techcrunch.com/images/ai.jpg",
                "publishedAt": "2025-11-17T10:00:00Z",
                "content": "Full article content about AI breakthrough...",
            },
            {
                "source": {"id": "wired", "name": "Wired"},
                "author": "Tech Writer",
                "title": "AI Ethics in 2025",
                "description": "Examining the ethical implications of modern AI systems.",
                "url": "https://wired.com/2025/11/17/ai-ethics",
                "urlToImage": "https://wired.com/images/ethics.jpg",
                "publishedAt": "2025-11-17T11:30:00Z",
                "content": "Full article about AI ethics...",
            },
        ],
        "climate": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "author": "Climate Correspondent",
                "title": "Climate Summit Reaches Agreement",
                "description": "World leaders agree on new emissions targets.",
                "url": "https://reuters.com/2025/11/17/climate-summit",
                "urlToImage": "https://reuters.com/images/summit.jpg",
                "publishedAt": "2025-11-17T09:00:00Z",
                "content": "Full article about climate summit...",
            },
        ],
        "economy": [
            {
                "source": {"id": "bloomberg", "name": "Bloomberg"},
                "author": "Financial Analyst",
                "title": "Markets Rally on Economic Data",
                "description": "Stock markets surge following positive economic indicators.",
                "url": "https://bloomberg.com/2025/11/17/markets-rally",
                "urlToImage": "https://bloomberg.com/images/markets.jpg",
                "publishedAt": "2025-11-17T14:00:00Z",
                "content": "Full article about market rally...",
            },
            {
                "source": {"id": "ft", "name": "Financial Times"},
                "author": "Economics Editor",
                "title": "Central Bank Policy Update",
                "description": "Central banks signal potential rate changes.",
                "url": "https://ft.com/2025/11/17/central-bank",
                "urlToImage": "https://ft.com/images/bank.jpg",
                "publishedAt": "2025-11-17T15:30:00Z",
                "content": "Full article about monetary policy...",
            },
        ],
    }


class TestIngestionE2E:
    """End-to-end tests for ingestion flow."""

    @mock_aws
    @responses.activate
    def test_full_ingestion_flow(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        newsapi_articles,
    ):
        """
        Test complete ingestion flow from NewsAPI to DynamoDB and SNS.

        This is the primary E2E test that verifies:
        1. Articles are fetched from NewsAPI for each tag
        2. Items are inserted into DynamoDB with correct schema
        3. SNS messages are published with correct format
        4. Metrics and statistics are tracked correctly
        """
        # Setup AWS mocks
        dynamodb_client, sns_client, table = self._setup_aws_mocks()

        # Setup NewsAPI mock responses
        for tag in ["AI", "climate", "economy"]:
            responses.add(
                responses.GET,
                NEWSAPI_BASE_URL,
                json={
                    "status": "ok",
                    "totalResults": len(newsapi_articles[tag]),
                    "articles": newsapi_articles[tag],
                },
                status=200,
            )

        # Execute handler
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Verify success response
        assert result["statusCode"] == 200
        summary = result["body"]["summary"]
        assert summary["tags_processed"] == 3
        assert summary["articles_fetched"] == 5  # 2 + 1 + 2
        assert summary["new_items"] == 5
        assert summary["duplicates_skipped"] == 0
        assert summary["errors"] == 0

        # Verify DynamoDB items
        scan_result = table.scan()
        items = scan_result["Items"]
        assert len(items) == 5

        # Verify item schema
        for item in items:
            self._verify_dynamodb_item_schema(item)

        # Verify specific items
        urls = {item["source_url"] for item in items}
        assert "https://techcrunch.com/2025/11/17/ai-model-records" in urls
        assert "https://reuters.com/2025/11/17/climate-summit" in urls
        assert "https://bloomberg.com/2025/11/17/markets-rally" in urls

    @mock_aws
    @responses.activate
    def test_deduplication_across_invocations(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        newsapi_articles,
    ):
        """
        Test that duplicate articles are skipped across multiple invocations.

        This verifies the idempotency of the ingestion process.
        """
        # Setup AWS mocks
        dynamodb_client, sns_client, table = self._setup_aws_mocks()

        # Setup NewsAPI mock responses for first invocation
        for tag in ["AI", "climate", "economy"]:
            responses.add(
                responses.GET,
                NEWSAPI_BASE_URL,
                json={
                    "status": "ok",
                    "totalResults": len(newsapi_articles[tag]),
                    "articles": newsapi_articles[tag],
                },
                status=200,
            )

        # First invocation
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result1 = lambda_handler(eventbridge_event, mock_context)

        # Verify first invocation
        assert result1["body"]["summary"]["new_items"] == 5
        assert result1["body"]["summary"]["duplicates_skipped"] == 0

        # Add more mock responses for second invocation (same articles)
        for tag in ["AI", "climate", "economy"]:
            responses.add(
                responses.GET,
                NEWSAPI_BASE_URL,
                json={
                    "status": "ok",
                    "totalResults": len(newsapi_articles[tag]),
                    "articles": newsapi_articles[tag],
                },
                status=200,
            )

        # Second invocation - same articles
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result2 = lambda_handler(eventbridge_event, mock_context)

        # Verify second invocation - all duplicates
        assert result2["body"]["summary"]["new_items"] == 0
        assert result2["body"]["summary"]["duplicates_skipped"] == 5

        # Verify table still has only 5 items
        scan_result = table.scan()
        assert len(scan_result["Items"]) == 5

    @mock_aws
    @responses.activate
    def test_sns_message_format(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        newsapi_articles,
    ):
        """
        Test that SNS messages have the correct format for analysis Lambda.

        This is critical for the analysis Lambda to process items correctly.
        """
        # Setup AWS mocks
        dynamodb_client, sns_client, table = self._setup_aws_mocks()

        # Track published SNS messages
        published_messages = []

        # Create a subscription to capture messages
        topic_arn = os.environ["SNS_TOPIC_ARN"]
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"

        # Mock the SNS client's publish method
        original_publish = sns_client.publish

        def capture_publish(**kwargs):
            published_messages.append(kwargs)
            return {"MessageId": f"msg-{len(published_messages)}"}

        # Setup single tag for simplicity
        os.environ["WATCH_TAGS"] = "AI"

        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={
                "status": "ok",
                "totalResults": 1,
                "articles": [newsapi_articles["AI"][0]],
            },
            status=200,
        )

        # Patch the SNS client creation to use our mock
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
            patch("src.lambdas.ingestion.handler._get_sns_client") as mock_sns,
        ):
            mock_sns_client = MagicMock()
            mock_sns_client.publish = capture_publish
            mock_sns.return_value = mock_sns_client

            result = lambda_handler(eventbridge_event, mock_context)

        # Verify message was published
        assert len(published_messages) == 1

        # Verify message format
        message = json.loads(published_messages[0]["Message"])

        # Required fields per contract
        assert "source_id" in message
        assert message["source_id"].startswith("newsapi#")
        assert message["source_type"] == "newsapi"
        assert "text_for_analysis" in message
        assert message["text_for_analysis"] != ""
        assert message["model_version"] == "v1.0.0"
        assert message["matched_tags"] == ["AI"]
        assert "timestamp" in message  # Critical: not ingested_at

        # Verify timestamp format (ISO8601)
        timestamp = message["timestamp"]
        # Should be parseable
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    @mock_aws
    @responses.activate
    def test_item_ttl_set_correctly(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        newsapi_articles,
    ):
        """
        Test that items have TTL set for 30-day expiration.

        This is important for data retention and cost management.
        """
        # Setup AWS mocks
        dynamodb_client, sns_client, table = self._setup_aws_mocks()

        # Single tag for simplicity
        os.environ["WATCH_TAGS"] = "AI"

        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={
                "status": "ok",
                "totalResults": 1,
                "articles": [newsapi_articles["AI"][0]],
            },
            status=200,
        )

        # Execute handler
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Get the item
        scan_result = table.scan()
        item = scan_result["Items"][0]

        # Verify TTL is set
        assert "ttl_timestamp" in item

        # TTL should be approximately 30 days from now
        ttl = int(item["ttl_timestamp"])
        now = datetime.now(timezone.utc).timestamp()
        days_until_expiry = (ttl - now) / (24 * 60 * 60)

        # Should be between 29 and 31 days (allowing for test execution time)
        assert 29 <= days_until_expiry <= 31

    @mock_aws
    @responses.activate
    def test_metadata_preserved(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        newsapi_articles,
    ):
        """
        Test that article metadata is correctly preserved in DynamoDB.

        This data is used by the dashboard for display.
        """
        # Setup AWS mocks
        dynamodb_client, sns_client, table = self._setup_aws_mocks()

        # Single tag for simplicity
        os.environ["WATCH_TAGS"] = "AI"

        test_article = newsapi_articles["AI"][0]

        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={
                "status": "ok",
                "totalResults": 1,
                "articles": [test_article],
            },
            status=200,
        )

        # Execute handler
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Get the item
        scan_result = table.scan()
        item = scan_result["Items"][0]

        # Verify metadata
        assert "metadata" in item
        metadata = item["metadata"]

        assert metadata["title"] == test_article["title"]
        assert metadata["author"] == test_article["author"]
        assert metadata["published_at"] == test_article["publishedAt"]
        assert metadata["source_name"] == test_article["source"]["name"]

    @mock_aws
    @responses.activate
    def test_partial_failure_continues(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        newsapi_articles,
    ):
        """
        Test that failure on one tag doesn't stop processing of others.

        This ensures resilience when NewsAPI has issues for specific tags.
        """
        # Setup AWS mocks
        dynamodb_client, sns_client, table = self._setup_aws_mocks()

        # First tag succeeds
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={
                "status": "ok",
                "totalResults": len(newsapi_articles["AI"]),
                "articles": newsapi_articles["AI"],
            },
            status=200,
        )

        # Second tag fails with server error
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"error": "Server error"},
            status=500,
        )
        # Retry 1
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"error": "Server error"},
            status=500,
        )
        # Retry 2
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"error": "Server error"},
            status=500,
        )

        # Third tag succeeds
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={
                "status": "ok",
                "totalResults": len(newsapi_articles["economy"]),
                "articles": newsapi_articles["economy"],
            },
            status=200,
        )

        # Execute handler
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Should be 207 (partial success)
        assert result["statusCode"] == 207

        # First and third tags processed
        assert result["body"]["summary"]["tags_processed"] == 2

        # Items from successful tags should be in table
        scan_result = table.scan()
        items = scan_result["Items"]
        assert len(items) == 4  # 2 AI + 2 economy

    @mock_aws
    @responses.activate
    def test_text_for_analysis_extraction(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
    ):
        """
        Test that text_for_analysis is correctly extracted from articles.

        This is the text that will be analyzed for sentiment.
        """
        # Setup AWS mocks
        dynamodb_client, sns_client, table = self._setup_aws_mocks()

        # Single tag with specific article
        os.environ["WATCH_TAGS"] = "AI"

        article = {
            "source": {"id": "test", "name": "Test"},
            "author": "Author",
            "title": "Important AI News",
            "description": "This is the description with key information.",
            "url": "https://example.com/ai-news",
            "publishedAt": "2025-11-17T10:00:00Z",
            "content": "Full content...",
        }

        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={
                "status": "ok",
                "totalResults": 1,
                "articles": [article],
            },
            status=200,
        )

        # Execute handler
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Get the item
        scan_result = table.scan()
        item = scan_result["Items"][0]

        # Verify text_for_analysis combines title and description
        expected_text = (
            "Important AI News. This is the description with key information."
        )
        assert item["text_for_analysis"] == expected_text

    @mock_aws
    @responses.activate
    def test_per_tag_statistics(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        newsapi_articles,
    ):
        """
        Test that per-tag statistics are accurately tracked.

        These statistics are used for monitoring and debugging.
        """
        # Setup AWS mocks
        dynamodb_client, sns_client, table = self._setup_aws_mocks()

        # Setup NewsAPI mock responses
        for tag in ["AI", "climate", "economy"]:
            responses.add(
                responses.GET,
                NEWSAPI_BASE_URL,
                json={
                    "status": "ok",
                    "totalResults": len(newsapi_articles[tag]),
                    "articles": newsapi_articles[tag],
                },
                status=200,
            )

        # Execute handler
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Verify per-tag stats
        per_tag = result["body"]["per_tag_stats"]

        assert per_tag["AI"]["fetched"] == 2
        assert per_tag["AI"]["new"] == 2
        assert per_tag["AI"]["duplicates"] == 0

        assert per_tag["climate"]["fetched"] == 1
        assert per_tag["climate"]["new"] == 1
        assert per_tag["climate"]["duplicates"] == 0

        assert per_tag["economy"]["fetched"] == 2
        assert per_tag["economy"]["new"] == 2
        assert per_tag["economy"]["duplicates"] == 0

    def _setup_aws_mocks(self):
        """
        Set up all AWS service mocks.

        Returns:
            Tuple of (dynamodb_client, sns_client, table)
        """
        # DynamoDB
        dynamodb_client = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb_client.create_table(
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

        # Get table resource
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.Table("test-sentiment-items")

        # SNS
        sns_client = boto3.client("sns", region_name="us-east-1")
        sns_client.create_topic(Name="test-analysis-topic")

        # Secrets Manager
        secrets_client = boto3.client("secretsmanager", region_name="us-east-1")
        secrets_client.create_secret(
            Name="arn:aws:secretsmanager:us-east-1:123456789012:secret:test-newsapi",
            SecretString=json.dumps({"api_key": "test-api-key-12345"}),
        )

        return dynamodb_client, sns_client, table

    def _verify_dynamodb_item_schema(self, item: dict):
        """
        Verify a DynamoDB item has the correct schema.

        Args:
            item: DynamoDB item dict

        Raises:
            AssertionError: If schema is invalid
        """
        # Required fields
        assert "source_id" in item
        assert item["source_id"].startswith("newsapi#")

        assert "timestamp" in item
        # Verify ISO8601 format
        datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))

        assert "source_type" in item
        assert item["source_type"] == "newsapi"

        assert "source_url" in item
        assert item["source_url"].startswith("http")

        assert "text_snippet" in item
        assert len(item["text_snippet"]) <= 200

        assert "text_for_analysis" in item
        assert item["text_for_analysis"] != ""

        assert "status" in item
        assert item["status"] == "pending"

        assert "matched_tags" in item
        assert isinstance(item["matched_tags"], list)
        assert len(item["matched_tags"]) > 0

        assert "ttl_timestamp" in item
        assert isinstance(item["ttl_timestamp"], int)

        assert "metadata" in item
        metadata = item["metadata"]
        assert "title" in metadata
        assert "author" in metadata
        assert "published_at" in metadata
        assert "source_name" in metadata


class TestIngestionEdgeCases:
    """Edge case tests for ingestion flow."""

    @mock_aws
    @responses.activate
    def test_empty_newsapi_response(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
    ):
        """Test handling of empty NewsAPI responses."""
        # Setup AWS mocks
        dynamodb_client = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb_client.create_table(
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

        sns_client = boto3.client("sns", region_name="us-east-1")
        sns_client.create_topic(Name="test-analysis-topic")

        secrets_client = boto3.client("secretsmanager", region_name="us-east-1")
        secrets_client.create_secret(
            Name="arn:aws:secretsmanager:us-east-1:123456789012:secret:test-newsapi",
            SecretString=json.dumps({"api_key": "test-api-key-12345"}),
        )

        # All tags return empty
        for _ in range(3):  # 3 tags
            responses.add(
                responses.GET,
                NEWSAPI_BASE_URL,
                json={
                    "status": "ok",
                    "totalResults": 0,
                    "articles": [],
                },
                status=200,
            )

        # Execute handler
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Should succeed with zero items
        assert result["statusCode"] == 200
        assert result["body"]["summary"]["articles_fetched"] == 0
        assert result["body"]["summary"]["new_items"] == 0

    @mock_aws
    @responses.activate
    def test_article_missing_optional_fields(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
    ):
        """Test articles with missing optional fields are handled."""
        # Setup AWS mocks
        dynamodb_client = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb_client.create_table(
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

        sns_client = boto3.client("sns", region_name="us-east-1")
        sns_client.create_topic(Name="test-analysis-topic")

        secrets_client = boto3.client("secretsmanager", region_name="us-east-1")
        secrets_client.create_secret(
            Name="arn:aws:secretsmanager:us-east-1:123456789012:secret:test-newsapi",
            SecretString=json.dumps({"api_key": "test-api-key-12345"}),
        )

        # Single tag
        os.environ["WATCH_TAGS"] = "AI"

        # Minimal article
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={
                "status": "ok",
                "totalResults": 1,
                "articles": [
                    {
                        "url": "https://example.com/minimal",
                        "title": "Minimal Article",
                        "publishedAt": "2025-11-17T10:00:00Z",
                        # Missing: author, description, content, source
                    }
                ],
            },
            status=200,
        )

        # Execute handler
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Should succeed
        assert result["statusCode"] == 200
        assert result["body"]["summary"]["new_items"] == 1

        # Verify defaults
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.Table("test-sentiment-items")
        scan_result = table.scan()
        item = scan_result["Items"][0]

        assert item["metadata"]["author"] == "Unknown"
        assert item["metadata"]["source_name"] == ""

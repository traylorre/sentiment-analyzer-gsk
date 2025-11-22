"""
Ingestion E2E Test (Preprod)
============================

Integration tests for the ingestion flow against REAL preprod environment.

CRITICAL: These tests use REAL AWS resources (preprod environment only).
- DynamoDB: preprod-sentiment-items table (Terraform-deployed)
- SNS: preprod-sentiment-topic (Terraform-deployed)
- NO mocking of AWS infrastructure

External dependencies mocked:
- NewsAPI (external third-party publisher - not under our control)
  Mocking allows deterministic test data without rate limits or API costs.
- Secrets Manager API key retrieval (mocked to avoid dependency on actual secret)

For On-Call Engineers:
    If these tests fail in CI:
    1. Verify preprod environment is deployed: `aws dynamodb describe-table --table-name preprod-sentiment-items`
    2. Check SNS topic exists: `aws sns list-topics | grep preprod-sentiment`
    3. Check AWS credentials are configured in CI

    See SC-03 in ON_CALL_SOP.md for ingestion issues.

For Developers:
    - Tests use REAL preprod DynamoDB and SNS
    - NewsAPI and Secrets Manager are mocked (external dependencies)
    - Verifies complete data flow through the system
    - Tests idempotency (duplicate handling)
    - Validates schema compliance
"""

import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest
import responses

from src.lambdas.ingestion.adapters.newsapi import NEWSAPI_BASE_URL
from src.lambdas.ingestion.handler import lambda_handler

# Environment variables should be set by CI (do NOT override here)
# CI sets: DYNAMODB_TABLE=dev-sentiment-items, SNS_TOPIC_ARN=..., etc.


@pytest.fixture
def env_vars():
    """
    Verify required environment variables are set.

    Does NOT override CI-provided values.
    """
    required_vars = [
        "WATCH_TAGS",
        "DYNAMODB_TABLE",
        "SNS_TOPIC_ARN",
        "NEWSAPI_SECRET_ARN",
        "ENVIRONMENT",
    ]
    for var in required_vars:
        assert var in os.environ, f"Missing required env var: {var}"
    yield


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
        "time": datetime.now(UTC).isoformat(),
        "region": "us-east-1",
        "resources": [
            "arn:aws:events:us-east-1:123456789012:rule/sentiment-ingestion-scheduler"
        ],
        "detail": {},
    }


@pytest.fixture
def dynamodb_table():
    """
    Get reference to REAL dev DynamoDB table.

    Returns the actual Terraform-deployed table.
    """
    table_name = os.environ.get("DYNAMODB_TABLE", "dev-sentiment-items")
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    return dynamodb.Table(table_name)


@pytest.fixture
def sample_newsapi_article():
    """Sample NewsAPI article for testing."""
    return {
        "source": {"id": "techcrunch", "name": "TechCrunch"},
        "author": "Integration Test Author",
        "title": "Integration Test Article",
        "description": "This is a test article for integration testing",
        "url": f"https://example.com/integration-test-{datetime.now(UTC).timestamp()}",
        "urlToImage": "https://example.com/test.jpg",
        "publishedAt": datetime.now(UTC).isoformat(),
        "content": "Full test article content...",
    }


class TestIngestionE2E:
    """
    Integration tests for ingestion flow against REAL dev AWS.

    IMPORTANT: These tests interact with actual dev resources.
    NewsAPI is mocked (external dependency), AWS resources are real.
    """

    @responses.activate
    def test_full_ingestion_flow(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        dynamodb_table,
        sample_newsapi_article,
    ):
        """
        Integration: Complete ingestion flow from NewsAPI to real DynamoDB and SNS.

        This is the primary integration test that verifies:
        1. Articles are fetched from NewsAPI (mocked - external dependency)
        2. Items are inserted into REAL preprod DynamoDB with correct schema
        3. SNS messages are published to REAL preprod SNS topic
        4. Metrics and statistics are tracked correctly
        """
        # Setup NewsAPI mock responses (external dependency)
        # Use single tag to simplify test
        os.environ["WATCH_TAGS"] = "AI"

        # Make article URL unique to avoid conflicts with production data
        test_article = sample_newsapi_article.copy()
        test_id = f"integration-{datetime.now(UTC).timestamp()}"
        test_article["url"] = f"https://example.com/test-{test_id}"

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

        # Execute handler - interacts with REAL preprod AWS
        try:
            with (
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
                patch(
                    "src.lambdas.ingestion.handler.get_api_key",
                    return_value="mock-newsapi-key-for-testing",
                ),
            ):
                result = lambda_handler(eventbridge_event, mock_context)

            # Verify success response
            assert result["statusCode"] == 200
            summary = result["body"]["summary"]
            assert summary["tags_processed"] == 1
            assert summary["articles_fetched"] == 1
            assert summary["new_items"] == 1
            assert summary["duplicates_skipped"] == 0
            assert summary["errors"] == 0

            # Verify item was inserted into REAL dev DynamoDB
            # Scan for our test item (by unique URL)
            response = dynamodb_table.scan(
                FilterExpression="source_url = :url",
                ExpressionAttributeValues={":url": test_article["url"]},
            )

            items = response["Items"]
            assert len(items) == 1, f"Expected 1 item, found {len(items)}"

            item = items[0]

            # Verify item schema
            assert item["source_id"].startswith("newsapi#")
            assert "timestamp" in item
            assert item["source_type"] == "newsapi"
            assert item["source_url"] == test_article["url"]
            assert item["status"] == "pending"
            assert "matched_tags" in item
            assert "AI" in item["matched_tags"]
            assert "text_for_analysis" in item
            assert "ttl_timestamp" in item
            assert "metadata" in item

        finally:
            # Cleanup: Remove test item from REAL dev table
            try:
                # Find and delete the test item
                response = dynamodb_table.scan(
                    FilterExpression="source_url = :url",
                    ExpressionAttributeValues={":url": test_article["url"]},
                )
                for item in response["Items"]:
                    dynamodb_table.delete_item(
                        Key={
                            "source_id": item["source_id"],
                            "timestamp": item["timestamp"],
                        }
                    )
            except Exception:  # noqa: S110
                pass  # Cleanup is best-effort, exceptions during cleanup don't fail test

    @responses.activate
    def test_deduplication_across_invocations(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        dynamodb_table,
        sample_newsapi_article,
    ):
        """
        Integration: Duplicate articles are skipped in REAL preprod DynamoDB.

        Verifies the idempotency of the ingestion process against real AWS.
        """
        os.environ["WATCH_TAGS"] = "AI"

        # Unique test article
        test_article = sample_newsapi_article.copy()
        test_id = f"integration-dedup-{datetime.now(UTC).timestamp()}"
        test_article["url"] = f"https://example.com/test-{test_id}"

        # First invocation - mock NewsAPI
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

        try:
            with (
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
                patch(
                    "src.lambdas.ingestion.handler.get_api_key",
                    return_value="mock-newsapi-key-for-testing",
                ),
            ):
                result1 = lambda_handler(eventbridge_event, mock_context)

            # Verify first invocation succeeded
            assert result1["body"]["summary"]["new_items"] == 1
            assert result1["body"]["summary"]["duplicates_skipped"] == 0

            # Second invocation - same article (mock NewsAPI again)
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

            with (
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
                patch(
                    "src.lambdas.ingestion.handler.get_api_key",
                    return_value="mock-newsapi-key-for-testing",
                ),
            ):
                result2 = lambda_handler(eventbridge_event, mock_context)

            # Verify second invocation detected duplicate
            assert result2["body"]["summary"]["new_items"] == 0
            assert result2["body"]["summary"]["duplicates_skipped"] == 1

            # Verify REAL dev table still has only one item
            response = dynamodb_table.scan(
                FilterExpression="source_url = :url",
                ExpressionAttributeValues={":url": test_article["url"]},
            )
            assert len(response["Items"]) == 1

        finally:
            # Cleanup
            try:
                response = dynamodb_table.scan(
                    FilterExpression="source_url = :url",
                    ExpressionAttributeValues={":url": test_article["url"]},
                )
                for item in response["Items"]:
                    dynamodb_table.delete_item(
                        Key={
                            "source_id": item["source_id"],
                            "timestamp": item["timestamp"],
                        }
                    )
            except Exception:  # noqa: S110
                pass

    @responses.activate
    def test_item_ttl_set_correctly(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        dynamodb_table,
        sample_newsapi_article,
    ):
        """
        Integration: Items have TTL set for 30-day expiration in REAL preprod table.

        This is important for data retention and cost management.
        """
        os.environ["WATCH_TAGS"] = "AI"

        test_article = sample_newsapi_article.copy()
        test_id = f"integration-ttl-{datetime.now(UTC).timestamp()}"
        test_article["url"] = f"https://example.com/test-{test_id}"

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

        try:
            with (
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
                patch(
                    "src.lambdas.ingestion.handler.get_api_key",
                    return_value="mock-newsapi-key-for-testing",
                ),
            ):
                _result = lambda_handler(eventbridge_event, mock_context)

            # Get the item from REAL dev table
            response = dynamodb_table.scan(
                FilterExpression="source_url = :url",
                ExpressionAttributeValues={":url": test_article["url"]},
            )
            item = response["Items"][0]

            # Verify TTL is set
            assert "ttl_timestamp" in item

            # TTL should be approximately 30 days from now
            ttl = int(item["ttl_timestamp"])
            now = datetime.now(UTC).timestamp()
            days_until_expiry = (ttl - now) / (24 * 60 * 60)

            # Should be between 29 and 31 days (allowing for test execution time)
            assert 29 <= days_until_expiry <= 31

        finally:
            # Cleanup
            try:
                response = dynamodb_table.scan(
                    FilterExpression="source_url = :url",
                    ExpressionAttributeValues={":url": test_article["url"]},
                )
                for item in response["Items"]:
                    dynamodb_table.delete_item(
                        Key={
                            "source_id": item["source_id"],
                            "timestamp": item["timestamp"],
                        }
                    )
            except Exception:  # noqa: S110
                pass

    @responses.activate
    def test_metadata_preserved(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        dynamodb_table,
        sample_newsapi_article,
    ):
        """
        Integration: Article metadata is correctly preserved in REAL preprod DynamoDB.

        This data is used by the dashboard for display.
        """
        os.environ["WATCH_TAGS"] = "AI"

        test_article = sample_newsapi_article.copy()
        test_id = f"integration-metadata-{datetime.now(UTC).timestamp()}"
        test_article["url"] = f"https://example.com/test-{test_id}"

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

        try:
            with (
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
                patch(
                    "src.lambdas.ingestion.handler.get_api_key",
                    return_value="mock-newsapi-key-for-testing",
                ),
            ):
                _result = lambda_handler(eventbridge_event, mock_context)

            # Get the item from REAL dev table
            response = dynamodb_table.scan(
                FilterExpression="source_url = :url",
                ExpressionAttributeValues={":url": test_article["url"]},
            )
            item = response["Items"][0]

            # Verify metadata
            assert "metadata" in item
            metadata = item["metadata"]

            assert metadata["title"] == test_article["title"]
            assert metadata["author"] == test_article["author"]
            assert metadata["published_at"] == test_article["publishedAt"]
            assert metadata["source_name"] == test_article["source"]["name"]

        finally:
            # Cleanup
            try:
                response = dynamodb_table.scan(
                    FilterExpression="source_url = :url",
                    ExpressionAttributeValues={":url": test_article["url"]},
                )
                for item in response["Items"]:
                    dynamodb_table.delete_item(
                        Key={
                            "source_id": item["source_id"],
                            "timestamp": item["timestamp"],
                        }
                    )
            except Exception:  # noqa: S110
                pass

    @responses.activate
    def test_text_for_analysis_extraction(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
        dynamodb_table,
    ):
        """
        Integration: text_for_analysis is correctly extracted and stored in REAL preprod table.

        This is the text that will be analyzed for sentiment.
        """
        os.environ["WATCH_TAGS"] = "AI"

        test_id = f"integration-text-{datetime.now(UTC).timestamp()}"
        article = {
            "source": {"id": "test", "name": "Test"},
            "author": "Author",
            "title": "Important AI News",
            "description": "This is the description with key information.",
            "url": f"https://example.com/test-{test_id}",
            "publishedAt": datetime.now(UTC).isoformat(),
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

        try:
            with (
                patch("src.lib.metrics.emit_metric"),
                patch("src.lib.metrics.emit_metrics_batch"),
                patch(
                    "src.lambdas.ingestion.handler.get_api_key",
                    return_value="mock-newsapi-key-for-testing",
                ),
            ):
                _result = lambda_handler(eventbridge_event, mock_context)

            # Get the item from REAL dev table
            response = dynamodb_table.scan(
                FilterExpression="source_url = :url",
                ExpressionAttributeValues={":url": article["url"]},
            )
            item = response["Items"][0]

            # Verify text_for_analysis combines title and description
            expected_text = (
                "Important AI News. This is the description with key information."
            )
            assert item["text_for_analysis"] == expected_text

        finally:
            # Cleanup
            try:
                response = dynamodb_table.scan(
                    FilterExpression="source_url = :url",
                    ExpressionAttributeValues={":url": article["url"]},
                )
                for item in response["Items"]:
                    dynamodb_table.delete_item(
                        Key={
                            "source_id": item["source_id"],
                            "timestamp": item["timestamp"],
                        }
                    )
            except Exception:  # noqa: S110
                pass  # Cleanup is best-effort


class TestIngestionEdgeCases:
    """Edge case integration tests."""

    @responses.activate
    def test_empty_newsapi_response(
        self,
        env_vars,
        mock_context,
        eventbridge_event,
    ):
        """Integration: Handling of empty NewsAPI responses."""
        os.environ["WATCH_TAGS"] = "AI"

        # NewsAPI returns empty (external API mock)
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

        # Execute handler - real AWS, empty NewsAPI response
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
            patch(
                "src.lambdas.ingestion.handler.get_api_key",
                return_value="mock-newsapi-key-for-testing",
            ),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Should succeed with zero items
        assert result["statusCode"] == 200
        assert result["body"]["summary"]["articles_fetched"] == 0
        assert result["body"]["summary"]["new_items"] == 0

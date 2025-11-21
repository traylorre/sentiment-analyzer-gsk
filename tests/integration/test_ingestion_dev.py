"""
Ingestion E2E Tests - Dev Environment
======================================

End-to-end tests for dev environment with ALL AWS resources mocked.

IMPORTANT: These tests use moto to mock ALL AWS infrastructure.
- Purpose: Fast feedback during development
- Run on: Every PR, every merge, Dependabot PRs
- Cost: $0 (no real AWS resources)

Mocking Strategy:
- AWS resources (DynamoDB, SNS, Secrets): moto
- NewsAPI HTTP requests: responses library

For actual integration testing against real AWS, see test_ingestion_preprod.py.
"""

import json
import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest
import responses
from moto import mock_aws

from src.lambdas.ingestion.adapters.newsapi import NEWSAPI_BASE_URL
from src.lambdas.ingestion.handler import lambda_handler


@pytest.fixture
def env_vars():
    """Set test environment variables."""
    os.environ["WATCH_TAGS"] = "AI"
    os.environ["DYNAMODB_TABLE"] = "test-sentiment-items"
    os.environ[
        "SNS_TOPIC_ARN"
    ] = "arn:aws:sns:us-east-1:123456789012:test-analysis-topic"
    os.environ[
        "NEWSAPI_SECRET_ARN"
    ] = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-newsapi"
    os.environ["MODEL_VERSION"] = "v1.0.0"
    os.environ["ENVIRONMENT"] = "test"
    yield
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
    context.aws_request_id = "test-request-123"
    context.function_name = "test-sentiment-ingestion"
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
        "time": datetime.now(UTC).isoformat(),
        "region": "us-east-1",
        "detail": {},
    }


class TestIngestionDevE2E:
    """Dev environment E2E tests with mocked AWS."""

    @mock_aws
    @responses.activate
    def test_full_ingestion_flow(self, env_vars, mock_context, eventbridge_event):
        """E2E: Complete ingestion flow with mocked AWS and NewsAPI."""
        # Create mock DynamoDB table
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

        # Create mock SNS topic
        sns_client = boto3.client("sns", region_name="us-east-1")
        sns_client.create_topic(Name="test-analysis-topic")

        # Create mock Secrets Manager secret
        secrets_client = boto3.client("secretsmanager", region_name="us-east-1")
        secrets_client.create_secret(
            Name="arn:aws:secretsmanager:us-east-1:123456789012:secret:test-newsapi",
            SecretString=json.dumps({"api_key": "test-key-12345"}),
        )

        # Mock NewsAPI response
        test_article = {
            "source": {"id": "techcrunch", "name": "TechCrunch"},
            "author": "Test Author",
            "title": "Test AI Article",
            "description": "Test description",
            "url": "https://example.com/test-article",
            "publishedAt": "2025-11-20T10:00:00Z",
            "content": "Test content...",
        }

        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"status": "ok", "totalResults": 1, "articles": [test_article]},
            status=200,
        )

        # Execute handler
        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result = lambda_handler(eventbridge_event, mock_context)

        # Verify success
        assert result["statusCode"] == 200
        summary = result["body"]["summary"]
        assert summary["tags_processed"] == 1
        assert summary["articles_fetched"] == 1
        assert summary["new_items"] == 1
        assert summary["duplicates_skipped"] == 0

        # Verify item in DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.Table("test-sentiment-items")
        scan_result = table.scan()
        assert len(scan_result["Items"]) == 1

        item = scan_result["Items"][0]
        assert item["source_id"].startswith("newsapi#")
        assert item["status"] == "pending"
        assert "text_for_analysis" in item

    @mock_aws
    @responses.activate
    def test_deduplication(self, env_vars, mock_context, eventbridge_event):
        """E2E: Duplicate articles are skipped."""
        # Setup mock AWS
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
            SecretString=json.dumps({"api_key": "test-key-12345"}),
        )

        test_article = {
            "source": {"id": "test", "name": "Test"},
            "title": "Duplicate Test",
            "url": "https://example.com/duplicate",
            "publishedAt": "2025-11-20T10:00:00Z",
        }

        # First invocation
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"status": "ok", "totalResults": 1, "articles": [test_article]},
            status=200,
        )

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result1 = lambda_handler(eventbridge_event, mock_context)

        assert result1["body"]["summary"]["new_items"] == 1
        assert result1["body"]["summary"]["duplicates_skipped"] == 0

        # Second invocation (duplicate)
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"status": "ok", "totalResults": 1, "articles": [test_article]},
            status=200,
        )

        with (
            patch("src.lib.metrics.emit_metric"),
            patch("src.lib.metrics.emit_metrics_batch"),
        ):
            result2 = lambda_handler(eventbridge_event, mock_context)

        assert result2["body"]["summary"]["new_items"] == 0
        assert result2["body"]["summary"]["duplicates_skipped"] == 1

        # Verify still only one item
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.Table("test-sentiment-items")
        scan_result = table.scan()
        assert len(scan_result["Items"]) == 1

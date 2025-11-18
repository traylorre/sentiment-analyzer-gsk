"""
Unit Tests for DynamoDB Helper Module
=====================================

Tests all DynamoDB helper functions using moto mocks.

For On-Call Engineers:
    If tests fail in CI but pass locally:
    1. Check moto version matches (moto==4.2.0)
    2. Verify test fixtures match current DynamoDB schema
    3. Check AWS_DEFAULT_REGION is set to us-east-1

For Developers:
    - All tests use moto to mock DynamoDB (no real AWS calls)
    - Fixtures create table with correct schema (PK=source_id, SK=timestamp)
    - Test both success and failure cases
"""

import os
from decimal import Decimal

# Import after setting up mocks
import boto3
import pytest
from moto import mock_aws

from src.lambdas.shared.dynamodb import (
    build_key,
    get_dynamodb_resource,
    get_table,
    item_exists,
    parse_dynamodb_item,
    put_item_if_not_exists,
    update_item_status,
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
def dynamodb_table(aws_credentials):
    """
    Create a mocked DynamoDB table with correct schema.

    Schema matches infrastructure/terraform/modules/dynamodb/main.tf:
    - PK: source_id (String)
    - SK: timestamp (String)
    - GSIs: by_sentiment, by_tag, by_status
    """
    with mock_aws():
        # Set table name env var
        os.environ["DYNAMODB_TABLE"] = "test-sentiment-items"

        # Create table with production schema
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
                {"AttributeName": "sentiment", "AttributeType": "S"},
                {"AttributeName": "tag", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "by_sentiment",
                    "KeySchema": [
                        {"AttributeName": "sentiment", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "by_tag",
                    "KeySchema": [
                        {"AttributeName": "tag", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "by_status",
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "KEYS_ONLY"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Get table resource
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        table = resource.Table("test-sentiment-items")

        yield table


class TestBuildKey:
    """Tests for build_key function."""

    def test_build_key_basic(self):
        """Test basic key construction."""
        key = build_key("newsapi#abc123", "2025-11-17T14:30:00.000Z")

        assert key == {
            "source_id": "newsapi#abc123",
            "timestamp": "2025-11-17T14:30:00.000Z",
        }

    def test_build_key_with_special_chars(self):
        """Test key with special characters in source_id."""
        key = build_key("newsapi#abc123def456", "2025-11-17T14:30:00.000Z")

        assert key["source_id"] == "newsapi#abc123def456"

    def test_build_key_empty_values(self):
        """Test key with empty strings (edge case)."""
        key = build_key("", "")

        assert key == {"source_id": "", "timestamp": ""}


class TestParseDynamoDBItem:
    """Tests for parse_dynamodb_item function."""

    def test_parse_empty_item(self):
        """Test parsing empty dict."""
        result = parse_dynamodb_item({})
        assert result == {}

    def test_parse_none_item(self):
        """Test parsing None."""
        result = parse_dynamodb_item(None)
        assert result == {}

    def test_parse_decimal_to_int(self):
        """Test Decimal whole numbers convert to int."""
        item = {"count": Decimal("42")}
        result = parse_dynamodb_item(item)

        assert result["count"] == 42
        assert isinstance(result["count"], int)

    def test_parse_decimal_to_float(self):
        """Test Decimal with decimals converts to float."""
        item = {"score": Decimal("0.95")}
        result = parse_dynamodb_item(item)

        assert result["score"] == 0.95
        assert isinstance(result["score"], float)

    def test_parse_set_to_list(self):
        """Test set converts to list."""
        item = {"tags": {"AI", "climate"}}
        result = parse_dynamodb_item(item)

        assert isinstance(result["tags"], list)
        assert set(result["tags"]) == {"AI", "climate"}

    def test_parse_nested_dict(self):
        """Test nested dict with Decimals."""
        item = {
            "metadata": {
                "count": Decimal("10"),
                "nested": {"value": Decimal("3.14")},
            }
        }
        result = parse_dynamodb_item(item)

        assert result["metadata"]["count"] == 10
        assert result["metadata"]["nested"]["value"] == 3.14

    def test_parse_list_with_decimals(self):
        """Test list containing Decimals."""
        item = {"scores": [Decimal("0.8"), Decimal("0.9"), Decimal("0.75")]}
        result = parse_dynamodb_item(item)

        assert result["scores"] == [0.8, 0.9, 0.75]

    def test_parse_string_unchanged(self):
        """Test strings pass through unchanged."""
        item = {"source_id": "newsapi#abc123", "title": "Test Article"}
        result = parse_dynamodb_item(item)

        assert result["source_id"] == "newsapi#abc123"
        assert result["title"] == "Test Article"


class TestGetDynamoDBResource:
    """Tests for get_dynamodb_resource function."""

    def test_get_resource_default_region(self, aws_credentials):
        """Test resource creation with default region."""
        with mock_aws():
            resource = get_dynamodb_resource()
            assert resource is not None

    def test_get_resource_custom_region(self, aws_credentials):
        """Test resource creation with custom region."""
        with mock_aws():
            resource = get_dynamodb_resource(region_name="us-west-2")
            assert resource is not None


class TestGetTable:
    """Tests for get_table function."""

    def test_get_table_from_env(self, dynamodb_table):
        """Test getting table from DYNAMODB_TABLE env var."""
        table = get_table()
        assert table.table_name == "test-sentiment-items"

    def test_get_table_explicit_name(self, dynamodb_table):
        """Test getting table with explicit name."""
        table = get_table(table_name="test-sentiment-items")
        assert table.table_name == "test-sentiment-items"

    def test_get_table_no_name_raises(self, aws_credentials):
        """Test that missing table name raises ValueError."""
        with mock_aws():
            # Remove env var
            os.environ.pop("DYNAMODB_TABLE", None)

            with pytest.raises(ValueError, match="Table name required"):
                get_table()


class TestItemExists:
    """Tests for item_exists function."""

    def test_item_exists_true(self, dynamodb_table):
        """Test item_exists returns True for existing item."""
        # Insert test item
        dynamodb_table.put_item(
            Item={
                "source_id": "newsapi#test123",
                "timestamp": "2025-11-17T14:30:00.000Z",
                "status": "pending",
            }
        )

        result = item_exists(
            dynamodb_table,
            "newsapi#test123",
            "2025-11-17T14:30:00.000Z",
        )

        assert result is True

    def test_item_exists_false(self, dynamodb_table):
        """Test item_exists returns False for non-existing item."""
        result = item_exists(
            dynamodb_table,
            "newsapi#nonexistent",
            "2025-11-17T14:30:00.000Z",
        )

        assert result is False


class TestPutItemIfNotExists:
    """Tests for put_item_if_not_exists function."""

    def test_put_new_item_succeeds(self, dynamodb_table):
        """Test putting a new item succeeds."""
        item = {
            "source_id": "newsapi#new123",
            "timestamp": "2025-11-17T14:30:00.000Z",
            "status": "pending",
            "title": "Test Article",
        }

        result = put_item_if_not_exists(dynamodb_table, item)

        assert result is True

        # Verify item was created
        response = dynamodb_table.get_item(
            Key={"source_id": "newsapi#new123", "timestamp": "2025-11-17T14:30:00.000Z"}
        )
        assert "Item" in response
        assert response["Item"]["title"] == "Test Article"

    def test_put_existing_item_returns_false(self, dynamodb_table):
        """Test putting existing item returns False (deduplication)."""
        item = {
            "source_id": "newsapi#exists123",
            "timestamp": "2025-11-17T14:30:00.000Z",
            "status": "pending",
        }

        # First put succeeds
        result1 = put_item_if_not_exists(dynamodb_table, item)
        assert result1 is True

        # Second put returns False (item exists)
        result2 = put_item_if_not_exists(dynamodb_table, item)
        assert result2 is False

    def test_put_item_preserves_original(self, dynamodb_table):
        """Test that existing item is not overwritten."""
        original = {
            "source_id": "newsapi#preserve123",
            "timestamp": "2025-11-17T14:30:00.000Z",
            "status": "pending",
            "title": "Original Title",
        }

        updated = {
            "source_id": "newsapi#preserve123",
            "timestamp": "2025-11-17T14:30:00.000Z",
            "status": "analyzed",
            "title": "Updated Title",
        }

        # Put original
        put_item_if_not_exists(dynamodb_table, original)

        # Try to put updated
        put_item_if_not_exists(dynamodb_table, updated)

        # Verify original is preserved
        response = dynamodb_table.get_item(
            Key={
                "source_id": "newsapi#preserve123",
                "timestamp": "2025-11-17T14:30:00.000Z",
            }
        )
        assert response["Item"]["title"] == "Original Title"
        assert response["Item"]["status"] == "pending"


class TestUpdateItemStatus:
    """Tests for update_item_status function."""

    def test_update_status_only(self, dynamodb_table):
        """Test updating just the status field."""
        # Create item
        dynamodb_table.put_item(
            Item={
                "source_id": "newsapi#update123",
                "timestamp": "2025-11-17T14:30:00.000Z",
                "status": "pending",
            }
        )

        # Update status
        result = update_item_status(
            dynamodb_table,
            "newsapi#update123",
            "2025-11-17T14:30:00.000Z",
            "analyzed",
        )

        assert result is True

        # Verify update
        response = dynamodb_table.get_item(
            Key={
                "source_id": "newsapi#update123",
                "timestamp": "2025-11-17T14:30:00.000Z",
            }
        )
        assert response["Item"]["status"] == "analyzed"

    def test_update_with_additional_attrs(self, dynamodb_table):
        """Test updating status with additional attributes."""
        # Create item
        dynamodb_table.put_item(
            Item={
                "source_id": "newsapi#attrs123",
                "timestamp": "2025-11-17T14:30:00.000Z",
                "status": "pending",
            }
        )

        # Update with additional attributes
        result = update_item_status(
            dynamodb_table,
            "newsapi#attrs123",
            "2025-11-17T14:30:00.000Z",
            "analyzed",
            additional_attrs={
                "sentiment": "positive",
                "score": Decimal("0.95"),
                "model_version": "v1.0.0",
            },
        )

        assert result is True

        # Verify all updates
        response = dynamodb_table.get_item(
            Key={
                "source_id": "newsapi#attrs123",
                "timestamp": "2025-11-17T14:30:00.000Z",
            }
        )
        item = response["Item"]
        assert item["status"] == "analyzed"
        assert item["sentiment"] == "positive"
        assert item["score"] == Decimal("0.95")
        assert item["model_version"] == "v1.0.0"

    def test_update_nonexistent_item(self, dynamodb_table):
        """Test updating a non-existent item creates it (upsert behavior)."""
        # DynamoDB update_item creates the item if it doesn't exist
        result = update_item_status(
            dynamodb_table,
            "newsapi#nonexistent",
            "2025-11-17T14:30:00.000Z",
            "analyzed",
        )

        assert result is True

        # Verify item was created
        response = dynamodb_table.get_item(
            Key={
                "source_id": "newsapi#nonexistent",
                "timestamp": "2025-11-17T14:30:00.000Z",
            }
        )
        assert response["Item"]["status"] == "analyzed"

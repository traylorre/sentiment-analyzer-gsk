"""
Unit Tests for Dashboard Metrics Module
========================================

Tests for the metrics aggregation functions used by the dashboard.

For On-Call Engineers:
    If these tests fail in CI:
    1. Check moto version compatibility (moto 5.x required)
    2. Verify boto3 version matches Lambda runtime
    3. Check test isolation (each test should be independent)

For Developers:
    - Uses moto for DynamoDB mocking
    - Tests cover all aggregation functions
    - GSI queries are tested with realistic data
    - Edge cases include empty tables, missing fields
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

from src.lambdas.dashboard.metrics import (
    MAX_RECENT_ITEMS,
    aggregate_dashboard_metrics,
    calculate_ingestion_rate,
    calculate_sentiment_distribution,
    calculate_tag_distribution,
    clear_metrics_cache,
    get_items_by_sentiment,
    get_recent_items,
    sanitize_item_for_response,
)


@pytest.fixture
def dynamodb_table():
    """Create a mocked DynamoDB table with GSIs for testing."""
    # Clear metrics cache before each test to ensure isolation
    clear_metrics_cache()

    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        # Create table with GSIs matching production schema
        table = dynamodb.create_table(
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
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        table.meta.client.get_waiter("table_exists").wait(
            TableName="test-sentiment-items"
        )

        yield table


@pytest.fixture
def sample_items():
    """Generate sample items for testing."""
    now = datetime.now(UTC)

    items = [
        {
            "source_id": "article#article1",
            "timestamp": (now - timedelta(minutes=10)).isoformat(),
            "title": "Positive News Article",
            "sentiment": "positive",
            "score": Decimal("0.95"),
            "status": "analyzed",
            "tags": ["tech", "ai"],
            "source": "techcrunch",
        },
        {
            "source_id": "article#article2",
            "timestamp": (now - timedelta(minutes=20)).isoformat(),
            "title": "Neutral News Article",
            "sentiment": "neutral",
            "score": Decimal("0.55"),
            "status": "analyzed",
            "tags": ["tech"],
            "source": "reuters",
        },
        {
            "source_id": "article#article3",
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "title": "Negative News Article",
            "sentiment": "negative",
            "score": Decimal("0.85"),
            "status": "analyzed",
            "tags": ["business", "finance"],
            "source": "bloomberg",
        },
        {
            "source_id": "article#article4",
            "timestamp": (now - timedelta(minutes=40)).isoformat(),
            "title": "Another Positive Article",
            "sentiment": "positive",
            "score": Decimal("0.78"),
            "status": "analyzed",
            "tags": ["ai"],
            "source": "wired",
        },
        {
            "source_id": "article#article5",
            "timestamp": (now - timedelta(minutes=50)).isoformat(),
            "title": "Pending Article",
            "status": "pending",
            "tags": ["tech"],
            "source": "verge",
        },
    ]

    return items


def seed_table(table, items):
    """Helper to seed table with items."""
    for item in items:
        table.put_item(Item=item)


class TestCalculateSentimentDistribution:
    """Tests for calculate_sentiment_distribution function."""

    def test_basic_distribution(self):
        """Test basic sentiment counting."""
        items = [
            {"sentiment": "positive"},
            {"sentiment": "positive"},
            {"sentiment": "neutral"},
            {"sentiment": "negative"},
        ]

        result = calculate_sentiment_distribution(items)

        assert result == {
            "positive": 2,
            "neutral": 1,
            "negative": 1,
        }

    def test_empty_list(self):
        """Test with empty item list."""
        result = calculate_sentiment_distribution([])

        assert result == {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
        }

    def test_missing_sentiment_field(self):
        """Test items without sentiment field are skipped."""
        items = [
            {"sentiment": "positive"},
            {"title": "No sentiment"},
            {"sentiment": "negative"},
        ]

        result = calculate_sentiment_distribution(items)

        assert result == {
            "positive": 1,
            "neutral": 0,
            "negative": 1,
        }

    def test_case_insensitive(self):
        """Test sentiment values are case-insensitive."""
        items = [
            {"sentiment": "POSITIVE"},
            {"sentiment": "Neutral"},
            {"sentiment": "negative"},
        ]

        result = calculate_sentiment_distribution(items)

        assert result == {
            "positive": 1,
            "neutral": 1,
            "negative": 1,
        }

    def test_invalid_sentiment_logged(self, caplog):
        """Test that invalid sentiment values are logged.

        Note: In test environment, expected warnings are logged at DEBUG level
        to prevent log pollution (see src.lib.logging_utils).
        """
        items = [
            {"sentiment": "positive", "source_id": "test1"},
            {"sentiment": "invalid", "source_id": "test2"},
        ]

        with caplog.at_level("DEBUG"):
            result = calculate_sentiment_distribution(items)

        assert result["positive"] == 1
        assert "Unexpected sentiment value" in caplog.text


class TestCalculateTagDistribution:
    """Tests for calculate_tag_distribution function."""

    def test_basic_distribution(self):
        """Test basic tag counting."""
        items = [
            {"tags": ["tech", "ai"]},
            {"tags": ["tech", "business"]},
            {"tags": ["ai"]},
        ]

        result = calculate_tag_distribution(items)

        assert result == {
            "tech": 2,
            "ai": 2,
            "business": 1,
        }

    def test_sorted_by_count_descending(self):
        """Test tags are sorted by count descending."""
        items = [
            {"tags": ["rare"]},
            {"tags": ["common", "common2"]},
            {"tags": ["common"]},
            {"tags": ["common"]},
        ]

        result = calculate_tag_distribution(items)
        keys = list(result.keys())

        assert keys[0] == "common"
        assert result["common"] == 3

    def test_empty_list(self):
        """Test with empty item list."""
        result = calculate_tag_distribution([])
        assert result == {}

    def test_missing_tags_field(self):
        """Test items without tags field are skipped."""
        items = [
            {"tags": ["tech"]},
            {"title": "No tags"},
        ]

        result = calculate_tag_distribution(items)
        assert result == {"tech": 1}

    def test_empty_tags_list(self):
        """Test items with empty tags list."""
        items = [
            {"tags": ["tech"]},
            {"tags": []},
        ]

        result = calculate_tag_distribution(items)
        assert result == {"tech": 1}

    def test_ignores_empty_string_tags(self):
        """Test empty string tags are ignored."""
        items = [
            {"tags": ["tech", "", "ai"]},
        ]

        result = calculate_tag_distribution(items)
        assert result == {"tech": 1, "ai": 1}

    def test_non_string_tags_ignored(self):
        """Test non-string tags are ignored."""
        items = [
            {"tags": ["tech", 123, None]},
        ]

        result = calculate_tag_distribution(items)
        assert result == {"tech": 1}


class TestGetRecentItems:
    """Tests for get_recent_items function."""

    def test_returns_items_sorted_descending(self, dynamodb_table, sample_items):
        """Test items are returned in descending timestamp order."""
        seed_table(dynamodb_table, sample_items)

        result = get_recent_items(dynamodb_table, limit=10)

        # Should have 4 analyzed items (not the pending one)
        assert len(result) == 4

        # Verify sorted descending
        timestamps = [item["timestamp"] for item in result]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_respects_limit(self, dynamodb_table, sample_items):
        """Test limit parameter is respected."""
        seed_table(dynamodb_table, sample_items)

        result = get_recent_items(dynamodb_table, limit=2)

        assert len(result) == 2

    def test_filters_by_status(self, dynamodb_table, sample_items):
        """Test filtering by status works."""
        seed_table(dynamodb_table, sample_items)

        # Get pending items
        result = get_recent_items(dynamodb_table, limit=10, status="pending")

        assert len(result) == 1
        assert result[0]["status"] == "pending"

    def test_empty_table(self, dynamodb_table):
        """Test with empty table returns empty list."""
        result = get_recent_items(dynamodb_table, limit=10)
        assert result == []

    def test_default_limit(self, dynamodb_table, sample_items):
        """Test default limit is MAX_RECENT_ITEMS."""
        seed_table(dynamodb_table, sample_items)

        result = get_recent_items(dynamodb_table)

        # Should return all analyzed items (4) since less than MAX_RECENT_ITEMS
        assert len(result) <= MAX_RECENT_ITEMS


class TestGetItemsBySentiment:
    """Tests for get_items_by_sentiment function."""

    def test_filters_by_sentiment(self, dynamodb_table, sample_items):
        """Test filtering by sentiment value."""
        seed_table(dynamodb_table, sample_items)

        result = get_items_by_sentiment(dynamodb_table, "positive", hours=24)

        assert len(result) == 2
        for item in result:
            assert item["sentiment"] == "positive"

    def test_invalid_sentiment_raises_error(self, dynamodb_table):
        """Test invalid sentiment value raises ValueError."""
        with pytest.raises(ValueError, match="Invalid sentiment"):
            get_items_by_sentiment(dynamodb_table, "invalid", hours=24)

    def test_case_insensitive(self, dynamodb_table, sample_items):
        """Test sentiment filter is case-insensitive."""
        seed_table(dynamodb_table, sample_items)

        result = get_items_by_sentiment(dynamodb_table, "NEGATIVE", hours=24)

        assert len(result) == 1
        assert result[0]["sentiment"] == "negative"

    def test_time_window(self, dynamodb_table):
        """Test time window filtering."""
        now = datetime.now(UTC)

        # Create items at different times
        old_item = {
            "source_id": "article#old",
            "timestamp": (now - timedelta(hours=48)).isoformat(),
            "sentiment": "positive",
            "status": "analyzed",
        }
        recent_item = {
            "source_id": "article#recent",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "sentiment": "positive",
            "status": "analyzed",
        }

        dynamodb_table.put_item(Item=old_item)
        dynamodb_table.put_item(Item=recent_item)

        # Query with 24-hour window
        result = get_items_by_sentiment(dynamodb_table, "positive", hours=24)

        assert len(result) == 1
        assert result[0]["source_id"] == "article#recent"


class TestCalculateIngestionRate:
    """Tests for calculate_ingestion_rate function."""

    def test_calculates_rates(self, dynamodb_table):
        """Test rate calculation for different time windows."""
        now = datetime.now(UTC)

        # Create items at different times
        items = [
            # Within last hour
            {
                "source_id": "article#recent1",
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
                "status": "analyzed",
            },
            {
                "source_id": "article#recent2",
                "timestamp": (now - timedelta(minutes=45)).isoformat(),
                "status": "analyzed",
            },
            # Within last 24 hours but not last hour
            {
                "source_id": "article#older1",
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "status": "analyzed",
            },
            {
                "source_id": "article#older2",
                "timestamp": (now - timedelta(hours=12)).isoformat(),
                "status": "analyzed",
            },
        ]

        seed_table(dynamodb_table, items)

        result = calculate_ingestion_rate(dynamodb_table, hours=24)

        assert result["rate_last_hour"] == 2
        assert result["rate_last_24h"] == 4

    def test_includes_pending_items(self, dynamodb_table):
        """Test pending items are included in rate calculation."""
        now = datetime.now(UTC)

        items = [
            {
                "source_id": "article#analyzed",
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
                "status": "analyzed",
            },
            {
                "source_id": "article#pending",
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
                "status": "pending",
            },
        ]

        seed_table(dynamodb_table, items)

        result = calculate_ingestion_rate(dynamodb_table, hours=24)

        assert result["rate_last_hour"] == 2

    def test_empty_table(self, dynamodb_table):
        """Test with empty table returns zeros."""
        result = calculate_ingestion_rate(dynamodb_table, hours=24)

        assert result["rate_last_hour"] == 0
        assert result["rate_last_24h"] == 0


class TestAggregateDashboardMetrics:
    """Tests for aggregate_dashboard_metrics function."""

    def test_aggregates_all_metrics(self, dynamodb_table, sample_items):
        """Test full metrics aggregation."""
        seed_table(dynamodb_table, sample_items)

        result = aggregate_dashboard_metrics(dynamodb_table, hours=24)

        # Check all required fields present
        assert "total" in result
        assert "positive" in result
        assert "neutral" in result
        assert "negative" in result
        assert "by_tag" in result
        assert "rate_last_hour" in result
        assert "rate_last_24h" in result
        assert "recent_items" in result

        # Check counts (only analyzed items have sentiment)
        assert result["total"] == 4  # 4 analyzed items
        assert result["positive"] == 2
        assert result["neutral"] == 1
        assert result["negative"] == 1

        # Check tag distribution
        assert "tech" in result["by_tag"]
        assert "ai" in result["by_tag"]

        # Check recent items
        assert len(result["recent_items"]) == 4

    def test_empty_table(self, dynamodb_table):
        """Test with empty table returns zeros."""
        result = aggregate_dashboard_metrics(dynamodb_table, hours=24)

        assert result["total"] == 0
        assert result["positive"] == 0
        assert result["neutral"] == 0
        assert result["negative"] == 0
        assert result["by_tag"] == {}
        assert result["recent_items"] == []


class TestSanitizeItemForResponse:
    """Tests for sanitize_item_for_response function."""

    def test_removes_hidden_fields(self):
        """Test hidden fields are removed."""
        item = {
            "source_id": "test",
            "title": "Test Article",
            "ttl": 123456789,
            "content_hash": "abc123",
        }

        result = sanitize_item_for_response(item)

        assert "source_id" in result
        assert "title" in result
        assert "ttl" not in result
        assert "content_hash" not in result

    def test_preserves_allowed_fields(self):
        """Test allowed fields are preserved."""
        item = {
            "source_id": "test",
            "timestamp": "2025-11-17T10:00:00Z",
            "title": "Test",
            "sentiment": "positive",
            "score": 0.95,
            "tags": ["tech"],
            "source": "test",
            "status": "analyzed",
        }

        result = sanitize_item_for_response(item)

        assert result["source_id"] == "test"
        assert result["timestamp"] == "2025-11-17T10:00:00Z"
        assert result["title"] == "Test"
        assert result["sentiment"] == "positive"
        assert result["score"] == 0.95
        assert result["tags"] == ["tech"]
        assert result["status"] == "analyzed"

    def test_empty_item(self):
        """Test with empty item returns empty dict."""
        result = sanitize_item_for_response({})
        assert result == {}


class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_large_tag_list(self):
        """Test with many tags per item."""
        items = [
            {"tags": [f"tag{i}" for i in range(100)]},
        ]

        result = calculate_tag_distribution(items)

        assert len(result) == 100
        assert all(count == 1 for count in result.values())

    def test_unicode_in_tags(self):
        """Test tags with unicode characters."""
        items = [
            {"tags": ["日本語", "emoji🎉", "normal"]},
        ]

        result = calculate_tag_distribution(items)

        assert result["日本語"] == 1
        assert result["emoji🎉"] == 1
        assert result["normal"] == 1

    def test_decimal_score_values(self):
        """Test Decimal values from DynamoDB are handled."""
        items = [
            {"sentiment": "positive", "score": Decimal("0.95")},
            {"sentiment": "negative", "score": Decimal("0.85")},
        ]

        # Should not raise any errors
        result = calculate_sentiment_distribution(items)
        assert result["positive"] == 1
        assert result["negative"] == 1

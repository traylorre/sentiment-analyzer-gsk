"""Unit tests for DynamoDB upsert with source attribution using moto.

Tests atomic conditional writes for cross-source deduplication.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws

from src.lambdas.ingestion.dedup import (
    build_source_attribution,
    generate_dedup_key,
    upsert_article_with_source,
)


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB table with moto."""
    with mock_aws():
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
        table.meta.client.get_waiter("table_exists").wait(
            TableName="test-sentiment-items"
        )
        yield table


class TestUpsertWithMoto:
    """Integration tests using moto mock DynamoDB."""

    def test_create_new_article(self, dynamodb_table):
        """Creates new article when it doesn't exist."""
        dedup_key = generate_dedup_key("Apple Reports Earnings", "2025-12-21")
        timestamp = "2025-12-21T10:30:00Z"

        attr = build_source_attribution(
            source="tiingo",
            article_id="12345",
            url="https://tiingo.com/article",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Apple Reports Earnings",
        )

        result = upsert_article_with_source(
            table=dynamodb_table,
            dedup_key=dedup_key,
            timestamp=timestamp,
            source="tiingo",
            attribution=attr,
            item_data={
                "headline": "Apple Reports Earnings",
                "status": "pending",
                "matched_tickers": ["AAPL"],
            },
        )

        assert result == "created"

        # Verify item was created
        response = dynamodb_table.get_item(
            Key={"source_id": f"dedup:{dedup_key}", "timestamp": timestamp}
        )
        item = response["Item"]

        assert item["sources"] == ["tiingo"]
        assert "tiingo" in item["source_attribution"]
        assert item["status"] == "pending"
        assert item["headline"] == "Apple Reports Earnings"

    def test_add_second_source_to_existing(self, dynamodb_table):
        """Adds second source to existing article."""
        dedup_key = generate_dedup_key("Tesla Deliveries Beat", "2025-12-21")
        timestamp = "2025-12-21T11:00:00Z"

        # First: Create with Tiingo
        tiingo_attr = build_source_attribution(
            source="tiingo",
            article_id="11111",
            url="https://tiingo.com/tesla",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Tesla Deliveries Beat",
        )

        result1 = upsert_article_with_source(
            table=dynamodb_table,
            dedup_key=dedup_key,
            timestamp=timestamp,
            source="tiingo",
            attribution=tiingo_attr,
            item_data={"headline": "Tesla Deliveries Beat", "status": "pending"},
        )

        assert result1 == "created"

        # Second: Add Finnhub
        finnhub_attr = build_source_attribution(
            source="finnhub",
            article_id="fh-222",
            url="https://finnhub.io/tesla",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Tesla deliveries beat",
        )

        result2 = upsert_article_with_source(
            table=dynamodb_table,
            dedup_key=dedup_key,
            timestamp=timestamp,
            source="finnhub",
            attribution=finnhub_attr,
            item_data={},  # No new data needed
        )

        assert result2 == "updated"

        # Verify item has both sources
        response = dynamodb_table.get_item(
            Key={"source_id": f"dedup:{dedup_key}", "timestamp": timestamp}
        )
        item = response["Item"]

        assert "tiingo" in item["sources"]
        assert "finnhub" in item["sources"]
        assert "tiingo" in item["source_attribution"]
        assert "finnhub" in item["source_attribution"]

    def test_duplicate_source_not_added(self, dynamodb_table):
        """Same source is not added twice."""
        dedup_key = generate_dedup_key("Microsoft AI News", "2025-12-21")
        timestamp = "2025-12-21T12:00:00Z"

        attr1 = build_source_attribution(
            source="tiingo",
            article_id="33333",
            url="https://tiingo.com/msft",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Microsoft AI News",
        )

        # First insert
        result1 = upsert_article_with_source(
            table=dynamodb_table,
            dedup_key=dedup_key,
            timestamp=timestamp,
            source="tiingo",
            attribution=attr1,
            item_data={"headline": "Microsoft AI News", "status": "pending"},
        )

        assert result1 == "created"

        # Second insert with same source
        attr2 = build_source_attribution(
            source="tiingo",
            article_id="33333",  # Same article
            url="https://tiingo.com/msft",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Microsoft AI News",
        )

        result2 = upsert_article_with_source(
            table=dynamodb_table,
            dedup_key=dedup_key,
            timestamp=timestamp,
            source="tiingo",
            attribution=attr2,
            item_data={},
        )

        assert result2 == "duplicate"

        # Verify sources array has only one entry
        response = dynamodb_table.get_item(
            Key={"source_id": f"dedup:{dedup_key}", "timestamp": timestamp}
        )
        item = response["Item"]

        assert item["sources"] == ["tiingo"]

    def test_cross_source_dedup_end_to_end(self, dynamodb_table):
        """End-to-end test of cross-source deduplication."""
        # Same article, different formatting
        tiingo_headline = "NVIDIA Stock Hits All-Time High"
        finnhub_headline = "Nvidia stock hits all-time high"
        date = "2025-12-21"
        timestamp = f"{date}T14:00:00Z"

        # Both should generate same dedup key
        dedup_key = generate_dedup_key(tiingo_headline, date)
        assert dedup_key == generate_dedup_key(finnhub_headline, date)

        # Tiingo first
        tiingo_attr = build_source_attribution(
            source="tiingo",
            article_id="t-nvda-1",
            url="https://tiingo.com/nvda",
            crawl_timestamp=datetime.now(UTC),
            original_headline=tiingo_headline,
            source_name="reuters",
        )

        result1 = upsert_article_with_source(
            table=dynamodb_table,
            dedup_key=dedup_key,
            timestamp=timestamp,
            source="tiingo",
            attribution=tiingo_attr,
            item_data={
                "headline": tiingo_headline,
                "normalized_headline": "nvidia stock hits alltime high",
                "status": "pending",
                "matched_tickers": ["NVDA"],
            },
        )

        assert result1 == "created"

        # Finnhub second (same article)
        finnhub_attr = build_source_attribution(
            source="finnhub",
            article_id="fh-nvda-99",
            url="https://finnhub.io/nvda",
            crawl_timestamp=datetime.now(UTC),
            original_headline=finnhub_headline,
            source_name="reuters",
        )

        result2 = upsert_article_with_source(
            table=dynamodb_table,
            dedup_key=dedup_key,
            timestamp=timestamp,
            source="finnhub",
            attribution=finnhub_attr,
            item_data={},
        )

        assert result2 == "updated"

        # Verify final state
        response = dynamodb_table.get_item(
            Key={"source_id": f"dedup:{dedup_key}", "timestamp": timestamp}
        )
        item = response["Item"]

        # Only one record
        assert item["source_id"] == f"dedup:{dedup_key}"

        # Both sources tracked
        assert len(item["sources"]) == 2
        assert "tiingo" in item["sources"]
        assert "finnhub" in item["sources"]

        # Both attributions preserved
        assert item["source_attribution"]["tiingo"]["article_id"] == "t-nvda-1"
        assert item["source_attribution"]["finnhub"]["article_id"] == "fh-nvda-99"

        # Original headlines preserved in attribution
        assert (
            item["source_attribution"]["tiingo"]["original_headline"] == tiingo_headline
        )
        assert (
            item["source_attribution"]["finnhub"]["original_headline"]
            == finnhub_headline
        )


class TestDedupKeyIntegration:
    """Integration tests for dedup key in upsert flow."""

    def test_different_articles_create_separate_records(self, dynamodb_table):
        """Different articles create separate records."""
        date = "2025-12-21"
        timestamp = f"{date}T15:00:00Z"

        # Article 1: Apple news
        key1 = generate_dedup_key("Apple Reports Q4 Earnings", date)
        attr1 = build_source_attribution(
            source="tiingo",
            article_id="apple-1",
            url="https://tiingo.com/apple",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Apple Reports Q4 Earnings",
        )

        result1 = upsert_article_with_source(
            table=dynamodb_table,
            dedup_key=key1,
            timestamp=timestamp,
            source="tiingo",
            attribution=attr1,
            item_data={"headline": "Apple Reports Q4 Earnings", "status": "pending"},
        )

        # Article 2: Microsoft news
        key2 = generate_dedup_key("Microsoft Reports Q4 Earnings", date)
        attr2 = build_source_attribution(
            source="tiingo",
            article_id="msft-1",
            url="https://tiingo.com/msft",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Microsoft Reports Q4 Earnings",
        )

        result2 = upsert_article_with_source(
            table=dynamodb_table,
            dedup_key=key2,
            timestamp=timestamp,
            source="tiingo",
            attribution=attr2,
            item_data={
                "headline": "Microsoft Reports Q4 Earnings",
                "status": "pending",
            },
        )

        assert result1 == "created"
        assert result2 == "created"
        assert key1 != key2

        # Both records exist
        scan = dynamodb_table.scan()
        assert scan["Count"] == 2

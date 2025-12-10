"""Unit tests for source attribution tracking (T029).

Verifies that the storage layer properly tracks which data source
provided each news item, enabling failover transparency.
"""

from datetime import UTC, datetime

from src.lambdas.shared.models.news_item import NewsItem
from src.lambdas.shared.utils.dedup import generate_dedup_key


class TestSourceAttributionInNewsItem:
    """Tests for source attribution in NewsItem model."""

    def test_news_item_stores_tiingo_source(self) -> None:
        """NewsItem should correctly store tiingo as source."""
        dedup_key = generate_dedup_key(
            headline="Test Article",
            source="tiingo",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        item = NewsItem(
            dedup_key=dedup_key,
            source="tiingo",
            headline="Test Article",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 5, 0, tzinfo=UTC),
        )

        assert item.source == "tiingo"

    def test_news_item_stores_finnhub_source(self) -> None:
        """NewsItem should correctly store finnhub as source."""
        dedup_key = generate_dedup_key(
            headline="Test Article",
            source="finnhub",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        item = NewsItem(
            dedup_key=dedup_key,
            source="finnhub",
            headline="Test Article",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 5, 0, tzinfo=UTC),
        )

        assert item.source == "finnhub"

    def test_source_included_in_sort_key(self) -> None:
        """Sort key should include source for attribution queries."""
        dedup_key = generate_dedup_key(
            headline="Test Article",
            source="tiingo",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        item = NewsItem(
            dedup_key=dedup_key,
            source="tiingo",
            headline="Test Article",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 5, 0, tzinfo=UTC),
        )

        # SK format: {source}#{ingested_at_iso}
        assert item.sk.startswith("tiingo#")

    def test_source_included_in_dynamodb_item(self) -> None:
        """DynamoDB item should include source attribute."""
        dedup_key = generate_dedup_key(
            headline="Test Article",
            source="finnhub",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        item = NewsItem(
            dedup_key=dedup_key,
            source="finnhub",
            headline="Test Article",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 5, 0, tzinfo=UTC),
        )

        dynamo_item = item.to_dynamodb_item()

        assert dynamo_item["source"] == "finnhub"


class TestSourceAttributionFromDynamoDB:
    """Tests for source attribution when reading from DynamoDB."""

    def test_source_preserved_on_read(self) -> None:
        """Source should be preserved when reading from DynamoDB."""
        dynamo_item = {
            "PK": "NEWS#abcd1234abcd1234abcd1234abcd1234",
            "SK": "finnhub#2025-12-09T14:05:00+00:00",
            "dedup_key": "abcd1234abcd1234abcd1234abcd1234",
            "source": "finnhub",
            "headline": "Test Article",
            "published_at": "2025-12-09T14:00:00+00:00",
            "ingested_at": "2025-12-09T14:05:00+00:00",
            "tickers": ["AAPL"],
            "tags": [],
            "entity_type": "NEWS_ITEM",
        }

        item = NewsItem.from_dynamodb_item(dynamo_item)

        assert item.source == "finnhub"


class TestSourceAttributionDifferentiation:
    """Tests for source-based differentiation."""

    def test_same_article_different_sources_have_different_dedup_keys(self) -> None:
        """Same headline from different sources should have different dedup keys."""
        headline = "Apple Reports Strong Earnings"
        published_at = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        tiingo_key = generate_dedup_key(
            headline=headline,
            source="tiingo",
            published_at=published_at,
        )

        finnhub_key = generate_dedup_key(
            headline=headline,
            source="finnhub",
            published_at=published_at,
        )

        # Different sources should produce different keys
        # This allows tracking the same news from multiple sources
        assert tiingo_key != finnhub_key

    def test_source_attribution_enables_failover_tracking(self) -> None:
        """Source field enables identifying which source provided data during failover."""
        # Simulate normal collection from tiingo
        tiingo_item = NewsItem(
            dedup_key="aaaa" * 8,
            source="tiingo",
            headline="Normal Collection",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 5, 0, tzinfo=UTC),
        )

        # Simulate failover collection from finnhub
        finnhub_item = NewsItem(
            dedup_key="bbbb" * 8,
            source="finnhub",
            headline="Failover Collection",
            published_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 15, 0, tzinfo=UTC),
        )

        # Both items can coexist and be distinguished by source
        assert tiingo_item.source == "tiingo"
        assert finnhub_item.source == "finnhub"

        # SK includes source for querying by source
        assert "tiingo" in tiingo_item.sk
        assert "finnhub" in finnhub_item.sk

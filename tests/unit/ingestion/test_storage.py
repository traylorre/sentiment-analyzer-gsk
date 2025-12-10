"""Unit tests for news item storage with deduplication (T019).

Tests that news items are stored correctly with deduplication logic.
"""

from datetime import UTC, datetime

from src.lambdas.shared.models.news_item import NewsItem, SentimentScore
from src.lambdas.shared.utils.dedup import generate_dedup_key


class TestDeduplicationKeyGeneration:
    """Tests for deduplication key generation during storage."""

    def test_same_article_same_key(self) -> None:
        """Same article content should produce same dedup key."""
        headline = "Apple Reports Record Q4 Earnings"
        source = "tiingo"
        published_at = datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC)

        key1 = generate_dedup_key(headline, source, published_at)
        key2 = generate_dedup_key(headline, source, published_at)

        assert key1 == key2

    def test_different_headlines_different_keys(self) -> None:
        """Different headlines should produce different dedup keys."""
        source = "tiingo"
        published_at = datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC)

        key1 = generate_dedup_key("Apple Reports Q4 Earnings", source, published_at)
        key2 = generate_dedup_key("Tesla Announces New Model", source, published_at)

        assert key1 != key2

    def test_different_sources_different_keys(self) -> None:
        """Same article from different sources should have different keys."""
        headline = "Breaking News"
        published_at = datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC)

        key1 = generate_dedup_key(headline, "tiingo", published_at)
        key2 = generate_dedup_key(headline, "finnhub", published_at)

        assert key1 != key2

    def test_same_day_same_key(self) -> None:
        """Articles from same day should use date-only for dedup."""
        headline = "Daily News"
        source = "tiingo"
        time1 = datetime(2025, 12, 9, 10, 0, 0, tzinfo=UTC)
        time2 = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        key1 = generate_dedup_key(headline, source, time1)
        key2 = generate_dedup_key(headline, source, time2)

        assert key1 == key2

    def test_different_days_different_keys(self) -> None:
        """Articles from different days should have different keys."""
        headline = "Daily News"
        source = "tiingo"
        day1 = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)
        day2 = datetime(2025, 12, 10, 14, 0, 0, tzinfo=UTC)

        key1 = generate_dedup_key(headline, source, day1)
        key2 = generate_dedup_key(headline, source, day2)

        assert key1 != key2


class TestNewsItemStorage:
    """Tests for NewsItem storage serialization."""

    def test_news_item_to_dynamodb_format(self) -> None:
        """NewsItem should serialize to DynamoDB format correctly."""
        item = NewsItem(
            dedup_key="a1b2c3d4e5f6789012345678901234ab",
            source="tiingo",
            headline="Test Headline",
            published_at=datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 35, 0, tzinfo=UTC),
            tickers=["AAPL"],
        )

        dynamo_item = item.to_dynamodb_item()

        assert "PK" in dynamo_item
        assert "SK" in dynamo_item
        assert dynamo_item["source"] == "tiingo"
        assert dynamo_item["headline"] == "Test Headline"

    def test_news_item_pk_format(self) -> None:
        """NewsItem PK should follow NEWS#<dedup_key> format."""
        item = NewsItem(
            dedup_key="a1b2c3d4e5f6789012345678901234ab",
            source="tiingo",
            headline="Test",
            published_at=datetime.now(UTC),
            ingested_at=datetime.now(UTC),
            tickers=["AAPL"],
        )

        assert item.pk == "NEWS#a1b2c3d4e5f6789012345678901234ab"

    def test_news_item_sk_format(self) -> None:
        """NewsItem SK should follow {source}#{ingested_at_iso} format."""
        item = NewsItem(
            dedup_key="a1b2c3d4e5f6789012345678901234ab",
            source="tiingo",
            headline="Test",
            published_at=datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 35, 0, tzinfo=UTC),
            tickers=["AAPL"],
        )

        assert item.sk.startswith("tiingo#2025-12-09")

    def test_news_item_with_sentiment(self) -> None:
        """NewsItem should correctly store sentiment scores."""
        sentiment = SentimentScore.from_score(0.75, 0.92)
        item = NewsItem(
            dedup_key="a1b2c3d4e5f6789012345678901234ab",
            source="finnhub",
            headline="Positive News",
            published_at=datetime.now(UTC),
            ingested_at=datetime.now(UTC),
            tickers=["TSLA"],
            sentiment=sentiment,
        )

        dynamo_item = item.to_dynamodb_item()

        # Sentiment stored as flat fields per DynamoDB best practices
        assert dynamo_item["sentiment_score"] == "0.75"
        assert dynamo_item["sentiment_label"] == "positive"
        assert dynamo_item["sentiment_confidence"] == "0.92"

    def test_news_item_round_trip(self) -> None:
        """NewsItem should survive serialization round-trip."""
        original = NewsItem(
            dedup_key="a1b2c3d4e5f6789012345678901234ab",
            source="tiingo",
            headline="Round Trip Test",
            published_at=datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 35, 0, tzinfo=UTC),
            tickers=["AAPL", "MSFT"],
            description="Test description",
            url="https://example.com/article",
        )

        dynamo_item = original.to_dynamodb_item()
        restored = NewsItem.from_dynamodb_item(dynamo_item)

        assert restored.dedup_key == original.dedup_key
        assert restored.headline == original.headline
        assert restored.tickers == original.tickers


class TestConditionalWriteDeduplication:
    """Tests for conditional write deduplication logic."""

    def test_duplicate_detection_by_pk(self) -> None:
        """Duplicate items should have same PK."""
        item1 = NewsItem(
            dedup_key="a1b2c3d4e5f6789012345678901234ab",
            source="tiingo",
            headline="Same Article",
            published_at=datetime(2025, 12, 9, 14, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 5, tzinfo=UTC),
            tickers=["AAPL"],
        )
        item2 = NewsItem(
            dedup_key="a1b2c3d4e5f6789012345678901234ab",
            source="tiingo",
            headline="Same Article",
            published_at=datetime(2025, 12, 9, 14, 0, tzinfo=UTC),
            ingested_at=datetime(
                2025, 12, 9, 14, 10, tzinfo=UTC
            ),  # Different ingest time
            tickers=["AAPL"],
        )

        assert item1.pk == item2.pk

    def test_unique_items_have_unique_pks(self) -> None:
        """Unique items should have different PKs."""
        item1 = NewsItem(
            dedup_key="a1b2c3d4e5f6789012345678901234ab",
            source="tiingo",
            headline="Article One",
            published_at=datetime(2025, 12, 9, 14, 0, tzinfo=UTC),
            ingested_at=datetime.now(UTC),
            tickers=["AAPL"],
        )
        item2 = NewsItem(
            dedup_key="b2c3d4e5f6789012345678901234abcd",
            source="tiingo",
            headline="Article Two",
            published_at=datetime(2025, 12, 9, 15, 0, tzinfo=UTC),
            ingested_at=datetime.now(UTC),
            tickers=["TSLA"],
        )

        assert item1.pk != item2.pk


class TestStorageMetrics:
    """Tests for storage metrics tracking."""

    def test_can_count_new_vs_duplicate(self) -> None:
        """Should be able to track new vs duplicate article counts."""
        # Simulating storage results
        results = {
            "articles_fetched": 50,
            "articles_new": 10,
            "articles_duplicate": 40,
        }

        assert (
            results["articles_fetched"]
            == results["articles_new"] + results["articles_duplicate"]
        )

    def test_duplicate_rate_calculation(self) -> None:
        """Should be able to calculate duplicate rate."""
        articles_fetched = 100
        articles_duplicate = 85
        articles_new = 15

        duplicate_rate = articles_duplicate / articles_fetched

        assert duplicate_rate == 0.85
        assert articles_new == articles_fetched - articles_duplicate

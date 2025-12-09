"""Unit tests for NewsItem pydantic model.

Tests NewsItem creation, validation, and DynamoDB serialization.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.lambdas.shared.models.news_item import NewsItem, SentimentScore


class TestSentimentScore:
    """Tests for SentimentScore embedded model."""

    def test_valid_sentiment_score(self) -> None:
        """Valid sentiment score should be created."""
        sentiment = SentimentScore(score=0.75, confidence=0.9, label="positive")

        assert sentiment.score == 0.75
        assert sentiment.confidence == 0.9
        assert sentiment.label == "positive"

    def test_from_score_positive(self) -> None:
        """Score >= 0.33 should derive 'positive' label."""
        sentiment = SentimentScore.from_score(score=0.5, confidence=0.8)

        assert sentiment.score == 0.5
        assert sentiment.confidence == 0.8
        assert sentiment.label == "positive"

    def test_from_score_negative(self) -> None:
        """Score <= -0.33 should derive 'negative' label."""
        sentiment = SentimentScore.from_score(score=-0.5, confidence=0.85)

        assert sentiment.score == -0.5
        assert sentiment.label == "negative"

    def test_from_score_neutral(self) -> None:
        """Score between -0.33 and 0.33 should derive 'neutral' label."""
        sentiment = SentimentScore.from_score(score=0.0, confidence=0.7)

        assert sentiment.score == 0.0
        assert sentiment.label == "neutral"

    def test_from_score_boundary_positive(self) -> None:
        """Score at exactly 0.33 should be 'positive'."""
        sentiment = SentimentScore.from_score(score=0.33, confidence=0.9)
        assert sentiment.label == "positive"

    def test_from_score_boundary_negative(self) -> None:
        """Score at exactly -0.33 should be 'negative'."""
        sentiment = SentimentScore.from_score(score=-0.33, confidence=0.9)
        assert sentiment.label == "negative"

    def test_score_out_of_range_high(self) -> None:
        """Score > 1.0 should raise validation error."""
        with pytest.raises(ValidationError):
            SentimentScore(score=1.5, confidence=0.9, label="positive")

    def test_score_out_of_range_low(self) -> None:
        """Score < -1.0 should raise validation error."""
        with pytest.raises(ValidationError):
            SentimentScore(score=-1.5, confidence=0.9, label="negative")

    def test_confidence_out_of_range(self) -> None:
        """Confidence > 1.0 should raise validation error."""
        with pytest.raises(ValidationError):
            SentimentScore(score=0.5, confidence=1.5, label="positive")


class TestNewsItem:
    """Tests for NewsItem model."""

    @pytest.fixture
    def valid_news_item_data(self) -> dict:
        """Fixture for valid NewsItem data."""
        return {
            "dedup_key": "a" * 32,  # 32 char hex string
            "source": "tiingo",
            "headline": "Apple Q4 Earnings Beat Expectations",
            "published_at": datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
            "ingested_at": datetime(2025, 12, 9, 14, 35, 0, tzinfo=UTC),
            "tickers": ["AAPL"],
        }

    def test_create_minimal_news_item(self, valid_news_item_data: dict) -> None:
        """NewsItem with only required fields should be created."""
        item = NewsItem(**valid_news_item_data)

        assert item.dedup_key == "a" * 32
        assert item.source == "tiingo"
        assert item.headline == "Apple Q4 Earnings Beat Expectations"
        assert item.tickers == ["AAPL"]
        assert item.sentiment is None

    def test_create_full_news_item(self, valid_news_item_data: dict) -> None:
        """NewsItem with all fields should be created."""
        valid_news_item_data.update(
            {
                "description": "Apple reported strong Q4 results...",
                "url": "https://example.com/article",
                "tags": ["earnings", "tech"],
                "source_name": "Bloomberg",
                "sentiment": SentimentScore(
                    score=0.6, confidence=0.85, label="positive"
                ),
            }
        )
        item = NewsItem(**valid_news_item_data)

        assert item.description == "Apple reported strong Q4 results..."
        assert item.url == "https://example.com/article"
        assert item.tags == ["earnings", "tech"]
        assert item.source_name == "Bloomberg"
        assert item.sentiment is not None
        assert item.sentiment.score == 0.6

    def test_invalid_source(self, valid_news_item_data: dict) -> None:
        """Invalid source should raise validation error."""
        valid_news_item_data["source"] = "invalid_source"
        with pytest.raises(ValidationError):
            NewsItem(**valid_news_item_data)

    def test_dedup_key_too_short(self, valid_news_item_data: dict) -> None:
        """Dedup key shorter than 32 chars should raise validation error."""
        valid_news_item_data["dedup_key"] = "abc"
        with pytest.raises(ValidationError):
            NewsItem(**valid_news_item_data)

    def test_dedup_key_too_long(self, valid_news_item_data: dict) -> None:
        """Dedup key longer than 32 chars should raise validation error."""
        valid_news_item_data["dedup_key"] = "a" * 64
        with pytest.raises(ValidationError):
            NewsItem(**valid_news_item_data)

    def test_empty_headline(self, valid_news_item_data: dict) -> None:
        """Empty headline should raise validation error."""
        valid_news_item_data["headline"] = ""
        with pytest.raises(ValidationError):
            NewsItem(**valid_news_item_data)

    def test_pk_property(self, valid_news_item_data: dict) -> None:
        """PK should be formatted as NEWS#{dedup_key}."""
        item = NewsItem(**valid_news_item_data)
        assert item.pk == f"NEWS#{'a' * 32}"

    def test_sk_property(self, valid_news_item_data: dict) -> None:
        """SK should be formatted as {source}#{ingested_at_iso}."""
        item = NewsItem(**valid_news_item_data)
        assert item.sk.startswith("tiingo#2025-12-09T14:35:00")


class TestNewsItemDynamoDB:
    """Tests for NewsItem DynamoDB serialization."""

    @pytest.fixture
    def news_item(self) -> NewsItem:
        """Fixture for a complete NewsItem."""
        return NewsItem(
            dedup_key="b" * 32,
            source="finnhub",
            headline="Tesla Stock Update",
            description="Tesla shares rose...",
            url="https://example.com/tesla",
            published_at=datetime(2025, 12, 9, 10, 0, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 10, 5, 0, tzinfo=UTC),
            tickers=["TSLA"],
            tags=["automotive", "ev"],
            source_name="Reuters",
            sentiment=SentimentScore(score=0.45, confidence=0.8, label="positive"),
        )

    def test_to_dynamodb_item(self, news_item: NewsItem) -> None:
        """to_dynamodb_item should serialize all fields correctly."""
        item = news_item.to_dynamodb_item()

        assert item["PK"] == f"NEWS#{'b' * 32}"
        assert item["SK"].startswith("finnhub#2025-12-09T10:05:00")
        assert item["entity_type"] == "NEWS_ITEM"
        assert item["headline"] == "Tesla Stock Update"
        assert item["description"] == "Tesla shares rose..."
        assert item["tickers"] == ["TSLA"]
        assert item["sentiment_score"] == "0.45"
        assert item["sentiment_confidence"] == "0.8"
        assert item["sentiment_label"] == "positive"

    def test_from_dynamodb_item(self, news_item: NewsItem) -> None:
        """from_dynamodb_item should deserialize correctly."""
        db_item = news_item.to_dynamodb_item()
        restored = NewsItem.from_dynamodb_item(db_item)

        assert restored.dedup_key == news_item.dedup_key
        assert restored.source == news_item.source
        assert restored.headline == news_item.headline
        assert restored.sentiment is not None
        assert restored.sentiment.score == 0.45
        assert restored.sentiment.label == "positive"

    def test_round_trip_without_sentiment(self) -> None:
        """Item without sentiment should round-trip correctly."""
        item = NewsItem(
            dedup_key="c" * 32,
            source="tiingo",
            headline="Market Summary",
            published_at=datetime(2025, 12, 9, 16, 0, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 16, 1, 0, tzinfo=UTC),
        )

        db_item = item.to_dynamodb_item()
        restored = NewsItem.from_dynamodb_item(db_item)

        assert restored.sentiment is None
        assert "sentiment_score" not in db_item

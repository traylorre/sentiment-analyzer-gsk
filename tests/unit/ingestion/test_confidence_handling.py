"""Unit tests for confidence handling (T039).

Tests the confidence scoring strategy per US3 clarification:
- Finnhub: Use native confidence score from API response
- Tiingo: Mark as "unscored" (confidence=null)

Future work: Research deriving confidence from article metadata
for sources that don't provide native confidence.
"""

from datetime import UTC, datetime

from src.lambdas.shared.models.news_item import NewsItem, SentimentScore
from src.lambdas.shared.utils.dedup import generate_dedup_key


class TestFinnhubConfidenceHandling:
    """Tests for Finnhub native confidence handling."""

    def test_finnhub_sentiment_has_native_confidence(self) -> None:
        """Finnhub sentiment should include native confidence score."""
        # Simulate Finnhub response with native confidence
        finnhub_confidence = 0.85

        sentiment = SentimentScore.from_score(score=0.7, confidence=finnhub_confidence)

        assert sentiment.confidence == 0.85
        assert sentiment.is_low_confidence is False

    def test_finnhub_high_confidence_not_flagged(self) -> None:
        """Finnhub with confidence >= 0.6 should not be flagged as low."""
        sentiment = SentimentScore.from_score(score=0.5, confidence=0.75)

        assert sentiment.confidence == 0.75
        assert sentiment.is_low_confidence is False

    def test_finnhub_low_confidence_flagged(self) -> None:
        """Finnhub with confidence < 0.6 should be flagged as low."""
        sentiment = SentimentScore.from_score(score=0.5, confidence=0.45)

        assert sentiment.confidence == 0.45
        assert sentiment.is_low_confidence is True

    def test_finnhub_news_item_with_sentiment(self) -> None:
        """NewsItem from Finnhub should have complete sentiment data."""
        dedup_key = generate_dedup_key(
            headline="Market Rally Continues",
            source="finnhub",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        sentiment = SentimentScore.from_score(score=0.65, confidence=0.9)

        item = NewsItem(
            dedup_key=dedup_key,
            source="finnhub",
            headline="Market Rally Continues",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 5, 0, tzinfo=UTC),
            sentiment=sentiment,
        )

        assert item.sentiment is not None
        assert item.sentiment.score == 0.65
        assert item.sentiment.confidence == 0.9
        assert item.sentiment.label == "positive"
        assert item.sentiment.is_low_confidence is False


class TestTiingoUnscoredHandling:
    """Tests for Tiingo unscored (null confidence) handling."""

    def test_tiingo_sentiment_null_confidence(self) -> None:
        """Tiingo sentiment should have null confidence (unscored)."""
        # Tiingo doesn't provide native confidence - mark as unscored
        sentiment = SentimentScore.from_score(score=0.5, confidence=None)

        assert sentiment.confidence is None
        assert sentiment.is_low_confidence is True

    def test_tiingo_unscored_always_low_confidence(self) -> None:
        """Tiingo unscored (null) should always be flagged as low confidence."""
        # Even with a high sentiment score, null confidence = low confidence
        sentiment = SentimentScore.from_score(score=0.95, confidence=None)

        assert sentiment.confidence is None
        assert sentiment.is_low_confidence is True

    def test_tiingo_news_item_with_unscored_sentiment(self) -> None:
        """NewsItem from Tiingo should have sentiment with null confidence."""
        dedup_key = generate_dedup_key(
            headline="Apple Reports Strong Earnings",
            source="tiingo",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        # Tiingo: score from article analysis, confidence = null
        sentiment = SentimentScore.from_score(score=0.72, confidence=None)

        item = NewsItem(
            dedup_key=dedup_key,
            source="tiingo",
            headline="Apple Reports Strong Earnings",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 5, 0, tzinfo=UTC),
            sentiment=sentiment,
        )

        assert item.sentiment is not None
        assert item.sentiment.score == 0.72
        assert item.sentiment.confidence is None
        assert item.sentiment.label == "positive"
        assert item.sentiment.is_low_confidence is True

    def test_tiingo_negative_sentiment_unscored(self) -> None:
        """Tiingo negative sentiment should also be unscored."""
        sentiment = SentimentScore.from_score(score=-0.6, confidence=None)

        assert sentiment.confidence is None
        assert sentiment.label == "negative"
        assert sentiment.is_low_confidence is True


class TestConfidenceSourceDifferentiation:
    """Tests for differentiating confidence handling by source."""

    def test_same_headline_different_confidence_handling(self) -> None:
        """Same headline from different sources has different confidence handling."""
        headline = "Tesla Stock Rises on Delivery Numbers"
        pub_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)
        ingest_time = datetime(2025, 12, 9, 14, 5, 0, tzinfo=UTC)

        # Finnhub: native confidence
        finnhub_sentiment = SentimentScore.from_score(score=0.55, confidence=0.82)
        finnhub_item = NewsItem(
            dedup_key=generate_dedup_key(headline, "finnhub", pub_time),
            source="finnhub",
            headline=headline,
            published_at=pub_time,
            ingested_at=ingest_time,
            sentiment=finnhub_sentiment,
        )

        # Tiingo: unscored (null confidence)
        tiingo_sentiment = SentimentScore.from_score(score=0.55, confidence=None)
        tiingo_item = NewsItem(
            dedup_key=generate_dedup_key(headline, "tiingo", pub_time),
            source="tiingo",
            headline=headline,
            published_at=pub_time,
            ingested_at=ingest_time,
            sentiment=tiingo_sentiment,
        )

        # Same score, different confidence
        assert finnhub_item.sentiment.score == tiingo_item.sentiment.score
        assert finnhub_item.sentiment.confidence == 0.82
        assert tiingo_item.sentiment.confidence is None

        # Different low_confidence flag
        assert finnhub_item.sentiment.is_low_confidence is False
        assert tiingo_item.sentiment.is_low_confidence is True

    def test_confidence_preserved_in_dynamodb_conversion(self) -> None:
        """Null confidence should be preserved in DynamoDB round-trip."""
        dedup_key = generate_dedup_key(
            headline="Test Article",
            source="tiingo",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        # Create item with null confidence
        sentiment = SentimentScore.from_score(score=0.5, confidence=None)
        item = NewsItem(
            dedup_key=dedup_key,
            source="tiingo",
            headline="Test Article",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            ingested_at=datetime(2025, 12, 9, 14, 5, 0, tzinfo=UTC),
            sentiment=sentiment,
        )

        # Convert to DynamoDB format and back
        dynamo_item = item.to_dynamodb_item()
        restored_item = NewsItem.from_dynamodb_item(dynamo_item)

        # Confidence should still be None after round-trip
        assert restored_item.sentiment is not None
        assert restored_item.sentiment.confidence is None
        assert restored_item.sentiment.is_low_confidence is True


class TestConfidenceThresholdBoundary:
    """Tests for the 0.6 confidence threshold boundary."""

    def test_confidence_just_below_threshold(self) -> None:
        """Confidence of 0.59 should be flagged as low."""
        sentiment = SentimentScore.from_score(score=0.5, confidence=0.59)
        assert sentiment.is_low_confidence is True

    def test_confidence_at_threshold(self) -> None:
        """Confidence of 0.6 should NOT be flagged as low."""
        sentiment = SentimentScore.from_score(score=0.5, confidence=0.6)
        assert sentiment.is_low_confidence is False

    def test_confidence_just_above_threshold(self) -> None:
        """Confidence of 0.61 should NOT be flagged as low."""
        sentiment = SentimentScore.from_score(score=0.5, confidence=0.61)
        assert sentiment.is_low_confidence is False

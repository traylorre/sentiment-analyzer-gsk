"""Unit tests for SentimentResult model."""

from datetime import UTC, datetime

from src.lambdas.shared.models.sentiment_result import (
    SentimentResult,
    SentimentSource,
    sentiment_label_from_score,
)


def _make_result(**overrides):
    defaults = {
        "result_id": "abc-123",
        "ticker": "TSLA",
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "sentiment_score": 0.75,
        "sentiment_label": "positive",
        "confidence": 0.9,
        "source": SentimentSource(
            source_type="tiingo",
            inference_version="v2",
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    }
    defaults.update(overrides)
    return SentimentResult(**defaults)


class TestSentimentResultProperties:
    def test_pk(self):
        assert _make_result().pk == "TICKER#TSLA"

    def test_sk_contains_timestamp_and_source(self):
        sk = _make_result().sk
        assert "tiingo" in sk


class TestSentimentResultDynamoDB:
    def test_to_dynamodb_item(self):
        item = _make_result().to_dynamodb_item()
        assert item["PK"] == "TICKER#TSLA"
        assert item["entity_type"] == "SENTIMENT_RESULT"
        assert item["sentiment_score"] == "0.75"
        assert item["source_type"] == "tiingo"

    def test_from_dynamodb_item_roundtrip(self):
        original = _make_result()
        item = original.to_dynamodb_item()
        restored = SentimentResult.from_dynamodb_item(item)
        assert restored.ticker == "TSLA"
        assert restored.sentiment_score == 0.75
        assert restored.source.source_type == "tiingo"
        assert restored.source.inference_version == "v2"


class TestSentimentLabelFromScore:
    def test_negative(self):
        assert sentiment_label_from_score(-0.5) == "negative"

    def test_positive(self):
        assert sentiment_label_from_score(0.5) == "positive"

    def test_neutral(self):
        assert sentiment_label_from_score(0.0) == "neutral"

    def test_boundary_negative(self):
        assert sentiment_label_from_score(-0.33) == "negative"

    def test_boundary_positive(self):
        assert sentiment_label_from_score(0.33) == "positive"

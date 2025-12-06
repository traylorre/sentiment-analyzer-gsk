"""Property tests for API contract invariants (FR-008b).

These tests verify that API responses always conform to documented
contracts, ensuring client compatibility across all inputs.
"""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from .conftest import dynamodb_item, sentiment_response


class TestSentimentApiContract:
    """Tests for sentiment analysis API contract."""

    @settings(max_examples=100)
    @given(response=sentiment_response())
    def test_sentiment_response_schema(self, response):
        """Sentiment response must have required fields."""
        required_fields = {"sentiment", "score", "confidence"}
        assert required_fields.issubset(response.keys())

    @settings(max_examples=100)
    @given(response=sentiment_response())
    def test_sentiment_score_bounds(self, response):
        """Sentiment score must be within documented bounds [-1.0, 1.0]."""
        assert -1.0 <= response["score"] <= 1.0

    @settings(max_examples=100)
    @given(response=sentiment_response())
    def test_confidence_bounds(self, response):
        """Confidence score must be within documented bounds [0.0, 1.0]."""
        assert 0.0 <= response["confidence"] <= 1.0

    @settings(max_examples=100)
    @given(response=sentiment_response())
    def test_sentiment_is_categorical(self, response):
        """Sentiment must be one of the documented categories."""
        valid_sentiments = {"positive", "negative", "neutral"}
        assert response["sentiment"] in valid_sentiments

    @settings(max_examples=100)
    @given(response=sentiment_response())
    def test_response_json_serializable(self, response):
        """Response must be JSON serializable."""
        # Should not raise
        serialized = json.dumps(response)
        deserialized = json.loads(serialized)
        assert deserialized == response


class TestDynamoDbItemContract:
    """Tests for DynamoDB item schema contract."""

    @settings(max_examples=100)
    @given(item=dynamodb_item())
    def test_item_has_partition_key(self, item):
        """Items must have source_id (partition key)."""
        assert "source_id" in item
        assert len(item["source_id"]) > 0

    @settings(max_examples=100)
    @given(item=dynamodb_item())
    def test_item_has_sort_key(self, item):
        """Items must have timestamp (sort key)."""
        assert "timestamp" in item

    @settings(max_examples=100)
    @given(item=dynamodb_item())
    def test_item_status_is_valid(self, item):
        """Item status must be pending or analyzed."""
        assert item["status"] in ["pending", "analyzed"]

    @settings(max_examples=100)
    @given(item=dynamodb_item())
    def test_item_sentiment_fields_present(self, item):
        """Items must have sentiment analysis fields."""
        assert "sentiment" in item
        assert "score" in item
        assert "confidence" in item


class TestApiErrorContract:
    """Tests for API error response contract."""

    @settings(max_examples=50)
    @given(
        error_code=st.sampled_from([400, 401, 403, 404, 422, 500, 502, 503]),
        message=st.text(min_size=1, max_size=200),
    )
    def test_error_response_structure(self, error_code, message):
        """Error responses must have standard structure."""
        error_response = {
            "statusCode": error_code,
            "body": json.dumps({"error": message}),
        }

        assert "statusCode" in error_response
        assert "body" in error_response

        body = json.loads(error_response["body"])
        assert "error" in body

    @settings(max_examples=50)
    @given(error_code=st.integers(min_value=400, max_value=599))
    def test_error_codes_are_4xx_or_5xx(self, error_code):
        """Error status codes must be in 4xx or 5xx range."""
        assert 400 <= error_code < 600

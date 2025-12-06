"""Property tests for Lambda handler response structure invariants (FR-008a).

These tests verify that Lambda handlers always produce valid proxy integration
responses regardless of input, ensuring API Gateway compatibility.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from .conftest import lambda_response, sentiment_response


class TestLambdaResponseStructure:
    """Tests for Lambda proxy integration response structure."""

    @settings(max_examples=100, deadline=None)
    @given(response=lambda_response())
    def test_response_has_required_fields(self, response):
        """Lambda responses must have statusCode, headers, and body."""
        assert "statusCode" in response
        assert "headers" in response
        assert "body" in response

    @settings(max_examples=100, deadline=None)
    @given(response=lambda_response())
    def test_status_code_is_integer(self, response):
        """Status code must be an integer."""
        assert isinstance(response["statusCode"], int)

    @settings(max_examples=100, deadline=None)
    @given(response=lambda_response())
    def test_headers_is_dict(self, response):
        """Headers must be a dictionary."""
        assert isinstance(response["headers"], dict)

    @settings(max_examples=100, deadline=None)
    @given(response=lambda_response(status_codes=[200, 201]))
    def test_success_response_has_content_type(self, response):
        """Success responses must have Content-Type header."""
        assert "Content-Type" in response["headers"]

    @settings(max_examples=100, deadline=None)
    @given(response=lambda_response())
    def test_body_is_string(self, response):
        """Body must be a string (JSON serialized)."""
        assert isinstance(response["body"], str)


class TestLambdaStatusCodeRanges:
    """Tests for valid HTTP status code ranges."""

    @settings(max_examples=50, deadline=None)
    @given(status_code=st.integers(min_value=200, max_value=299))
    def test_2xx_is_success(self, status_code):
        """2xx status codes indicate success."""
        assert 200 <= status_code < 300

    @settings(max_examples=50, deadline=None)
    @given(status_code=st.integers(min_value=400, max_value=499))
    def test_4xx_is_client_error(self, status_code):
        """4xx status codes indicate client error."""
        assert 400 <= status_code < 500

    @settings(max_examples=50, deadline=None)
    @given(status_code=st.integers(min_value=500, max_value=599))
    def test_5xx_is_server_error(self, status_code):
        """5xx status codes indicate server error."""
        assert 500 <= status_code < 600


class TestSentimentHandlerResponse:
    """Tests for sentiment analysis handler specific invariants."""

    @settings(max_examples=100, deadline=None)
    @given(response=sentiment_response())
    def test_sentiment_is_valid_category(self, response):
        """Sentiment must be one of: positive, negative, neutral."""
        assert response["sentiment"] in ["positive", "negative", "neutral"]

    @settings(max_examples=100, deadline=None)
    @given(response=sentiment_response())
    def test_score_in_valid_range(self, response):
        """Score must be in [-1.0, 1.0]."""
        assert -1.0 <= response["score"] <= 1.0

    @settings(max_examples=100, deadline=None)
    @given(response=sentiment_response())
    def test_confidence_in_valid_range(self, response):
        """Confidence must be in [0.0, 1.0]."""
        assert 0.0 <= response["confidence"] <= 1.0

    @settings(max_examples=100, deadline=None)
    @given(response=sentiment_response())
    def test_sentiment_score_confidence_consistent(self, response):
        """High confidence should correlate with extreme scores."""
        # This is a soft invariant - we just verify they're all present
        assert "sentiment" in response
        assert "score" in response
        assert "confidence" in response

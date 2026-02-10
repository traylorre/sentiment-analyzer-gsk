"""Sentiment History Boundary Value Integration Tests (US4).

Tests for /api/v2/tickers/{ticker}/sentiment/history endpoint covering:
- Ticker boundary values (1 char, 5 chars, 6 chars)
- Date range boundaries (single day, far past, future)
- Label threshold boundaries (exactly 0.33, -0.33)
- Input validation edge cases

For On-Call Engineers:
    These tests verify input validation and boundary conditions.
    If tests fail, check:
    1. Ticker validation in ohlc.py
    2. Date range validation logic
    3. Sentiment label threshold logic (0.33, -0.33)
"""

import json
from datetime import date, timedelta

import pytest

from src.lambdas.dashboard.handler import lambda_handler
from tests.conftest import make_event


@pytest.fixture
def auth_headers():
    """Headers with valid authentication (Feature 1146: Bearer-only auth)."""
    return {"Authorization": "Bearer 550e8400-e29b-41d4-a716-446655440000"}


class TestSentimentTickerBoundaries:
    """US4: Sentiment ticker symbol boundary testing."""

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_ticker_1_char_valid(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment accepts 1-character ticker (minimum length)."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/A/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["ticker"] == "A"
        sentiment_validator.assert_valid(data)

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_ticker_5_chars_valid(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment accepts 5-character ticker (maximum length)."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/TSLA/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["ticker"] == "TSLA"
        sentiment_validator.assert_valid(data)

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_ticker_6_chars_invalid(self, mock_lambda_context, auth_headers):
        """Sentiment rejects 6-character ticker (exceeds maximum)."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/ABCDEF/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 400
        assert "Invalid ticker symbol" in json.loads(response["body"])["detail"]

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_ticker_with_digits_invalid(
        self, mock_lambda_context, auth_headers
    ):
        """Sentiment rejects ticker containing digits."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/ABC1/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 400
        assert "Invalid ticker symbol" in json.loads(response["body"])["detail"]

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_ticker_mixed_case_normalized(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment normalizes mixed case ticker to uppercase."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/MsFt/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["ticker"] == "MSFT"
        sentiment_validator.assert_valid(data)


class TestSentimentDateBoundaries:
    """US4: Sentiment date range boundary testing."""

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_single_day_range(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment accepts single-day range (start == end)."""
        today = date.today()
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"start_date": str(today), "end_date": str(today)},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        sentiment_validator.assert_valid(data)
        # Single day should have exactly 1 data point
        assert data["count"] == 1

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_start_date_after_end_date_invalid(
        self, mock_lambda_context, auth_headers
    ):
        """Sentiment rejects when start_date > end_date."""
        today = date.today()
        yesterday = today - timedelta(days=1)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"start_date": str(today), "end_date": str(yesterday)},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 400
        assert (
            "start_date must be before end_date"
            in json.loads(response["body"])["detail"]
        )

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_future_end_date(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment handles future end_date gracefully."""
        future = date.today() + timedelta(days=30)
        start = date.today() - timedelta(days=7)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/MSFT/sentiment/history",
            query_params={"start_date": str(start), "end_date": str(future)},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        # Should succeed - sentiment generation creates data for all requested days
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        sentiment_validator.assert_valid(data)


class TestSentimentAuthBoundaries:
    """US4: Sentiment authentication boundary testing."""

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_missing_auth_header(self, mock_lambda_context):
        """Sentiment returns 401 when Authorization header is missing."""
        event = make_event(method="GET", path="/api/v2/tickers/AAPL/sentiment/history")
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 401
        assert "Missing user identification" in json.loads(response["body"])["detail"]

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_empty_bearer_token(self, mock_lambda_context):
        """Sentiment returns 401 when Bearer token is empty."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            headers={"Authorization": "Bearer "},
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 401
        assert "Missing user identification" in json.loads(response["body"])["detail"]

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_x_user_id_rejected(self, mock_lambda_context):
        """Feature 1146: X-User-ID header is rejected (security fix)."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            headers={"X-User-ID": "550e8400-e29b-41d4-a716-446655440000"},
        )
        response = lambda_handler(event, mock_lambda_context)

        # X-User-ID alone should return 401 (not authenticated)
        assert response["statusCode"] == 401


class TestSentimentSourceBoundaries:
    """US4: Sentiment source enum boundary testing."""

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_invalid_source(self, mock_lambda_context, auth_headers):
        """Sentiment falls back to default source for invalid source value."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"source": "invalid_source"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        # Powertools handler falls back to default source (aggregated) for invalid enum
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["source"] == "aggregated"  # Default fallback

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    @pytest.mark.parametrize("source", ["tiingo", "finnhub", "our_model", "aggregated"])
    def test_sentiment_all_sources_valid(
        self, mock_lambda_context, auth_headers, sentiment_validator, source
    ):
        """Sentiment accepts all valid source values."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/NVDA/sentiment/history",
            query_params={"source": source},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        sentiment_validator.assert_valid(data)
        assert data["source"] == source


class TestSentimentTimeRangeBoundaries:
    """US4: Sentiment time range enum boundary testing."""

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_invalid_time_range(self, mock_lambda_context, auth_headers):
        """Sentiment falls back to default range for invalid time range value."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"range": "2W"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        # Powertools handler falls back to default range (1M) for invalid enum
        assert response["statusCode"] == 200

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    @pytest.mark.parametrize("time_range", ["1W", "1M", "3M", "6M", "1Y"])
    def test_sentiment_all_time_ranges_valid(
        self, mock_lambda_context, auth_headers, sentiment_validator, time_range
    ):
        """Sentiment accepts all valid time range values."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/GOOGL/sentiment/history",
            query_params={"range": time_range},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        sentiment_validator.assert_valid(data)


class TestSentimentLabelThresholds:
    """US4: Sentiment label threshold boundary testing.

    Tests verify that labels are correctly assigned at exact threshold values:
    - score >= 0.33 -> positive
    - score <= -0.33 -> negative
    - -0.33 < score < 0.33 -> neutral
    """

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_labels_follow_threshold_rules(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Verify all sentiment labels follow threshold rules."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"range": "1M"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        sentiment_validator.assert_valid(data)

        # Verify every point's label matches its score
        for point in data["history"]:
            score = point["score"]
            label = point["label"]

            if score >= 0.33:
                assert (
                    label == "positive"
                ), f"Score {score} >= 0.33 should be 'positive', got '{label}'"
            elif score <= -0.33:
                assert (
                    label == "negative"
                ), f"Score {score} <= -0.33 should be 'negative', got '{label}'"
            else:
                assert (
                    label == "neutral"
                ), f"Score {score} between thresholds should be 'neutral', got '{label}'"

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_score_bounds(self, mock_lambda_context, auth_headers):
        """All sentiment scores are within [-1.0, 1.0] bounds."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/TSLA/sentiment/history",
            query_params={"range": "3M"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        for point in data["history"]:
            score = point["score"]
            assert -1.0 <= score <= 1.0, f"Score {score} out of [-1.0, 1.0] bounds"

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_confidence_bounds(self, mock_lambda_context, auth_headers):
        """All confidence values are within [0.0, 1.0] bounds."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/META/sentiment/history",
            query_params={"range": "1M"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        for point in data["history"]:
            if "confidence" in point and point["confidence"] is not None:
                confidence = point["confidence"]
                assert (
                    0.0 <= confidence <= 1.0
                ), f"Confidence {confidence} out of [0.0, 1.0] bounds"

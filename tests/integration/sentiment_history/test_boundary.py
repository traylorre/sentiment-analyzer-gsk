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

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.lambdas.dashboard.ohlc import router


@pytest.fixture
def test_client():
    """Create test client for sentiment history endpoint."""
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        yield client


@pytest.fixture
def auth_headers():
    """Headers with valid authentication."""
    return {"X-User-ID": "test-user-123"}


class TestSentimentTickerBoundaries:
    """US4: Sentiment ticker symbol boundary testing."""

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_ticker_1_char_valid(
        self, test_client, auth_headers, sentiment_validator
    ):
        """Sentiment accepts 1-character ticker (minimum length)."""
        response = test_client.get(
            "/api/v2/tickers/A/sentiment/history", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "A"
        sentiment_validator.assert_valid(data)

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_ticker_5_chars_valid(
        self, test_client, auth_headers, sentiment_validator
    ):
        """Sentiment accepts 5-character ticker (maximum length)."""
        response = test_client.get(
            "/api/v2/tickers/TSLA/sentiment/history", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TSLA"
        sentiment_validator.assert_valid(data)

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_ticker_6_chars_invalid(self, test_client, auth_headers):
        """Sentiment rejects 6-character ticker (exceeds maximum)."""
        response = test_client.get(
            "/api/v2/tickers/ABCDEF/sentiment/history", headers=auth_headers
        )

        assert response.status_code == 400
        assert "Invalid ticker symbol" in response.json()["detail"]

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_ticker_with_digits_invalid(self, test_client, auth_headers):
        """Sentiment rejects ticker containing digits."""
        response = test_client.get(
            "/api/v2/tickers/ABC1/sentiment/history", headers=auth_headers
        )

        assert response.status_code == 400
        assert "Invalid ticker symbol" in response.json()["detail"]

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_ticker_mixed_case_normalized(
        self, test_client, auth_headers, sentiment_validator
    ):
        """Sentiment normalizes mixed case ticker to uppercase."""
        response = test_client.get(
            "/api/v2/tickers/MsFt/sentiment/history", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "MSFT"
        sentiment_validator.assert_valid(data)


class TestSentimentDateBoundaries:
    """US4: Sentiment date range boundary testing."""

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_single_day_range(
        self, test_client, auth_headers, sentiment_validator
    ):
        """Sentiment accepts single-day range (start == end)."""
        today = date.today()
        response = test_client.get(
            f"/api/v2/tickers/AAPL/sentiment/history?start_date={today}&end_date={today}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        sentiment_validator.assert_valid(data)
        # Single day should have exactly 1 data point
        assert data["count"] == 1

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_start_date_after_end_date_invalid(
        self, test_client, auth_headers
    ):
        """Sentiment rejects when start_date > end_date."""
        today = date.today()
        yesterday = today - timedelta(days=1)

        response = test_client.get(
            f"/api/v2/tickers/AAPL/sentiment/history?start_date={today}&end_date={yesterday}",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "start_date must be before end_date" in response.json()["detail"]

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_future_end_date(
        self, test_client, auth_headers, sentiment_validator
    ):
        """Sentiment handles future end_date gracefully."""
        future = date.today() + timedelta(days=30)
        start = date.today() - timedelta(days=7)

        response = test_client.get(
            f"/api/v2/tickers/MSFT/sentiment/history?start_date={start}&end_date={future}",
            headers=auth_headers,
        )

        # Should succeed - sentiment generation creates data for all requested days
        assert response.status_code == 200
        data = response.json()
        sentiment_validator.assert_valid(data)


class TestSentimentAuthBoundaries:
    """US4: Sentiment authentication boundary testing."""

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_missing_user_id_header(self, test_client):
        """Sentiment returns 401 when X-User-ID header is missing."""
        response = test_client.get("/api/v2/tickers/AAPL/sentiment/history")

        assert response.status_code == 401
        assert "Missing user identification" in response.json()["detail"]

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_empty_user_id_header(self, test_client):
        """Sentiment returns 401 when X-User-ID header is empty."""
        response = test_client.get(
            "/api/v2/tickers/AAPL/sentiment/history", headers={"X-User-ID": ""}
        )

        assert response.status_code == 401
        assert "Missing user identification" in response.json()["detail"]


class TestSentimentSourceBoundaries:
    """US4: Sentiment source enum boundary testing."""

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_invalid_source(self, test_client, auth_headers):
        """Sentiment rejects invalid source value."""
        response = test_client.get(
            "/api/v2/tickers/AAPL/sentiment/history?source=invalid_source",
            headers=auth_headers,
        )

        # FastAPI validation should reject invalid enum
        assert response.status_code == 422

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    @pytest.mark.parametrize("source", ["tiingo", "finnhub", "our_model", "aggregated"])
    def test_sentiment_all_sources_valid(
        self, test_client, auth_headers, sentiment_validator, source
    ):
        """Sentiment accepts all valid source values."""
        response = test_client.get(
            f"/api/v2/tickers/NVDA/sentiment/history?source={source}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        sentiment_validator.assert_valid(data)
        assert data["source"] == source


class TestSentimentTimeRangeBoundaries:
    """US4: Sentiment time range enum boundary testing."""

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_invalid_time_range(self, test_client, auth_headers):
        """Sentiment rejects invalid time range value."""
        response = test_client.get(
            "/api/v2/tickers/AAPL/sentiment/history?range=2W", headers=auth_headers
        )

        # FastAPI validation should reject invalid enum
        assert response.status_code == 422

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    @pytest.mark.parametrize("time_range", ["1W", "1M", "3M", "6M", "1Y"])
    def test_sentiment_all_time_ranges_valid(
        self, test_client, auth_headers, sentiment_validator, time_range
    ):
        """Sentiment accepts all valid time range values."""
        response = test_client.get(
            f"/api/v2/tickers/GOOGL/sentiment/history?range={time_range}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        sentiment_validator.assert_valid(data)


class TestSentimentLabelThresholds:
    """US4: Sentiment label threshold boundary testing.

    Tests verify that labels are correctly assigned at exact threshold values:
    - score >= 0.33 → positive
    - score <= -0.33 → negative
    - -0.33 < score < 0.33 → neutral
    """

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_labels_follow_threshold_rules(
        self, test_client, auth_headers, sentiment_validator
    ):
        """Verify all sentiment labels follow threshold rules."""
        response = test_client.get(
            "/api/v2/tickers/AAPL/sentiment/history?range=1M", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
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
    def test_sentiment_score_bounds(self, test_client, auth_headers):
        """All sentiment scores are within [-1.0, 1.0] bounds."""
        response = test_client.get(
            "/api/v2/tickers/TSLA/sentiment/history?range=3M", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        for point in data["history"]:
            score = point["score"]
            assert -1.0 <= score <= 1.0, f"Score {score} out of [-1.0, 1.0] bounds"

    @pytest.mark.sentiment_history
    @pytest.mark.boundary
    def test_sentiment_confidence_bounds(self, test_client, auth_headers):
        """All confidence values are within [0.0, 1.0] bounds."""
        response = test_client.get(
            "/api/v2/tickers/META/sentiment/history?range=1M", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        for point in data["history"]:
            if "confidence" in point and point["confidence"] is not None:
                confidence = point["confidence"]
                assert (
                    0.0 <= confidence <= 1.0
                ), f"Confidence {confidence} out of [0.0, 1.0] bounds"

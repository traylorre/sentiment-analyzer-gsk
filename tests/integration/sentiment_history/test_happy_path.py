"""Sentiment History Happy Path Integration Tests (US2).

Tests for /api/v2/tickers/{ticker}/sentiment/history endpoint covering:
- Valid ticker with default parameters (T026)
- Source filtering (T027-T030)
- Time range variations (T031)
- Custom date ranges (T032)
- Ticker normalization (T033)
- Count and date consistency (T034)

For On-Call Engineers:
    These tests validate the sentiment history endpoint.
    If tests fail, check:
    1. Sentiment generation is using correct label thresholds
    2. Date range calculations are correct
    3. Response model serialization is correct
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


class TestSentimentHistoryHappyPath:
    """US2: Sentiment History Happy Path Validation tests."""

    # T026: Valid ticker with default parameters
    @pytest.mark.sentiment_history
    def test_sentiment_valid_ticker_default_params(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment endpoint returns valid data for ticker with default params."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        # Validate response structure and business rules
        sentiment_validator.assert_valid(data)

        # Verify default values
        assert data["ticker"] == "AAPL"
        assert data["source"] == "aggregated"  # Default source
        assert data["count"] > 0
        assert len(data["history"]) == data["count"]

    # T027: Source filter - tiingo
    @pytest.mark.sentiment_history
    def test_sentiment_source_filter_tiingo(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment endpoint filters by source=tiingo."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/MSFT/sentiment/history",
            query_params={"source": "tiingo"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        sentiment_validator.assert_valid(data)
        assert data["source"] == "tiingo"
        # All history points should have tiingo source
        for point in data["history"]:
            assert point["source"] == "tiingo"

    # T028: Source filter - finnhub
    @pytest.mark.sentiment_history
    def test_sentiment_source_filter_finnhub(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment endpoint filters by source=finnhub."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/GOOGL/sentiment/history",
            query_params={"source": "finnhub"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        sentiment_validator.assert_valid(data)
        assert data["source"] == "finnhub"
        for point in data["history"]:
            assert point["source"] == "finnhub"

    # T029: Source filter - our_model
    @pytest.mark.sentiment_history
    def test_sentiment_source_filter_our_model(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment endpoint filters by source=our_model."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/NVDA/sentiment/history",
            query_params={"source": "our_model"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        sentiment_validator.assert_valid(data)
        assert data["source"] == "our_model"
        for point in data["history"]:
            assert point["source"] == "our_model"

    # T030: Source filter - aggregated (explicit)
    @pytest.mark.sentiment_history
    def test_sentiment_source_filter_aggregated(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment endpoint returns aggregated data when explicitly requested."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/TSLA/sentiment/history",
            query_params={"source": "aggregated"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        sentiment_validator.assert_valid(data)
        assert data["source"] == "aggregated"
        for point in data["history"]:
            assert point["source"] == "aggregated"

    # T031: Time range parameterized test
    @pytest.mark.sentiment_history
    @pytest.mark.parametrize(
        "time_range,expected_days_min,expected_days_max",
        [
            ("1W", 7, 8),  # 7 days (includes weekends for sentiment)
            ("1M", 30, 31),  # ~30 days
            ("3M", 89, 91),  # ~90 days
            ("6M", 179, 181),  # ~180 days
            ("1Y", 364, 366),  # ~365 days
        ],
        ids=["1W", "1M", "3M", "6M", "1Y"],
    )
    def test_sentiment_time_ranges(
        self,
        mock_lambda_context,
        auth_headers,
        sentiment_validator,
        time_range,
        expected_days_min,
        expected_days_max,
    ):
        """Sentiment endpoint returns appropriate data for each time range."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AMD/sentiment/history",
            query_params={"range": time_range},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        sentiment_validator.assert_valid(data)
        # Sentiment includes ALL calendar days (including weekends)
        assert expected_days_min <= data["count"] <= expected_days_max

    # T032: Custom date range
    @pytest.mark.sentiment_history
    def test_sentiment_custom_date_range(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment endpoint accepts custom start_date and end_date."""
        start = date.today() - timedelta(days=14)
        end = date.today()

        event = make_event(
            method="GET",
            path="/api/v2/tickers/META/sentiment/history",
            query_params={"start_date": str(start), "end_date": str(end)},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        sentiment_validator.assert_valid(data)
        # Should have exactly 15 days of data (14 days ago through today)
        assert data["count"] == 15

    # T033: Lowercase ticker normalization
    @pytest.mark.sentiment_history
    def test_sentiment_lowercase_ticker_normalization(
        self, mock_lambda_context, auth_headers, sentiment_validator
    ):
        """Sentiment endpoint normalizes lowercase ticker to uppercase."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/aapl/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        # Ticker should be normalized to uppercase
        assert data["ticker"] == "AAPL"
        sentiment_validator.assert_valid(data)

    # T034: Count matches history array length
    @pytest.mark.sentiment_history
    def test_sentiment_count_matches_history_length(
        self, mock_lambda_context, auth_headers
    ):
        """Sentiment response count field equals len(history)."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AMZN/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        assert data["count"] == len(data["history"])
        assert data["count"] > 0


class TestSentimentHistoryScoreValidation:
    """Additional tests for sentiment score and label validation."""

    @pytest.mark.sentiment_history
    def test_sentiment_scores_in_valid_range(self, mock_lambda_context, auth_headers):
        """All sentiment scores are in [-1.0, 1.0] range."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/NFLX/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        for point in data["history"]:
            assert (
                -1.0 <= point["score"] <= 1.0
            ), f"Score {point['score']} out of valid range [-1.0, 1.0]"

    @pytest.mark.sentiment_history
    def test_sentiment_labels_consistent_with_scores(
        self, mock_lambda_context, auth_headers
    ):
        """Sentiment labels match score thresholds."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/DIS/sentiment/history",
            query_params={"range": "1M"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        for i, point in enumerate(data["history"]):
            score = point["score"]
            label = point["label"]

            if score >= 0.33:
                expected = "positive"
            elif score <= -0.33:
                expected = "negative"
            else:
                expected = "neutral"

            assert (
                label == expected
            ), f"Point {i}: score={score} should have label='{expected}', got '{label}'"

    @pytest.mark.sentiment_history
    def test_sentiment_confidence_in_valid_range(
        self, mock_lambda_context, auth_headers
    ):
        """All confidence values are in [0.0, 1.0] range."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/PYPL/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        for point in data["history"]:
            if "confidence" in point and point["confidence"] is not None:
                assert (
                    0.0 <= point["confidence"] <= 1.0
                ), f"Confidence {point['confidence']} out of valid range [0.0, 1.0]"

    @pytest.mark.sentiment_history
    def test_sentiment_history_sorted_by_date(self, mock_lambda_context, auth_headers):
        """Sentiment history is sorted by date in ascending order."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/CRM/sentiment/history",
            query_params={"range": "1M"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        dates = [point["date"] for point in data["history"]]
        assert dates == sorted(dates), "History should be sorted by date ascending"


class TestSentimentHistoryDateFields:
    """Tests for start_date and end_date consistency."""

    @pytest.mark.sentiment_history
    def test_sentiment_start_date_matches_first_point(
        self, mock_lambda_context, auth_headers
    ):
        """Sentiment response start_date equals first history point's date."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/INTC/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        assert len(data["history"]) > 0
        first_point_date = data["history"][0]["date"]
        assert str(data["start_date"]) == str(first_point_date)

    @pytest.mark.sentiment_history
    def test_sentiment_end_date_matches_last_point(
        self, mock_lambda_context, auth_headers
    ):
        """Sentiment response end_date equals last history point's date."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/IBM/sentiment/history",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        assert len(data["history"]) > 0
        last_point_date = data["history"][-1]["date"]
        assert str(data["end_date"]) == str(last_point_date)


class TestSentimentHistoryDeterminism:
    """Tests for deterministic behavior (same ticker = same data)."""

    @pytest.mark.sentiment_history
    def test_sentiment_same_ticker_returns_same_scores(
        self, mock_lambda_context, auth_headers
    ):
        """Same ticker returns same sentiment scores (deterministic)."""
        # Make two requests for the same ticker
        event = make_event(
            method="GET",
            path="/api/v2/tickers/ORCL/sentiment/history",
            query_params={"range": "1W"},
            headers=auth_headers,
        )
        response1 = lambda_handler(event, mock_lambda_context)
        response2 = lambda_handler(event, mock_lambda_context)

        assert response1["statusCode"] == 200
        assert response2["statusCode"] == 200

        data1 = json.loads(response1["body"])
        data2 = json.loads(response2["body"])

        # Scores should be identical
        scores1 = [point["score"] for point in data1["history"]]
        scores2 = [point["score"] for point in data2["history"]]

        assert scores1 == scores2, "Same ticker should return same scores"

    @pytest.mark.sentiment_history
    def test_sentiment_different_tickers_different_scores(
        self, mock_lambda_context, auth_headers
    ):
        """Different tickers return different sentiment scores."""
        event_aapl = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"range": "1W"},
            headers=auth_headers,
        )
        event_msft = make_event(
            method="GET",
            path="/api/v2/tickers/MSFT/sentiment/history",
            query_params={"range": "1W"},
            headers=auth_headers,
        )
        response_aapl = lambda_handler(event_aapl, mock_lambda_context)
        response_msft = lambda_handler(event_msft, mock_lambda_context)

        assert response_aapl["statusCode"] == 200
        assert response_msft["statusCode"] == 200

        scores_aapl = [
            point["score"] for point in json.loads(response_aapl["body"])["history"]
        ]
        scores_msft = [
            point["score"] for point in json.loads(response_msft["body"])["history"]
        ]

        # Different tickers should have different scores
        assert (
            scores_aapl != scores_msft
        ), "Different tickers should have different scores"

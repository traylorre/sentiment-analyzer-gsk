"""Unit tests for sentiment history endpoint.

Tests the GET /api/v2/tickers/{ticker}/sentiment/history endpoint.
"""

import json
from datetime import date, timedelta

from src.lambdas.dashboard.handler import lambda_handler
from tests.conftest import make_event

# Feature 1049: Valid UUID required for auth
# Feature 1146: Bearer-only authentication (X-User-ID header fallback removed)
AUTH_HEADERS = {"Authorization": "Bearer 12345678-1234-5678-1234-567812345678"}


class TestSentimentHistoryEndpoint:
    """Tests for GET /api/v2/tickers/{ticker}/sentiment/history."""

    def test_returns_sentiment_history_response(self, mock_lambda_context):
        """Test endpoint returns properly structured response."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        # Verify required fields
        assert data["ticker"] == "AAPL"
        assert data["source"] == "aggregated"  # default
        assert isinstance(data["history"], list)
        assert len(data["history"]) > 0
        assert "start_date" in data
        assert "end_date" in data
        assert data["count"] == len(data["history"])

    def test_validates_user_id_header(self, mock_lambda_context):
        """Test endpoint requires X-User-ID header."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 401
        assert "Missing user identification" in json.loads(response["body"])["detail"]

    def test_validates_ticker_symbol(self, mock_lambda_context):
        """Test endpoint validates ticker format."""
        # Invalid: too long
        event = make_event(
            method="GET",
            path="/api/v2/tickers/TOOLONG/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        assert "Invalid ticker symbol" in json.loads(response["body"])["detail"]

        # Invalid: contains numbers
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AB12/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400

    def test_normalizes_ticker_to_uppercase(self, mock_lambda_context):
        """Test ticker is normalized to uppercase."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/aapl/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        assert json.loads(response["body"])["ticker"] == "AAPL"

    def test_supports_source_param(self, mock_lambda_context):
        """Test source parameter filters sentiment data."""
        sources = ["tiingo", "finnhub", "our_model", "aggregated"]

        for source in sources:
            event = make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/sentiment/history",
                query_params={"source": source},
                headers=AUTH_HEADERS,
            )
            response = lambda_handler(event, mock_lambda_context)

            assert response["statusCode"] == 200
            data = json.loads(response["body"])
            assert data["source"] == source

            # Verify all points have correct source
            for point in data["history"]:
                assert point["source"] == source

    def test_supports_time_range_param(self, mock_lambda_context):
        """Test time range parameter affects data span."""
        # Test 1 week
        event_1w = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"range": "1W"},
            headers=AUTH_HEADERS,
        )
        response_1w = lambda_handler(event_1w, mock_lambda_context)
        assert response_1w["statusCode"] == 200
        data_1w = json.loads(response_1w["body"])

        # Test 1 month
        event_1m = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"range": "1M"},
            headers=AUTH_HEADERS,
        )
        response_1m = lambda_handler(event_1m, mock_lambda_context)
        assert response_1m["statusCode"] == 200
        data_1m = json.loads(response_1m["body"])

        # 1M should have more data points than 1W
        assert data_1m["count"] > data_1w["count"]

    def test_supports_custom_date_range(self, mock_lambda_context):
        """Test custom start_date and end_date parameters."""
        end_date = date.today()
        start_date = end_date - timedelta(days=14)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"start_date": str(start_date), "end_date": str(end_date)},
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        # Should have ~15 days of data
        assert 14 <= data["count"] <= 16

    def test_validates_date_range_order(self, mock_lambda_context):
        """Test start_date must be before end_date."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"start_date": "2024-12-01", "end_date": "2024-11-01"},
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 400
        assert (
            "start_date must be before end_date"
            in json.loads(response["body"])["detail"]
        )

    def test_sentiment_point_structure(self, mock_lambda_context):
        """Test sentiment point has all required fields."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        point = data["history"][0]

        # Required fields
        assert "date" in point
        assert "score" in point
        assert "source" in point

        # Optional fields
        assert "confidence" in point
        assert "label" in point

        # Validate ranges
        assert -1.0 <= point["score"] <= 1.0
        if point["confidence"] is not None:
            assert 0.0 <= point["confidence"] <= 1.0
        if point["label"] is not None:
            assert point["label"] in ["positive", "neutral", "negative"]

    def test_history_sorted_by_date_ascending(self, mock_lambda_context):
        """Test sentiment history is sorted oldest to newest."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"range": "1M"},
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        history = json.loads(response["body"])["history"]

        dates = [point["date"] for point in history]
        assert dates == sorted(dates)

    def test_deterministic_results_for_same_ticker(self, mock_lambda_context):
        """Test same ticker returns consistent results (seeded random)."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"range": "1W"},
            headers=AUTH_HEADERS,
        )
        response1 = lambda_handler(event, mock_lambda_context)
        response2 = lambda_handler(event, mock_lambda_context)

        assert (
            json.loads(response1["body"])["history"]
            == json.loads(response2["body"])["history"]
        )

    def test_different_tickers_have_different_results(self, mock_lambda_context):
        """Test different tickers return different sentiment values."""
        event_aapl = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"range": "1W"},
            headers=AUTH_HEADERS,
        )
        event_msft = make_event(
            method="GET",
            path="/api/v2/tickers/MSFT/sentiment/history",
            query_params={"range": "1W"},
            headers=AUTH_HEADERS,
        )
        response_aapl = lambda_handler(event_aapl, mock_lambda_context)
        response_msft = lambda_handler(event_msft, mock_lambda_context)

        # Scores should differ (seeded by ticker)
        aapl_scores = [p["score"] for p in json.loads(response_aapl["body"])["history"]]
        msft_scores = [p["score"] for p in json.loads(response_msft["body"])["history"]]

        assert aapl_scores != msft_scores


class TestSentimentSourceEnum:
    """Tests for sentiment source validation."""

    def test_invalid_source_falls_back_to_default(self, mock_lambda_context):
        """Test invalid source parameter falls back to aggregated (Powertools default)."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"source": "invalid"},
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        # Powertools handler falls back to default source (aggregated) for invalid enum
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["source"] == "aggregated"  # Default fallback

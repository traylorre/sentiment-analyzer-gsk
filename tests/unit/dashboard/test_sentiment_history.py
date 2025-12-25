"""Unit tests for sentiment history endpoint.

Tests the GET /api/v2/tickers/{ticker}/sentiment/history endpoint.
"""

from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.lambdas.dashboard.ohlc import router

# Create test app with router
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# Feature 1049: Valid UUID required for auth
AUTH_HEADERS = {"X-User-ID": "12345678-1234-5678-1234-567812345678"}


class TestSentimentHistoryEndpoint:
    """Tests for GET /api/v2/tickers/{ticker}/sentiment/history."""

    def test_returns_sentiment_history_response(self):
        """Test endpoint returns properly structured response."""
        response = client.get(
            "/api/v2/tickers/AAPL/sentiment/history",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert data["ticker"] == "AAPL"
        assert data["source"] == "aggregated"  # default
        assert isinstance(data["history"], list)
        assert len(data["history"]) > 0
        assert "start_date" in data
        assert "end_date" in data
        assert data["count"] == len(data["history"])

    def test_validates_user_id_header(self):
        """Test endpoint requires X-User-ID header."""
        response = client.get("/api/v2/tickers/AAPL/sentiment/history")

        assert response.status_code == 401
        assert "Missing user identification" in response.json()["detail"]

    def test_validates_ticker_symbol(self):
        """Test endpoint validates ticker format."""
        # Invalid: too long
        response = client.get(
            "/api/v2/tickers/TOOLONG/sentiment/history",
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 400
        assert "Invalid ticker symbol" in response.json()["detail"]

        # Invalid: contains numbers
        response = client.get(
            "/api/v2/tickers/AB12/sentiment/history",
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 400

    def test_normalizes_ticker_to_uppercase(self):
        """Test ticker is normalized to uppercase."""
        response = client.get(
            "/api/v2/tickers/aapl/sentiment/history",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        assert response.json()["ticker"] == "AAPL"

    def test_supports_source_param(self):
        """Test source parameter filters sentiment data."""
        sources = ["tiingo", "finnhub", "our_model", "aggregated"]

        for source in sources:
            response = client.get(
                f"/api/v2/tickers/AAPL/sentiment/history?source={source}",
                headers=AUTH_HEADERS,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["source"] == source

            # Verify all points have correct source
            for point in data["history"]:
                assert point["source"] == source

    def test_supports_time_range_param(self):
        """Test time range parameter affects data span."""
        # Test 1 week
        response_1w = client.get(
            "/api/v2/tickers/AAPL/sentiment/history?range=1W",
            headers=AUTH_HEADERS,
        )
        assert response_1w.status_code == 200
        data_1w = response_1w.json()

        # Test 1 month
        response_1m = client.get(
            "/api/v2/tickers/AAPL/sentiment/history?range=1M",
            headers=AUTH_HEADERS,
        )
        assert response_1m.status_code == 200
        data_1m = response_1m.json()

        # 1M should have more data points than 1W
        assert data_1m["count"] > data_1w["count"]

    def test_supports_custom_date_range(self):
        """Test custom start_date and end_date parameters."""
        end_date = date.today()
        start_date = end_date - timedelta(days=14)

        response = client.get(
            f"/api/v2/tickers/AAPL/sentiment/history"
            f"?start_date={start_date}&end_date={end_date}",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()

        # Should have ~15 days of data
        assert 14 <= data["count"] <= 16

    def test_validates_date_range_order(self):
        """Test start_date must be before end_date."""
        response = client.get(
            "/api/v2/tickers/AAPL/sentiment/history"
            "?start_date=2024-12-01&end_date=2024-11-01",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 400
        assert "start_date must be before end_date" in response.json()["detail"]

    def test_sentiment_point_structure(self):
        """Test sentiment point has all required fields."""
        response = client.get(
            "/api/v2/tickers/AAPL/sentiment/history",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
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

    def test_history_sorted_by_date_ascending(self):
        """Test sentiment history is sorted oldest to newest."""
        response = client.get(
            "/api/v2/tickers/AAPL/sentiment/history?range=1M",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        history = response.json()["history"]

        dates = [point["date"] for point in history]
        assert dates == sorted(dates)

    def test_deterministic_results_for_same_ticker(self):
        """Test same ticker returns consistent results (seeded random)."""
        response1 = client.get(
            "/api/v2/tickers/AAPL/sentiment/history?range=1W",
            headers=AUTH_HEADERS,
        )
        response2 = client.get(
            "/api/v2/tickers/AAPL/sentiment/history?range=1W",
            headers=AUTH_HEADERS,
        )

        assert response1.json()["history"] == response2.json()["history"]

    def test_different_tickers_have_different_results(self):
        """Test different tickers return different sentiment values."""
        response_aapl = client.get(
            "/api/v2/tickers/AAPL/sentiment/history?range=1W",
            headers=AUTH_HEADERS,
        )
        response_msft = client.get(
            "/api/v2/tickers/MSFT/sentiment/history?range=1W",
            headers=AUTH_HEADERS,
        )

        # Scores should differ (seeded by ticker)
        aapl_scores = [p["score"] for p in response_aapl.json()["history"]]
        msft_scores = [p["score"] for p in response_msft.json()["history"]]

        assert aapl_scores != msft_scores


class TestSentimentSourceEnum:
    """Tests for sentiment source validation."""

    def test_invalid_source_rejected(self):
        """Test invalid source parameter is rejected."""
        response = client.get(
            "/api/v2/tickers/AAPL/sentiment/history?source=invalid",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 422  # Validation error

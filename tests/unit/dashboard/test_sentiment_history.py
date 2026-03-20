"""Unit tests for sentiment history endpoint (Feature 1227).

Tests the GET /api/v2/tickers/{ticker}/sentiment/history endpoint
after the synthetic generator was replaced with real DynamoDB queries.

Uses mocked timeseries query to isolate endpoint logic from DynamoDB.
"""

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from src.lambdas.dashboard.handler import lambda_handler
from tests.conftest import make_event

# Feature 1049: Valid UUID required for auth
# Feature 1146: Bearer-only authentication
AUTH_HEADERS = {"Authorization": "Bearer 12345678-1234-5678-1234-567812345678"}


@dataclass
class MockBucket:
    """Mimics SentimentBucketResponse from timeseries.py."""

    ticker: str
    resolution: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    count: int
    avg: float
    label_counts: dict = field(default_factory=dict)
    is_partial: bool = False
    sources: list = field(default_factory=list)
    progress_pct: float | None = None


@dataclass
class MockTimeseriesResponse:
    """Mimics TimeseriesResponse from timeseries.py."""

    ticker: str
    resolution: str
    buckets: list
    partial_bucket: object = None
    cache_hit: bool = False
    query_time_ms: float = 1.0
    next_cursor: str | None = None
    has_more: bool = False


def _make_buckets(
    ticker: str, start_date: date, count: int, source: str = "tiingo"
) -> list:
    """Generate test buckets for a ticker."""
    buckets = []
    for i in range(count):
        d = start_date + timedelta(days=i)
        buckets.append(
            MockBucket(
                ticker=ticker,
                resolution="24h",
                timestamp=f"{d}T00:00:00+00:00",
                open=0.8 + i * 0.01,
                high=0.9 + i * 0.01,
                low=0.7 + i * 0.01,
                close=0.85 + i * 0.01,
                count=1,
                avg=round(0.85 + i * 0.01, 4),
                sources=[f"{source}:{90000000 + i}"],
            )
        )
    return buckets


def _mock_query(buckets, ticker="AAPL"):
    """Create a mock for query_timeseries that returns the given buckets."""
    return MockTimeseriesResponse(
        ticker=ticker,
        resolution="24h",
        buckets=buckets,
    )


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear sentiment cache between tests."""
    from src.lambdas.shared.cache.sentiment_cache import clear_cache

    clear_cache()
    yield
    clear_cache()


class TestSentimentHistoryEndpoint:
    """Tests for GET /api/v2/tickers/{ticker}/sentiment/history."""

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    @patch(
        "src.lambdas.shared.cache.sentiment_cache.get_cached_history", return_value=None
    )
    def test_returns_sentiment_history_response(
        self, mock_cache, mock_query, mock_lambda_context
    ):
        """Test endpoint returns properly structured response."""
        buckets = _make_buckets("AAPL", date(2026, 3, 1), 7)
        mock_query.return_value = _mock_query(buckets)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        assert data["ticker"] == "AAPL"
        assert data["source"] == "aggregated"
        assert isinstance(data["history"], list)
        assert len(data["history"]) == 7
        assert "start_date" in data
        assert "end_date" in data
        assert data["count"] == 7

    def test_validates_user_id_header(self, mock_lambda_context):
        """Test endpoint requires auth header."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 401
        assert "Missing user identification" in json.loads(response["body"])["detail"]

    def test_validates_ticker_symbol(self, mock_lambda_context):
        """Test endpoint validates ticker format."""
        event = make_event(
            method="GET",
            path="/api/v2/tickers/TOOLONG/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        assert "Invalid ticker symbol" in json.loads(response["body"])["detail"]

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AB12/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    @patch(
        "src.lambdas.shared.cache.sentiment_cache.get_cached_history", return_value=None
    )
    def test_normalizes_ticker_to_uppercase(
        self, mock_cache, mock_query, mock_lambda_context
    ):
        """Test ticker is normalized to uppercase."""
        buckets = _make_buckets("AAPL", date(2026, 3, 1), 3)
        mock_query.return_value = _mock_query(buckets)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/aapl/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        assert json.loads(response["body"])["ticker"] == "AAPL"

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    @patch(
        "src.lambdas.shared.cache.sentiment_cache.get_cached_history", return_value=None
    )
    def test_source_filter_tiingo(self, mock_cache, mock_query, mock_lambda_context):
        """Test source filter returns only matching sources."""
        buckets = _make_buckets("AAPL", date(2026, 3, 1), 3, source="tiingo")
        mock_query.return_value = _mock_query(buckets)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"source": "tiingo"},
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["source"] == "tiingo"
        for point in data["history"]:
            assert point["source"] == "tiingo"

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    @patch(
        "src.lambdas.shared.cache.sentiment_cache.get_cached_history", return_value=None
    )
    def test_source_filter_excludes_non_matching(
        self, mock_cache, mock_query, mock_lambda_context
    ):
        """Test source filter excludes records from other sources."""
        buckets = _make_buckets("AAPL", date(2026, 3, 1), 3, source="tiingo")
        mock_query.return_value = _mock_query(buckets)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"source": "finnhub"},
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["count"] == 0
        assert data["history"] == []

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    @patch(
        "src.lambdas.shared.cache.sentiment_cache.get_cached_history", return_value=None
    )
    def test_aggregated_returns_all_sources(
        self, mock_cache, mock_query, mock_lambda_context
    ):
        """Test aggregated source returns all records regardless of source."""
        buckets = _make_buckets("AAPL", date(2026, 3, 1), 3, source="tiingo")
        mock_query.return_value = _mock_query(buckets)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"source": "aggregated"},
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["count"] == 3

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    @patch(
        "src.lambdas.shared.cache.sentiment_cache.get_cached_history", return_value=None
    )
    def test_empty_results_return_count_zero(
        self, mock_cache, mock_query, mock_lambda_context
    ):
        """Test empty timeseries returns count 0 (not synthetic filler, FR-005)."""
        mock_query.return_value = _mock_query([])

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["count"] == 0
        assert data["history"] == []

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

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    @patch(
        "src.lambdas.shared.cache.sentiment_cache.get_cached_history", return_value=None
    )
    def test_sentiment_point_structure(
        self, mock_cache, mock_query, mock_lambda_context
    ):
        """Test sentiment point has all required fields with valid ranges."""
        buckets = _make_buckets("AAPL", date(2026, 3, 1), 1)
        mock_query.return_value = _mock_query(buckets)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        point = data["history"][0]

        assert "date" in point
        assert "score" in point
        assert "source" in point
        assert "confidence" in point
        assert "label" in point

        assert -1.0 <= point["score"] <= 1.0
        assert 0.0 <= point["confidence"] <= 1.0
        assert point["label"] in ["positive", "neutral", "negative"]

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    @patch(
        "src.lambdas.shared.cache.sentiment_cache.get_cached_history", return_value=None
    )
    def test_x_cache_source_header_present(
        self, mock_cache, mock_query, mock_lambda_context
    ):
        """Test x-cache-source header is set (FR-006)."""
        buckets = _make_buckets("AAPL", date(2026, 3, 1), 3)
        mock_query.return_value = _mock_query(buckets)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        headers = response.get("headers", {})
        assert "x-cache-source" in headers
        assert headers["x-cache-source"] == "persistent-cache"

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    @patch("src.lambdas.shared.cache.sentiment_cache.get_cached_history")
    def test_cache_hit_returns_in_memory_header(
        self, mock_cache_get, mock_query, mock_lambda_context
    ):
        """Test in-memory cache hit returns x-cache-source: in-memory."""
        mock_cache_get.return_value = {
            "ticker": "AAPL",
            "source": "aggregated",
            "history": [
                {
                    "date": "2026-03-01",
                    "score": 0.85,
                    "source": "tiingo",
                    "confidence": 0.8,
                    "label": "positive",
                }
            ],
            "start_date": "2026-03-01",
            "end_date": "2026-03-01",
            "count": 1,
        }

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        headers = response.get("headers", {})
        assert headers.get("x-cache-source") == "in-memory"
        mock_query.assert_not_called()


class TestSentimentSourceEnum:
    """Tests for sentiment source validation."""

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    @patch(
        "src.lambdas.shared.cache.sentiment_cache.get_cached_history", return_value=None
    )
    def test_invalid_source_falls_back_to_default(
        self, mock_cache, mock_query, mock_lambda_context
    ):
        """Test invalid source parameter falls back to aggregated."""
        buckets = _make_buckets("AAPL", date(2026, 3, 1), 3)
        mock_query.return_value = _mock_query(buckets)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/sentiment/history",
            query_params={"source": "invalid"},
            headers=AUTH_HEADERS,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["source"] == "aggregated"

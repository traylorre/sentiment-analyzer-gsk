"""Unit tests for the rewritten get_sentiment_by_configuration() (T018).

Tests the timeseries-based sentiment overview that:
- Takes config_id, tickers, resolution (default TWENTY_FOUR_HOURS), skip_cache
- Calls query_timeseries(ticker, resolution) for each ticker
- Transforms SentimentBucketResponse -> SourceSentiment under "aggregated" key
- Returns SentimentResponse with cache_status="fresh"
- Wraps timeseries calls in try/except, logs warning on failure
"""

from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from src.lambdas.dashboard.sentiment import (
    SentimentResponse,
    clear_sentiment_cache,
    get_sentiment_by_configuration,
)
from src.lib.timeseries.models import Resolution


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear sentiment cache before each test to avoid cross-test pollution."""
    clear_sentiment_cache()
    yield
    clear_sentiment_cache()


def _make_timeseries_response(
    ticker: str,
    buckets: list | None = None,
    partial_bucket=None,
) -> MagicMock:
    """Create a mock TimeseriesResponse with the given buckets."""
    mock_response = MagicMock()
    mock_response.ticker = ticker
    mock_response.buckets = buckets if buckets is not None else []
    mock_response.partial_bucket = partial_bucket
    mock_response.cache_hit = False
    mock_response.query_time_ms = 5.0
    return mock_response


def _make_bucket(
    avg: float = 0.65, count: int = 5, timestamp: str = "2024-01-02T00:00:00Z"
) -> MagicMock:
    """Create a mock SentimentBucketResponse bucket."""
    bucket = MagicMock()
    bucket.avg = avg
    bucket.count = count
    bucket.timestamp = timestamp
    bucket.sources = ["tiingo:123"]
    return bucket


class TestSentimentOverview:
    """Tests for the timeseries-based get_sentiment_by_configuration."""

    @freeze_time("2024-01-02T10:00:00Z")
    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_overview_returns_real_data(self, mock_query):
        """Mock query_timeseries to return buckets for 2 tickers; verify
        non-empty sentiment with 'aggregated' key."""
        mock_query.side_effect = [
            _make_timeseries_response("AAPL", buckets=[_make_bucket(avg=0.65)]),
            _make_timeseries_response("MSFT", buckets=[_make_bucket(avg=0.40)]),
        ]

        response = get_sentiment_by_configuration(
            config_id="cfg-001",
            tickers=["AAPL", "MSFT"],
            skip_cache=True,
        )

        assert isinstance(response, SentimentResponse)
        assert response.config_id == "cfg-001"
        assert len(response.tickers) == 2

        for ticker_data in response.tickers:
            assert (
                "aggregated" in ticker_data.sentiment
            ), f"Expected 'aggregated' key in sentiment for {ticker_data.symbol}"
            source = ticker_data.sentiment["aggregated"]
            assert source.score is not None
            assert source.label in ("positive", "negative", "neutral")
            assert source.confidence == 0.8
            assert source.updated_at == "2024-01-02T00:00:00Z"

    @freeze_time("2024-01-02T10:00:00Z")
    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_overview_graceful_degradation(self, mock_query):
        """One ticker has data, one has empty response. Verify first has
        sentiment, second has empty dict."""
        mock_query.side_effect = [
            _make_timeseries_response("AAPL", buckets=[_make_bucket(avg=0.5)]),
            _make_timeseries_response("FAIL", buckets=[]),
        ]

        response = get_sentiment_by_configuration(
            config_id="cfg-002",
            tickers=["AAPL", "FAIL"],
            skip_cache=True,
        )

        assert len(response.tickers) == 2

        aapl = next(t for t in response.tickers if t.symbol == "AAPL")
        fail = next(t for t in response.tickers if t.symbol == "FAIL")

        assert "aggregated" in aapl.sentiment
        assert len(fail.sentiment) == 0

    @freeze_time("2024-01-02T10:00:00Z")
    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_overview_aggregated_score(self, mock_query):
        """Verify bucket.avg maps to score, score_to_label maps correctly."""
        # Positive score (>= 0.33)
        mock_query.return_value = _make_timeseries_response(
            "AAPL", buckets=[_make_bucket(avg=0.65)]
        )

        response = get_sentiment_by_configuration(
            config_id="cfg-003",
            tickers=["AAPL"],
            skip_cache=True,
        )

        source = response.tickers[0].sentiment["aggregated"]
        assert source.score == round(0.65, 4)
        assert source.label == "positive"

        # Reset cache and mock for negative score
        clear_sentiment_cache()
        mock_query.return_value = _make_timeseries_response(
            "BEAR", buckets=[_make_bucket(avg=-0.50)]
        )

        response = get_sentiment_by_configuration(
            config_id="cfg-003b",
            tickers=["BEAR"],
            skip_cache=True,
        )

        source = response.tickers[0].sentiment["aggregated"]
        assert source.score == round(-0.50, 4)
        assert source.label == "negative"

        # Neutral score (between -0.33 and 0.33)
        clear_sentiment_cache()
        mock_query.return_value = _make_timeseries_response(
            "NEUT", buckets=[_make_bucket(avg=0.10)]
        )

        response = get_sentiment_by_configuration(
            config_id="cfg-003c",
            tickers=["NEUT"],
            skip_cache=True,
        )

        source = response.tickers[0].sentiment["aggregated"]
        assert source.score == round(0.10, 4)
        assert source.label == "neutral"

    @freeze_time("2024-01-02T10:00:00Z")
    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_overview_resolution_parameter(self, mock_query):
        """Verify resolution param is passed through to query_timeseries."""
        mock_query.return_value = _make_timeseries_response(
            "AAPL", buckets=[_make_bucket()]
        )

        get_sentiment_by_configuration(
            config_id="cfg-004",
            tickers=["AAPL"],
            resolution=Resolution.ONE_HOUR,
            skip_cache=True,
        )

        mock_query.assert_called_once_with(
            ticker="AAPL",
            resolution=Resolution.ONE_HOUR,
        )

    @freeze_time("2024-01-02T10:00:00Z")
    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_overview_resolution_default(self, mock_query):
        """Verify default resolution is TWENTY_FOUR_HOURS when not specified."""
        mock_query.return_value = _make_timeseries_response(
            "AAPL", buckets=[_make_bucket()]
        )

        get_sentiment_by_configuration(
            config_id="cfg-004b",
            tickers=["AAPL"],
            skip_cache=True,
        )

        mock_query.assert_called_once_with(
            ticker="AAPL",
            resolution=Resolution.TWENTY_FOUR_HOURS,
        )

    @freeze_time("2024-01-02T10:00:00Z")
    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_overview_cache_hit(self, mock_query):
        """First call populates cache, second call returns cached
        (mock query_timeseries called once)."""
        mock_query.return_value = _make_timeseries_response(
            "AAPL", buckets=[_make_bucket(avg=0.65)]
        )

        # First call: cache miss, calls query_timeseries
        response1 = get_sentiment_by_configuration(
            config_id="cfg-005",
            tickers=["AAPL"],
        )

        assert response1.cache_status == "fresh"
        assert mock_query.call_count == 1

        # Second call: cache hit, should NOT call query_timeseries again
        response2 = get_sentiment_by_configuration(
            config_id="cfg-005",
            tickers=["AAPL"],
        )

        assert response2.cache_status == "fresh"
        assert mock_query.call_count == 1  # Still 1 — served from cache

        # Verify both responses carry the same ticker data
        assert len(response2.tickers) == 1
        assert response2.tickers[0].symbol == "AAPL"

    @freeze_time("2024-01-02T10:00:00Z")
    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_overview_partial_ticker_failure(self, mock_query):
        """One ticker's query_timeseries raises an exception; verify that
        ticker gets sentiment={} while others still get real data (Feature 1231)."""

        def _side_effect(ticker, resolution=None, **kwargs):
            if ticker == "FAIL":
                raise Exception("DynamoDB throttle for FAIL")
            return _make_timeseries_response(ticker, buckets=[_make_bucket(avg=0.45)])

        mock_query.side_effect = _side_effect

        response = get_sentiment_by_configuration(
            config_id="cfg-partial",
            tickers=["AAPL", "FAIL", "MSFT"],
            skip_cache=True,
        )

        assert isinstance(response, SentimentResponse)
        assert len(response.tickers) == 3

        aapl = next(t for t in response.tickers if t.symbol == "AAPL")
        fail = next(t for t in response.tickers if t.symbol == "FAIL")
        msft = next(t for t in response.tickers if t.symbol == "MSFT")

        # Successful tickers have real sentiment data
        assert "aggregated" in aapl.sentiment
        assert aapl.sentiment["aggregated"].score == 0.45
        assert "aggregated" in msft.sentiment
        assert msft.sentiment["aggregated"].score == 0.45

        # Failed ticker has empty sentiment (not crash)
        assert fail.sentiment == {}

    @freeze_time("2024-01-02T10:00:00Z")
    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_overview_db_error(self, mock_query):
        """Mock query_timeseries to raise exception; verify empty sentiment
        (not crash)."""
        mock_query.side_effect = Exception("DynamoDB connection timeout")

        response = get_sentiment_by_configuration(
            config_id="cfg-006",
            tickers=["AAPL"],
            skip_cache=True,
        )

        assert isinstance(response, SentimentResponse)
        assert response.config_id == "cfg-006"
        assert len(response.tickers) == 1
        # Ticker is present but sentiment dict should be empty
        assert response.tickers[0].symbol == "AAPL"
        assert len(response.tickers[0].sentiment) == 0
        assert response.cache_status == "fresh"

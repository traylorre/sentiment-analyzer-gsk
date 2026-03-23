"""Unit tests for get_ticker_sentiment_history().

Tests the rewritten function that:
- Verifies config ownership via DynamoDB
- Queries timeseries buckets for a ticker over N days
- Transforms buckets to SourceSentiment entries keyed by timestamp
- Supports source filtering (e.g., "tiingo" matches "tiingo:123")
- Returns ErrorResponse on config-not-found or timeseries failure
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from freezegun import freeze_time

from src.lambdas.dashboard.sentiment import (
    ErrorResponse,
    SentimentResponse,
    get_ticker_sentiment_history,
)
from src.lib.timeseries.models import Resolution

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bucket(
    avg: float,
    count: int,
    timestamp: str,
    sources: list[str] | None = None,
) -> MagicMock:
    """Create a mock timeseries bucket."""
    bucket = MagicMock()
    bucket.avg = avg
    bucket.count = count
    bucket.timestamp = timestamp
    bucket.sources = sources or []
    return bucket


def _make_table(config_exists: bool = True) -> MagicMock:
    """Create a mock DynamoDB table resource."""
    table = MagicMock()
    if config_exists:
        table.get_item.return_value = {
            "Item": {"PK": "USER#user1", "SK": "CONFIG#cfg1"},
        }
    else:
        table.get_item.return_value = {}
    return table


def _make_ts_response(buckets: list[MagicMock]) -> MagicMock:
    """Create a mock TimeseriesResponse."""
    ts_response = MagicMock()
    ts_response.buckets = buckets
    return ts_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@freeze_time("2024-01-02T10:00:00Z")
class TestSentimentHistory:
    """Tests for get_ticker_sentiment_history()."""

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_history_returns_real_buckets(self, mock_query):
        """7 daily buckets produce 7 entries in the response."""
        buckets = [
            _make_bucket(
                avg=0.1 * (i + 1),
                count=3,
                timestamp=f"2023-12-{26 + i:02d}T00:00:00Z",
                sources=["tiingo:123"],
            )
            for i in range(7)
        ]
        mock_query.return_value = _make_ts_response(buckets)
        table = _make_table()

        result = get_ticker_sentiment_history(
            table=table,
            user_id="user1",
            config_id="cfg1",
            ticker="AAPL",
            days=7,
        )

        assert isinstance(result, SentimentResponse)
        assert len(result.tickers) == 1
        assert result.tickers[0].symbol == "AAPL"
        assert len(result.tickers[0].sentiment) == 7

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_history_source_filter_tiingo(self, mock_query):
        """Source filter 'tiingo' keeps only buckets with tiingo sources."""
        buckets = [
            _make_bucket(
                avg=0.5,
                count=3,
                timestamp="2024-01-01T00:00:00Z",
                sources=["tiingo:123", "finnhub:456"],
            ),
            _make_bucket(
                avg=0.3,
                count=2,
                timestamp="2024-01-01T01:00:00Z",
                sources=["finnhub:789"],
            ),
            _make_bucket(
                avg=0.4,
                count=1,
                timestamp="2024-01-01T02:00:00Z",
                sources=["tiingo:222"],
            ),
            _make_bucket(
                avg=0.6,
                count=4,
                timestamp="2024-01-01T03:00:00Z",
                sources=["finnhub:333"],
            ),
            _make_bucket(
                avg=0.2,
                count=5,
                timestamp="2024-01-01T04:00:00Z",
                sources=["tiingo:444", "finnhub:555"],
            ),
        ]
        mock_query.return_value = _make_ts_response(buckets)
        table = _make_table()

        result = get_ticker_sentiment_history(
            table=table,
            user_id="user1",
            config_id="cfg1",
            ticker="AAPL",
            source="tiingo",
            days=7,
        )

        assert isinstance(result, SentimentResponse)
        # Buckets 0, 2, 4 have a source starting with "tiingo"
        assert len(result.tickers[0].sentiment) == 3

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_history_partial_data(self, mock_query):
        """Only 3 buckets for a 7-day request returns exactly 3 entries (no padding)."""
        buckets = [
            _make_bucket(
                avg=0.5, count=3, timestamp="2023-12-30T00:00:00Z", sources=["tiingo:1"]
            ),
            _make_bucket(
                avg=0.3, count=2, timestamp="2023-12-31T00:00:00Z", sources=["tiingo:2"]
            ),
            _make_bucket(
                avg=0.7, count=5, timestamp="2024-01-01T00:00:00Z", sources=["tiingo:3"]
            ),
        ]
        mock_query.return_value = _make_ts_response(buckets)
        table = _make_table()

        result = get_ticker_sentiment_history(
            table=table,
            user_id="user1",
            config_id="cfg1",
            ticker="TSLA",
            days=7,
        )

        assert isinstance(result, SentimentResponse)
        assert len(result.tickers[0].sentiment) == 3

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_history_no_data(self, mock_query):
        """Empty bucket list results in empty sentiment dict."""
        mock_query.return_value = _make_ts_response([])
        table = _make_table()

        result = get_ticker_sentiment_history(
            table=table,
            user_id="user1",
            config_id="cfg1",
            ticker="MSFT",
            days=7,
        )

        assert isinstance(result, SentimentResponse)
        assert result.tickers[0].sentiment == {}

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_history_resolution_parameter(self, mock_query):
        """Resolution.FIVE_MINUTES is forwarded to query_timeseries."""
        mock_query.return_value = _make_ts_response([])
        table = _make_table()

        get_ticker_sentiment_history(
            table=table,
            user_id="user1",
            config_id="cfg1",
            ticker="AAPL",
            days=1,
            resolution=Resolution.FIVE_MINUTES,
        )

        call_kwargs = mock_query.call_args.kwargs
        assert call_kwargs["resolution"] == Resolution.FIVE_MINUTES

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_history_days_bounds_query(self, mock_query):
        """start_dt passed to query_timeseries equals now minus requested days."""
        mock_query.return_value = _make_ts_response([])
        table = _make_table()

        days = 14
        get_ticker_sentiment_history(
            table=table,
            user_id="user1",
            config_id="cfg1",
            ticker="AAPL",
            days=days,
        )

        call_kwargs = mock_query.call_args.kwargs
        # freeze_time is 2024-01-02T10:00:00Z
        expected_now = datetime(2024, 1, 2, 10, 0, 0)
        expected_start = expected_now - timedelta(days=days)
        # Compare as naive datetimes (strip tzinfo for comparison)
        actual_start = call_kwargs["start"].replace(tzinfo=None)
        actual_end = call_kwargs["end"].replace(tzinfo=None)
        assert actual_start == expected_start
        assert actual_end == expected_now

    def test_history_config_not_found(self):
        """Missing config Item triggers CONFIG_NOT_FOUND error."""
        table = _make_table(config_exists=False)

        result = get_ticker_sentiment_history(
            table=table,
            user_id="user1",
            config_id="cfg_missing",
            ticker="AAPL",
        )

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "CONFIG_NOT_FOUND"

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_history_db_error(self, mock_query):
        """Exception from query_timeseries yields DB_ERROR response."""
        mock_query.side_effect = RuntimeError("DynamoDB timeout")
        table = _make_table()

        result = get_ticker_sentiment_history(
            table=table,
            user_id="user1",
            config_id="cfg1",
            ticker="AAPL",
            days=7,
        )

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "DB_ERROR"

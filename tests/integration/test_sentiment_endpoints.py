"""Sentiment Endpoints Integration Tests.

Integration-lite tests for the sentiment overview and history endpoints.
These tests mock the timeseries query layer (query_timeseries) to validate
the full aggregation and response-building logic in isolation from DynamoDB.

Test cases:
- Overview returns real data for configured tickers
- History respects source filtering
- Graceful degradation when ticker data is missing
- Performance: 20-ticker overview completes within 2 seconds

For On-Call Engineers:
    If tests fail, check:
    1. SentimentResponse model field changes (config_id, tickers, cache_status)
    2. query_timeseries return type (TimeseriesResponse dataclass)
    3. Source filtering logic in get_ticker_sentiment_history
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from src.lambdas.dashboard.sentiment import (
    ErrorResponse,
    clear_sentiment_cache,
    get_sentiment_by_configuration,
    get_ticker_sentiment_history,
)
from src.lambdas.dashboard.timeseries import SentimentBucketResponse, TimeseriesResponse
from src.lib.timeseries.models import Resolution

# =============================================================================
# Helpers
# =============================================================================


def _make_bucket(
    ticker: str,
    avg: float,
    count: int = 5,
    sources: list[str] | None = None,
    timestamp: str = "2024-01-01T00:00:00Z",
) -> SentimentBucketResponse:
    """Create a SentimentBucketResponse for testing."""
    return SentimentBucketResponse(
        ticker=ticker,
        resolution="24h",
        timestamp=timestamp,
        open=avg - 0.05,
        high=avg + 0.1,
        low=avg - 0.1,
        close=avg + 0.02,
        count=count,
        avg=avg,
        label_counts={"positive": count // 2, "neutral": count - count // 2},
        is_partial=False,
        sources=sources or ["tiingo", "finnhub"],
    )


def _make_timeseries_response(
    ticker: str,
    buckets: list[SentimentBucketResponse] | None = None,
    partial_bucket: SentimentBucketResponse | None = None,
) -> TimeseriesResponse:
    """Create a TimeseriesResponse for testing."""
    return TimeseriesResponse(
        ticker=ticker,
        resolution="24h",
        buckets=buckets or [],
        partial_bucket=partial_bucket,
        cache_hit=False,
        query_time_ms=1.5,
    )


def _make_dynamo_table_mock(
    config_exists: bool = True, user_id: str = "user-1", config_id: str = "cfg-1"
) -> MagicMock:
    """Create a mock DynamoDB table with optional config item."""
    table = MagicMock()
    if config_exists:
        table.get_item.return_value = {
            "Item": {
                "PK": f"USER#{user_id}",
                "SK": f"CONFIG#{config_id}",
                "tickers": ["AAPL", "GOOGL"],
            }
        }
    else:
        table.get_item.return_value = {}
    return table


# =============================================================================
# Test: Overview returns real data
# =============================================================================


@pytest.mark.integration
@freeze_time("2024-01-02T10:00:00Z")
class TestOverviewReturnsRealData:
    """Verify get_sentiment_by_configuration aggregates data from timeseries buckets."""

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_overview_returns_real_data_integration(self, mock_query):
        """Create config with tickers AAPL/GOOGL, populate buckets, verify non-empty sentiment."""
        clear_sentiment_cache()

        # Arrange: mock query_timeseries to return buckets for each ticker
        def query_side_effect(ticker, resolution, **kwargs):
            if ticker == "AAPL":
                bucket = _make_bucket(
                    "AAPL", avg=0.72, count=10, sources=["tiingo", "finnhub"]
                )
                return _make_timeseries_response("AAPL", buckets=[bucket])
            elif ticker == "GOOGL":
                bucket = _make_bucket("GOOGL", avg=-0.15, count=8, sources=["tiingo"])
                return _make_timeseries_response("GOOGL", buckets=[bucket])
            return _make_timeseries_response(ticker)

        mock_query.side_effect = query_side_effect

        # Act
        response = get_sentiment_by_configuration(
            config_id="cfg-overview-001",
            tickers=["AAPL", "GOOGL"],
            resolution=Resolution.TWENTY_FOUR_HOURS,
            skip_cache=True,
        )

        # Assert: response has sentiment for both tickers
        assert response.config_id == "cfg-overview-001"
        assert len(response.tickers) == 2
        assert response.cache_status == "fresh"

        # AAPL should have aggregated sentiment
        aapl_data = next(t for t in response.tickers if t.symbol == "AAPL")
        assert "aggregated" in aapl_data.sentiment
        assert aapl_data.sentiment["aggregated"].score == 0.72
        assert aapl_data.sentiment["aggregated"].label == "positive"

        # GOOGL should have aggregated sentiment
        googl_data = next(t for t in response.tickers if t.symbol == "GOOGL")
        assert "aggregated" in googl_data.sentiment
        assert googl_data.sentiment["aggregated"].score == -0.15
        assert googl_data.sentiment["aggregated"].label == "neutral"

        # Verify query was called for each ticker
        assert mock_query.call_count == 2


# =============================================================================
# Test: History with source filter
# =============================================================================


@pytest.mark.integration
@freeze_time("2024-01-02T10:00:00Z")
class TestHistoryWithSourceFilter:
    """Verify get_ticker_sentiment_history filters by source correctly."""

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_history_with_source_filter_integration(self, mock_query):
        """Populate buckets with mixed sources, filter by tiingo, verify only tiingo returned."""
        clear_sentiment_cache()

        # Arrange: create buckets with different sources
        tiingo_bucket = _make_bucket(
            "AAPL",
            avg=0.55,
            count=6,
            sources=["tiingo"],
            timestamp="2024-01-01T00:00:00Z",
        )
        finnhub_bucket = _make_bucket(
            "AAPL",
            avg=0.30,
            count=4,
            sources=["finnhub"],
            timestamp="2023-12-31T00:00:00Z",
        )
        mixed_bucket = _make_bucket(
            "AAPL",
            avg=0.42,
            count=10,
            sources=["tiingo", "finnhub"],
            timestamp="2023-12-30T00:00:00Z",
        )

        mock_query.return_value = _make_timeseries_response(
            "AAPL",
            buckets=[finnhub_bucket, mixed_bucket, tiingo_bucket],
        )

        # Act: call with source="tiingo"
        table = _make_dynamo_table_mock(
            config_exists=True, user_id="user-1", config_id="cfg-hist-001"
        )

        result = get_ticker_sentiment_history(
            table=table,
            user_id="user-1",
            config_id="cfg-hist-001",
            ticker="AAPL",
            source="tiingo",
            days=7,
            resolution=Resolution.TWENTY_FOUR_HOURS,
        )

        # Assert: should be a SentimentResponse (not ErrorResponse)
        assert not isinstance(
            result, ErrorResponse
        ), f"Expected SentimentResponse, got {result}"

        # Only buckets with tiingo in sources should be present
        assert len(result.tickers) == 1
        assert result.tickers[0].symbol == "AAPL"

        # The sentiment dict keys are bucket timestamps
        sentiment_entries = result.tickers[0].sentiment
        # tiingo_bucket and mixed_bucket have "tiingo" in sources; finnhub_bucket does not
        returned_timestamps = set(sentiment_entries.keys())
        assert (
            "2024-01-01T00:00:00Z" in returned_timestamps
        ), "tiingo-only bucket should be included"
        assert (
            "2023-12-30T00:00:00Z" in returned_timestamps
        ), "mixed tiingo+finnhub bucket should be included"
        assert (
            "2023-12-31T00:00:00Z" not in returned_timestamps
        ), "finnhub-only bucket should be excluded"


# =============================================================================
# Test: Graceful degradation for missing ticker
# =============================================================================


@pytest.mark.integration
@freeze_time("2024-01-02T10:00:00Z")
class TestGracefulDegradationMissingTicker:
    """Verify overview gracefully handles tickers with no data."""

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_graceful_degradation_missing_ticker(self, mock_query):
        """Config has AAPL and UNKNOWN. Only AAPL has data. Verify UNKNOWN returns empty."""
        clear_sentiment_cache()

        # Arrange: AAPL has data, UNKNOWN returns empty buckets
        def query_side_effect(ticker, resolution, **kwargs):
            if ticker == "AAPL":
                bucket = _make_bucket("AAPL", avg=0.65, count=12)
                return _make_timeseries_response("AAPL", buckets=[bucket])
            # UNKNOWN and any other ticker: no data
            return _make_timeseries_response(ticker, buckets=[], partial_bucket=None)

        mock_query.side_effect = query_side_effect

        # Act
        response = get_sentiment_by_configuration(
            config_id="cfg-degrade-001",
            tickers=["AAPL", "UNKNOWN"],
            resolution=Resolution.TWENTY_FOUR_HOURS,
            skip_cache=True,
        )

        # Assert: both tickers present in response
        assert len(response.tickers) == 2

        # AAPL has sentiment data
        aapl = next(t for t in response.tickers if t.symbol == "AAPL")
        assert len(aapl.sentiment) > 0
        assert "aggregated" in aapl.sentiment
        assert aapl.sentiment["aggregated"].score == 0.65

        # UNKNOWN has empty sentiment (graceful degradation)
        unknown = next(t for t in response.tickers if t.symbol == "UNKNOWN")
        assert len(unknown.sentiment) == 0

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_graceful_degradation_query_exception(self, mock_query):
        """If query_timeseries raises for one ticker, the other still returns data."""
        clear_sentiment_cache()

        def query_side_effect(ticker, resolution, **kwargs):
            if ticker == "AAPL":
                bucket = _make_bucket("AAPL", avg=0.50, count=5)
                return _make_timeseries_response("AAPL", buckets=[bucket])
            raise ConnectionError("DynamoDB timeout for UNKNOWN")

        mock_query.side_effect = query_side_effect

        # Act: should not raise
        response = get_sentiment_by_configuration(
            config_id="cfg-degrade-002",
            tickers=["AAPL", "UNKNOWN"],
            resolution=Resolution.TWENTY_FOUR_HOURS,
            skip_cache=True,
        )

        # AAPL still has data
        aapl = next(t for t in response.tickers if t.symbol == "AAPL")
        assert "aggregated" in aapl.sentiment

        # UNKNOWN has empty sentiment (exception caught internally)
        unknown = next(t for t in response.tickers if t.symbol == "UNKNOWN")
        assert len(unknown.sentiment) == 0


# =============================================================================
# Test: Overview performance with 20 tickers
# =============================================================================


@pytest.mark.integration
@freeze_time("2024-01-02T10:00:00Z")
class TestOverviewPerformance:
    """Verify the overview endpoint completes within acceptable time for 20 tickers."""

    @patch("src.lambdas.dashboard.timeseries.query_timeseries")
    def test_overview_performance_20_tickers(self, mock_query):
        """Create config with 20 tickers, populate minimal data, assert < 2s."""
        clear_sentiment_cache()

        # Arrange: 20 tickers, each returning a small response quickly
        tickers = [f"TICK{i:02d}" for i in range(20)]

        def query_side_effect(ticker, resolution, **kwargs):
            bucket = _make_bucket(ticker, avg=0.10, count=2)
            return _make_timeseries_response(ticker, buckets=[bucket])

        mock_query.side_effect = query_side_effect

        # Act: time the call
        start = time.monotonic()
        response = get_sentiment_by_configuration(
            config_id="cfg-perf-001",
            tickers=tickers,
            resolution=Resolution.TWENTY_FOUR_HOURS,
            skip_cache=True,
        )
        elapsed = time.monotonic() - start

        # Assert: completes within 2 seconds
        assert elapsed < 2.0, f"Overview for 20 tickers took {elapsed:.2f}s (max 2.0s)"

        # All 20 tickers should be in the response
        assert len(response.tickers) == 20

        # Each ticker should have aggregated sentiment
        for ticker_data in response.tickers:
            assert (
                "aggregated" in ticker_data.sentiment
            ), f"{ticker_data.symbol} missing aggregated sentiment"

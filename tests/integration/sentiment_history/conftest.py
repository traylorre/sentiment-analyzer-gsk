"""Fixtures for sentiment history integration tests.

Feature 1227: Now that the sentiment history endpoint queries DynamoDB
(instead of generating synthetic data), integration tests need mock
timeseries data. This conftest provides an autouse fixture that patches
query_timeseries to return realistic test buckets.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from unittest.mock import patch

import pytest


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


def _generate_buckets(ticker: str, days: int = 30) -> list[MockBucket]:
    """Generate realistic test buckets spanning `days` days."""
    buckets = []
    base_date = date.today() - timedelta(days=days - 1)
    # Vary scores across tickers for deterministic but distinct data
    ticker_offset = sum(ord(c) for c in ticker) % 100 / 200  # 0.0 to 0.5

    for i in range(days):
        d = base_date + timedelta(days=i)

        score = round(0.3 + ticker_offset + (i % 7) * 0.05, 4)
        score = max(-1.0, min(1.0, score))

        buckets.append(
            MockBucket(
                ticker=ticker,
                resolution="24h",
                timestamp=f"{d}T00:00:00+00:00",
                open=score - 0.02,
                high=score + 0.05,
                low=score - 0.05,
                close=score,
                count=1,
                avg=score,
                sources=[f"tiingo:{90000000 + i}"],
            )
        )
    return buckets


def _mock_query_timeseries(
    ticker, resolution, start=None, end=None, limit=None, cursor=None
):
    """Mock implementation of query_timeseries that returns test data."""
    # Generate ~30 days of data, filter to requested range
    all_buckets = _generate_buckets(ticker, days=400)

    if start:
        start_str = start.strftime("%Y-%m-%d")
        all_buckets = [b for b in all_buckets if b.timestamp[:10] >= start_str]
    if end:
        end_str = end.strftime("%Y-%m-%d")
        all_buckets = [b for b in all_buckets if b.timestamp[:10] <= end_str]

    return MockTimeseriesResponse(
        ticker=ticker,
        resolution="24h",
        buckets=all_buckets,
    )


@pytest.fixture(autouse=True)
def _mock_timeseries_query():
    """Auto-mock query_timeseries for all sentiment history integration tests.

    Feature 1227: The endpoint now queries DynamoDB. Integration tests
    run without real AWS credentials, so we mock the timeseries query
    with realistic test data.
    """
    with patch(
        "src.lambdas.dashboard.timeseries.query_timeseries",
        side_effect=_mock_query_timeseries,
    ):
        yield


@pytest.fixture(autouse=True)
def _clear_sentiment_cache():
    """Clear in-memory sentiment cache between tests."""
    from src.lambdas.shared.cache.sentiment_cache import clear_cache

    clear_cache()
    yield
    clear_cache()

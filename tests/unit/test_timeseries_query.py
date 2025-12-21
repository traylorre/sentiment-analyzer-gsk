"""Tests for timeseries query service in Dashboard Lambda.

TDD-QUERY-001: Time-series query service with caching
Canonical: [CS-001] DynamoDB best practices for time-series queries
[CS-005] Lambda global scope for caching

This test file implements tests for the timeseries query service
that powers the GET /api/v2/timeseries/{ticker} endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import boto3
import pytest
from freezegun import freeze_time
from moto import mock_aws

# Import will fail until module is implemented - this is expected for TDD
from src.lambdas.dashboard.timeseries import (
    TimeseriesQueryService,
    TimeseriesResponse,
    query_timeseries,
)
from src.lambdas.sse_streaming import cache as cache_module
from src.lib.timeseries import Resolution


@pytest.fixture(autouse=True)
def clear_global_cache() -> None:
    """Clear global cache between tests to ensure isolation."""
    # Reset the global cache singleton
    cache_module._global_cache = None
    yield
    # Cleanup after test
    cache_module._global_cache = None


def create_test_table(dynamodb_client: Any, table_name: str) -> None:
    """Create DynamoDB timeseries table for testing."""
    dynamodb_client.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def insert_bucket(
    table: Any,
    ticker: str,
    resolution: str,
    timestamp: str,
    *,
    open_val: float = 0.5,
    high: float = 0.8,
    low: float = 0.2,
    close: float = 0.6,
    count: int = 10,
    sum_val: float = 6.0,
    is_partial: bool = False,
) -> None:
    """Insert a sentiment bucket into DynamoDB."""
    pk = f"{ticker}#{resolution}"
    table.put_item(
        Item={
            "pk": pk,
            "sk": timestamp,
            "ticker": ticker,
            "resolution": resolution,
            "open": Decimal(str(open_val)),
            "high": Decimal(str(high)),
            "low": Decimal(str(low)),
            "close": Decimal(str(close)),
            "count": count,
            "sum": Decimal(str(sum_val)),
            "label_counts": {"positive": 7, "neutral": 2, "negative": 1},
            "sources": ["source1", "source2"],
            "is_partial": is_partial,
        }
    )


@pytest.fixture
def timeseries_table_name() -> str:
    """Return consistent table name for tests."""
    return "test-sentiment-timeseries"


class TestTimeseriesQueryService:
    """Tests for TimeseriesQueryService."""

    @mock_aws
    def test_query_returns_buckets_in_time_order(
        self, timeseries_table_name: str
    ) -> None:
        """Query MUST return buckets sorted by timestamp ascending."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )
        table = dynamodb.Table(timeseries_table_name)

        # Insert buckets out of order
        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:40:00Z")
        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:35:00Z")
        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:45:00Z")

        service = TimeseriesQueryService(table_name=timeseries_table_name)
        response = service.query("AAPL", Resolution.FIVE_MINUTES)

        timestamps = [b.timestamp for b in response.buckets]
        assert timestamps == [
            "2025-12-21T10:35:00Z",
            "2025-12-21T10:40:00Z",
            "2025-12-21T10:45:00Z",
        ]

    @mock_aws
    def test_query_filters_by_resolution(self, timeseries_table_name: str) -> None:
        """Query MUST only return buckets for requested resolution."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )
        table = dynamodb.Table(timeseries_table_name)

        # Insert buckets for different resolutions
        insert_bucket(table, "AAPL", "1m", "2025-12-21T10:35:00Z")
        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:35:00Z")
        insert_bucket(table, "AAPL", "1h", "2025-12-21T10:00:00Z")

        service = TimeseriesQueryService(table_name=timeseries_table_name)
        response = service.query("AAPL", Resolution.FIVE_MINUTES)

        assert len(response.buckets) == 1
        assert response.buckets[0].resolution == "5m"

    @mock_aws
    def test_query_respects_time_range(self, timeseries_table_name: str) -> None:
        """Query MUST filter by start/end time range."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )
        table = dynamodb.Table(timeseries_table_name)

        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:30:00Z")
        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:35:00Z")
        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:40:00Z")
        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:45:00Z")

        service = TimeseriesQueryService(table_name=timeseries_table_name)
        response = service.query(
            "AAPL",
            Resolution.FIVE_MINUTES,
            start=datetime(2025, 12, 21, 10, 35, tzinfo=UTC),
            end=datetime(2025, 12, 21, 10, 45, tzinfo=UTC),
        )

        assert len(response.buckets) == 2
        assert response.buckets[0].timestamp == "2025-12-21T10:35:00Z"
        assert response.buckets[1].timestamp == "2025-12-21T10:40:00Z"

    @mock_aws
    def test_query_returns_partial_bucket_separately(
        self, timeseries_table_name: str
    ) -> None:
        """Query MUST return partial bucket in dedicated field."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )
        table = dynamodb.Table(timeseries_table_name)

        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:35:00Z", is_partial=False)
        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:40:00Z", is_partial=True)

        service = TimeseriesQueryService(table_name=timeseries_table_name)
        response = service.query("AAPL", Resolution.FIVE_MINUTES)

        assert len(response.buckets) == 1
        assert response.buckets[0].timestamp == "2025-12-21T10:35:00Z"
        assert response.partial_bucket is not None
        assert response.partial_bucket.timestamp == "2025-12-21T10:40:00Z"
        assert response.partial_bucket.is_partial is True

    @mock_aws
    def test_query_returns_empty_when_no_data(self, timeseries_table_name: str) -> None:
        """Query MUST return empty list when no buckets exist."""
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )

        service = TimeseriesQueryService(table_name=timeseries_table_name)
        response = service.query("AAPL", Resolution.FIVE_MINUTES)

        assert response.buckets == []
        assert response.partial_bucket is None

    @mock_aws
    def test_query_tracks_timing(self, timeseries_table_name: str) -> None:
        """Query MUST include execution time in response."""
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )

        service = TimeseriesQueryService(table_name=timeseries_table_name)
        response = service.query("AAPL", Resolution.FIVE_MINUTES)

        assert response.query_time_ms >= 0
        assert isinstance(response.query_time_ms, float)


class TestTimeseriesQueryWithCache:
    """Tests for caching behavior in query service."""

    @mock_aws
    def test_cache_hit_returns_cached_data(self, timeseries_table_name: str) -> None:
        """Cached query MUST return cached data without DB call."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )
        table = dynamodb.Table(timeseries_table_name)

        insert_bucket(table, "AAPL", "5m", "2025-12-21T10:35:00Z")

        service = TimeseriesQueryService(
            table_name=timeseries_table_name, use_cache=True
        )

        # First query - cache miss
        response1 = service.query("AAPL", Resolution.FIVE_MINUTES)
        assert response1.cache_hit is False

        # Second query - cache hit
        response2 = service.query("AAPL", Resolution.FIVE_MINUTES)
        assert response2.cache_hit is True

    @mock_aws
    def test_cache_miss_after_ttl(self, timeseries_table_name: str) -> None:
        """Query MUST miss cache after resolution TTL expires."""
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )

        service = TimeseriesQueryService(
            table_name=timeseries_table_name, use_cache=True
        )

        with freeze_time("2025-12-21T10:35:00Z"):
            response1 = service.query("AAPL", Resolution.ONE_MINUTE)
            assert response1.cache_hit is False

        # After 60 seconds (1m TTL)
        with freeze_time("2025-12-21T10:36:01Z"):
            response2 = service.query("AAPL", Resolution.ONE_MINUTE)
            assert response2.cache_hit is False  # TTL expired

    @mock_aws
    def test_cache_isolated_by_ticker_and_resolution(
        self, timeseries_table_name: str
    ) -> None:
        """Cache entries MUST be keyed by (ticker, resolution)."""
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )

        service = TimeseriesQueryService(
            table_name=timeseries_table_name, use_cache=True
        )

        # Query AAPL/5m
        service.query("AAPL", Resolution.FIVE_MINUTES)

        # Query AAPL/1m - should be cache miss
        response = service.query("AAPL", Resolution.ONE_MINUTE)
        assert response.cache_hit is False

        # Query TSLA/5m - should be cache miss
        response = service.query("TSLA", Resolution.FIVE_MINUTES)
        assert response.cache_hit is False


class TestTimeseriesResponse:
    """Tests for TimeseriesResponse model."""

    def test_response_includes_metadata(self) -> None:
        """Response MUST include ticker, resolution, and timing."""
        response = TimeseriesResponse(
            ticker="AAPL",
            resolution="5m",
            buckets=[],
            partial_bucket=None,
            cache_hit=False,
            query_time_ms=15.3,
        )

        assert response.ticker == "AAPL"
        assert response.resolution == "5m"
        assert response.cache_hit is False
        assert response.query_time_ms == 15.3

    def test_response_serializes_to_dict(self) -> None:
        """Response MUST be JSON-serializable for API output."""
        response = TimeseriesResponse(
            ticker="AAPL",
            resolution="5m",
            buckets=[],
            partial_bucket=None,
            cache_hit=True,
            query_time_ms=5.2,
        )

        result = response.to_dict()

        assert result["ticker"] == "AAPL"
        assert result["resolution"] == "5m"
        assert result["buckets"] == []
        assert result["partial_bucket"] is None
        assert result["cache_hit"] is True
        assert result["query_time_ms"] == 5.2


class TestQueryTimeseries:
    """Tests for the query_timeseries convenience function."""

    @mock_aws
    def test_query_timeseries_uses_env_table_name(
        self, timeseries_table_name: str
    ) -> None:
        """query_timeseries MUST use TIMESERIES_TABLE env var."""
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )

        with patch.dict("os.environ", {"TIMESERIES_TABLE": timeseries_table_name}):
            response = query_timeseries("AAPL", Resolution.FIVE_MINUTES)

        assert response.ticker == "AAPL"
        assert response.resolution == "5m"

    @mock_aws
    def test_query_timeseries_defaults_cache_enabled(
        self, timeseries_table_name: str
    ) -> None:
        """query_timeseries MUST enable cache by default for performance."""
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )

        with patch.dict("os.environ", {"TIMESERIES_TABLE": timeseries_table_name}):
            # First call (cache miss)
            query_timeseries("AAPL", Resolution.FIVE_MINUTES)
            # Second call should hit cache
            response2 = query_timeseries("AAPL", Resolution.FIVE_MINUTES)

        assert response2.cache_hit is True


class TestTimeseriesQueryEdgeCases:
    """Tests for edge cases and error handling."""

    @mock_aws
    def test_query_handles_ticker_with_special_chars(
        self, timeseries_table_name: str
    ) -> None:
        """Query MUST handle tickers correctly (uppercase only per spec)."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )
        table = dynamodb.Table(timeseries_table_name)

        insert_bucket(table, "BRK.A", "5m", "2025-12-21T10:35:00Z")

        service = TimeseriesQueryService(table_name=timeseries_table_name)
        response = service.query("BRK.A", Resolution.FIVE_MINUTES)

        assert len(response.buckets) == 1
        assert response.buckets[0].ticker == "BRK.A"

    @mock_aws
    def test_query_handles_decimal_precision(self, timeseries_table_name: str) -> None:
        """Query MUST correctly convert DynamoDB Decimal to float."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )
        table = dynamodb.Table(timeseries_table_name)

        insert_bucket(
            table,
            "AAPL",
            "5m",
            "2025-12-21T10:35:00Z",
            open_val=0.123456789,
            high=0.987654321,
        )

        service = TimeseriesQueryService(table_name=timeseries_table_name)
        response = service.query("AAPL", Resolution.FIVE_MINUTES)

        bucket = response.buckets[0]
        assert isinstance(bucket.open, float)
        assert isinstance(bucket.high, float)
        assert abs(bucket.open - 0.123456789) < 0.0001
        assert abs(bucket.high - 0.987654321) < 0.0001

    @mock_aws
    def test_query_includes_avg_calculation(self, timeseries_table_name: str) -> None:
        """Bucket avg MUST be calculated as sum/count."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )
        table = dynamodb.Table(timeseries_table_name)

        insert_bucket(
            table,
            "AAPL",
            "5m",
            "2025-12-21T10:35:00Z",
            count=10,
            sum_val=7.5,
        )

        service = TimeseriesQueryService(table_name=timeseries_table_name)
        response = service.query("AAPL", Resolution.FIVE_MINUTES)

        bucket = response.buckets[0]
        assert bucket.avg == pytest.approx(0.75)  # 7.5 / 10

    @mock_aws
    def test_query_with_no_start_end_uses_defaults(
        self, timeseries_table_name: str
    ) -> None:
        """Query without time range MUST use sensible defaults."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_test_table(
            boto3.client("dynamodb", region_name="us-east-1"), timeseries_table_name
        )
        table = dynamodb.Table(timeseries_table_name)

        # Insert data for the past hour
        for i in range(12):  # 12 * 5 = 60 minutes
            ts = f"2025-12-21T{10 + i // 12:02d}:{(i * 5) % 60:02d}:00Z"
            insert_bucket(table, "AAPL", "5m", ts)

        service = TimeseriesQueryService(table_name=timeseries_table_name)

        with freeze_time("2025-12-21T10:55:00Z"):
            response = service.query("AAPL", Resolution.FIVE_MINUTES)

        # Should return some reasonable number of buckets
        assert len(response.buckets) > 0

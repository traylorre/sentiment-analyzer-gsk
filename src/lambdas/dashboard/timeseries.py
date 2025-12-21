"""Time-series query service for Dashboard Lambda.

Canonical References:
[CS-001] "Design your application to process one partition key at a time"
         - AWS DynamoDB Best Practices

[CS-005] "Initialize SDK clients and database connections outside of the
         function handler so they can be reused across invocations."
         - AWS Lambda Best Practices

This module provides the TimeseriesQueryService for querying sentiment
time-series data from DynamoDB with caching support.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import boto3

from src.lambdas.sse_streaming.cache import ResolutionCache, get_global_cache
from src.lib.timeseries import Resolution

if TYPE_CHECKING:
    pass


@dataclass
class SentimentBucketResponse:
    """A sentiment bucket as returned from queries."""

    ticker: str
    resolution: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    count: int
    avg: float
    label_counts: dict[str, int]
    is_partial: bool
    sources: list[str] = field(default_factory=list)
    progress_pct: float | None = None
    next_update_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "ticker": self.ticker,
            "resolution": self.resolution,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "count": self.count,
            "avg": self.avg,
            "label_counts": self.label_counts,
            "is_partial": self.is_partial,
        }
        if self.progress_pct is not None:
            result["progress_pct"] = self.progress_pct
        if self.next_update_at is not None:
            result["next_update_at"] = self.next_update_at
        return result


@dataclass
class TimeseriesResponse:
    """Response from a time-series query."""

    ticker: str
    resolution: str
    buckets: list[SentimentBucketResponse]
    partial_bucket: SentimentBucketResponse | None
    cache_hit: bool
    query_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "ticker": self.ticker,
            "resolution": self.resolution,
            "buckets": [b.to_dict() for b in self.buckets],
            "partial_bucket": self.partial_bucket.to_dict()
            if self.partial_bucket
            else None,
            "cache_hit": self.cache_hit,
            "query_time_ms": self.query_time_ms,
        }


def _decimal_to_float(value: Decimal | float | int) -> float:
    """Convert DynamoDB Decimal to Python float."""
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _item_to_bucket(item: dict[str, Any]) -> SentimentBucketResponse:
    """Convert a DynamoDB item to SentimentBucketResponse."""
    count = int(item.get("count", 0))
    sum_val = _decimal_to_float(item.get("sum", 0))
    avg = sum_val / count if count > 0 else 0.0

    # Convert label_counts Decimals to ints
    raw_label_counts = item.get("label_counts", {})
    label_counts = {
        k: int(v) if isinstance(v, Decimal) else int(v)
        for k, v in raw_label_counts.items()
    }

    return SentimentBucketResponse(
        ticker=item["ticker"],
        resolution=item["resolution"],
        timestamp=item["sk"],
        open=_decimal_to_float(item.get("open", 0)),
        high=_decimal_to_float(item.get("high", 0)),
        low=_decimal_to_float(item.get("low", 0)),
        close=_decimal_to_float(item.get("close", 0)),
        count=count,
        avg=avg,
        label_counts=label_counts,
        is_partial=item.get("is_partial", False),
        sources=list(item.get("sources", [])),
    )


class TimeseriesQueryService:
    """Service for querying time-series sentiment data.

    Supports caching via Lambda global scope per [CS-005].
    Uses composite primary key queries per [CS-001].

    Attributes:
        table_name: DynamoDB table name.
        use_cache: Whether to use resolution-aware caching.
    """

    def __init__(
        self,
        table_name: str,
        *,
        use_cache: bool = True,
        region: str = "us-east-1",
    ) -> None:
        """Initialize query service.

        Args:
            table_name: DynamoDB table name.
            use_cache: Whether to enable caching (default True).
            region: AWS region for DynamoDB.
        """
        self.table_name = table_name
        self.use_cache = use_cache
        self._dynamodb = boto3.resource("dynamodb", region_name=region)
        self._table = self._dynamodb.Table(table_name)
        self._cache: ResolutionCache | None = get_global_cache() if use_cache else None

    def query(
        self,
        ticker: str,
        resolution: Resolution,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> TimeseriesResponse:
        """Query time-series data for a ticker/resolution.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            resolution: Time resolution for data.
            start: Start of time range (inclusive). Defaults to 1 period ago.
            end: End of time range (exclusive). Defaults to now.

        Returns:
            TimeseriesResponse with buckets and metadata.
        """
        query_start = time.time()
        cache_hit = False

        # Check cache first if enabled
        if self._cache is not None:
            if start is None and end is None:
                # Only use cache for default time range queries
                cached = self._cache.get(ticker, resolution)
                if cached is not None:
                    cache_hit = True
                    query_time_ms = (time.time() - query_start) * 1000
                    return TimeseriesResponse(
                        ticker=ticker,
                        resolution=resolution.value,
                        buckets=cached["buckets"],
                        partial_bucket=cached.get("partial_bucket"),
                        cache_hit=True,
                        query_time_ms=query_time_ms,
                    )

        # Build partition key
        pk = f"{ticker}#{resolution.value}"

        # Build key condition expression
        key_condition = "pk = :pk"
        expression_values: dict[str, Any] = {":pk": pk}

        # Add time range conditions if specified
        # Use BETWEEN for key condition and FilterExpression for exclusive end
        filter_expression: str | None = None
        if start is not None and end is not None:
            key_condition += " AND sk BETWEEN :start AND :end"
            expression_values[":start"] = start.isoformat().replace("+00:00", "Z")
            expression_values[":end"] = end.isoformat().replace("+00:00", "Z")
            # FilterExpression for exclusive end (end is excluded)
            filter_expression = "sk < :end"
        elif start is not None:
            key_condition += " AND sk >= :start"
            expression_values[":start"] = start.isoformat().replace("+00:00", "Z")
        elif end is not None:
            key_condition += " AND sk < :end"
            expression_values[":end"] = end.isoformat().replace("+00:00", "Z")

        # Execute query
        query_kwargs = {
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeValues": expression_values,
            "ScanIndexForward": True,  # Ascending order by SK (timestamp)
        }
        if filter_expression:
            query_kwargs["FilterExpression"] = filter_expression

        response = self._table.query(**query_kwargs)

        # Convert items to buckets
        all_buckets: list[SentimentBucketResponse] = []
        partial_bucket: SentimentBucketResponse | None = None

        for item in response.get("Items", []):
            bucket = _item_to_bucket(item)
            if bucket.is_partial:
                partial_bucket = bucket
            else:
                all_buckets.append(bucket)

        # Cache the result if using cache and no time range specified
        if self._cache is not None and start is None and end is None:
            self._cache.set(
                ticker,
                resolution,
                data={
                    "buckets": all_buckets,
                    "partial_bucket": partial_bucket,
                },
            )

        query_time_ms = (time.time() - query_start) * 1000

        return TimeseriesResponse(
            ticker=ticker,
            resolution=resolution.value,
            buckets=all_buckets,
            partial_bucket=partial_bucket,
            cache_hit=cache_hit,
            query_time_ms=query_time_ms,
        )


# Global service instance for Lambda warm invocations
_global_service: TimeseriesQueryService | None = None


def query_timeseries(
    ticker: str,
    resolution: Resolution,
    start: datetime | None = None,
    end: datetime | None = None,
) -> TimeseriesResponse:
    """Convenience function to query time-series data.

    Uses a global service instance per [CS-005] for Lambda warm invocations.
    Table name is read from TIMESERIES_TABLE environment variable.

    Args:
        ticker: Stock ticker symbol.
        resolution: Time resolution.
        start: Optional start time.
        end: Optional end time.

    Returns:
        TimeseriesResponse with buckets and metadata.
    """
    global _global_service

    if _global_service is None:
        table_name = os.environ.get("TIMESERIES_TABLE", "sentiment-timeseries")
        region = os.environ.get("AWS_REGION", "us-east-1")
        _global_service = TimeseriesQueryService(
            table_name=table_name,
            use_cache=True,
            region=region,
        )

    return _global_service.query(ticker, resolution, start, end)

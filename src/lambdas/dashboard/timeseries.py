"""Time-series query service for Dashboard Lambda.

Canonical References:
[CS-001] "Design your application to process one partition key at a time"
         - AWS DynamoDB Best Practices

[CS-002] "ticker#resolution composite key for multi-dimensional time-series"
         - DynamoDB Key Design Best Practices

[CS-005] "Initialize SDK clients and database connections outside of the
         function handler so they can be reused across invocations."
         - AWS Lambda Best Practices

[CS-006] "Shared caching across users for same ticker+resolution"
         - Feature 1009 Spec

This module provides the TimeseriesQueryService for querying sentiment
time-series data from DynamoDB with caching support.

Feature 1009 Phase 6 additions:
- T050: query_batch() for multi-ticker queries in parallel
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import boto3

from src.lib.timeseries import Resolution, ResolutionCache, get_global_cache

logger = logging.getLogger(__name__)

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
    """Response from a time-series query.

    Supports cursor-based pagination per [CS-001]:
    "Design your application to process one partition key at a time"
    """

    ticker: str
    resolution: str
    buckets: list[SentimentBucketResponse]
    partial_bucket: SentimentBucketResponse | None
    cache_hit: bool
    query_time_ms: float
    next_cursor: str | None = None
    has_more: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "ticker": self.ticker,
            "resolution": self.resolution,
            "buckets": [b.to_dict() for b in self.buckets],
            "partial_bucket": self.partial_bucket.to_dict()
            if self.partial_bucket
            else None,
            "cache_hit": self.cache_hit,
            "query_time_ms": self.query_time_ms,
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
        }
        return result


def _decimal_to_float(value: Decimal | float | int) -> float:
    """Convert DynamoDB Decimal to Python float."""
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _item_to_bucket(item: dict[str, Any]) -> SentimentBucketResponse:
    """Convert a DynamoDB item to SentimentBucketResponse.

    DynamoDB items use uppercase keys PK and SK:
    - PK: "TICKER#resolution" (e.g., "AAPL#6h")
    - SK: timestamp (e.g., "2025-12-15T00:00:00+00:00")
    """
    count = int(item.get("count", 0))
    sum_val = _decimal_to_float(item.get("sum", 0))
    avg = sum_val / count if count > 0 else 0.0

    # Convert label_counts Decimals to ints
    raw_label_counts = item.get("label_counts", {})
    label_counts = {
        k: int(v) if isinstance(v, Decimal) else int(v)
        for k, v in raw_label_counts.items()
    }

    # Parse ticker and resolution from PK (format: "TICKER#resolution")
    pk = item["PK"]
    ticker, resolution = pk.rsplit("#", 1)

    return SentimentBucketResponse(
        ticker=ticker,
        resolution=resolution,
        timestamp=item["SK"],
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

    # Default limits per resolution (approximately 1 hour of data at that resolution)
    DEFAULT_LIMITS = {
        Resolution.ONE_MINUTE: 60,
        Resolution.FIVE_MINUTES: 12,
        Resolution.TEN_MINUTES: 6,
        Resolution.ONE_HOUR: 24,
        Resolution.THREE_HOURS: 8,
        Resolution.SIX_HOURS: 4,
        Resolution.TWELVE_HOURS: 14,
        Resolution.TWENTY_FOUR_HOURS: 7,
    }

    def query(
        self,
        ticker: str,
        resolution: Resolution,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> TimeseriesResponse:
        """Query time-series data for a ticker/resolution with pagination.

        Supports cursor-based pagination per [CS-001]:
        "Design your application to process one partition key at a time"

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            resolution: Time resolution for data.
            start: Start of time range (inclusive). Defaults to 1 period ago.
            end: End of time range (exclusive). Defaults to now.
            limit: Maximum number of buckets to return. Defaults to resolution-based limit.
            cursor: Pagination cursor (SK value) to continue from previous query.

        Returns:
            TimeseriesResponse with buckets, metadata, and pagination info.
        """
        query_start = time.time()
        cache_hit = False

        # Use default limit if not specified
        if limit is None:
            limit = self.DEFAULT_LIMITS.get(resolution, 60)

        # Check cache first if enabled (only for non-paginated queries)
        if self._cache is not None and cursor is None:
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
                        next_cursor=None,
                        has_more=False,
                    )

        # Build partition key
        pk = f"{ticker}#{resolution.value}"

        # Build key condition expression (DynamoDB uses uppercase PK and SK)
        key_condition = "PK = :pk"
        expression_values: dict[str, Any] = {":pk": pk}

        # Add time range conditions if specified
        # Use BETWEEN for key condition and FilterExpression for exclusive end
        filter_expression: str | None = None
        if start is not None and end is not None:
            key_condition += " AND SK BETWEEN :start AND :end"
            expression_values[":start"] = start.isoformat().replace("+00:00", "Z")
            expression_values[":end"] = end.isoformat().replace("+00:00", "Z")
            # FilterExpression for exclusive end (end is excluded)
            filter_expression = "SK < :end"
        elif start is not None:
            key_condition += " AND SK >= :start"
            expression_values[":start"] = start.isoformat().replace("+00:00", "Z")
        elif end is not None:
            key_condition += " AND SK < :end"
            expression_values[":end"] = end.isoformat().replace("+00:00", "Z")

        # Execute query with pagination support
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeValues": expression_values,
            "ScanIndexForward": True,  # Ascending order by SK (timestamp)
            "Limit": limit,
        }
        if filter_expression:
            query_kwargs["FilterExpression"] = filter_expression

        # Add cursor for pagination (ExclusiveStartKey uses uppercase keys)
        if cursor is not None:
            query_kwargs["ExclusiveStartKey"] = {"PK": pk, "SK": cursor}

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

        # Extract pagination cursor from response (uses uppercase SK)
        last_evaluated_key = response.get("LastEvaluatedKey")
        next_cursor = last_evaluated_key["SK"] if last_evaluated_key else None
        has_more = last_evaluated_key is not None

        # Cache the result if using cache and no time range/pagination specified
        if self._cache is not None and start is None and end is None and cursor is None:
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
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def query_batch(
        self,
        tickers: list[str],
        resolution: Resolution,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> dict[str, TimeseriesResponse]:
        """Query time-series data for multiple tickers in parallel.

        Task T050: Batch query for multi-ticker comparison view.
        Canonical: [CS-002] "ticker#resolution composite key"

        Goal: 10 tickers load in <1 second (SC-006)

        Args:
            tickers: List of stock ticker symbols.
            resolution: Time resolution for data.
            start: Start of time range (inclusive).
            end: End of time range (exclusive).
            limit: Maximum number of buckets per ticker.

        Returns:
            Dict mapping ticker symbol to TimeseriesResponse.
            Tickers with errors return empty buckets (partial failure handling).
        """
        if not tickers:
            return {}

        results: dict[str, TimeseriesResponse] = {}

        # Use ThreadPoolExecutor for parallel I/O
        # Max workers = min(len(tickers), 10) to avoid overwhelming DynamoDB
        max_workers = min(len(tickers), 10)

        def query_ticker(ticker: str) -> tuple[str, TimeseriesResponse]:
            """Query a single ticker and return (ticker, response) tuple."""
            try:
                response = self.query(
                    ticker=ticker,
                    resolution=resolution,
                    start=start,
                    end=end,
                    limit=limit,
                )
                return ticker, response
            except Exception as e:
                # Log error but return empty response (partial failure handling)
                logger.warning(
                    "Failed to query ticker",
                    extra={
                        "ticker": ticker,
                        "resolution": resolution.value,
                        "error": str(e),
                    },
                )
                # Return empty response for failed ticker
                return ticker, TimeseriesResponse(
                    ticker=ticker,
                    resolution=resolution.value,
                    buckets=[],
                    partial_bucket=None,
                    cache_hit=False,
                    query_time_ms=0.0,
                    next_cursor=None,
                    has_more=False,
                )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all ticker queries
            futures = {
                executor.submit(query_ticker, ticker): ticker for ticker in tickers
            }

            # Collect results as they complete
            for future in as_completed(futures):
                ticker, response = future.result()
                results[ticker] = response

        return results


# Global service instance for Lambda warm invocations
_global_service: TimeseriesQueryService | None = None


def query_timeseries(
    ticker: str,
    resolution: Resolution,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> TimeseriesResponse:
    """Convenience function to query time-series data with pagination.

    Uses a global service instance per [CS-005] for Lambda warm invocations.
    Table name is read from TIMESERIES_TABLE environment variable.

    Args:
        ticker: Stock ticker symbol.
        resolution: Time resolution.
        start: Optional start time.
        end: Optional end time.
        limit: Maximum number of buckets to return.
        cursor: Pagination cursor to continue from previous query.

    Returns:
        TimeseriesResponse with buckets, metadata, and pagination info.
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

    return _global_service.query(ticker, resolution, start, end, limit, cursor)

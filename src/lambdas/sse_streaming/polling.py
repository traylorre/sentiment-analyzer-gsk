"""DynamoDB polling service for SSE streaming Lambda.

Polls DynamoDB at configurable intervals to detect new sentiment data.
Per FR-015: Poll at 5-second intervals (configurable via SSE_POLL_INTERVAL).
"""

import asyncio
import logging
import os
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import NamedTuple

import boto3
from botocore.exceptions import ClientError
from models import MetricsEventData
from tracing import get_tracer, is_enabled

logger = logging.getLogger(__name__)


@dataclass
class TickerAggregate:
    """Per-ticker sentiment aggregate for change detection (FR-003)."""

    ticker: str
    score: float  # Weighted average score across items
    label: str  # Majority sentiment label
    confidence: float  # Average confidence across items
    count: int  # Total articles for this ticker


class PollResult(NamedTuple):
    """Result of a single polling cycle."""

    metrics: MetricsEventData
    metrics_changed: bool
    per_ticker: dict[str, TickerAggregate]
    timeseries_buckets: dict[str, dict]


class PollingService:
    """Polls DynamoDB for sentiment data and aggregates metrics.

    Uses the same aggregation logic as the dashboard Lambda to ensure
    consistency between REST API and SSE streaming data.
    """

    def __init__(
        self,
        table_name: str | None = None,
        poll_interval: int | None = None,
    ):
        """Initialize polling service.

        Args:
            table_name: DynamoDB table name.
                       Defaults to SENTIMENTS_TABLE env var.
            poll_interval: Poll interval in seconds.
                          Defaults to SSE_POLL_INTERVAL env var or 5.

        Raises:
            ValueError: If SENTIMENTS_TABLE env var is not set and no table_name provided.
        """
        self._table_name = table_name or os.environ.get("SENTIMENTS_TABLE")
        if not self._table_name:
            raise ValueError(
                "SENTIMENTS_TABLE environment variable is required "
                "(no fallback - Amendment 1.15)"
            )
        self._poll_interval = poll_interval or int(
            os.environ.get("SSE_POLL_INTERVAL", "5")
        )
        self._table = None  # Lazy initialization
        self._timeseries_table_name = os.environ.get("TIMESERIES_TABLE")
        self._last_metrics: MetricsEventData | None = None

    @property
    def poll_interval(self) -> int:
        """Get poll interval in seconds."""
        return self._poll_interval

    def _get_table(self):
        """Get DynamoDB table resource (lazy initialization)."""
        if self._table is None:
            dynamodb = boto3.resource("dynamodb")
            self._table = dynamodb.Table(self._table_name)
        return self._table

    def _aggregate_metrics(self, items: list[dict]) -> MetricsEventData:
        """Aggregate sentiment items into metrics.

        Args:
            items: List of DynamoDB items

        Returns:
            Aggregated MetricsEventData
        """
        total = len(items)
        positive = 0
        neutral = 0
        negative = 0
        by_tag: dict[str, int] = {}

        for item in items:
            sentiment = item.get("sentiment", "").lower()
            if sentiment == "positive":
                positive += 1
            elif sentiment == "neutral":
                neutral += 1
            elif sentiment == "negative":
                negative += 1

            for ticker in item.get("matched_tickers", []):
                if ticker:
                    by_tag[ticker] = by_tag.get(ticker, 0) + 1

        return MetricsEventData(
            total=total,
            positive=positive,
            neutral=neutral,
            negative=negative,
            by_tag=by_tag,
            rate_last_hour=0,  # Would need timestamp filtering
            rate_last_24h=total,  # Simplified for now
            timestamp=datetime.now(UTC),
        )

    def _metrics_changed(
        self, old: MetricsEventData | None, new: MetricsEventData
    ) -> bool:
        """Check if metrics have changed.

        Args:
            old: Previous metrics (None if first poll)
            new: Current metrics

        Returns:
            True if metrics changed, False otherwise
        """
        if old is None:
            return True

        # Compare key fields (ignore timestamp)
        if old.total != new.total:
            return True
        if old.positive != new.positive:
            return True
        if old.neutral != new.neutral:
            return True
        if old.negative != new.negative:
            return True
        if old.by_tag != new.by_tag:
            return True

        return False

    def _compute_per_ticker_aggregates(
        self, items: list[dict]
    ) -> dict[str, TickerAggregate]:
        """Compute per-ticker sentiment aggregates from DynamoDB items.

        For each ticker found in items' matched_tickers lists, computes:
        - Weighted average score (sum of scores / count)
        - Majority sentiment label
        - Average confidence (same as score, since items lack separate confidence)
        - Total article count

        Args:
            items: List of DynamoDB items with score, sentiment, matched_tickers fields

        Returns:
            Dict mapping ticker symbol to TickerAggregate
        """
        # Accumulators per ticker
        score_sums: dict[str, Decimal] = {}
        label_counts: dict[str, Counter] = {}
        counts: dict[str, int] = {}

        for item in items:
            tickers = item.get("matched_tickers", [])
            score = item.get("score", Decimal("0"))
            sentiment = item.get("sentiment", "neutral").lower()

            # Coerce score to Decimal if needed
            if not isinstance(score, Decimal):
                score = Decimal(str(score))

            for ticker in tickers:
                if not ticker:
                    continue
                score_sums[ticker] = score_sums.get(ticker, Decimal("0")) + score
                counts[ticker] = counts.get(ticker, 0) + 1
                if ticker not in label_counts:
                    label_counts[ticker] = Counter()
                label_counts[ticker][sentiment] += 1

        result: dict[str, TickerAggregate] = {}
        for ticker in counts:
            count = counts[ticker]
            avg_score = float(score_sums[ticker] / count)
            majority_label = label_counts[ticker].most_common(1)[0][0]
            result[ticker] = TickerAggregate(
                ticker=ticker,
                score=avg_score,
                label=majority_label,
                confidence=avg_score,  # No separate confidence field in items
                count=count,
            )

        return result

    def _fetch_timeseries_buckets(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch current timeseries bucket data for all tickers and resolutions.

        Uses BatchGetItem to fetch the current (in-progress) bucket for each
        ticker x resolution combination. This enables partial_bucket event
        emission in the SSE stream (FR-002, FR-004a).

        Args:
            tickers: List of ticker symbols to fetch buckets for

        Returns:
            Dict mapping "{ticker}#{resolution}" to bucket data dict
            (containing open, close, high, low, count, sum).
            Returns empty dict on failure or if TIMESERIES_TABLE is not set.
        """
        from src.lib.timeseries import Resolution, floor_to_bucket

        if not self._timeseries_table_name:
            return {}

        if not tickers:
            return {}

        try:
            now = datetime.now(UTC)

            # Build keys for all ticker x resolution combinations
            all_keys: list[dict] = []
            for ticker in tickers:
                for resolution in Resolution:
                    pk = f"{ticker}#{resolution.value}"
                    sk = floor_to_bucket(now, resolution).isoformat()
                    all_keys.append(
                        {
                            "PK": {"S": pk},
                            "SK": {"S": sk},
                        }
                    )

            if not all_keys:
                return {}

            # Use low-level client for BatchGetItem
            dynamodb_client = boto3.client("dynamodb")
            result: dict[str, dict] = {}

            # Split into batches of 100 (DynamoDB BatchGetItem limit)
            for i in range(0, len(all_keys), 100):
                batch_keys = all_keys[i : i + 100]
                response = dynamodb_client.batch_get_item(
                    RequestItems={
                        self._timeseries_table_name: {
                            "Keys": batch_keys,
                        }
                    }
                )

                # Parse response items
                items = response.get("Responses", {}).get(
                    self._timeseries_table_name, []
                )
                for item in items:
                    pk = item.get("PK", {}).get("S", "")
                    bucket_data: dict = {}
                    for field in ("open", "close", "high", "low", "sum"):
                        if field in item and "N" in item[field]:
                            bucket_data[field] = float(item[field]["N"])
                    if "count" in item and "N" in item["count"]:
                        bucket_data["count"] = int(item["count"]["N"])
                    if pk and bucket_data:
                        result[pk] = bucket_data

            return result

        except ClientError as e:
            logger.warning(
                "Timeseries poll failed",
                extra={"error": str(e)},
            )
            return {}

    async def poll(self) -> PollResult:
        """Poll DynamoDB and return current metrics with per-ticker aggregates.

        Uses by_sentiment GSI queries for O(result) performance.
        (502-gsi-query-optimization: Replaced scan with GSI queries)

        Returns:
            PollResult with metrics, change flag, per-ticker aggregates,
            and timeseries bucket data.
        """
        # T042: OTel span for DynamoDB poll cycle
        otel_tracer = get_tracer()
        span = None
        if otel_tracer and is_enabled():
            from opentelemetry.trace import SpanKind

            span = otel_tracer.start_span("dynamodb_poll", kind=SpanKind.CLIENT)

        poll_start = time.perf_counter()
        try:
            # Run DynamoDB GSI queries in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self._query_all_sentiments)

            items = response.get("Items", [])
            metrics = self._aggregate_metrics(items)
            per_ticker = self._compute_per_ticker_aggregates(items)

            # T022: Fetch timeseries buckets for partial_bucket events
            tickers = list(per_ticker.keys())
            timeseries = await loop.run_in_executor(
                None, self._fetch_timeseries_buckets, tickers
            )

            changed = self._metrics_changed(self._last_metrics, metrics)
            self._last_metrics = metrics

            poll_duration_ms = (time.perf_counter() - poll_start) * 1000

            # T042: Span annotations
            if span:
                span.set_attribute("item_count", len(items))
                span.set_attribute("changed_count", 1 if changed else 0)
                span.set_attribute("poll_duration_ms", poll_duration_ms)

                # T094: Cache hit rate aggregate annotation (FR-009)
                try:
                    from src.lib.timeseries.cache import get_global_cache

                    cache = get_global_cache()
                    stats = cache.stats()
                    total_requests = stats.get("hits", 0) + stats.get("misses", 0)
                    if total_requests > 0:
                        hit_rate = stats["hits"] / total_requests
                        span.set_attribute("cache_hit_rate", round(hit_rate, 4))
                    span.set_attribute("cache_hit", not changed)
                except Exception:  # noqa: S110
                    pass  # Best-effort cache metrics

            logger.debug(
                "DynamoDB poll complete",
                extra={
                    "total_items": metrics.total,
                    "changed": changed,
                },
            )

            return PollResult(
                metrics=metrics,
                metrics_changed=changed,
                per_ticker=per_ticker,
                timeseries_buckets=timeseries,
            )

        except ClientError as e:
            # T048: Dual-call error pattern (FR-144, FR-150)
            if span:
                from opentelemetry.trace import StatusCode

                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)

            logger.error(
                "DynamoDB poll failed",
                extra={"error": str(e)},
                exc_info=True,
            )
            # Return last known metrics if available
            fallback_metrics = self._last_metrics or MetricsEventData(
                total=0, positive=0, neutral=0, negative=0
            )
            return PollResult(
                metrics=fallback_metrics,
                metrics_changed=False,
                per_ticker={},
                timeseries_buckets={},
            )

        finally:
            if span:
                span.end()

    def _query_by_sentiment(self, sentiment: str) -> list[dict]:
        """Query DynamoDB table for sentiment items by sentiment type using GSI.

        Uses by_sentiment GSI for O(result) query performance instead of O(table) scan.
        (502-gsi-query-optimization)

        Args:
            sentiment: Sentiment type to query (positive, neutral, negative)

        Returns:
            List of DynamoDB items matching the sentiment
        """
        table = self._get_table()
        items: list[dict] = []

        response = table.query(
            IndexName="by_sentiment",
            KeyConditionExpression="sentiment = :sentiment",
            ExpressionAttributeValues={":sentiment": sentiment},
        )
        items.extend(response.get("Items", []))

        # Handle pagination with LastEvaluatedKey
        while "LastEvaluatedKey" in response:
            response = table.query(
                IndexName="by_sentiment",
                KeyConditionExpression="sentiment = :sentiment",
                ExpressionAttributeValues={":sentiment": sentiment},
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        return items

    def _query_all_sentiments(self) -> dict:
        """Query all sentiment types using by_sentiment GSI.

        Uses by_sentiment GSI for O(result) query performance instead of O(table) scan.
        (502-gsi-query-optimization: Replaced _scan_table)

        Returns:
            Dict with 'Items' key containing all sentiment items
        """
        all_items: list[dict] = []

        # Query each sentiment type using GSI
        for sentiment in ("positive", "neutral", "negative"):
            items = self._query_by_sentiment(sentiment)
            all_items.extend(items)

        return {"Items": all_items}

    async def poll_loop(self):
        """Continuous polling loop generator.

        Yields:
            Tuple of (metrics, changed) on each poll interval
        """
        while True:
            yield await self.poll()
            await asyncio.sleep(self._poll_interval)


def detect_ticker_changes(
    current: dict[str, TickerAggregate],
    previous: dict[str, TickerAggregate],
) -> set[str]:
    """Detect which tickers have changed between two polling snapshots.

    A ticker is considered changed if:
    - It is new (present in current but not previous)
    - It disappeared (present in previous but not current)
    - Its score, label, confidence, or count changed

    Args:
        current: Current per-ticker aggregates
        previous: Previous per-ticker aggregates

    Returns:
        Set of ticker symbols that changed
    """
    changed: set[str] = set()

    # New or modified tickers
    for ticker, agg in current.items():
        if ticker not in previous:
            changed.add(ticker)
        else:
            prev = previous[ticker]
            if (
                agg.score != prev.score
                or agg.label != prev.label
                or agg.confidence != prev.confidence
                or agg.count != prev.count
            ):
                changed.add(ticker)

    # Disappeared tickers
    for ticker in previous:
        if ticker not in current:
            changed.add(ticker)

    return changed


# Global polling service instance (lazy initialization)
_polling_service: PollingService | None = None


def get_polling_service() -> PollingService:
    """Get or create the global polling service instance.

    Uses lazy initialization to defer creation until SENTIMENTS_TABLE
    environment variable is available (at Lambda runtime, not import time).
    """
    global _polling_service
    if _polling_service is None:
        _polling_service = PollingService()
    return _polling_service


# Backwards compatibility alias - prefer get_polling_service()
polling_service = None  # type: ignore[assignment]

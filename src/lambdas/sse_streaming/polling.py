"""DynamoDB polling service for SSE streaming Lambda.

Polls DynamoDB at configurable intervals to detect new sentiment data.
Per FR-015: Poll at 5-second intervals (configurable via SSE_POLL_INTERVAL).
"""

import asyncio
import logging
import os
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError
from models import MetricsEventData

logger = logging.getLogger(__name__)


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
                       Defaults to DYNAMODB_TABLE env var.
            poll_interval: Poll interval in seconds.
                          Defaults to SSE_POLL_INTERVAL env var or 5.

        Raises:
            ValueError: If DYNAMODB_TABLE env var is not set and no table_name provided.
        """
        self._table_name = table_name or os.environ.get("DYNAMODB_TABLE")
        if not self._table_name:
            raise ValueError(
                "DYNAMODB_TABLE environment variable is required "
                "(no fallback - Amendment 1.15)"
            )
        self._poll_interval = poll_interval or int(
            os.environ.get("SSE_POLL_INTERVAL", "5")
        )
        self._table = None  # Lazy initialization
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

            ticker = item.get("ticker")
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

    async def poll(self) -> tuple[MetricsEventData, bool]:
        """Poll DynamoDB and return current metrics.

        Uses by_sentiment GSI queries for O(result) performance.
        (502-gsi-query-optimization: Replaced scan with GSI queries)

        Returns:
            Tuple of (metrics, changed) where changed indicates if
            metrics are different from last poll.
        """
        try:
            # Run DynamoDB GSI queries in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self._query_all_sentiments)

            items = response.get("Items", [])
            metrics = self._aggregate_metrics(items)

            changed = self._metrics_changed(self._last_metrics, metrics)
            self._last_metrics = metrics

            logger.debug(
                "DynamoDB poll complete",
                extra={
                    "total_items": metrics.total,
                    "changed": changed,
                },
            )

            return metrics, changed

        except ClientError as e:
            logger.error(
                "DynamoDB poll failed",
                extra={"error": str(e)},
                exc_info=True,
            )
            # Return last known metrics if available
            if self._last_metrics:
                return self._last_metrics, False
            # Return empty metrics on first poll failure
            return MetricsEventData(total=0, positive=0, neutral=0, negative=0), False

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


# Global polling service instance (lazy initialization)
_polling_service: PollingService | None = None


def get_polling_service() -> PollingService:
    """Get or create the global polling service instance.

    Uses lazy initialization to defer creation until DYNAMODB_TABLE
    environment variable is available (at Lambda runtime, not import time).
    """
    global _polling_service
    if _polling_service is None:
        _polling_service = PollingService()
    return _polling_service


# Backwards compatibility alias - prefer get_polling_service()
polling_service = None  # type: ignore[assignment]

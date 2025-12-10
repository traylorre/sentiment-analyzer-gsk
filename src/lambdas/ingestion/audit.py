"""CollectionEvent persistence for audit trail (T052).

Provides DynamoDB persistence for collection events to support
operational visibility and audit requirements per US4.

Architecture:
    audit.py --> boto3 DynamoDB --> DynamoDB Table
"""

import logging
from typing import Any

from botocore.exceptions import ClientError

from src.lambdas.shared.models.collection_event import CollectionEvent

logger = logging.getLogger(__name__)


class CollectionEventRepository:
    """Repository for persisting CollectionEvent audit records.

    Stores collection events in DynamoDB for operational visibility and
    historical analysis.

    Usage:
        repo = CollectionEventRepository(table)
        event = CollectionEvent(...)
        repo.save(event)
    """

    def __init__(self, table: Any) -> None:
        """Initialize repository with DynamoDB table.

        Args:
            table: DynamoDB Table resource
        """
        self._table = table

    def save(self, event: CollectionEvent) -> bool:
        """Persist a collection event to DynamoDB.

        Args:
            event: CollectionEvent to persist

        Returns:
            True if saved successfully, False on error
        """
        try:
            item = event.to_dynamodb_item()
            self._table.put_item(Item=item)

            logger.info(
                "Saved collection event",
                extra={
                    "event_id": event.event_id[:8],
                    "status": event.status,
                    "source": event.source_used,
                    "items_stored": event.items_stored,
                },
            )
            return True

        except ClientError as e:
            logger.error(
                "Failed to save collection event",
                extra={
                    "event_id": event.event_id[:8],
                    "error": str(e),
                },
            )
            return False

    def get_by_date(
        self,
        date_str: str,
        limit: int = 100,
    ) -> list[CollectionEvent]:
        """Get collection events for a specific date.

        Args:
            date_str: Date in YYYY-MM-DD format
            limit: Maximum events to return

        Returns:
            List of CollectionEvent objects
        """
        try:
            response = self._table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={
                    ":pk": f"COLLECTION#{date_str}",
                },
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )

            events = []
            for item in response.get("Items", []):
                try:
                    event = CollectionEvent.from_dynamodb_item(item)
                    events.append(event)
                except Exception as e:
                    logger.warning(
                        "Failed to parse collection event",
                        extra={"error": str(e), "item_pk": item.get("PK")},
                    )

            return events

        except ClientError as e:
            logger.error(
                "Failed to query collection events",
                extra={"date": date_str, "error": str(e)},
            )
            return []

    def get_recent_failures(
        self,
        date_str: str,
        limit: int = 10,
    ) -> list[CollectionEvent]:
        """Get recent failed collection events.

        Args:
            date_str: Date in YYYY-MM-DD format
            limit: Maximum events to return

        Returns:
            List of failed CollectionEvent objects
        """
        try:
            response = self._table.query(
                KeyConditionExpression="PK = :pk",
                FilterExpression="status = :failed",
                ExpressionAttributeValues={
                    ":pk": f"COLLECTION#{date_str}",
                    ":failed": "failed",
                },
                Limit=limit,
                ScanIndexForward=False,
            )

            events = []
            for item in response.get("Items", []):
                try:
                    event = CollectionEvent.from_dynamodb_item(item)
                    events.append(event)
                except Exception as e:
                    logger.warning(
                        "Failed to parse collection event",
                        extra={"error": str(e)},
                    )

            return events

        except ClientError as e:
            logger.error(
                "Failed to query failed collection events",
                extra={"date": date_str, "error": str(e)},
            )
            return []


def create_collection_event_repository(table: Any) -> CollectionEventRepository:
    """Factory function to create CollectionEventRepository.

    Args:
        table: DynamoDB Table resource

    Returns:
        Configured CollectionEventRepository instance
    """
    return CollectionEventRepository(table)

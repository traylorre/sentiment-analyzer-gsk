"""Downstream notification for new data events (T058).

Notifies dependent systems within 30 seconds of new data storage
per FR-004 and SC-005.

Architecture:
    storage.py --> notification.py --> boto3 SNS --> Downstream Systems
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class NewDataNotification:
    """Notification payload for new data availability.

    Attributes:
        items_stored: Number of new items stored
        source: Data source identifier (tiingo, finnhub)
        collection_timestamp: When collection occurred
        is_failover: Whether failover source was used
        items_duplicate: Number of duplicates skipped
    """

    items_stored: int
    source: str
    collection_timestamp: datetime
    is_failover: bool = False
    items_duplicate: int = 0

    def to_sns_message(self) -> str:
        """Format notification as SNS message body."""
        failover_text = " (failover)" if self.is_failover else ""
        return (
            f"New market data available.\n\n"
            f"Source: {self.source}{failover_text}\n"
            f"Items stored: {self.items_stored}\n"
            f"Duplicates skipped: {self.items_duplicate}\n"
            f"Collection timestamp: {self.collection_timestamp.isoformat()}\n\n"
            "Downstream systems should refresh their data cache."
        )

    def to_sns_subject(self) -> str:
        """Format notification as SNS subject line."""
        return f"[Ingestion] New Data: {self.items_stored} items from {self.source}"


class NotificationPublisher:
    """Publishes new data notifications to SNS.

    Usage:
        publisher = NotificationPublisher(topic_arn="arn:aws:sns:...")
        publisher.publish(NewDataNotification(...))
    """

    def __init__(
        self,
        topic_arn: str,
        sns_client: Any = None,
    ) -> None:
        """Initialize NotificationPublisher.

        Args:
            topic_arn: SNS topic ARN for notifications
            sns_client: Optional boto3 SNS client for testing
        """
        self._topic_arn = topic_arn
        self._sns = sns_client if sns_client is not None else boto3.client("sns")

    def publish(self, notification: NewDataNotification) -> str | None:
        """Publish new data notification to SNS.

        Args:
            notification: Notification data to publish

        Returns:
            SNS message ID if successful, None on error or skip
        """
        # Don't notify for zero items
        if notification.items_stored == 0:
            logger.info(
                "Skipping notification for zero items",
                extra={"source": notification.source},
            )
            return None

        try:
            response = self._sns.publish(
                TopicArn=self._topic_arn,
                Message=notification.to_sns_message(),
                Subject=notification.to_sns_subject(),
                MessageAttributes={
                    "Source": {
                        "DataType": "String",
                        "StringValue": notification.source,
                    },
                    "ItemCount": {
                        "DataType": "Number",
                        "StringValue": str(notification.items_stored),
                    },
                    "IsFailover": {
                        "DataType": "String",
                        "StringValue": str(notification.is_failover).lower(),
                    },
                },
            )

            message_id = response.get("MessageId")
            logger.info(
                "Published new data notification",
                extra={
                    "message_id": message_id,
                    "source": notification.source,
                    "items_stored": notification.items_stored,
                },
            )
            return message_id

        except ClientError as e:
            logger.error(
                "Failed to publish notification",
                extra={
                    "error": str(e),
                    "topic_arn": self._topic_arn,
                    "source": notification.source,
                },
            )
            return None


def create_notification_publisher(
    topic_arn: str,
    sns_client: Any = None,
) -> NotificationPublisher:
    """Factory function to create NotificationPublisher.

    Args:
        topic_arn: SNS topic ARN for notifications
        sns_client: Optional boto3 SNS client for testing

    Returns:
        Configured NotificationPublisher instance
    """
    return NotificationPublisher(
        topic_arn=topic_arn,
        sns_client=sns_client,
    )

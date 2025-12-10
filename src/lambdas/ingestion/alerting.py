"""Alert publishing for ingestion operations (US4).

Provides SNS-based alerting for operational visibility:
- Consecutive failure alerts (3 failures within 15 minutes)
- High latency alerts (>30 seconds)
- Alert deduplication with cooldown periods

Architecture:
    alerting.py --> boto3 SNS --> SNS Topic --> Email/PagerDuty/etc.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Default thresholds per spec clarifications
DEFAULT_FAILURE_THRESHOLD = 3  # Consecutive failures to trigger alert
DEFAULT_FAILURE_WINDOW_MINUTES = 15  # Window for consecutive failures
DEFAULT_LATENCY_THRESHOLD_MS = 30000  # 30 seconds (3x normal 10s timeout)
DEFAULT_ALERT_COOLDOWN_MINUTES = 5  # Don't repeat same alert within this window


class AlertType(Enum):
    """Types of alerts for message routing."""

    CONSECUTIVE_FAILURE = "consecutive_failure"
    HIGH_LATENCY = "high_latency"
    ALL_SOURCES_DOWN = "all_sources_down"
    RECOVERY = "recovery"


@dataclass
class ConsecutiveFailureAlert:
    """Alert data for consecutive collection failures.

    Attributes:
        failure_count: Number of consecutive failures
        window_minutes: Time window the failures occurred in
        first_failure_at: Timestamp of first failure
        last_failure_at: Timestamp of most recent failure
        sources_affected: List of sources that failed
        error_summary: Brief description of the error
    """

    failure_count: int
    window_minutes: int
    first_failure_at: datetime
    last_failure_at: datetime
    sources_affected: list[str]
    error_summary: str

    def to_sns_message(self) -> str:
        """Format alert as SNS message body."""
        sources = ", ".join(self.sources_affected)
        return (
            f"ALERT: {self.failure_count} consecutive failures detected in "
            f"{self.window_minutes} minutes.\n\n"
            f"Sources affected: {sources}\n"
            f"First failure: {self.first_failure_at.isoformat()}\n"
            f"Last failure: {self.last_failure_at.isoformat()}\n"
            f"Error: {self.error_summary}\n\n"
            "Action required: Check data source connectivity and API status."
        )

    def to_sns_subject(self) -> str:
        """Format alert as SNS subject line."""
        return (
            f"[ALERT] Ingestion: {self.failure_count} Consecutive Collection Failures"
        )


@dataclass
class LatencyAlert:
    """Alert data for high collection latency.

    Attributes:
        latency_ms: Actual latency in milliseconds
        threshold_ms: Threshold that was exceeded
        source: Source that experienced high latency
        timestamp: When the latency was measured
    """

    latency_ms: int
    threshold_ms: int
    source: str
    timestamp: datetime

    def to_sns_message(self) -> str:
        """Format alert as SNS message body."""
        latency_sec = self.latency_ms / 1000
        threshold_sec = self.threshold_ms / 1000
        return (
            f"ALERT: High collection latency detected.\n\n"
            f"Source: {self.source}\n"
            f"Latency: {latency_sec:.1f}s (threshold: {threshold_sec:.1f}s)\n"
            f"Timestamp: {self.timestamp.isoformat()}\n\n"
            "This may indicate network issues or source API degradation."
        )

    def to_sns_subject(self) -> str:
        """Format alert as SNS subject line."""
        latency_sec = self.latency_ms / 1000
        return (
            f"[ALERT] Ingestion: High Latency ({latency_sec:.1f}s) from {self.source}"
        )

    def percentage_over_threshold(self) -> float:
        """Calculate how far over threshold the latency is."""
        if self.threshold_ms == 0:
            return 0.0
        return ((self.latency_ms - self.threshold_ms) / self.threshold_ms) * 100


class AlertPublisher:
    """Publishes alerts to SNS with deduplication.

    Usage:
        publisher = AlertPublisher(topic_arn="arn:aws:sns:...")
        if publisher.should_alert(failure_count=3, window_minutes=15):
            publisher.publish_failure_alert(alert)
    """

    def __init__(
        self,
        topic_arn: str,
        sns_client: Any = None,
        alert_cooldown_minutes: int = DEFAULT_ALERT_COOLDOWN_MINUTES,
        latency_threshold_ms: int = DEFAULT_LATENCY_THRESHOLD_MS,
    ) -> None:
        """Initialize AlertPublisher.

        Args:
            topic_arn: SNS topic ARN for alerts
            sns_client: Optional boto3 SNS client for testing
            alert_cooldown_minutes: Cooldown between duplicate alerts
            latency_threshold_ms: Latency threshold for alerts
        """
        self._topic_arn = topic_arn
        self._sns = sns_client if sns_client is not None else boto3.client("sns")
        self._alert_cooldown_minutes = alert_cooldown_minutes
        self._latency_threshold_ms = latency_threshold_ms
        self._last_alert_time: datetime | None = None
        self._last_latency_alert_by_source: dict[str, datetime] = {}

    def should_alert(self, failure_count: int, window_minutes: int) -> bool:
        """Check if failure threshold is met for alerting.

        Args:
            failure_count: Number of consecutive failures
            window_minutes: Time window the failures occurred in

        Returns:
            True if alert should be sent
        """
        # Must have at least 3 failures
        if failure_count < DEFAULT_FAILURE_THRESHOLD:
            return False

        # Must be within 15-minute window
        if window_minutes > DEFAULT_FAILURE_WINDOW_MINUTES:
            return False

        return True

    def should_alert_latency(self, latency_ms: int, threshold_ms: int) -> bool:
        """Check if latency threshold is exceeded.

        Args:
            latency_ms: Actual latency in milliseconds
            threshold_ms: Threshold to compare against

        Returns:
            True if latency exceeds threshold
        """
        return latency_ms > threshold_ms

    def publish_failure_alert(self, alert: ConsecutiveFailureAlert) -> None:
        """Publish consecutive failure alert to SNS.

        Args:
            alert: Alert data to publish
        """
        # Check cooldown
        now = datetime.now(UTC)
        if self._last_alert_time is not None:
            elapsed = now - self._last_alert_time
            if elapsed < timedelta(minutes=self._alert_cooldown_minutes):
                logger.info(
                    "Skipping alert due to cooldown",
                    extra={
                        "last_alert": self._last_alert_time.isoformat(),
                        "cooldown_minutes": self._alert_cooldown_minutes,
                    },
                )
                return

        try:
            self._sns.publish(
                TopicArn=self._topic_arn,
                Message=alert.to_sns_message(),
                Subject=alert.to_sns_subject(),
                MessageAttributes={
                    "AlertType": {
                        "DataType": "String",
                        "StringValue": AlertType.CONSECUTIVE_FAILURE.value,
                    },
                    "FailureCount": {
                        "DataType": "Number",
                        "StringValue": str(alert.failure_count),
                    },
                },
            )
            self._last_alert_time = now
            logger.info(
                "Published failure alert",
                extra={
                    "failure_count": alert.failure_count,
                    "sources": alert.sources_affected,
                },
            )
        except ClientError as e:
            logger.error(
                "Failed to publish failure alert",
                extra={"error": str(e), "topic_arn": self._topic_arn},
            )

    def publish_latency_alert(self, alert: LatencyAlert) -> None:
        """Publish high latency alert to SNS.

        Args:
            alert: Latency alert data to publish
        """
        # Check per-source cooldown
        now = datetime.now(UTC)
        last_alert = self._last_latency_alert_by_source.get(alert.source)
        if last_alert is not None:
            elapsed = now - last_alert
            if elapsed < timedelta(minutes=self._alert_cooldown_minutes):
                logger.info(
                    "Skipping latency alert due to cooldown",
                    extra={
                        "source": alert.source,
                        "last_alert": last_alert.isoformat(),
                    },
                )
                return

        try:
            self._sns.publish(
                TopicArn=self._topic_arn,
                Message=alert.to_sns_message(),
                Subject=alert.to_sns_subject(),
                MessageAttributes={
                    "AlertType": {
                        "DataType": "String",
                        "StringValue": AlertType.HIGH_LATENCY.value,
                    },
                    "Source": {
                        "DataType": "String",
                        "StringValue": alert.source,
                    },
                    "LatencyMs": {
                        "DataType": "Number",
                        "StringValue": str(alert.latency_ms),
                    },
                },
            )
            self._last_latency_alert_by_source[alert.source] = now
            logger.info(
                "Published latency alert",
                extra={
                    "source": alert.source,
                    "latency_ms": alert.latency_ms,
                    "threshold_ms": alert.threshold_ms,
                },
            )
        except ClientError as e:
            logger.error(
                "Failed to publish latency alert",
                extra={"error": str(e), "topic_arn": self._topic_arn},
            )


def create_alert_publisher(
    topic_arn: str,
    sns_client: Any = None,
    alert_cooldown_minutes: int = DEFAULT_ALERT_COOLDOWN_MINUTES,
    latency_threshold_ms: int = DEFAULT_LATENCY_THRESHOLD_MS,
) -> AlertPublisher:
    """Factory function to create AlertPublisher.

    Args:
        topic_arn: SNS topic ARN for alerts
        sns_client: Optional boto3 SNS client for testing
        alert_cooldown_minutes: Cooldown between duplicate alerts
        latency_threshold_ms: Latency threshold for alerts

    Returns:
        Configured AlertPublisher instance
    """
    return AlertPublisher(
        topic_arn=topic_arn,
        sns_client=sns_client,
        alert_cooldown_minutes=alert_cooldown_minutes,
        latency_threshold_ms=latency_threshold_ms,
    )

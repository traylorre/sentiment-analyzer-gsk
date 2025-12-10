"""CloudWatch metrics for ingestion operations.

Provides structured metric publishing for operational visibility:
- Failover events (count, duration)
- Collection metrics (success rate, latency)
- Data quality metrics (duplicate rate)

Architecture:
    metrics.py --> boto3 CloudWatch --> CloudWatch Metrics
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# CloudWatch namespace for ingestion metrics
METRICS_NAMESPACE = "SentimentAnalyzer/Ingestion"

# Metric names
METRIC_FAILOVER_COUNT = "FailoverCount"
METRIC_FAILOVER_DURATION = "FailoverDurationSeconds"
METRIC_COLLECTION_SUCCESS = "CollectionSuccess"
METRIC_COLLECTION_FAILURE = "CollectionFailure"
METRIC_COLLECTION_LATENCY = "CollectionLatencyMs"
METRIC_ITEMS_COLLECTED = "ItemsCollected"
METRIC_ITEMS_DUPLICATE = "ItemsDuplicate"
METRIC_DUPLICATE_RATE = "DuplicateRate"
METRIC_PRIMARY_RECOVERY_ATTEMPT = "PrimaryRecoveryAttempt"
METRIC_PRIMARY_RECOVERY_SUCCESS = "PrimaryRecoverySuccess"
METRIC_HIGH_LATENCY_ALERT = "HighLatencyAlert"
METRIC_COLLECTION_SUCCESS_RATE = "CollectionSuccessRate"
METRIC_NOTIFICATION_LATENCY = "NotificationLatencyMs"

# Default latency threshold (30s = 3x normal 10s timeout per US4 spec)
DEFAULT_LATENCY_THRESHOLD_MS = 30000
# Notification SLA: 30 seconds per FR-004/SC-005
DEFAULT_NOTIFICATION_SLA_MS = 30000


@dataclass
class FailoverMetrics:
    """Metrics for a failover event.

    Attributes:
        source_used: Which source provided data after failover
        failover_duration_seconds: How long we were in failover before recovery
        primary_error: Reason for failover
        was_recovery_attempt: Whether this was a recovery attempt to primary
    """

    source_used: Literal["tiingo", "finnhub"]
    failover_duration_seconds: float
    primary_error: str | None = None
    was_recovery_attempt: bool = False


@dataclass
class CollectionMetrics:
    """Metrics for a collection operation.

    Attributes:
        source: Data source used
        success: Whether collection succeeded
        latency_ms: Collection duration in milliseconds
        items_collected: Number of items fetched
        items_duplicate: Number of duplicates skipped
        is_failover: Whether failover was used
    """

    source: Literal["tiingo", "finnhub"]
    success: bool
    latency_ms: int
    items_collected: int = 0
    items_duplicate: int = 0
    is_failover: bool = False


class MetricsPublisher:
    """Publishes metrics to CloudWatch.

    Usage:
        publisher = MetricsPublisher()
        publisher.record_failover(FailoverMetrics(...))
        publisher.record_collection(CollectionMetrics(...))
    """

    def __init__(
        self,
        namespace: str = METRICS_NAMESPACE,
        cloudwatch_client: Any = None,
    ):
        """Initialize metrics publisher.

        Args:
            namespace: CloudWatch metrics namespace
            cloudwatch_client: Optional boto3 CloudWatch client for testing
        """
        self._namespace = namespace
        self._cloudwatch = cloudwatch_client or boto3.client("cloudwatch")

    def record_failover(self, metrics: FailoverMetrics) -> None:
        """Record failover event metrics.

        Args:
            metrics: Failover metrics to record
        """
        timestamp = datetime.now(UTC)
        metric_data = [
            {
                "MetricName": METRIC_FAILOVER_COUNT,
                "Timestamp": timestamp,
                "Value": 1,
                "Unit": "Count",
                "Dimensions": [
                    {"Name": "Source", "Value": metrics.source_used},
                ],
            },
        ]

        # Add duration if available
        if metrics.failover_duration_seconds > 0:
            metric_data.append(
                {
                    "MetricName": METRIC_FAILOVER_DURATION,
                    "Timestamp": timestamp,
                    "Value": metrics.failover_duration_seconds,
                    "Unit": "Seconds",
                    "Dimensions": [
                        {"Name": "Source", "Value": metrics.source_used},
                    ],
                }
            )

        # Track recovery attempts
        if metrics.was_recovery_attempt:
            metric_data.append(
                {
                    "MetricName": METRIC_PRIMARY_RECOVERY_ATTEMPT,
                    "Timestamp": timestamp,
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [],
                }
            )

        self._publish_metrics(metric_data)

        logger.info(
            "Recorded failover metrics",
            extra={
                "source": metrics.source_used,
                "duration_seconds": metrics.failover_duration_seconds,
                "recovery_attempt": metrics.was_recovery_attempt,
            },
        )

    def record_recovery_success(self) -> None:
        """Record successful primary recovery."""
        timestamp = datetime.now(UTC)
        metric_data = [
            {
                "MetricName": METRIC_PRIMARY_RECOVERY_SUCCESS,
                "Timestamp": timestamp,
                "Value": 1,
                "Unit": "Count",
                "Dimensions": [],
            },
        ]

        self._publish_metrics(metric_data)
        logger.info("Recorded primary recovery success")

    def record_collection(self, metrics: CollectionMetrics) -> None:
        """Record collection operation metrics.

        Args:
            metrics: Collection metrics to record
        """
        timestamp = datetime.now(UTC)
        dimensions = [
            {"Name": "Source", "Value": metrics.source},
            {"Name": "IsFailover", "Value": str(metrics.is_failover).lower()},
        ]

        metric_data = [
            {
                "MetricName": METRIC_COLLECTION_SUCCESS
                if metrics.success
                else METRIC_COLLECTION_FAILURE,
                "Timestamp": timestamp,
                "Value": 1,
                "Unit": "Count",
                "Dimensions": dimensions,
            },
            {
                "MetricName": METRIC_COLLECTION_LATENCY,
                "Timestamp": timestamp,
                "Value": metrics.latency_ms,
                "Unit": "Milliseconds",
                "Dimensions": dimensions,
            },
        ]

        if metrics.items_collected > 0:
            metric_data.append(
                {
                    "MetricName": METRIC_ITEMS_COLLECTED,
                    "Timestamp": timestamp,
                    "Value": metrics.items_collected,
                    "Unit": "Count",
                    "Dimensions": dimensions,
                }
            )

        if metrics.items_duplicate > 0:
            metric_data.append(
                {
                    "MetricName": METRIC_ITEMS_DUPLICATE,
                    "Timestamp": timestamp,
                    "Value": metrics.items_duplicate,
                    "Unit": "Count",
                    "Dimensions": dimensions,
                }
            )

            # Calculate duplicate rate
            total = metrics.items_collected + metrics.items_duplicate
            if total > 0:
                duplicate_rate = metrics.items_duplicate / total
                metric_data.append(
                    {
                        "MetricName": METRIC_DUPLICATE_RATE,
                        "Timestamp": timestamp,
                        "Value": duplicate_rate,
                        "Unit": "None",
                        "Dimensions": dimensions,
                    }
                )

        self._publish_metrics(metric_data)

        logger.info(
            "Recorded collection metrics",
            extra={
                "source": metrics.source,
                "success": metrics.success,
                "latency_ms": metrics.latency_ms,
                "items": metrics.items_collected,
                "duplicates": metrics.items_duplicate,
            },
        )

    def check_latency_threshold(
        self,
        latency_ms: int,
        source: str,
        threshold_ms: int = DEFAULT_LATENCY_THRESHOLD_MS,
    ) -> bool:
        """Check if latency exceeds threshold and record metric if so.

        US4 implementation (T051): Monitors collection latency against 30s
        threshold (3x normal 10s timeout) and records CloudWatch metric when
        exceeded.

        Args:
            latency_ms: Actual latency in milliseconds
            source: Data source that experienced the latency
            threshold_ms: Threshold to compare against (default 30000ms)

        Returns:
            True if latency exceeded threshold (alert condition)
        """
        if latency_ms <= threshold_ms:
            return False

        # Record high latency alert metric
        timestamp = datetime.now(UTC)
        metric_data = [
            {
                "MetricName": METRIC_HIGH_LATENCY_ALERT,
                "Timestamp": timestamp,
                "Value": 1,
                "Unit": "Count",
                "Dimensions": [
                    {"Name": "Source", "Value": source},
                ],
            },
            {
                "MetricName": METRIC_COLLECTION_LATENCY,
                "Timestamp": timestamp,
                "Value": latency_ms,
                "Unit": "Milliseconds",
                "Dimensions": [
                    {"Name": "Source", "Value": source},
                    {"Name": "ThresholdExceeded", "Value": "true"},
                ],
            },
        ]

        self._publish_metrics(metric_data)

        logger.warning(
            "High latency detected",
            extra={
                "source": source,
                "latency_ms": latency_ms,
                "threshold_ms": threshold_ms,
                "over_threshold_pct": round(
                    (latency_ms - threshold_ms) / threshold_ms * 100, 1
                ),
            },
        )

        return True

    def record_success_rate(
        self,
        success_count: int,
        failure_count: int,
        source: str | None = None,
    ) -> None:
        """Record collection success rate metric.

        US4 implementation (T053): Publishes collection success rate as a
        percentage metric (0.0-1.0) for operational monitoring.

        The spec requires 99.5% collection success rate target.

        Args:
            success_count: Number of successful collections
            failure_count: Number of failed collections
            source: Optional source dimension (tiingo, finnhub)
        """
        total = success_count + failure_count
        if total == 0:
            return

        success_rate = success_count / total
        timestamp = datetime.now(UTC)

        dimensions = []
        if source:
            dimensions.append({"Name": "Source", "Value": source})

        metric_data = [
            {
                "MetricName": METRIC_COLLECTION_SUCCESS_RATE,
                "Timestamp": timestamp,
                "Value": success_rate,
                "Unit": "None",
                "Dimensions": dimensions,
            },
        ]

        self._publish_metrics(metric_data)

        logger.info(
            "Recorded collection success rate",
            extra={
                "success_rate": round(success_rate * 100, 2),
                "success_count": success_count,
                "failure_count": failure_count,
                "source": source or "all",
            },
        )

    def record_notification_latency(
        self,
        latency_ms: int,
        source: str | None = None,
        sla_ms: int = DEFAULT_NOTIFICATION_SLA_MS,
    ) -> bool:
        """Record notification latency metric.

        T061 implementation: Publishes notification latency to CloudWatch
        for monitoring the 30s SLA per FR-004/SC-005.

        Args:
            latency_ms: Time from storage completion to notification publish
            source: Optional source dimension (tiingo, finnhub)
            sla_ms: SLA threshold in milliseconds (default 30000ms)

        Returns:
            True if SLA was met, False if exceeded
        """
        timestamp = datetime.now(UTC)
        sla_met = latency_ms <= sla_ms

        dimensions = []
        if source:
            dimensions.append({"Name": "Source", "Value": source})
        dimensions.append({"Name": "SLAMet", "Value": str(sla_met).lower()})

        metric_data = [
            {
                "MetricName": METRIC_NOTIFICATION_LATENCY,
                "Timestamp": timestamp,
                "Value": latency_ms,
                "Unit": "Milliseconds",
                "Dimensions": dimensions,
            },
        ]

        self._publish_metrics(metric_data)

        log_level = logger.info if sla_met else logger.warning
        log_level(
            "Recorded notification latency",
            extra={
                "latency_ms": latency_ms,
                "sla_ms": sla_ms,
                "sla_met": sla_met,
                "source": source or "all",
            },
        )

        return sla_met

    def _publish_metrics(self, metric_data: list[dict]) -> None:
        """Publish metrics to CloudWatch.

        Args:
            metric_data: List of metric data dictionaries
        """
        try:
            self._cloudwatch.put_metric_data(
                Namespace=self._namespace,
                MetricData=metric_data,
            )
        except ClientError as e:
            logger.error(
                "Failed to publish metrics to CloudWatch",
                extra={"error": str(e), "metric_count": len(metric_data)},
            )


def create_metrics_publisher(
    cloudwatch_client: Any = None,
) -> MetricsPublisher:
    """Factory function to create MetricsPublisher.

    Args:
        cloudwatch_client: Optional boto3 CloudWatch client for testing

    Returns:
        Configured MetricsPublisher instance
    """
    return MetricsPublisher(cloudwatch_client=cloudwatch_client)

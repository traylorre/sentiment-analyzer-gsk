"""CloudWatch metrics for ingestion operations.

Provides structured metric publishing for operational visibility:
- Failover events (count, duration)
- Collection metrics (success rate, latency)
- Data quality metrics (duplicate rate)
- Cross-source collision metrics (Feature 1010)

Architecture:
    metrics.py --> boto3 CloudWatch --> CloudWatch Metrics
"""

import logging
import time
from collections import defaultdict
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


class IngestionMetrics:
    """Tracks cross-source ingestion and collision metrics.

    Feature 1010: Tracks deduplication metrics for parallel ingestion.

    Metrics tracked:
    - articles_fetched: Per-source fetch counts
    - articles_stored: Unique articles stored after dedup
    - collisions_detected: Duplicate articles found across sources
    - collision_rate: collisions / total_fetched
    - duration_ms: Total processing time

    Thresholds (per SC-008):
    - collision_rate > 0.40: Alert (too high, possible duplicate data)
    - collision_rate < 0.05: Alert (too low, possible source mismatch)
    - Expected range: 15-25% for typical financial news
    """

    LOW_COLLISION_THRESHOLD = 0.05
    HIGH_COLLISION_THRESHOLD = 0.40

    def __init__(self) -> None:
        """Initialize metrics tracking."""
        self.articles_fetched: dict[str, int] = defaultdict(int)
        self.articles_stored: int = 0
        self.collisions_detected: int = 0
        self._start_time: float | None = None
        self._end_time: float | None = None

    def record_fetch(self, source: str, count: int) -> None:
        """Record articles fetched from a source.

        Args:
            source: Source name (tiingo or finnhub)
            count: Number of articles fetched
        """
        self.articles_fetched[source] += count

    def record_stored(self) -> None:
        """Record a new unique article stored."""
        self.articles_stored += 1

    def record_collision(self) -> None:
        """Record a duplicate article detected."""
        self.collisions_detected += 1

    def start_timing(self) -> None:
        """Start timing the ingestion run."""
        self._start_time = time.time()

    def stop_timing(self) -> None:
        """Stop timing the ingestion run."""
        self._end_time = time.time()

    @property
    def total_fetched(self) -> int:
        """Total articles fetched across all sources."""
        return sum(self.articles_fetched.values())

    @property
    def collision_rate(self) -> float:
        """Calculate collision rate.

        Returns:
            Collision rate as a fraction (0.0 to 1.0).
            Returns 0.0 if no articles fetched.
        """
        total = self.total_fetched
        if total == 0:
            return 0.0
        return self.collisions_detected / total

    @property
    def duration_ms(self) -> int:
        """Get processing duration in milliseconds."""
        if self._start_time is None or self._end_time is None:
            return 0
        return int((self._end_time - self._start_time) * 1000)

    def is_anomalous(self) -> bool:
        """Check if collision rate is outside normal range.

        Returns:
            True if collision rate is anomalous (< 5% or > 40%)
            and both sources were fetched.
        """
        # Zero rate is expected for single source or empty ingestion
        if self.total_fetched == 0:
            return False

        # Check if we have data from both sources
        has_both_sources = (
            self.articles_fetched.get("tiingo", 0) > 0
            and self.articles_fetched.get("finnhub", 0) > 0
        )

        if not has_both_sources:
            # Single source ingestion - zero collisions is expected
            return False

        rate = self.collision_rate
        return (
            rate < self.LOW_COLLISION_THRESHOLD or rate > self.HIGH_COLLISION_THRESHOLD
        )

    @property
    def anomaly_type(self) -> str | None:
        """Get the type of anomaly detected.

        Returns:
            "high_collision_rate", "low_collision_rate", or None
        """
        if not self.is_anomalous():
            return None

        rate = self.collision_rate
        if rate > self.HIGH_COLLISION_THRESHOLD:
            return "high_collision_rate"
        elif rate < self.LOW_COLLISION_THRESHOLD:
            return "low_collision_rate"
        return None

    def get_anomaly_message(self) -> str | None:
        """Get a descriptive message for the anomaly.

        Returns:
            Human-readable anomaly description or None if normal.
        """
        anomaly = self.anomaly_type
        rate_pct = self.collision_rate * 100

        if anomaly == "high_collision_rate":
            return (
                f"High collision rate detected: {rate_pct:.1f}% "
                f"(threshold: >{self.HIGH_COLLISION_THRESHOLD * 100:.0f}%). "
                "This may indicate duplicate data in sources."
            )
        elif anomaly == "low_collision_rate":
            return (
                f"Low collision rate detected: {rate_pct:.1f}% "
                f"(threshold: <{self.LOW_COLLISION_THRESHOLD * 100:.0f}%). "
                "This may indicate source data mismatch or API issues."
            )
        return None

    def reset(self) -> None:
        """Reset all metrics to initial state."""
        self.articles_fetched = defaultdict(int)
        self.articles_stored = 0
        self.collisions_detected = 0
        self._start_time = None
        self._end_time = None

    def to_dict(self) -> dict[str, Any]:
        """Export metrics as dictionary for logging.

        Returns:
            Dictionary containing all metric values.
        """
        return {
            "articles_fetched": dict(self.articles_fetched),
            "total_fetched": self.total_fetched,
            "articles_stored": self.articles_stored,
            "collisions_detected": self.collisions_detected,
            "collision_rate": self.collision_rate,
            "duration_ms": self.duration_ms,
            "is_anomalous": self.is_anomalous(),
            "anomaly_type": self.anomaly_type,
        }

    def publish_to_cloudwatch(self, namespace: str = METRICS_NAMESPACE) -> None:
        """Publish metrics to CloudWatch.

        Args:
            namespace: CloudWatch namespace for metrics
        """
        try:
            client = boto3.client("cloudwatch")

            metric_data = [
                {
                    "MetricName": "TiingoArticlesFetched",
                    "Value": self.articles_fetched.get("tiingo", 0),
                    "Unit": "Count",
                },
                {
                    "MetricName": "FinnhubArticlesFetched",
                    "Value": self.articles_fetched.get("finnhub", 0),
                    "Unit": "Count",
                },
                {
                    "MetricName": "ArticlesStored",
                    "Value": self.articles_stored,
                    "Unit": "Count",
                },
                {
                    "MetricName": "CollisionsDetected",
                    "Value": self.collisions_detected,
                    "Unit": "Count",
                },
                {
                    "MetricName": "CollisionRate",
                    "Value": self.collision_rate,
                    "Unit": "None",
                },
                {
                    "MetricName": "AnomalousCollisionRate",
                    "Value": 1 if self.is_anomalous() else 0,
                    "Unit": "None",
                },
            ]

            if self.duration_ms > 0:
                metric_data.append(
                    {
                        "MetricName": "IngestionDurationMs",
                        "Value": self.duration_ms,
                        "Unit": "Milliseconds",
                    }
                )

            client.put_metric_data(Namespace=namespace, MetricData=metric_data)

            logger.info(
                "Published ingestion metrics to CloudWatch",
                extra={
                    "namespace": namespace,
                    "metrics": self.to_dict(),
                },
            )

        except Exception as e:
            logger.error(f"Failed to publish CloudWatch metrics: {e}")

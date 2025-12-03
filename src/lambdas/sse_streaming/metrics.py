"""CloudWatch custom metrics helper for SSE streaming Lambda.

Emits metrics for connection count, event throughput, and latency.
Per FR-017: Custom CloudWatch metrics required.
"""

import logging
import os
import time
from collections.abc import Generator
from contextlib import contextmanager

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Metric namespace
NAMESPACE = "SentimentAnalyzer/SSE"


class MetricsEmitter:
    """Emits custom CloudWatch metrics for SSE Lambda.

    Metrics emitted:
    - ConnectionCount: Current active SSE connections
    - EventsSent: Number of SSE events sent
    - EventLatencyMs: Time to process and send events
    - ConnectionAcquireFailures: Connection limit rejections
    """

    def __init__(self, environment: str | None = None):
        """Initialize metrics emitter.

        Args:
            environment: Environment name (dev/preprod/prod).
                        Defaults to ENVIRONMENT env var.
        """
        self._environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self._cloudwatch = None

    @property
    def cloudwatch(self):
        """Lazy-load CloudWatch client."""
        if self._cloudwatch is None:
            self._cloudwatch = boto3.client("cloudwatch")
        return self._cloudwatch

    def _put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict | None = None,
    ) -> None:
        """Put a single metric to CloudWatch.

        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: CloudWatch unit (Count, Milliseconds, etc.)
            dimensions: Additional dimensions beyond Environment
        """
        try:
            metric_dimensions = [
                {"Name": "Environment", "Value": self._environment},
            ]
            if dimensions:
                metric_dimensions.extend(
                    [{"Name": k, "Value": str(v)} for k, v in dimensions.items()]
                )

            self.cloudwatch.put_metric_data(
                Namespace=NAMESPACE,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Value": value,
                        "Unit": unit,
                        "Dimensions": metric_dimensions,
                    }
                ],
            )
            logger.debug(
                "Metric emitted",
                extra={"metric": metric_name, "value": value, "unit": unit},
            )
        except ClientError as e:
            logger.warning(
                "Failed to emit CloudWatch metric",
                extra={"metric": metric_name, "error": str(e)},
            )

    def emit_connection_count(self, count: int) -> None:
        """Emit current connection count metric.

        Args:
            count: Number of active connections
        """
        self._put_metric("ConnectionCount", float(count))

    def emit_events_sent(self, count: int = 1, event_type: str = "all") -> None:
        """Emit events sent counter.

        Args:
            count: Number of events sent
            event_type: Type of event (heartbeat/metrics/sentiment_update/all)
        """
        self._put_metric(
            "EventsSent", float(count), dimensions={"EventType": event_type}
        )

    def emit_event_latency(self, latency_ms: float) -> None:
        """Emit event processing latency.

        Args:
            latency_ms: Latency in milliseconds
        """
        self._put_metric("EventLatencyMs", latency_ms, unit="Milliseconds")

    def emit_connection_acquire_failure(self) -> None:
        """Emit connection acquire failure (limit reached)."""
        self._put_metric("ConnectionAcquireFailures", 1.0)

    def emit_poll_duration(self, duration_ms: float) -> None:
        """Emit DynamoDB poll duration.

        Args:
            duration_ms: Poll duration in milliseconds
        """
        self._put_metric("PollDurationMs", duration_ms, unit="Milliseconds")

    @contextmanager
    def measure_latency(self) -> Generator[None, None, None]:
        """Context manager to measure and emit latency.

        Example:
            with metrics.measure_latency():
                # do work
                pass
            # latency automatically emitted
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.emit_event_latency(elapsed_ms)


# Global metrics emitter instance
metrics_emitter = MetricsEmitter()

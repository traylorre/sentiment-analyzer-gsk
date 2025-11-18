"""
CloudWatch Metrics and Logging Utilities
========================================

Provides structured logging and CloudWatch metrics emission for all Lambdas.

For On-Call Engineers:
    Metrics emitted by this module:
    - ArticlesFetched: Raw count from NewsAPI
    - NewItemsIngested: After deduplication
    - DuplicatesSkipped: Dedup count
    - AnalysisCount: Items analyzed
    - InferenceLatencyMs: Model inference time

    CloudWatch Insights query for errors:
    ```
    fields @timestamp, @message
    | filter level = "ERROR"
    | filter correlation_id like /newsapi#/
    | sort @timestamp desc
    ```

    See ON_CALL_SOP.md for specific scenarios and commands.

For Developers:
    - Use log_structured() for all logging (JSON format for CloudWatch)
    - Use emit_metric() for CloudWatch custom metrics
    - Always include correlation_id in logs for tracing
    - Use get_correlation_id() to generate tracing IDs

Security Notes:
    - Never log secret values, only ARNs
    - Never log full article content (only snippets)
    - Correlation IDs are safe to log (contain only source_id prefix)
"""

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.config import Config

# Configure structured JSON logging
logger = logging.getLogger(__name__)

# CloudWatch client configuration
RETRY_CONFIG = Config(
    retries={
        "max_attempts": 3,
        "mode": "adaptive",
    },
    connect_timeout=5,
    read_timeout=10,
)

# Metric namespace
METRIC_NAMESPACE = "SentimentAnalyzer"


class StructuredLogger:
    """
    JSON structured logger for CloudWatch Logs Insights.

    Outputs logs in JSON format for easy querying in CloudWatch.

    Example output:
    {
        "timestamp": "2025-11-17T14:30:00.000Z",
        "level": "INFO",
        "message": "Item ingested",
        "source_id": "newsapi#abc123",
        "correlation_id": "newsapi#abc123-req-456"
    }
    """

    def __init__(self, name: str = __name__):
        self.logger = logging.getLogger(name)
        self._setup_handler()

    def _setup_handler(self):
        """Configure JSON handler if not already set."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(JsonFormatter())
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def debug(self, message: str, **kwargs):
        """Log debug message with structured data."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message with structured data."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with structured data."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message with structured data."""
        self._log(logging.ERROR, message, **kwargs)

    def _log(self, level: int, message: str, **kwargs):
        """Internal logging with extra fields."""
        # Add timestamp
        kwargs["timestamp"] = datetime.now(UTC).isoformat()

        self.logger.log(level, message, extra={"structured_data": kwargs})


class JsonFormatter(logging.Formatter):
    """
    Format log records as JSON for CloudWatch Logs Insights.

    On-Call Note:
        This format enables CloudWatch Insights queries like:
        fields @timestamp, message, source_id, error
        | filter level = "ERROR"
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add structured data if present
        if hasattr(record, "structured_data"):
            log_data.update(record.structured_data)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def get_cloudwatch_client(region_name: str | None = None) -> Any:
    """
    Get a CloudWatch client with retry configuration.

    Args:
        region_name: AWS region (defaults to AWS_DEFAULT_REGION)

    Returns:
        boto3 CloudWatch client
    """
    region = region_name or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    return boto3.client(
        "cloudwatch",
        region_name=region,
        config=RETRY_CONFIG,
    )


def emit_metric(
    name: str,
    value: float,
    unit: str = "Count",
    dimensions: dict[str, str] | None = None,
    region_name: str | None = None,
) -> None:
    """
    Emit a custom metric to CloudWatch.

    Args:
        name: Metric name (e.g., "ArticlesFetched")
        value: Metric value
        unit: CloudWatch unit (Count, Milliseconds, etc.)
        dimensions: Optional dimensions (e.g., {"Environment": "dev"})
        region_name: AWS region

    On-Call Note:
        Metrics appear in CloudWatch under namespace "SentimentAnalyzer".
        View with:
        aws cloudwatch get-metric-statistics \
          --namespace SentimentAnalyzer \
          --metric-name <name> \
          --start-time <time> --end-time <time> \
          --period 300 --statistics Sum
    """
    client = get_cloudwatch_client(region_name)

    # Build metric data
    metric_data = {
        "MetricName": name,
        "Value": value,
        "Unit": unit,
        "Timestamp": datetime.now(UTC),
    }

    # Add dimensions
    if dimensions:
        metric_data["Dimensions"] = [
            {"Name": k, "Value": v} for k, v in dimensions.items()
        ]

    # Add environment dimension by default
    environment = os.environ.get("ENVIRONMENT", "dev")
    if "Dimensions" not in metric_data:
        metric_data["Dimensions"] = []
    metric_data["Dimensions"].append({"Name": "Environment", "Value": environment})

    try:
        client.put_metric_data(
            Namespace=METRIC_NAMESPACE,
            MetricData=[metric_data],
        )
        logger.debug(
            f"Emitted metric {name}={value}",
            extra={"metric_name": name, "value": value, "unit": unit},
        )
    except Exception as e:
        # Log error but don't fail the Lambda
        logger.error(
            f"Failed to emit metric: {e}",
            extra={"metric_name": name, "error": str(e)},
        )


def emit_metrics_batch(
    metrics: list[dict[str, Any]],
    region_name: str | None = None,
) -> None:
    """
    Emit multiple metrics in a single API call.

    More efficient than multiple emit_metric() calls.

    Args:
        metrics: List of metric dicts with keys: name, value, unit, dimensions
        region_name: AWS region

    Example:
        >>> emit_metrics_batch([
        ...     {"name": "ArticlesFetched", "value": 100, "unit": "Count"},
        ...     {"name": "NewItemsIngested", "value": 80, "unit": "Count"},
        ... ])
    """
    if not metrics:
        return

    client = get_cloudwatch_client(region_name)
    environment = os.environ.get("ENVIRONMENT", "dev")

    metric_data_list = []
    for metric in metrics:
        data = {
            "MetricName": metric["name"],
            "Value": metric["value"],
            "Unit": metric.get("unit", "Count"),
            "Timestamp": datetime.now(UTC),
            "Dimensions": [{"Name": "Environment", "Value": environment}],
        }

        # Add custom dimensions
        if "dimensions" in metric and metric["dimensions"]:
            data["Dimensions"].extend(
                [{"Name": k, "Value": v} for k, v in metric["dimensions"].items()]
            )

        metric_data_list.append(data)

    try:
        # CloudWatch allows up to 1000 metrics per call
        for i in range(0, len(metric_data_list), 1000):
            batch = metric_data_list[i : i + 1000]
            client.put_metric_data(
                Namespace=METRIC_NAMESPACE,
                MetricData=batch,
            )

        logger.debug(f"Emitted {len(metrics)} metrics in batch")
    except Exception as e:
        logger.error(
            f"Failed to emit metric batch: {e}",
            extra={"count": len(metrics), "error": str(e)},
        )


def get_correlation_id(source_id: str, context: Any) -> str:
    """
    Generate a correlation ID for distributed tracing.

    Format: {source_id}-{lambda_request_id}

    Args:
        source_id: Article source_id
        context: Lambda context object (has aws_request_id)

    Returns:
        Correlation ID for logging

    On-Call Note:
        Use this ID to trace an item through all Lambdas:
        aws logs filter-log-events \
          --log-group-name /aws/lambda/dev-sentiment-ingestion \
          --filter-pattern "correlation_id newsapi#abc123-req-456"
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    return f"{source_id}-{request_id}"


def log_structured(
    level: str,
    message: str,
    **kwargs,
) -> None:
    """
    Log a structured message in JSON format.

    Convenience function for simple logging without creating a StructuredLogger.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: Log message
        **kwargs: Additional fields to include in log

    Example:
        >>> log_structured(
        ...     "INFO",
        ...     "Item ingested",
        ...     source_id="newsapi#abc123",
        ...     correlation_id="newsapi#abc123-req-456",
        ... )
    """
    log_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "message": message,
        **kwargs,
    }

    # Print as JSON (Lambda sends stdout to CloudWatch)
    print(json.dumps(log_data, default=str))


class Timer:
    """
    Context manager for timing code blocks.

    Automatically emits metric on exit.

    Example:
        >>> with Timer("InferenceLatencyMs"):
        ...     result = model.predict(text)
    """

    def __init__(
        self,
        metric_name: str,
        dimensions: dict[str, str] | None = None,
        emit: bool = True,
    ):
        self.metric_name = metric_name
        self.dimensions = dimensions
        self.emit = emit
        self.start_time: float = 0
        self.elapsed_ms: float = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.perf_counter() - self.start_time
        self.elapsed_ms = elapsed * 1000  # Convert to milliseconds

        if self.emit:
            emit_metric(
                self.metric_name,
                self.elapsed_ms,
                unit="Milliseconds",
                dimensions=self.dimensions,
            )

        return False  # Don't suppress exceptions


def create_logger(name: str) -> StructuredLogger:
    """
    Create a structured logger for a module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        StructuredLogger instance

    Example:
        >>> logger = create_logger(__name__)
        >>> logger.info("Processing started", item_count=10)
    """
    return StructuredLogger(name)

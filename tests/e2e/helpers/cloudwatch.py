# CloudWatch Helpers
#
# Utilities for querying CloudWatch Logs and Metrics during E2E tests.
# Used for observability validation (US11).

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import boto3


@dataclass
class LogEntry:
    """Represents a CloudWatch log entry."""

    timestamp: datetime
    message: str
    log_stream: str
    request_id: str | None = None


@dataclass
class MetricDataPoint:
    """Represents a CloudWatch metric data point."""

    timestamp: datetime
    value: float
    unit: str


def get_logs_client():
    """Get CloudWatch Logs client."""
    return boto3.client(
        "logs",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def get_cloudwatch_client():
    """Get CloudWatch metrics client."""
    return boto3.client(
        "cloudwatch",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


async def query_cloudwatch_logs(
    log_group: str,
    query: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    timeout_seconds: int = 30,
) -> list[LogEntry]:
    """Query CloudWatch Logs using Logs Insights.

    Args:
        log_group: Log group name (e.g., "/aws/lambda/dashboard-api")
        query: CloudWatch Logs Insights query string
        start_time: Query start time (default: 5 minutes ago)
        end_time: Query end time (default: now)
        timeout_seconds: Maximum time to wait for query results

    Returns:
        List of LogEntry objects matching the query

    Raises:
        TimeoutError: If query doesn't complete within timeout
    """
    client = get_logs_client()

    if start_time is None:
        start_time = datetime.now(UTC) - timedelta(minutes=5)
    if end_time is None:
        end_time = datetime.now(UTC)

    # Start the query
    response = client.start_query(
        logGroupName=log_group,
        startTime=int(start_time.timestamp()),
        endTime=int(end_time.timestamp()),
        queryString=query,
    )
    query_id = response["queryId"]

    # Poll for results
    start = time.time()
    while time.time() - start < timeout_seconds:
        result = client.get_query_results(queryId=query_id)

        if result["status"] == "Complete":
            entries = []
            for record in result.get("results", []):
                entry_data = {field["field"]: field["value"] for field in record}
                entries.append(
                    LogEntry(
                        timestamp=datetime.fromisoformat(
                            entry_data.get("@timestamp", "")
                        ),
                        message=entry_data.get("@message", ""),
                        log_stream=entry_data.get("@logStream", ""),
                        request_id=entry_data.get("@requestId"),
                    )
                )
            return entries

        if result["status"] in ("Failed", "Cancelled"):
            raise RuntimeError(f"Query failed with status: {result['status']}")

        await asyncio.sleep(1)

    raise TimeoutError(f"Query did not complete within {timeout_seconds} seconds")


async def query_logs_by_request_id(
    log_group: str,
    request_id: str,
    timeout_seconds: int = 30,
) -> list[LogEntry]:
    """Query CloudWatch Logs by request ID.

    Args:
        log_group: Log group name
        request_id: AWS request ID to search for
        timeout_seconds: Maximum time to wait

    Returns:
        List of log entries for the request
    """
    query = f'fields @timestamp, @message, @requestId | filter @requestId = "{request_id}" | sort @timestamp asc'
    return await query_cloudwatch_logs(
        log_group, query, timeout_seconds=timeout_seconds
    )


async def get_cloudwatch_metrics(
    namespace: str,
    metric_name: str,
    dimensions: list[dict[str, str]],
    stat: str = "Sum",
    period: int = 60,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[MetricDataPoint]:
    """Get CloudWatch metric data points.

    Args:
        namespace: Metric namespace (e.g., "SentimentAnalyzer")
        metric_name: Metric name (e.g., "APIRequests")
        dimensions: List of dimension dicts with "Name" and "Value"
        stat: Statistic to retrieve (Sum, Average, Maximum, etc.)
        period: Period in seconds for each data point
        start_time: Query start time (default: 5 minutes ago)
        end_time: Query end time (default: now)

    Returns:
        List of MetricDataPoint objects
    """
    client = get_cloudwatch_client()

    if start_time is None:
        start_time = datetime.now(UTC) - timedelta(minutes=5)
    if end_time is None:
        end_time = datetime.now(UTC)

    response = client.get_metric_data(
        MetricDataQueries=[
            {
                "Id": "m1",
                "MetricStat": {
                    "Metric": {
                        "Namespace": namespace,
                        "MetricName": metric_name,
                        "Dimensions": dimensions,
                    },
                    "Period": period,
                    "Stat": stat,
                },
            }
        ],
        StartTime=start_time,
        EndTime=end_time,
    )

    data_points = []
    result = response.get("MetricDataResults", [{}])[0]
    timestamps = result.get("Timestamps", [])
    values = result.get("Values", [])

    for ts, val in zip(timestamps, values, strict=False):
        data_points.append(
            MetricDataPoint(
                timestamp=ts,
                value=val,
                unit=result.get("Label", "Count"),
            )
        )

    return data_points


async def wait_for_log_entry(
    log_group: str,
    query: str,
    timeout_seconds: int = 60,
    poll_interval: int = 5,
) -> LogEntry | None:
    """Wait for a log entry matching the query to appear.

    Args:
        log_group: Log group name
        query: CloudWatch Logs Insights query
        timeout_seconds: Maximum time to wait
        poll_interval: Seconds between query attempts

    Returns:
        First matching LogEntry, or None if timeout
    """
    start = time.time()
    while time.time() - start < timeout_seconds:
        entries = await query_cloudwatch_logs(
            log_group,
            query,
            start_time=datetime.now(UTC) - timedelta(minutes=1),
            timeout_seconds=10,
        )
        if entries:
            return entries[0]
        await asyncio.sleep(poll_interval)
    return None


async def verify_metric_incremented(
    namespace: str,
    metric_name: str,
    dimensions: list[dict[str, str]],
    expected_increment: float = 1.0,
    tolerance: float = 0.1,
    timeout_seconds: int = 60,
) -> bool:
    """Verify a metric was incremented by expected amount.

    Args:
        namespace: Metric namespace
        metric_name: Metric name
        dimensions: Metric dimensions
        expected_increment: Expected metric change
        tolerance: Allowed variance from expected
        timeout_seconds: Time to wait for metric update

    Returns:
        True if metric increased by expected amount (within tolerance)
    """
    # Get baseline
    baseline = await get_cloudwatch_metrics(
        namespace,
        metric_name,
        dimensions,
        start_time=datetime.now(UTC) - timedelta(minutes=5),
    )
    baseline_sum = sum(dp.value for dp in baseline)

    # Wait for metric to update
    await asyncio.sleep(min(timeout_seconds / 2, 30))

    # Get updated value
    updated = await get_cloudwatch_metrics(
        namespace,
        metric_name,
        dimensions,
        start_time=datetime.now(UTC) - timedelta(minutes=5),
    )
    updated_sum = sum(dp.value for dp in updated)

    actual_increment = updated_sum - baseline_sum
    return abs(actual_increment - expected_increment) <= tolerance

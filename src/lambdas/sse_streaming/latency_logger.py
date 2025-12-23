"""Latency logging for SSE events.

Feature 1019: Validate Live Update Latency
Logs structured latency metrics to CloudWatch Logs for Logs Insights queries.

Canonical References:
- [CS-002] CloudWatch Logs Insights Query Syntax
- FR-003: Streaming Lambda MUST log latency metrics in structured JSON format
- FR-004: Latency metrics MUST include: event_type, origin_timestamp, send_timestamp, latency_ms
"""

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Track cold start state
_is_cold_start = True


def mark_warm() -> None:
    """Mark Lambda as warm (called after first event)."""
    global _is_cold_start
    _is_cold_start = False


def is_cold_start() -> bool:
    """Check if Lambda is in cold start state."""
    return _is_cold_start


def log_latency_metric(
    event_type: str,
    origin_timestamp: datetime,
    send_timestamp: datetime | None = None,
    ticker: str | None = None,
    resolution: str | None = None,
    connection_count: int = 0,
) -> None:
    """Log a latency metric in structured JSON format for CloudWatch Logs Insights.

    Per FR-003 and FR-004, logs structured latency metrics that can be queried
    using CloudWatch Logs Insights pctile() function.

    Args:
        event_type: Type of SSE event (bucket_update, partial_bucket, heartbeat)
        origin_timestamp: When the sentiment data was originally created
        send_timestamp: When the SSE event was serialized (defaults to now)
        ticker: Stock ticker symbol (None for heartbeat)
        resolution: Time resolution (None for heartbeat)
        connection_count: Active SSE connections when event sent

    Log Format:
        {
            "event_type": "bucket_update",
            "ticker": "AAPL",
            "resolution": "5m",
            "origin_timestamp": "2024-12-22T10:35:47.123Z",
            "send_timestamp": "2024-12-22T10:35:47.250Z",
            "latency_ms": 127,
            "is_cold_start": false,
            "connection_count": 5
        }
    """
    if send_timestamp is None:
        send_timestamp = datetime.now(UTC)

    # Calculate latency in milliseconds
    latency_delta = send_timestamp - origin_timestamp
    latency_ms = int(latency_delta.total_seconds() * 1000)

    # Check for clock skew (negative latency)
    is_clock_skew = latency_ms < 0

    # Determine log level based on latency
    # Warn if approaching 3s target (>2500ms)
    log_level = logging.WARNING if latency_ms > 2500 else logging.INFO

    # Log structured metric for CloudWatch Logs Insights
    logger.log(
        log_level,
        "SSE event latency",
        extra={
            "event_type": event_type,
            "ticker": ticker,
            "resolution": resolution,
            "origin_timestamp": origin_timestamp.isoformat(),
            "send_timestamp": send_timestamp.isoformat(),
            "latency_ms": latency_ms,
            "is_cold_start": is_cold_start(),
            "is_clock_skew": is_clock_skew,
            "connection_count": connection_count,
        },
    )

    # Mark as warm after first event
    if is_cold_start():
        mark_warm()

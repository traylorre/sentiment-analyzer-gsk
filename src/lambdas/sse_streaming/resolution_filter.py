"""
SSE event filtering based on resolution and ticker subscriptions.

Canonical References:
- [CS-007] MDN Server-Sent Events: "Filter events at server to reduce bandwidth"

This module provides server-side filtering of time-series bucket events
to reduce unnecessary data transmission to clients.
"""

from src.lambdas.sse_streaming.timeseries_models import (
    BucketUpdateEvent,
    HeartbeatEvent,
    PartialBucketEvent,
    SSEConnectionConfig,
)


def should_send_event(
    connection: SSEConnectionConfig,
    event: BucketUpdateEvent | PartialBucketEvent | HeartbeatEvent,
) -> bool:
    """
    Determine if an event should be sent to a connection based on filters.

    Canonical: [CS-007] "Filter events at server to reduce bandwidth"

    Filtering rules:
    1. HeartbeatEvent: Always pass (keepalive required)
    2. BucketUpdateEvent/PartialBucketEvent: Must match both:
       - Resolution filter (if not empty)
       - Ticker filter (if not empty)

    Args:
        connection: Connection configuration with filter subscriptions
        event: The event to evaluate

    Returns:
        True if event should be sent, False if it should be filtered out
    """
    # Heartbeats always pass - they're essential for connection keepalive
    if isinstance(event, HeartbeatEvent):
        return True

    # For bucket events, check both resolution and ticker filters
    if isinstance(event, BucketUpdateEvent | PartialBucketEvent):
        # Check resolution filter
        if not connection.matches_resolution(event.resolution):
            return False

        # Check ticker filter
        if not connection.matches_ticker(event.ticker):
            return False

        return True

    # Unknown event type - default to sending
    return True

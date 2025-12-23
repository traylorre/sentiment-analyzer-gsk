"""
Time-series SSE event models for resolution-filtered streaming.

Canonical References:
- [CS-007] MDN Server-Sent Events: "Filter events at server to reduce bandwidth"
- [CS-011] Netflix Tech Blog: "Partial aggregates with progress indicators"

This module defines models for time-series bucket update events that can be
filtered by resolution and ticker subscriptions.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.lib.timeseries import Resolution


class SSEConnectionConfig(BaseModel):
    """
    Configuration for an SSE connection with resolution/ticker subscriptions.

    Canonical: [CS-007] "Server-side filtering reduces bandwidth"
    """

    connection_id: str = Field(description="Unique connection identifier")
    subscribed_resolutions: list[Resolution] = Field(
        default_factory=list,
        description="Resolutions to receive (empty = all)",
    )
    subscribed_tickers: list[str] = Field(
        default_factory=list,
        description="Tickers to receive (empty = all)",
    )

    def matches_resolution(self, resolution: Resolution) -> bool:
        """Check if resolution matches subscription filter."""
        if not self.subscribed_resolutions:
            return True  # Empty = all
        return resolution in self.subscribed_resolutions

    def matches_ticker(self, ticker: str) -> bool:
        """Check if ticker matches subscription filter (case-sensitive)."""
        if not self.subscribed_tickers:
            return True  # Empty = all
        return ticker in self.subscribed_tickers


class BucketUpdateEvent(BaseModel):
    """
    Event indicating a time-series bucket has been updated.

    Sent when new sentiment data is aggregated into a bucket.

    Feature 1019 additions:
    - origin_timestamp: When sentiment data was originally created (for latency measurement)
    """

    ticker: str = Field(description="Stock ticker symbol")
    resolution: Resolution = Field(description="Time resolution of the bucket")
    bucket: dict[str, Any] = Field(description="Bucket data (OHLC, counts, etc.)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the SSE event was generated",
    )
    origin_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the sentiment data was originally created (FR-001)",
    )


class PartialBucketEvent(BucketUpdateEvent):
    """
    Event indicating a partial (in-progress) bucket update.

    Canonical: [CS-011] "Partial aggregates with progress indicators"
    """

    progress_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentage through bucket time period",
    )
    is_partial: bool = Field(default=True, description="Always true for partial events")


class HeartbeatEvent(BaseModel):
    """
    Heartbeat event for connection keepalive.

    Always passes resolution filter per [CS-007].
    """

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current server time",
    )
    connections: int = Field(description="Active connection count")
    uptime_seconds: int = Field(default=0, description="Lambda uptime in seconds")

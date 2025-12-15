"""SSE event models for streaming Lambda.

Defines Pydantic models for SSE event payloads per contracts/sse-events.md.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


def generate_event_id() -> str:
    """Generate a unique event ID in the format evt_{uuid}."""
    return f"evt_{uuid.uuid4()}"


class HeartbeatData(BaseModel):
    """Payload for heartbeat events.

    Sent every 30 seconds (configurable via SSE_HEARTBEAT_INTERVAL).
    """

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current server time (UTC)",
    )
    connections: int = Field(description="Active connection count")
    uptime_seconds: int = Field(description="Lambda uptime in seconds")


class MetricsEventData(BaseModel):
    """Payload for metrics events.

    Sent periodically (default 60s) or when data changes.
    """

    total: int = Field(description="Total items analyzed")
    positive: int = Field(description="Positive sentiment count")
    neutral: int = Field(description="Neutral sentiment count")
    negative: int = Field(description="Negative sentiment count")
    by_tag: dict[str, int] = Field(
        default_factory=dict, description="Counts per ticker tag"
    )
    rate_last_hour: int = Field(default=0, description="Items in last hour")
    rate_last_24h: int = Field(default=0, description="Items in last 24 hours")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When metrics were computed",
    )


class SentimentUpdateData(BaseModel):
    """Payload for sentiment_update events.

    Sent when a ticker's sentiment changes.
    """

    ticker: str = Field(description="Stock ticker symbol")
    score: float = Field(ge=-1.0, le=1.0, description="Sentiment score (-1.0 to 1.0)")
    label: str = Field(description="Sentiment label: positive/neutral/negative")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence (0.0-1.0)")
    source: str = Field(description="Data source (tiingo/finnhub)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When sentiment was computed",
    )


class SSEEvent(BaseModel):
    """An SSE event ready for streaming.

    Wraps event data with type, ID, and optional retry interval.

    Note: The data field accepts HeartbeatData, MetricsEventData, or
    SentimentUpdateData. A pre-validator handles already-instantiated
    model objects to work around pydantic 2.12 union validation issues.
    """

    event: str = Field(description="Event type: heartbeat/metrics/sentiment_update")
    id: str = Field(
        default_factory=generate_event_id, description="Unique event identifier"
    )
    data: Any = Field(description="Event payload")
    retry: int | None = Field(
        default=None, description="Reconnection delay in ms (optional)"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_data_type(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate that data is one of the allowed event data types.

        Pydantic 2.12 has issues with union types when passed already-instantiated
        model objects. This validator accepts the model instances directly.

        Note: Uses class name checking instead of isinstance() because the same
        module can be imported via different paths (e.g., 'models' vs
        'src.lambdas.sse_streaming.models'), causing isinstance to fail even
        when the types are logically the same.
        """
        if isinstance(values, dict):
            data = values.get("data")
            if data is not None:
                # Check by class name to handle dual-path imports
                allowed_types = {
                    "HeartbeatData",
                    "MetricsEventData",
                    "SentimentUpdateData",
                }
                if isinstance(data, dict):
                    pass  # dicts are allowed, will be validated by field type
                elif type(data).__name__ not in allowed_types:
                    raise ValueError(
                        f"data must be HeartbeatData, MetricsEventData, or SentimentUpdateData, "
                        f"got {type(data).__name__}"
                    )
        return values

    def to_sse_format(self) -> str:
        """Format event as SSE protocol string.

        Returns:
            Formatted SSE string with event, id, and data lines.
        """
        lines = []
        lines.append(f"event: {self.event}")
        lines.append(f"id: {self.id}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        # Serialize data as compact JSON
        lines.append(f"data: {self.data.model_dump_json()}")
        lines.append("")  # Empty line terminates event
        return "\n".join(lines)

    def to_sse_dict(self) -> dict:
        """Format event as dictionary for EventSourceResponse.

        EventSourceResponse from sse-starlette expects dictionaries with
        'event', 'id', 'data', and optionally 'retry' keys. This ensures
        proper Content-Type: text/event-stream header is set.

        Returns:
            Dictionary with SSE event fields.
        """
        result = {
            "event": self.event,
            "id": self.id,
            "data": self.data.model_dump_json(),
        }
        if self.retry is not None:
            result["retry"] = self.retry
        return result


class StreamStatus(BaseModel):
    """Response model for /api/v2/stream/status endpoint."""

    connections: int = Field(description="Current active connections")
    max_connections: int = Field(description="Maximum allowed connections")
    available: int = Field(description="Available connection slots")
    uptime_seconds: int = Field(description="Lambda uptime in seconds")

"""SSE event streaming logic.

Generates SSE events including heartbeats, metrics, and sentiment updates.
Per FR-006: Heartbeat every 30 seconds
Per FR-010: All events include event type, unique ID, and JSON payload

Feature 1009 additions:
- T027: Partial bucket streaming with progress_pct
- T028: 100ms debounce for multi-resolution updates
"""

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from connection import ConnectionManager, SSEConnection, connection_manager
from metrics import metrics_emitter
from models import (
    HeartbeatData,
    MetricsEventData,
    SentimentUpdateData,
    SSEEvent,
)
from polling import PollingService, get_polling_service
from timeseries_models import PartialBucketEvent

from src.lambdas.shared.logging_utils import sanitize_for_log
from src.lib.timeseries import Resolution, calculate_bucket_progress, floor_to_bucket

logger = logging.getLogger(__name__)

# Default debounce interval in milliseconds (T028)
DEFAULT_DEBOUNCE_MS = 100


class Debouncer:
    """
    Debounce mechanism for rate-limiting event emissions.

    Canonical: [CS-007] "Avoid flooding clients with rapid updates"
    Task: T028 - 100ms debounce for multi-resolution updates
    """

    def __init__(self, interval_ms: int = DEFAULT_DEBOUNCE_MS):
        """Initialize debouncer.

        Args:
            interval_ms: Minimum interval between emissions (default 100ms)
        """
        self._interval_seconds = interval_ms / 1000.0
        self._last_emit: dict[str, float] = {}  # key -> last emit timestamp

    def should_emit(self, key: str) -> bool:
        """Check if enough time has passed to emit for this key.

        Args:
            key: Unique identifier for the debounce group (e.g., "AAPL#5m")

        Returns:
            True if emission is allowed, False if debounced
        """
        current_time = time.time()
        last_emit = self._last_emit.get(key, 0.0)

        if current_time - last_emit >= self._interval_seconds:
            self._last_emit[key] = current_time
            return True
        return False

    def reset(self, key: str | None = None) -> None:
        """Reset debounce state.

        Args:
            key: Specific key to reset, or None to reset all
        """
        if key is None:
            self._last_emit.clear()
        else:
            self._last_emit.pop(key, None)


class EventBuffer:
    """Buffer for event ID tracking and replay.

    Supports Last-Event-ID reconnection per FR-007.
    """

    def __init__(self, max_size: int = 100):
        """Initialize event buffer.

        Args:
            max_size: Maximum events to keep in buffer
        """
        self._buffer: list[SSEEvent] = []
        self._max_size = max_size

    def add(self, event: SSEEvent) -> None:
        """Add event to buffer."""
        self._buffer.append(event)
        # Trim buffer if needed
        if len(self._buffer) > self._max_size:
            self._buffer = self._buffer[-self._max_size :]

    def get_events_after(self, event_id: str) -> list[SSEEvent]:
        """Get events after a specific event ID.

        Args:
            event_id: The Last-Event-ID from client

        Returns:
            List of events after the specified ID (empty if not found)
        """
        for i, event in enumerate(self._buffer):
            if event.id == event_id:
                return self._buffer[i + 1 :]
        return []

    def clear(self) -> None:
        """Clear the event buffer."""
        self._buffer.clear()


class SSEStreamGenerator:
    """Generates SSE event streams for connections.

    Combines heartbeats, metrics updates, and sentiment events
    into a single stream per connection.

    Feature 1009 additions:
    - T027: Partial bucket streaming with progress_pct
    - T028: 100ms debounce for multi-resolution updates
    """

    def __init__(
        self,
        conn_manager: ConnectionManager | None = None,
        poll_service: PollingService | None = None,
        heartbeat_interval: int | None = None,
        debounce_ms: int = DEFAULT_DEBOUNCE_MS,
    ):
        """Initialize stream generator.

        Args:
            conn_manager: Connection manager instance
            poll_service: Polling service instance
            heartbeat_interval: Heartbeat interval in seconds.
                              Defaults to SSE_HEARTBEAT_INTERVAL or 30.
            debounce_ms: Debounce interval for bucket updates (default 100ms)
        """
        self._conn_manager = conn_manager or connection_manager
        self._poll_service = poll_service or get_polling_service()
        self._heartbeat_interval = heartbeat_interval or int(
            os.environ.get("SSE_HEARTBEAT_INTERVAL", "30")
        )
        self._event_buffer = EventBuffer()
        self._start_time = time.time()
        self._debouncer = Debouncer(interval_ms=debounce_ms)

    @property
    def heartbeat_interval(self) -> int:
        """Get heartbeat interval in seconds."""
        return self._heartbeat_interval

    def _create_heartbeat(self) -> SSEEvent:
        """Create a heartbeat event."""
        return SSEEvent(
            event="heartbeat",
            data=HeartbeatData(
                timestamp=datetime.now(UTC),
                connections=self._conn_manager.count,
                uptime_seconds=int(time.time() - self._start_time),
            ),
            retry=3000,  # 3 second reconnect
        )

    def _create_metrics_event(self, metrics: MetricsEventData) -> SSEEvent:
        """Create a metrics event."""
        return SSEEvent(
            event="metrics",
            data=metrics,
        )

    def _create_sentiment_event(
        self, ticker: str, score: float, label: str, confidence: float, source: str
    ) -> SSEEvent:
        """Create a sentiment_update event."""
        return SSEEvent(
            event="sentiment_update",
            data=SentimentUpdateData(
                ticker=ticker,
                score=score,
                label=label,
                confidence=confidence,
                source=source,
                timestamp=datetime.now(UTC),
            ),
        )

    def _create_partial_bucket_event(
        self,
        ticker: str,
        resolution: Resolution,
        bucket_data: dict,
    ) -> SSEEvent:
        """Create a partial bucket event with progress_pct.

        Task T027: Partial bucket streaming with progress_pct.
        Canonical: [CS-011] "Partial aggregates with progress indicators"

        Args:
            ticker: Stock ticker symbol
            resolution: Time resolution of the bucket
            bucket_data: Current aggregated bucket data (OHLC, counts, etc.)

        Returns:
            SSEEvent containing PartialBucketEvent data
        """
        # Calculate current bucket start time
        now = datetime.now(UTC)
        bucket_start = floor_to_bucket(now, resolution)

        # Calculate progress through current bucket
        progress_pct = calculate_bucket_progress(bucket_start, resolution)

        event_data = PartialBucketEvent(
            ticker=ticker,
            resolution=resolution,
            bucket=bucket_data,
            progress_pct=progress_pct,
            is_partial=True,
            timestamp=now,
        )

        return SSEEvent(
            event="partial_bucket",
            data=event_data.model_dump(),
        )

    def should_emit_bucket_update(self, ticker: str, resolution: Resolution) -> bool:
        """Check if bucket update should be emitted (with debounce).

        Task T028: 100ms debounce for multi-resolution updates.
        Prevents flooding clients with rapid updates.

        Args:
            ticker: Stock ticker symbol
            resolution: Time resolution of the bucket

        Returns:
            True if update should be emitted, False if debounced
        """
        debounce_key = f"{ticker}#{resolution.value}"
        return self._debouncer.should_emit(debounce_key)

    async def generate_global_stream(
        self,
        connection: SSEConnection,
        last_event_id: str | None = None,
    ) -> AsyncGenerator[dict]:
        """Generate SSE events for global stream.

        Yields heartbeats and metrics updates.

        Args:
            connection: The SSE connection
            last_event_id: Last-Event-ID for reconnection replay

        Yields:
            SSE event dictionaries for EventSourceResponse
        """
        logger.info(
            "Starting global stream",
            extra={
                "connection_id": connection.connection_id,
                "last_event_id": (
                    sanitize_for_log(last_event_id) if last_event_id else None
                ),
            },
        )

        # Replay buffered events if reconnecting
        if last_event_id:
            for event in self._event_buffer.get_events_after(last_event_id):
                yield event.to_sse_dict()
                metrics_emitter.emit_events_sent(1, event.event)

        # Send initial heartbeat
        heartbeat = self._create_heartbeat()
        self._event_buffer.add(heartbeat)
        self._conn_manager.update_last_event_id(connection.connection_id, heartbeat.id)
        yield heartbeat.to_sse_dict()
        metrics_emitter.emit_events_sent(1, "heartbeat")

        # Track timing
        last_heartbeat = time.time()

        try:
            # Main event loop
            async for metrics, changed in self._poll_service.poll_loop():
                current_time = time.time()

                # Send metrics if changed
                if changed:
                    event = self._create_metrics_event(metrics)
                    self._event_buffer.add(event)
                    self._conn_manager.update_last_event_id(
                        connection.connection_id, event.id
                    )
                    yield event.to_sse_dict()
                    metrics_emitter.emit_events_sent(1, "metrics")

                # Send heartbeat if interval passed
                if current_time - last_heartbeat >= self._heartbeat_interval:
                    heartbeat = self._create_heartbeat()
                    self._event_buffer.add(heartbeat)
                    self._conn_manager.update_last_event_id(
                        connection.connection_id, heartbeat.id
                    )
                    yield heartbeat.to_sse_dict()
                    metrics_emitter.emit_events_sent(1, "heartbeat")
                    last_heartbeat = current_time

        except asyncio.CancelledError:
            logger.info(
                "Stream cancelled",
                extra={"connection_id": connection.connection_id},
            )
            raise
        except Exception as e:
            logger.error(
                "Stream error",
                extra={
                    "connection_id": connection.connection_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def generate_config_stream(
        self,
        connection: SSEConnection,
        last_event_id: str | None = None,
    ) -> AsyncGenerator[dict]:
        """Generate SSE events for configuration-specific stream.

        Yields heartbeats and filtered sentiment updates.

        Args:
            connection: The SSE connection with ticker filters
            last_event_id: Last-Event-ID for reconnection replay

        Yields:
            SSE event dictionaries for EventSourceResponse
        """
        logger.info(
            "Starting config stream",
            extra={
                "connection_id": connection.connection_id,
                "config_id": (
                    sanitize_for_log(connection.config_id)
                    if connection.config_id
                    else None
                ),
                "ticker_filters": connection.ticker_filters,
                "last_event_id": (
                    sanitize_for_log(last_event_id) if last_event_id else None
                ),
            },
        )

        # Replay buffered events if reconnecting (filtered)
        if last_event_id:
            for event in self._event_buffer.get_events_after(last_event_id):
                # Only replay sentiment events for matching tickers
                if event.event == "sentiment_update":
                    if hasattr(event.data, "ticker"):
                        if not connection.matches_ticker(event.data.ticker):
                            continue
                yield event.to_sse_dict()
                metrics_emitter.emit_events_sent(1, event.event)

        # Send initial heartbeat
        heartbeat = self._create_heartbeat()
        self._event_buffer.add(heartbeat)
        self._conn_manager.update_last_event_id(connection.connection_id, heartbeat.id)
        yield heartbeat.to_sse_dict()
        metrics_emitter.emit_events_sent(1, "heartbeat")

        try:
            # Main event loop - for config streams we just send heartbeats
            # Sentiment updates would come from a separate mechanism
            while True:
                await asyncio.sleep(self._heartbeat_interval)

                heartbeat = self._create_heartbeat()
                self._event_buffer.add(heartbeat)
                self._conn_manager.update_last_event_id(
                    connection.connection_id, heartbeat.id
                )
                yield heartbeat.to_sse_dict()
                metrics_emitter.emit_events_sent(1, "heartbeat")

        except asyncio.CancelledError:
            logger.info(
                "Config stream cancelled",
                extra={"connection_id": connection.connection_id},
            )
            raise
        except Exception as e:
            logger.error(
                "Config stream error",
                extra={
                    "connection_id": connection.connection_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise


# Global stream generator instance (lazy initialization)
_stream_generator: SSEStreamGenerator | None = None


def get_stream_generator() -> SSEStreamGenerator:
    """Get stream generator instance (lazy initialization).

    This avoids module-level instantiation which can break test collection
    by eagerly initializing ConnectionManager and PollingService dependencies.
    """
    global _stream_generator
    if _stream_generator is None:
        _stream_generator = SSEStreamGenerator()
    return _stream_generator


# Backwards compatibility alias - deprecated, use get_stream_generator()
stream_generator = None  # type: ignore[assignment]

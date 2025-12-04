"""SSE event streaming logic.

Generates SSE events including heartbeats, metrics, and sentiment updates.
Per FR-006: Heartbeat every 30 seconds
Per FR-010: All events include event type, unique ID, and JSON payload
"""

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from src.lambdas.shared.logging_utils import sanitize_for_log

from .connection import ConnectionManager, SSEConnection, connection_manager
from .metrics import metrics_emitter
from .models import (
    HeartbeatData,
    MetricsEventData,
    SentimentUpdateData,
    SSEEvent,
)
from .polling import PollingService, polling_service

logger = logging.getLogger(__name__)


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
    """

    def __init__(
        self,
        conn_manager: ConnectionManager | None = None,
        poll_service: PollingService | None = None,
        heartbeat_interval: int | None = None,
    ):
        """Initialize stream generator.

        Args:
            conn_manager: Connection manager instance
            poll_service: Polling service instance
            heartbeat_interval: Heartbeat interval in seconds.
                              Defaults to SSE_HEARTBEAT_INTERVAL or 30.
        """
        self._conn_manager = conn_manager or connection_manager
        self._poll_service = poll_service or polling_service
        self._heartbeat_interval = heartbeat_interval or int(
            os.environ.get("SSE_HEARTBEAT_INTERVAL", "30")
        )
        self._event_buffer = EventBuffer()
        self._start_time = time.time()

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

    async def generate_global_stream(
        self,
        connection: SSEConnection,
        last_event_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Generate SSE events for global stream.

        Yields heartbeats and metrics updates.

        Args:
            connection: The SSE connection
            last_event_id: Last-Event-ID for reconnection replay

        Yields:
            Formatted SSE event strings
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
                yield event.to_sse_format()
                metrics_emitter.emit_events_sent(1, event.event)

        # Send initial heartbeat
        heartbeat = self._create_heartbeat()
        self._event_buffer.add(heartbeat)
        self._conn_manager.update_last_event_id(connection.connection_id, heartbeat.id)
        yield heartbeat.to_sse_format()
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
                    yield event.to_sse_format()
                    metrics_emitter.emit_events_sent(1, "metrics")

                # Send heartbeat if interval passed
                if current_time - last_heartbeat >= self._heartbeat_interval:
                    heartbeat = self._create_heartbeat()
                    self._event_buffer.add(heartbeat)
                    self._conn_manager.update_last_event_id(
                        connection.connection_id, heartbeat.id
                    )
                    yield heartbeat.to_sse_format()
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
    ) -> AsyncGenerator[str, None]:
        """Generate SSE events for configuration-specific stream.

        Yields heartbeats and filtered sentiment updates.

        Args:
            connection: The SSE connection with ticker filters
            last_event_id: Last-Event-ID for reconnection replay

        Yields:
            Formatted SSE event strings
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
                yield event.to_sse_format()
                metrics_emitter.emit_events_sent(1, event.event)

        # Send initial heartbeat
        heartbeat = self._create_heartbeat()
        self._event_buffer.add(heartbeat)
        self._conn_manager.update_last_event_id(connection.connection_id, heartbeat.id)
        yield heartbeat.to_sse_format()
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
                yield heartbeat.to_sse_format()
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


# Global stream generator instance
stream_generator = SSEStreamGenerator()

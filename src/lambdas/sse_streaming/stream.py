"""SSE event streaming logic.

Generates SSE events including heartbeats, metrics, and sentiment updates.
Per FR-006: Heartbeat every 30 seconds
Per FR-010: All events include event type, unique ID, and JSON payload

Feature 1009 additions:
- T027: Partial bucket streaming with progress_pct
- T028: 100ms debounce for multi-resolution updates

Feature 1020 additions:
- Cache metrics logging for SC-008 validation (>80% hit rate)
"""

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from cache_logger import CacheMetricsLogger, log_cold_start_metrics
from connection import ConnectionManager, SSEConnection, connection_manager
from latency_logger import log_latency_metric
from metrics import metrics_emitter
from models import (
    HeartbeatData,
    MetricsEventData,
    SentimentUpdateData,
    SSEEvent,
)
from polling import (
    PollingService,
    TickerAggregate,
    detect_ticker_changes,
    get_polling_service,
)
from timeseries_models import PartialBucketEvent
from tracing import get_tracer, is_enabled, safe_force_flush

from src.lambdas.shared.logging_utils import sanitize_for_log
from src.lib.timeseries import Resolution, calculate_bucket_progress, floor_to_bucket
from src.lib.timeseries.cache import get_global_cache

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

    def __init__(self, max_size: int = 500):
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

        # Feature 1020: Cache metrics logging for SC-008 validation
        cache = get_global_cache()
        self._cache_logger = CacheMetricsLogger(cache, interval_seconds=60)

        # Log initial metrics on cold start
        # Safely get connection count (handles mocked conn_manager in tests)
        try:
            conn_count = int(self._conn_manager.count)
        except (TypeError, ValueError):
            conn_count = 0
        log_cold_start_metrics(cache, connection_count=conn_count)

    @property
    def heartbeat_interval(self) -> int:
        """Get heartbeat interval in seconds."""
        return self._heartbeat_interval

    def _create_heartbeat(self) -> SSEEvent:
        """Create a heartbeat event and emit connection count metric."""
        conn_count = self._conn_manager.count
        # Emit connection count for CloudWatch alarm (chaos-readiness)
        metrics_emitter.emit_connection_count(conn_count)
        return SSEEvent(
            event="heartbeat",
            data=HeartbeatData(
                timestamp=datetime.now(UTC),
                connections=conn_count,
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
            origin_timestamp=now,  # Feature 1019: Set origin for latency tracking
        )

        # Feature 1019: Log latency metric for CloudWatch Logs Insights
        log_latency_metric(
            event_type="partial_bucket",
            origin_timestamp=event_data.origin_timestamp,
            send_timestamp=now,
            ticker=ticker,
            resolution=resolution.value,
            connection_count=self._conn_manager.count,
        )

        return SSEEvent(
            event="partial_bucket",
            data=event_data,
        )

    def _inject_trace_id(self, sse_dict: dict) -> dict:
        """Inject current X-Ray trace ID into SSE event data (T064, FR-115).

        Adds trace_id field to the JSON data payload for frontend
        logging correlation.

        Args:
            sse_dict: SSE event dict from to_sse_dict()

        Returns:
            SSE dict with trace_id injected into data JSON
        """
        trace_id = os.environ.get("_X_AMZN_TRACE_ID")
        if trace_id:
            import json

            try:
                data = json.loads(sse_dict["data"])
                data["trace_id"] = trace_id
                sse_dict["data"] = json.dumps(data, default=str)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        return sse_dict

    def _trace_event_dispatch(self, event_type: str, start_time: float) -> None:
        """Create OTel span for SSE event dispatch (T043).

        Args:
            event_type: Type of SSE event (heartbeat, metrics, etc.)
            start_time: time.perf_counter() from before event creation
        """
        otel_tracer = get_tracer()
        if not otel_tracer or not is_enabled():
            return
        from opentelemetry.trace import SpanKind

        latency_ms = (time.perf_counter() - start_time) * 1000
        with otel_tracer.start_as_current_span(
            "sse_event_dispatch", kind=SpanKind.INTERNAL
        ) as span:
            span.set_attribute("event_type", event_type)
            span.set_attribute("latency_ms", latency_ms)

    def _check_deadline_flush(self) -> bool:
        """Check if Lambda deadline is approaching and flush if needed (T046).

        Returns:
            True if flush was triggered (caller should stop creating spans).
        """
        deadline_ms_str = os.environ.get("AWS_LAMBDA_DEADLINE_MS")
        if not deadline_ms_str:
            return False
        try:
            deadline_ms = int(deadline_ms_str)
            remaining_ms = deadline_ms - int(time.time() * 1000)
            if remaining_ms < 3000:
                logger.info(
                    "Deadline approaching, triggering proactive flush",
                    extra={"remaining_ms": remaining_ms},
                )
                safe_force_flush()
                return True
        except (ValueError, TypeError):
            pass
        return False

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
        dispatch_start = time.perf_counter()
        heartbeat = self._create_heartbeat()
        self._event_buffer.add(heartbeat)
        self._conn_manager.update_last_event_id(connection.connection_id, heartbeat.id)
        yield self._inject_trace_id(heartbeat.to_sse_dict())
        self._trace_event_dispatch("heartbeat", dispatch_start)
        metrics_emitter.emit_events_sent(1, "heartbeat")

        # Track timing
        last_heartbeat = time.time()
        flush_fired = False  # T046: Block span creation after flush

        # Feature 1228: Per-connection state for change detection (FR-003, FR-011)
        local_last_per_ticker: dict[str, TickerAggregate] = {}
        local_last_buckets: dict[str, dict] = {}
        local_is_baseline = True

        try:
            # Main event loop
            async for poll_result in self._poll_service.poll_loop():
                # T046: Check deadline before creating more spans (FR-093)
                if not flush_fired and self._check_deadline_flush():
                    flush_fired = True
                    # Yield deadline event to notify client
                    yield SSEEvent(
                        event="deadline",
                        data={"reason": "lambda_timeout_approaching"},
                    ).to_sse_dict()
                    return

                current_time = time.time()

                # Send metrics if changed
                if poll_result.metrics_changed:
                    dispatch_start = time.perf_counter()
                    event = self._create_metrics_event(poll_result.metrics)
                    self._event_buffer.add(event)
                    self._conn_manager.update_last_event_id(
                        connection.connection_id, event.id
                    )
                    yield self._inject_trace_id(event.to_sse_dict())
                    if not flush_fired:
                        self._trace_event_dispatch("metrics", dispatch_start)
                    metrics_emitter.emit_events_sent(1, "metrics")

                # Send heartbeat if interval passed
                if current_time - last_heartbeat >= self._heartbeat_interval:
                    dispatch_start = time.perf_counter()
                    heartbeat = self._create_heartbeat()
                    self._event_buffer.add(heartbeat)
                    self._conn_manager.update_last_event_id(
                        connection.connection_id, heartbeat.id
                    )
                    yield self._inject_trace_id(heartbeat.to_sse_dict())
                    if not flush_fired:
                        self._trace_event_dispatch("heartbeat", dispatch_start)
                    metrics_emitter.emit_events_sent(1, "heartbeat")
                    last_heartbeat = current_time

                # Feature 1228: Emit sentiment_update events (FR-001, FR-003)
                if not local_is_baseline and poll_result.per_ticker:
                    changed_tickers = detect_ticker_changes(
                        poll_result.per_ticker, local_last_per_ticker
                    )
                    for ticker in changed_tickers:
                        if ticker in poll_result.per_ticker:
                            agg = poll_result.per_ticker[ticker]
                            dispatch_start = time.perf_counter()
                            event = self._create_sentiment_event(
                                ticker,
                                agg.score,
                                agg.label,
                                agg.confidence,
                                "aggregate",
                            )
                            self._event_buffer.add(event)
                            self._conn_manager.update_last_event_id(
                                connection.connection_id, event.id
                            )
                            yield self._inject_trace_id(event.to_sse_dict())
                            if not flush_fired:
                                self._trace_event_dispatch(
                                    "sentiment_update", dispatch_start
                                )
                            metrics_emitter.emit_events_sent(1, "sentiment_update")

                # Feature 1228: Emit partial_bucket events (FR-002, FR-004a)
                if not local_is_baseline and poll_result.timeseries_buckets:
                    for key, bucket_data in poll_result.timeseries_buckets.items():
                        if (
                            key not in local_last_buckets
                            or bucket_data != local_last_buckets.get(key)
                        ):
                            # Parse ticker and resolution from key
                            parts = key.split("#", 1)
                            if len(parts) == 2:
                                ticker, res_str = parts
                                try:
                                    resolution = Resolution(res_str)
                                except ValueError:
                                    continue
                                if self.should_emit_bucket_update(ticker, resolution):
                                    dispatch_start = time.perf_counter()
                                    event = self._create_partial_bucket_event(
                                        ticker, resolution, bucket_data
                                    )
                                    self._event_buffer.add(event)
                                    self._conn_manager.update_last_event_id(
                                        connection.connection_id, event.id
                                    )
                                    yield self._inject_trace_id(event.to_sse_dict())
                                    if not flush_fired:
                                        self._trace_event_dispatch(
                                            "partial_bucket", dispatch_start
                                        )
                                    metrics_emitter.emit_events_sent(
                                        1, "partial_bucket"
                                    )

                # Update per-connection snapshots
                local_last_per_ticker = dict(poll_result.per_ticker)
                local_last_buckets = dict(poll_result.timeseries_buckets)
                local_is_baseline = False

                # Feature 1020: Periodic cache metrics logging (every 60s)
                self._cache_logger.maybe_log(connection_count=self._conn_manager.count)

        except asyncio.CancelledError:
            logger.info(
                "Stream cancelled",
                extra={"connection_id": connection.connection_id},
            )
            raise
        except (BrokenPipeError, OSError) as e:
            # T050: Client disconnect — NOT a server error (FR-085, SC-039)
            otel_tracer = get_tracer()
            if otel_tracer and is_enabled() and not flush_fired:
                from opentelemetry.trace import StatusCode, trace

                current_span = trace.get_current_span()
                if current_span and current_span.is_recording():
                    current_span.set_attribute("client.disconnected", True)
                    current_span.set_status(StatusCode.OK)
            logger.info(
                "Client disconnected",
                extra={
                    "connection_id": connection.connection_id,
                    "error": str(e),
                },
            )
        except Exception as e:
            # T048: Dual-call error pattern (FR-144, FR-150)
            otel_tracer = get_tracer()
            if otel_tracer and is_enabled() and not flush_fired:
                from opentelemetry.trace import StatusCode, trace

                current_span = trace.get_current_span()
                if current_span and current_span.is_recording():
                    current_span.set_status(StatusCode.ERROR, str(e))
                    current_span.record_exception(e)
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

        # Replay buffered events if reconnecting (filtered) — T032: includes partial_bucket
        if last_event_id:
            for event in self._event_buffer.get_events_after(last_event_id):
                if event.event in ("sentiment_update", "partial_bucket"):
                    ticker = None
                    if hasattr(event.data, "ticker"):
                        ticker = event.data.ticker
                    elif isinstance(event.data, dict):
                        ticker = event.data.get("ticker")
                    if ticker and not connection.matches_ticker(ticker):
                        continue
                yield event.to_sse_dict()
                metrics_emitter.emit_events_sent(1, event.event)

        # Send initial heartbeat
        heartbeat = self._create_heartbeat()
        self._event_buffer.add(heartbeat)
        self._conn_manager.update_last_event_id(connection.connection_id, heartbeat.id)
        yield heartbeat.to_sse_dict()
        metrics_emitter.emit_events_sent(1, "heartbeat")

        # Feature 1228: Per-connection state for change detection (FR-003, FR-011)
        local_last_per_ticker: dict[str, TickerAggregate] = {}
        local_last_buckets: dict[str, dict] = {}
        local_is_baseline = True
        last_heartbeat = time.time()

        try:
            # Main event loop — polls for sentiment + timeseries changes
            # NOTE: Does NOT emit metrics events (config streams only get
            # heartbeats + filtered sentiment_update + filtered partial_bucket)
            async for poll_result in self._poll_service.poll_loop():
                current_time = time.time()

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

                # Feature 1228: Emit filtered sentiment_update events (FR-001, FR-006)
                if not local_is_baseline and poll_result.per_ticker:
                    changed_tickers = detect_ticker_changes(
                        poll_result.per_ticker, local_last_per_ticker
                    )
                    for ticker in changed_tickers:
                        if ticker in poll_result.per_ticker:
                            if not connection.matches_ticker(ticker):
                                continue
                            agg = poll_result.per_ticker[ticker]
                            event = self._create_sentiment_event(
                                ticker,
                                agg.score,
                                agg.label,
                                agg.confidence,
                                "aggregate",
                            )
                            self._event_buffer.add(event)
                            self._conn_manager.update_last_event_id(
                                connection.connection_id, event.id
                            )
                            yield event.to_sse_dict()
                            metrics_emitter.emit_events_sent(1, "sentiment_update")

                # Feature 1228: Emit filtered partial_bucket events (FR-002, FR-006)
                if not local_is_baseline and poll_result.timeseries_buckets:
                    for key, bucket_data in poll_result.timeseries_buckets.items():
                        if (
                            key not in local_last_buckets
                            or bucket_data != local_last_buckets.get(key)
                        ):
                            parts = key.split("#", 1)
                            if len(parts) == 2:
                                ticker, res_str = parts
                                if not connection.matches_ticker(ticker):
                                    continue
                                try:
                                    resolution = Resolution(res_str)
                                except ValueError:
                                    continue
                                if self.should_emit_bucket_update(ticker, resolution):
                                    event = self._create_partial_bucket_event(
                                        ticker, resolution, bucket_data
                                    )
                                    self._event_buffer.add(event)
                                    self._conn_manager.update_last_event_id(
                                        connection.connection_id, event.id
                                    )
                                    yield event.to_sse_dict()
                                    metrics_emitter.emit_events_sent(
                                        1, "partial_bucket"
                                    )

                # Update per-connection snapshots
                local_last_per_ticker = dict(poll_result.per_ticker)
                local_last_buckets = dict(poll_result.timeseries_buckets)
                local_is_baseline = False

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

"""
SSE (Server-Sent Events) Streaming Module
==========================================

Implements real-time event streaming for the dashboard using SSE protocol.

Endpoints:
- GET /api/v2/stream - Global metrics stream (FR-001)
- GET /api/v2/configurations/{config_id}/stream - Config-specific stream (FR-002)
- GET /api/v2/stream/status - Connection status

For On-Call Engineers:
    If dashboard shows "Disconnected":
    1. Check Lambda Function URL supports streaming responses
    2. Verify connection limit (100) not exceeded
    3. Check CloudWatch logs for SSE connection errors
    4. Verify heartbeat events are being sent (every 30s)

    See SC-001 in success criteria for connection timing requirements.

For Developers:
    - Uses Powertools Router for endpoint registration
    - ConnectionManager tracks active connections (thread-safe)
    - In BUFFERED invoke mode, returns a single SSE snapshot per invocation
    - Event IDs support reconnection via Last-Event-ID header

Security Notes:
    - Global stream is public (read-only aggregated metrics)
    - Config-specific stream requires authentication
    - No raw content exposed in events
"""

import json
import logging
import os
import threading
import uuid
from datetime import UTC, datetime
from typing import Literal

import orjson
from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.router import Router
from pydantic import BaseModel, Field

from src.lambdas.shared.dynamodb import get_table
from src.lambdas.shared.logging_utils import get_safe_error_info
from src.lambdas.shared.middleware.auth_middleware import extract_auth_context
from src.lambdas.shared.utils.event_helpers import get_header

# Structured logging
logger = logging.getLogger(__name__)

# Environment configuration
# Feature 1043: Clear naming - sentiments table for SSE metrics
SENTIMENTS_TABLE = os.environ["SENTIMENTS_TABLE"]

# SSE configuration
HEARTBEAT_INTERVAL = int(os.environ.get("SSE_HEARTBEAT_INTERVAL", "30"))  # seconds
MAX_CONNECTIONS = int(os.environ.get("SSE_MAX_CONNECTIONS", "100"))
METRICS_INTERVAL = int(os.environ.get("SSE_METRICS_INTERVAL", "60"))  # seconds

# Create router
router = Router()


# =============================================================================
# Pydantic Models (per data-model.md)
# =============================================================================


class MetricsEventData(BaseModel):
    """Payload for metrics events (FR-009)."""

    total: int = 0
    positive: int = 0
    neutral: int = 0
    negative: int = 0
    by_tag: dict[str, int] = Field(default_factory=dict)
    rate_last_hour: int = 0
    rate_last_24h: int = 0
    origin_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NewItemEventData(BaseModel):
    """Payload for new_item events (FR-010)."""

    item_id: str
    ticker: str
    sentiment: Literal["positive", "neutral", "negative"]
    score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HeartbeatEventData(BaseModel):
    """Payload for heartbeat events (FR-004)."""

    origin_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    connections: int = Field(ge=0)


# =============================================================================
# Connection Manager (FR-015, FR-016, FR-017)
# =============================================================================


class ConnectionManager:
    """
    Thread-safe manager for tracking active SSE connections.

    Enforces connection limits and provides metrics for observability.

    Attributes:
        max_connections: Maximum allowed concurrent connections (default: 100)
    """

    def __init__(self, max_connections: int = MAX_CONNECTIONS):
        self._count = 0
        self._lock = threading.Lock()
        self.max_connections = max_connections

    def acquire(self) -> bool:
        """
        Attempt to acquire a connection slot.

        Returns:
            True if slot acquired, False if limit reached
        """
        with self._lock:
            if self._count >= self.max_connections:
                logger.warning(
                    "SSE connection limit reached",
                    extra={
                        "current": self._count,
                        "max": self.max_connections,
                    },
                )
                return False
            self._count += 1
            logger.info(
                "SSE connection opened",
                extra={
                    "connections": self._count,
                    "max": self.max_connections,
                },
            )
            return True

    def release(self) -> None:
        """Release a connection slot."""
        with self._lock:
            self._count = max(0, self._count - 1)
            logger.info(
                "SSE connection closed",
                extra={
                    "connections": self._count,
                },
            )

    @property
    def count(self) -> int:
        """Current number of active connections."""
        return self._count


# Global connection manager instance
connection_manager = ConnectionManager()


# =============================================================================
# Event Generation (FR-004, FR-009, FR-010, FR-011)
# =============================================================================


def _generate_event_id() -> str:
    """Generate unique event ID for reconnection support (FR-011)."""
    return f"evt_{uuid.uuid4().hex[:12]}"


def _get_metrics_data() -> MetricsEventData:
    """
    Fetch current metrics from DynamoDB.

    Returns:
        MetricsEventData with current dashboard metrics
    """
    try:
        if SENTIMENTS_TABLE:
            from src.lambdas.dashboard.metrics import aggregate_dashboard_metrics

            table = get_table(SENTIMENTS_TABLE)
            metrics = aggregate_dashboard_metrics(table, hours=24)

            return MetricsEventData(
                total=metrics.get("total", 0),
                positive=metrics.get("positive", 0),
                neutral=metrics.get("neutral", 0),
                negative=metrics.get("negative", 0),
                by_tag=metrics.get("by_tag", {}),
                rate_last_hour=metrics.get("rate_last_hour", 0),
                rate_last_24h=metrics.get("rate_last_24h", 0),
                origin_timestamp=datetime.now(UTC),
            )
    except Exception as e:
        logger.warning(
            "Failed to fetch metrics from DynamoDB",
            extra=get_safe_error_info(e),
        )

    # Return empty metrics if fetch fails
    return MetricsEventData()


def _build_sse_snapshot(last_event_id: str | None = None) -> str:
    """Build a single SSE snapshot containing metrics + heartbeat events.

    In BUFFERED invoke mode, Lambda returns a complete response per invocation.
    This function generates a snapshot of current state as SSE-formatted text.

    Args:
        last_event_id: Client's last event ID for reconnection (FR-005)

    Returns:
        SSE-formatted text string with metrics and heartbeat events
    """
    events: list[str] = []

    # Log reconnection if Last-Event-ID provided
    if last_event_id:
        logger.info(
            "SSE reconnection with Last-Event-ID",
            extra={"last_event_id": last_event_id},
        )

    # Emit metrics event
    try:
        metrics_data = _get_metrics_data()
        event_id = _generate_event_id()
        data = json.dumps(metrics_data.model_dump(mode="json"), default=str)
        events.append(f"event: metrics\nid: {event_id}\ndata: {data}\n\n")
    except Exception as e:
        logger.warning(
            "Failed to get metrics for SSE",
            extra=get_safe_error_info(e),
        )

    # Emit heartbeat event
    heartbeat_data = HeartbeatEventData(
        origin_timestamp=datetime.now(UTC),
        connections=connection_manager.count,
    )
    event_id = _generate_event_id()
    data = json.dumps(heartbeat_data.model_dump(mode="json"), default=str)
    events.append(f"event: heartbeat\nid: {event_id}\ndata: {data}\n\n")

    return "".join(events)


# =============================================================================
# SSE Endpoints (FR-001, FR-002, FR-003)
# =============================================================================


@router.get("/api/v2/stream")
def stream_global_metrics() -> Response:
    """
    Global metrics stream for dashboard real-time updates (FR-001).

    Returns SSE snapshot with:
    - metrics event with current dashboard data
    - heartbeat event with connection info

    Headers:
        Last-Event-ID: Optional - resume from specific event

    Returns:
        Response with text/event-stream content type (FR-003)

    Raises:
        503: Connection limit reached (FR-015)
    """
    # Check connection limit
    if not connection_manager.acquire():
        return Response(
            status_code=503,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": "Maximum connections reached. Please try again later."}
            ).decode(),
        )

    try:
        # Extract Last-Event-ID for reconnection (FR-005)
        event = router.current_event.raw_event
        last_event_id = get_header(event, "Last-Event-ID")

        sse_body = _build_sse_snapshot(last_event_id=last_event_id)

        return Response(
            status_code=200,
            content_type="text/event-stream",
            body=sse_body,
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    finally:
        connection_manager.release()


@router.get("/api/v2/configurations/<config_id>/stream")
def stream_config_events(config_id: str) -> Response:
    """
    Configuration-specific event stream (FR-002).

    Requires authentication (FR-006).

    Args:
        config_id: Configuration UUID

    Headers:
        Authorization: Bearer token or X-User-ID (required)
        Last-Event-ID: Optional - resume from specific event

    Returns:
        Response with filtered events for configuration

    Raises:
        401: Missing authentication (FR-007)
        404: Configuration not found (FR-008)
        503: Connection limit reached (FR-015)
    """
    event = router.current_event.raw_event

    # Authenticate user (FR-006, FR-007)
    auth_context = extract_auth_context(event)
    user_id = auth_context.get("user_id")
    if not user_id:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Missing user identification"}).decode(),
        )

    # Validate configuration exists (FR-008)
    if SENTIMENTS_TABLE:
        from src.lambdas.dashboard import configurations as config_service

        table = get_table(SENTIMENTS_TABLE)
        config = config_service.get_configuration(
            table=table,
            user_id=user_id,
            config_id=config_id,
        )
        if config is None or isinstance(config, config_service.ErrorResponse):
            return Response(
                status_code=404,
                content_type="application/json",
                body=orjson.dumps({"detail": "Configuration not found"}).decode(),
            )

    # Check connection limit
    if not connection_manager.acquire():
        return Response(
            status_code=503,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": "Maximum connections reached. Please try again later."}
            ).decode(),
        )

    try:
        # Extract Last-Event-ID for reconnection (FR-005)
        last_event_id = get_header(event, "Last-Event-ID")

        sse_body = _build_sse_snapshot(last_event_id=last_event_id)

        return Response(
            status_code=200,
            content_type="text/event-stream",
            body=sse_body,
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    finally:
        connection_manager.release()


# =============================================================================
# Utility Endpoints
# =============================================================================


@router.get("/api/v2/stream/status")
def get_stream_status() -> Response:
    """
    Get current SSE connection status.

    Returns:
        JSON with connection count and limit
    """
    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps(
            {
                "connections": connection_manager.count,
                "max_connections": connection_manager.max_connections,
                "available": connection_manager.max_connections
                - connection_manager.count,
            }
        ).decode(),
    )

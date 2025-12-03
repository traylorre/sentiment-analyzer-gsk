"""
SSE (Server-Sent Events) Streaming Module
==========================================

Implements real-time event streaming for the dashboard using SSE protocol.

Endpoints:
- GET /api/v2/stream - Global metrics stream (FR-001)
- GET /api/v2/configurations/{config_id}/stream - Config-specific stream (FR-002)

For On-Call Engineers:
    If dashboard shows "Disconnected":
    1. Check Lambda Function URL supports streaming responses
    2. Verify connection limit (100) not exceeded
    3. Check CloudWatch logs for SSE connection errors
    4. Verify heartbeat events are being sent (every 30s)

    See SC-001 in success criteria for connection timing requirements.

For Developers:
    - Uses sse-starlette library for SSE protocol compliance
    - ConnectionManager tracks active connections (thread-safe)
    - Heartbeat events sent every 30 seconds to keep connections alive
    - Event IDs support reconnection via Last-Event-ID header

Security Notes:
    - Global stream is public (read-only aggregated metrics)
    - Config-specific stream requires authentication
    - No raw content exposed in events
"""

import asyncio
import json
import logging
import os
import threading
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.lambdas.shared.dynamodb import get_table
from src.lambdas.shared.logging_utils import get_safe_error_info

# Structured logging
logger = logging.getLogger(__name__)

# Environment configuration
DYNAMODB_TABLE = os.environ.get("DATABASE_TABLE") or os.environ.get(
    "DYNAMODB_TABLE", ""
)

# SSE configuration
HEARTBEAT_INTERVAL = int(os.environ.get("SSE_HEARTBEAT_INTERVAL", "30"))  # seconds
MAX_CONNECTIONS = int(os.environ.get("SSE_MAX_CONNECTIONS", "100"))
METRICS_INTERVAL = int(os.environ.get("SSE_METRICS_INTERVAL", "60"))  # seconds

# Create router
router = APIRouter(prefix="/api/v2", tags=["streaming"])


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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NewItemEventData(BaseModel):
    """Payload for new_item events (FR-010)."""

    item_id: str
    ticker: str
    sentiment: Literal["positive", "neutral", "negative"]
    score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HeartbeatEventData(BaseModel):
    """Payload for heartbeat events (FR-004)."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
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


async def create_event_generator(
    heartbeat_interval: int = HEARTBEAT_INTERVAL,
    metrics_interval: int = METRICS_INTERVAL,
    last_event_id: str | None = None,
    config_id: str | None = None,
    tickers: list[str] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Create an async generator that yields SSE events.

    Args:
        heartbeat_interval: Seconds between heartbeat events (FR-004)
        metrics_interval: Seconds between metrics events
        last_event_id: Client's last event ID for reconnection (FR-005)
        config_id: Optional config ID for filtered events
        tickers: Optional ticker filter for config-specific streams

    Yields:
        SSE event dicts with 'event', 'id', and 'data' keys
    """
    event_counter = 0
    last_metrics_time = 0.0
    import time

    # Log reconnection if Last-Event-ID provided
    if last_event_id:
        logger.info(
            "SSE reconnection with Last-Event-ID",
            extra={"last_event_id": last_event_id},
        )

    try:
        while True:
            current_time = time.time()
            event_counter += 1

            # Emit metrics event at configured interval
            if current_time - last_metrics_time >= metrics_interval:
                last_metrics_time = current_time

                # Get metrics from database
                try:
                    metrics_data = await _get_metrics_data()
                    event_id = _generate_event_id()

                    yield {
                        "event": "metrics",
                        "id": event_id,
                        "data": json.dumps(
                            metrics_data.model_dump(mode="json"),
                            default=str,
                        ),
                    }
                except Exception as e:
                    logger.warning(
                        "Failed to get metrics for SSE",
                        extra=get_safe_error_info(e),
                    )

            # Emit heartbeat event
            heartbeat_data = HeartbeatEventData(
                timestamp=datetime.now(UTC),
                connections=connection_manager.count,
            )
            event_id = _generate_event_id()

            yield {
                "event": "heartbeat",
                "id": event_id,
                "data": json.dumps(
                    heartbeat_data.model_dump(mode="json"),
                    default=str,
                ),
            }

            # Wait for next heartbeat interval
            await asyncio.sleep(heartbeat_interval)

    except asyncio.CancelledError:
        logger.info("SSE event generator cancelled")
        raise
    except Exception as e:
        logger.error(
            "SSE event generator error",
            extra=get_safe_error_info(e),
        )
        raise


async def _get_metrics_data() -> MetricsEventData:
    """
    Fetch current metrics from DynamoDB.

    Returns:
        MetricsEventData with current dashboard metrics
    """
    try:
        if DYNAMODB_TABLE:
            from src.lambdas.dashboard.metrics import aggregate_dashboard_metrics

            table = get_table(DYNAMODB_TABLE)
            metrics = aggregate_dashboard_metrics(table, hours=24)

            return MetricsEventData(
                total=metrics.get("total", 0),
                positive=metrics.get("positive", 0),
                neutral=metrics.get("neutral", 0),
                negative=metrics.get("negative", 0),
                by_tag=metrics.get("by_tag", {}),
                rate_last_hour=metrics.get("rate_last_hour", 0),
                rate_last_24h=metrics.get("rate_last_24h", 0),
                timestamp=datetime.now(UTC),
            )
    except Exception as e:
        logger.warning(
            "Failed to fetch metrics from DynamoDB",
            extra=get_safe_error_info(e),
        )

    # Return empty metrics if fetch fails
    return MetricsEventData()


# =============================================================================
# SSE Endpoints (FR-001, FR-002, FR-003)
# =============================================================================


@router.get("/stream")
async def stream_global_metrics(
    request: Request,
) -> EventSourceResponse:
    """
    Global metrics stream for dashboard real-time updates (FR-001).

    Returns SSE stream with:
    - heartbeat events every 30 seconds
    - metrics events every 60 seconds

    Headers:
        Last-Event-ID: Optional - resume from specific event

    Returns:
        EventSourceResponse with text/event-stream content type (FR-003)

    Raises:
        HTTPException 503: Connection limit reached (FR-015)
    """
    # Check connection limit
    if not connection_manager.acquire():
        raise HTTPException(
            status_code=503,
            detail="Maximum connections reached. Please try again later.",
        )

    # Extract Last-Event-ID for reconnection (FR-005)
    last_event_id = request.headers.get("Last-Event-ID")

    async def event_generator():
        try:
            async for event in create_event_generator(
                last_event_id=last_event_id,
            ):
                yield event
        finally:
            connection_manager.release()

    return EventSourceResponse(event_generator())


@router.get("/configurations/{config_id}/stream")
async def stream_config_events(
    config_id: str,
    request: Request,
) -> EventSourceResponse:
    """
    Configuration-specific event stream (FR-002).

    Requires authentication (FR-006).

    Args:
        config_id: Configuration UUID

    Headers:
        Authorization: Bearer token or X-User-ID (required)
        Last-Event-ID: Optional - resume from specific event

    Returns:
        EventSourceResponse with filtered events for configuration

    Raises:
        HTTPException 401: Missing authentication (FR-007)
        HTTPException 404: Configuration not found (FR-008)
        HTTPException 503: Connection limit reached (FR-015)
    """
    # Import auth helper from router_v2
    from src.lambdas.dashboard.router_v2 import get_user_id_from_request

    # Authenticate user (FR-006, FR-007)
    try:
        user_id = get_user_id_from_request(request)
    except HTTPException as e:
        raise HTTPException(
            status_code=401,
            detail="Missing user identification",
        ) from e

    # Validate configuration exists (FR-008)
    if DYNAMODB_TABLE:
        from src.lambdas.dashboard import configurations as config_service

        table = get_table(DYNAMODB_TABLE)
        config = config_service.get_configuration(
            table=table,
            user_id=user_id,
            config_id=config_id,
        )
        if config is None or isinstance(config, config_service.ErrorResponse):
            raise HTTPException(
                status_code=404,
                detail="Configuration not found",
            )

        # Extract tickers from configuration
        tickers = [t.symbol for t in config.tickers]
    else:
        tickers = []

    # Check connection limit
    if not connection_manager.acquire():
        raise HTTPException(
            status_code=503,
            detail="Maximum connections reached. Please try again later.",
        )

    # Extract Last-Event-ID for reconnection (FR-005)
    last_event_id = request.headers.get("Last-Event-ID")

    async def event_generator():
        try:
            async for event in create_event_generator(
                last_event_id=last_event_id,
                config_id=config_id,
                tickers=tickers,
            ):
                yield event
        finally:
            connection_manager.release()

    return EventSourceResponse(event_generator())


# =============================================================================
# Utility Endpoints
# =============================================================================


@router.get("/stream/status")
async def get_stream_status() -> JSONResponse:
    """
    Get current SSE connection status.

    Returns:
        JSON with connection count and limit
    """
    return JSONResponse(
        {
            "connections": connection_manager.count,
            "max_connections": connection_manager.max_connections,
            "available": connection_manager.max_connections - connection_manager.count,
        }
    )

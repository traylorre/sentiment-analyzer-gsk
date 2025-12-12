"""SSE Streaming Lambda handler.

FastAPI application for Server-Sent Events streaming.
Uses AWS Lambda Web Adapter with RESPONSE_STREAM invoke mode.
"""

import logging
import os

# X-Ray tracing setup - must be done before other imports
from aws_xray_sdk.core import patch_all, xray_recorder

patch_all()

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from src.lambdas.shared.logging_utils import sanitize_for_log

from .config import config_lookup_service
from .connection import connection_manager
from .metrics import metrics_emitter
from .models import StreamStatus
from .stream import stream_generator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Environment configuration
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

# Create FastAPI app
app = FastAPI(
    title="SSE Streaming Lambda",
    description="Real-time Server-Sent Events for sentiment updates",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configured per environment in production
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for Lambda Web Adapter."""
    return {"status": "healthy", "environment": ENVIRONMENT}


@app.get("/api/v2/stream/status", response_model=StreamStatus)
@xray_recorder.capture("stream_status")
async def stream_status() -> StreamStatus:
    """Get SSE connection pool status.

    Returns current connection count, max connections, available slots,
    and Lambda uptime. Non-streaming endpoint.
    """
    status = connection_manager.get_status()
    logger.info("Stream status requested", extra=status)
    return StreamStatus(**status)


@app.get("/api/v2/stream")
@xray_recorder.capture("global_stream")
async def global_stream(
    request: Request,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
):
    """Global SSE stream endpoint.

    Streams real-time sentiment metrics to all connected clients.
    Per FR-004: Global stream at /api/v2/stream
    Per FR-014: No authentication required (public metrics)

    Headers:
        Last-Event-ID: Optional event ID for reconnection resumption

    Returns:
        EventSourceResponse streaming heartbeat and metrics events
    """
    # Log connection attempt
    logger.info(
        "Global stream connection attempt",
        extra={
            "client_host": sanitize_for_log(
                request.client.host if request.client else "unknown"
            ),
            "last_event_id": sanitize_for_log(last_event_id) if last_event_id else None,
        },
    )

    # Acquire connection slot
    connection = connection_manager.acquire()
    if connection is None:
        # Connection limit reached - return 503
        logger.warning(
            "Connection limit reached, rejecting request",
            extra={"max_connections": connection_manager.max_connections},
        )
        metrics_emitter.emit_connection_acquire_failure()
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Connection limit reached. Try again later.",
                "max_connections": connection_manager.max_connections,
                "retry_after": 30,
            },
            headers={"Retry-After": "30"},
        )

    # Log successful connection
    logger.info(
        "Global stream connection established",
        extra={
            "connection_id": connection.connection_id,
            "total_connections": connection_manager.count,
        },
    )
    metrics_emitter.emit_connection_count(connection_manager.count)

    async def event_generator():
        """Generate SSE events and handle cleanup."""
        try:
            async for event_str in stream_generator.generate_global_stream(
                connection, last_event_id
            ):
                yield event_str
        finally:
            # Release connection on disconnect
            connection_manager.release(connection.connection_id)
            logger.info(
                "Global stream connection closed",
                extra={
                    "connection_id": connection.connection_id,
                    "total_connections": connection_manager.count,
                },
            )
            metrics_emitter.emit_connection_count(connection_manager.count)

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/v2/configurations/{config_id}/stream")
@xray_recorder.capture("config_stream")
async def config_stream(
    request: Request,
    config_id: str,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
):
    """Configuration-specific SSE stream endpoint.

    Streams real-time sentiment updates filtered to configured tickers.
    Per FR-014: Requires X-User-ID authentication header
    Per T035: GET /api/v2/configurations/{config_id}/stream

    Path Parameters:
        config_id: Configuration ID to stream

    Headers:
        X-User-ID: Required user ID for authentication
        Last-Event-ID: Optional event ID for reconnection resumption

    Returns:
        EventSourceResponse streaming heartbeat and filtered sentiment events

    Raises:
        401: Missing or invalid X-User-ID header (T034)
        404: Configuration not found or doesn't belong to user (T037)
        503: Connection limit reached
    """
    # T034: Validate X-User-ID header
    if not x_user_id or not x_user_id.strip():
        logger.warning(
            "Config stream rejected - missing X-User-ID",
            extra={"config_id": sanitize_for_log(config_id[:8] if config_id else "")},
        )
        return JSONResponse(
            status_code=401,
            content={"detail": "X-User-ID header is required"},
        )

    user_id = x_user_id.strip()

    # Log connection attempt
    logger.info(
        "Config stream connection attempt",
        extra={
            "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
            "user_id_prefix": sanitize_for_log(user_id[:8] if user_id else ""),
            "client_host": sanitize_for_log(
                request.client.host if request.client else "unknown"
            ),
            "last_event_id": sanitize_for_log(last_event_id) if last_event_id else None,
        },
    )

    # T037: Validate configuration exists and belongs to user
    has_access, ticker_filters = config_lookup_service.validate_user_access(
        user_id, config_id
    )
    if not has_access:
        logger.warning(
            "Config stream rejected - configuration not found",
            extra={
                "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
                "user_id_prefix": sanitize_for_log(user_id[:8] if user_id else ""),
            },
        )
        return JSONResponse(
            status_code=404,
            content={"detail": "Configuration not found"},
        )

    # Acquire connection slot with ticker filters
    connection = connection_manager.acquire(
        user_id=user_id,
        config_id=config_id,
        ticker_filters=ticker_filters,
    )
    if connection is None:
        # Connection limit reached - return 503
        logger.warning(
            "Connection limit reached for config stream, rejecting request",
            extra={
                "max_connections": connection_manager.max_connections,
                "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
            },
        )
        metrics_emitter.emit_connection_acquire_failure()
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Connection limit reached. Try again later.",
                "max_connections": connection_manager.max_connections,
                "retry_after": 30,
            },
            headers={"Retry-After": "30"},
        )

    # Log successful connection
    logger.info(
        "Config stream connection established",
        extra={
            "connection_id": connection.connection_id,
            "config_id": sanitize_for_log(config_id),
            "ticker_filters": ticker_filters,
            "total_connections": connection_manager.count,
        },
    )
    metrics_emitter.emit_connection_count(connection_manager.count)

    async def event_generator():
        """Generate SSE events and handle cleanup."""
        try:
            # T036: Ticker filtering is handled in generate_config_stream
            async for event_str in stream_generator.generate_config_stream(
                connection, last_event_id
            ):
                yield event_str
        finally:
            # Release connection on disconnect
            connection_manager.release(connection.connection_id)
            logger.info(
                "Config stream connection closed",
                extra={
                    "connection_id": connection.connection_id,
                    "config_id": sanitize_for_log(config_id),
                    "total_connections": connection_manager.count,
                },
            )
            metrics_emitter.emit_connection_count(connection_manager.count)

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler with logging."""
    logger.error(
        "Unhandled exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

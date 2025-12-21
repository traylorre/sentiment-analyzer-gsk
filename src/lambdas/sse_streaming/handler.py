"""SSE Streaming Lambda handler.

FastAPI application for Server-Sent Events streaming.
Uses AWS Lambda Web Adapter with RESPONSE_STREAM invoke mode.
"""

import logging
import os

# X-Ray tracing setup - must be done before other imports
from aws_xray_sdk.core import patch_all, xray_recorder

patch_all()

# Use absolute imports instead of relative imports to work when
# handler.py is imported directly (not as part of a package).
# The Dockerfile sets PYTHONPATH=/app so these modules are findable.
# For tests, conftest.py adds the Lambda directory to sys.path.
from config import config_lookup_service
from connection import connection_manager
from fastapi import FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from metrics import metrics_emitter
from models import StreamStatus
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from stream import get_stream_generator

# Import logging utilities - try Docker path first (logging_utils.py copied to /app/),
# fall back to full path for tests
try:
    from logging_utils import sanitize_for_log
except ImportError:
    from src.lambdas.shared.logging_utils import sanitize_for_log

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


# Path normalization middleware - Fix(141): Lambda Web Adapter sends double slashes
class PathNormalizationMiddleware(BaseHTTPMiddleware):
    """Normalize request paths to handle Lambda Web Adapter double-slash issue.

    Lambda Web Adapter v0.9.1 can forward requests with double slashes
    (e.g., //health instead of /health), causing 404 errors since FastAPI
    routes don't match paths with leading double slashes.

    This middleware normalizes the path before routing by collapsing
    consecutive slashes into single slashes.
    """

    async def dispatch(self, request: Request, call_next):
        # Normalize path by collapsing multiple slashes
        original_path = request.scope.get("path", "")
        if "//" in original_path:
            import re

            normalized_path = re.sub(r"/+", "/", original_path)
            logger.debug(
                "Path normalized",
                extra={"original": original_path, "normalized": normalized_path},
            )
            request.scope["path"] = normalized_path
        return await call_next(request)


# Add path normalization middleware (applied first, before CORS)
app.add_middleware(PathNormalizationMiddleware)

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


@app.get("/debug")
async def debug_info() -> dict:
    """Debug endpoint for diagnosing Lambda configuration issues.

    Returns Lambda environment info and registered routes.
    Only available in non-prod environments for security.

    Fix(141): Added to diagnose path translation issues in preprod.
    """
    if ENVIRONMENT == "prod":
        return {"error": "Debug endpoint disabled in production"}

    # Get registered routes
    routes = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            routes.append(
                {
                    "path": route.path,
                    "methods": list(route.methods) if route.methods else [],
                    "name": route.name if hasattr(route, "name") else None,
                }
            )

    # Get relevant environment variables (exclude secrets)
    safe_env_vars = {
        "ENVIRONMENT": os.environ.get("ENVIRONMENT"),
        "AWS_REGION": os.environ.get("AWS_REGION"),
        "AWS_LAMBDA_FUNCTION_NAME": os.environ.get("AWS_LAMBDA_FUNCTION_NAME"),
        "AWS_LAMBDA_FUNCTION_VERSION": os.environ.get("AWS_LAMBDA_FUNCTION_VERSION"),
        "AWS_LAMBDA_FUNCTION_MEMORY_SIZE": os.environ.get(
            "AWS_LAMBDA_FUNCTION_MEMORY_SIZE"
        ),
        "AWS_LWA_INVOKE_MODE": os.environ.get("AWS_LWA_INVOKE_MODE"),
        "AWS_LWA_READINESS_CHECK_PATH": os.environ.get("AWS_LWA_READINESS_CHECK_PATH"),
        "PYTHONPATH": os.environ.get("PYTHONPATH"),
        "SSE_HEARTBEAT_INTERVAL": os.environ.get("SSE_HEARTBEAT_INTERVAL", "30"),
        "SSE_MAX_CONNECTIONS": os.environ.get("SSE_MAX_CONNECTIONS", "100"),
        "SSE_POLL_INTERVAL": os.environ.get("SSE_POLL_INTERVAL", "5"),
    }

    return {
        "status": "debug",
        "environment": ENVIRONMENT,
        "routes": routes,
        "env_vars": safe_env_vars,
        "python_version": f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}.{__import__('sys').version_info.micro}",
    }


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
# Note: X-Ray @xray_recorder.capture() is intentionally NOT used here.
# The capture decorator only works with synchronous functions (per AWS docs)
# and interferes with async streaming responses. Streaming requests are traced
# via the X-Ray middleware applied at startup via patch_all().
async def global_stream(
    request: Request,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
    resolutions: str | None = Query(
        None,
        description="Comma-separated resolution filters (e.g., '1m,5m,1h'). "
        "Valid: 1m,5m,10m,1h,3h,6h,12h,24h. Empty = all resolutions.",
    ),
):
    """Global SSE stream endpoint.

    Streams real-time sentiment metrics to all connected clients.
    Per FR-004: Global stream at /api/v2/stream
    Per FR-014: No authentication required (public metrics)

    Feature 1009: Multi-resolution time-series streaming
    Canonical: [CS-007] "SSE for real-time updates at subscribed resolutions"

    Headers:
        Last-Event-ID: Optional event ID for reconnection resumption

    Query Parameters:
        resolutions: Comma-separated list of resolution levels to subscribe to.
                    Valid values: 1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h
                    Empty or not specified = subscribe to all resolutions.

    Returns:
        EventSourceResponse streaming heartbeat and metrics events
    """
    # Feature 1009: Parse and validate resolution filters
    resolution_filters: list[str] = []
    valid_resolutions = {"1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"}
    if resolutions:
        for res in resolutions.split(","):
            res = res.strip().lower()
            if res and res in valid_resolutions:
                resolution_filters.append(res)
        # Log invalid resolutions for debugging
        requested = {r.strip().lower() for r in resolutions.split(",") if r.strip()}
        invalid = requested - valid_resolutions
        if invalid:
            logger.warning(
                "Invalid resolutions requested",
                extra={"invalid": list(invalid), "valid": list(valid_resolutions)},
            )

    # Log connection attempt
    logger.info(
        "Global stream connection attempt",
        extra={
            "client_host": sanitize_for_log(
                request.client.host if request.client else "unknown"
            ),
            "last_event_id": sanitize_for_log(last_event_id) if last_event_id else None,
            "resolution_filters": resolution_filters if resolution_filters else "all",
        },
    )

    # Acquire connection slot with resolution filters
    connection = connection_manager.acquire(resolution_filters=resolution_filters)
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
        """Generate SSE events and handle cleanup.

        Formats events as SSE protocol strings for StreamingResponse.
        Using StreamingResponse instead of EventSourceResponse for better
        Content-Type header handling with Lambda Web Adapter.
        """
        try:
            async for event_dict in get_stream_generator().generate_global_stream(
                connection, last_event_id
            ):
                # Format as SSE protocol string
                lines = []
                if "event" in event_dict:
                    lines.append(f"event: {event_dict['event']}")
                if "id" in event_dict:
                    lines.append(f"id: {event_dict['id']}")
                if "retry" in event_dict:
                    lines.append(f"retry: {event_dict['retry']}")
                if "data" in event_dict:
                    lines.append(f"data: {event_dict['data']}")
                lines.append("")  # Empty line terminates event
                yield "\n".join(lines) + "\n"
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

    # Use StreamingResponse instead of EventSourceResponse for better
    # Content-Type header handling with Lambda Web Adapter
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/v2/configurations/{config_id}/stream")
# Note: X-Ray @xray_recorder.capture() is intentionally NOT used here.
# The capture decorator only works with synchronous functions (per AWS docs)
# and interferes with async streaming responses. Streaming requests are traced
# via the X-Ray middleware applied at startup via patch_all().
async def config_stream(
    request: Request,
    config_id: str,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    user_token: str | None = Query(None, description="User token for EventSource auth"),
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
):
    """Configuration-specific SSE stream endpoint.

    Streams real-time sentiment updates filtered to configured tickers.
    Per FR-014: Requires authentication via X-User-ID header OR user_token query param
    Per T035: GET /api/v2/configurations/{config_id}/stream

    Path Parameters:
        config_id: Configuration ID to stream

    Headers:
        X-User-ID: User ID for authentication (preferred for non-EventSource clients)
        Last-Event-ID: Optional event ID for reconnection resumption

    Query Parameters:
        user_token: User token for EventSource authentication (browser limitation workaround)
                   EventSource API does not support custom headers, so tokens must be
                   passed via query parameter. Use short-lived tokens for security.

    Returns:
        EventSourceResponse streaming heartbeat and filtered sentiment events

    Raises:
        401: Missing or invalid authentication (T034)
        404: Configuration not found or doesn't belong to user (T037)
        503: Connection limit reached

    Security Notes:
        - Query param tokens appear in logs, browser history, and caches
        - Use short-lived tokens (5-min expiry recommended)
        - Always use HTTPS to prevent token interception
        - Response includes Cache-Control: no-store to prevent caching
    """
    # T034: Validate authentication - accept header OR query param
    # Header takes precedence if both provided
    user_id = None
    auth_method = None

    if x_user_id and x_user_id.strip():
        user_id = x_user_id.strip()
        auth_method = "header"
    elif user_token and user_token.strip():
        user_id = user_token.strip()
        auth_method = "query_param"

    if not user_id:
        logger.warning(
            "Config stream rejected - missing authentication",
            extra={"config_id": sanitize_for_log(config_id[:8] if config_id else "")},
        )
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Authentication required. Provide X-User-ID header or user_token query parameter."
            },
        )

    # Log connection attempt (redact token from query params for security)
    logger.info(
        "Config stream connection attempt",
        extra={
            "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
            "user_id_prefix": sanitize_for_log(user_id[:8] if user_id else ""),
            "auth_method": auth_method,
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
            async for event_str in get_stream_generator().generate_config_stream(
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
            # Prevent caching of authenticated streams (security: token in URL)
            "Cache-Control": "no-store, no-cache, private, must-revalidate",
            "X-Accel-Buffering": "no",
            "Pragma": "no-cache",
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

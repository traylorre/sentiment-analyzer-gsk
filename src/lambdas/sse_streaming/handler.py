"""SSE Streaming Lambda handler with native RESPONSE_STREAM support.

Custom runtime handler for Server-Sent Events streaming. Uses a Python generator
to yield SSE chunks, consumed by the bootstrap which streams them to clients via
the Lambda Runtime API with chunked transfer encoding.

Architecture:
    bootstrap.py polls Runtime API → calls handler(event, context) → handler yields bytes
    → bootstrap POSTs chunks to Runtime API with streaming headers

Endpoints:
- GET /api/v2/stream/status: Connection pool status (non-streaming, returns dict)
- GET /api/v2/stream: Global SSE stream with optional filters (streaming)
- GET /api/v2/configurations/{config_id}/stream: Authenticated config-specific stream

For On-Call Engineers:
    If SSE streaming stops working after deployment:
    1. Check that the bootstrap file is executable and at /var/task/bootstrap
    2. Check that the Lambda runtime is set to 'provided.al2023' (custom runtime)
    3. Check that the Function URL invoke mode is RESPONSE_STREAM
    4. Check CloudWatch logs for bootstrap or handler errors
"""

import asyncio
import json
import logging
import os
import re
from collections.abc import Generator

from aws_xray_sdk.core import patch_all, xray_recorder

patch_all()

from config import config_lookup_service
from connection import connection_manager
from metrics import metrics_emitter
from models import StreamStatus
from stream import get_stream_generator

from src.lambdas.shared.logging_utils import sanitize_for_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

# Null byte separator for Lambda Function URL streaming protocol
# 8 null bytes separate HTTP metadata prelude from response body
_NULL_SEPARATOR = b"\x00\x00\x00\x00\x00\x00\x00\x00"


# =============================================================================
# Helper Functions
# =============================================================================


def _get_header(event: dict, name: str) -> str | None:
    """Extract header from Lambda event (case-insensitive).

    Args:
        event: Lambda event dict
        name: Header name to find

    Returns:
        Header value if found, None otherwise
    """
    headers = event.get("headers") or {}
    name_lower = name.lower()
    for key, value in headers.items():
        if key.lower() == name_lower:
            return value
    return None


def _get_query_param(event: dict, name: str) -> str | None:
    """Extract query parameter from Lambda event.

    Args:
        event: Lambda event dict
        name: Query parameter name

    Returns:
        Parameter value if found, None otherwise
    """
    params = event.get("queryStringParameters") or {}
    return params.get(name)


def _match_config_stream_path(path: str) -> str | None:
    """Extract config_id from /api/v2/configurations/{config_id}/stream path.

    Args:
        path: Request path

    Returns:
        config_id if path matches, None otherwise
    """
    match = re.match(r"^/api/v2/configurations/([^/]+)/stream$", path)
    return match.group(1) if match else None


def _format_sse_event(event_dict: dict) -> bytes:
    """Format an SSE event dict as protocol bytes.

    Args:
        event_dict: Dict with keys: event, id, data, retry (optional)

    Returns:
        UTF-8 encoded SSE event string
    """
    lines = []
    if "event" in event_dict:
        lines.append(f"event: {event_dict['event']}")
    if "id" in event_dict:
        lines.append(f"id: {event_dict['id']}")
    if "retry" in event_dict:
        lines.append(f"retry: {event_dict['retry']}")
    if "data" in event_dict:
        lines.append(f"data: {event_dict['data']}")
    lines.append("")  # Empty line terminates SSE event
    return ("\n".join(lines) + "\n").encode("utf-8")


def _streaming_metadata(
    status_code: int = 200,
    content_type: str = "text/event-stream",
    extra_headers: dict | None = None,
) -> bytes:
    """Build HTTP metadata prelude for Lambda Function URL streaming.

    The metadata prelude is JSON followed by 8 null bytes, per the
    application/vnd.awslambda.http-integration-response protocol.

    Args:
        status_code: HTTP status code
        content_type: Content-Type header value
        extra_headers: Additional headers to include

    Returns:
        Encoded metadata prelude bytes (JSON + 8 null bytes)
    """
    headers = {"Content-Type": content_type}
    if extra_headers:
        headers.update(extra_headers)

    metadata = {
        "statusCode": status_code,
        "headers": headers,
        "cookies": [],
    }
    return json.dumps(metadata).encode("utf-8") + _NULL_SEPARATOR


def _error_metadata_and_body(
    status_code: int, detail: str, extra_headers: dict | None = None
) -> bytes:
    """Build a complete non-streaming error response (metadata + body).

    Args:
        status_code: HTTP status code
        detail: Error detail message
        extra_headers: Additional headers

    Returns:
        Complete response bytes (metadata prelude + JSON error body)
    """
    metadata = _streaming_metadata(
        status_code=status_code,
        content_type="application/json",
        extra_headers=extra_headers,
    )
    body = json.dumps({"detail": detail}).encode("utf-8")
    return metadata + body


# =============================================================================
# Route Handlers
# =============================================================================


@xray_recorder.capture("stream_status")
def _handle_stream_status() -> Generator[bytes]:
    """Handle GET /api/v2/stream/status (non-streaming).

    Yields a single complete response with connection pool status.
    """
    status = connection_manager.get_status()
    logger.info("Stream status requested", extra=status)

    metadata = _streaming_metadata(
        status_code=200,
        content_type="application/json",
    )
    body = StreamStatus(**status).model_dump_json().encode("utf-8")
    yield metadata + body


def _handle_global_stream(event: dict) -> Generator[bytes]:
    """Handle GET /api/v2/stream (streaming SSE).

    Streams real-time sentiment metrics to connected clients.
    Supports optional resolution and ticker filters via query params.
    """
    last_event_id = _get_header(event, "Last-Event-ID")
    resolutions = _get_query_param(event, "resolutions")
    tickers = _get_query_param(event, "tickers")

    # Parse resolution filters
    resolution_filters: list[str] = []
    valid_resolutions = {"1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"}
    if resolutions:
        for res in resolutions.split(","):
            res = res.strip().lower()
            if res and res in valid_resolutions:
                resolution_filters.append(res)
        requested = {r.strip().lower() for r in resolutions.split(",") if r.strip()}
        invalid = requested - valid_resolutions
        if invalid:
            logger.warning(
                "Invalid resolutions requested",
                extra={
                    "invalid": [sanitize_for_log(r) for r in invalid],
                    "valid": list(valid_resolutions),
                },
            )

    # Parse ticker filters
    ticker_filters: list[str] = []
    if tickers:
        for ticker in tickers.split(","):
            ticker = ticker.strip().upper()
            if ticker:
                ticker_filters.append(ticker)

    client_host = (
        event.get("requestContext", {}).get("http", {}).get("sourceIp", "unknown")
    )
    logger.info(
        "Global stream connection attempt",
        extra={
            "client_host": sanitize_for_log(client_host),
            "last_event_id": sanitize_for_log(last_event_id) if last_event_id else None,
            "resolution_filters": (
                [sanitize_for_log(r) for r in resolution_filters]
                if resolution_filters
                else "all"
            ),
            "ticker_filters": (
                [sanitize_for_log(t) for t in ticker_filters]
                if ticker_filters
                else "all"
            ),
        },
    )

    # Acquire connection slot
    connection = connection_manager.acquire(
        resolution_filters=resolution_filters, ticker_filters=ticker_filters
    )
    if connection is None:
        logger.warning(
            "Connection limit reached, rejecting request",
            extra={"max_connections": connection_manager.max_connections},
        )
        metrics_emitter.emit_connection_acquire_failure()
        yield _error_metadata_and_body(
            503,
            "Connection limit reached. Try again later.",
            extra_headers={"Retry-After": "30"},
        )
        return

    logger.info(
        "Global stream connection established",
        extra={
            "connection_id": connection.connection_id,
            "total_connections": connection_manager.count,
        },
    )
    metrics_emitter.emit_connection_count(connection_manager.count)

    # Yield SSE metadata prelude
    yield _streaming_metadata(
        extra_headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

    # Bridge async generator to sync yields
    try:
        yield from _consume_async_stream(
            get_stream_generator().generate_global_stream(connection, last_event_id),
            connection.connection_id,
        )
    finally:
        connection_manager.release(connection.connection_id)
        logger.info(
            "Global stream connection closed",
            extra={
                "connection_id": connection.connection_id,
                "total_connections": connection_manager.count,
            },
        )
        metrics_emitter.emit_connection_count(connection_manager.count)


def _handle_config_stream(event: dict, config_id: str) -> Generator[bytes]:
    """Handle GET /api/v2/configurations/{config_id}/stream (streaming SSE).

    Streams config-specific sentiment updates with authentication.
    Authentication precedence: Bearer token > X-User-ID header > user_token query param.
    """
    authorization = _get_header(event, "Authorization")
    x_user_id = _get_header(event, "X-User-ID")
    user_token = _get_query_param(event, "user_token")
    last_event_id = _get_header(event, "Last-Event-ID")

    # Resolve user identity
    user_id = None
    auth_method = None

    if authorization and authorization.startswith("Bearer "):
        bearer_token = authorization[7:].strip()
        if bearer_token:
            user_id = bearer_token
            auth_method = "bearer"

    if not user_id and x_user_id and x_user_id.strip():
        user_id = x_user_id.strip()
        auth_method = "header"

    if not user_id and user_token and user_token.strip():
        user_id = user_token.strip()
        auth_method = "query_param"

    if not user_id:
        logger.warning(
            "Config stream rejected - missing authentication",
            extra={"config_id": sanitize_for_log(config_id[:8] if config_id else "")},
        )
        yield _error_metadata_and_body(
            401,
            "Authentication required. Provide Authorization: Bearer header, "
            "X-User-ID header, or user_token query parameter.",
        )
        return

    client_host = (
        event.get("requestContext", {}).get("http", {}).get("sourceIp", "unknown")
    )
    logger.info(
        "Config stream connection attempt",
        extra={
            "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
            "user_id_prefix": sanitize_for_log(user_id[:8] if user_id else ""),
            "auth_method": auth_method,
            "client_host": sanitize_for_log(client_host),
            "last_event_id": sanitize_for_log(last_event_id) if last_event_id else None,
        },
    )

    # Validate configuration access
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
        yield _error_metadata_and_body(404, "Configuration not found")
        return

    # Acquire connection slot
    connection = connection_manager.acquire(
        user_id=user_id,
        config_id=config_id,
        ticker_filters=ticker_filters or [],
    )
    if connection is None:
        logger.warning(
            "Connection limit reached for config stream, rejecting request",
            extra={
                "max_connections": connection_manager.max_connections,
                "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
            },
        )
        metrics_emitter.emit_connection_acquire_failure()
        yield _error_metadata_and_body(
            503,
            "Connection limit reached. Try again later.",
            extra_headers={"Retry-After": "30"},
        )
        return

    logger.info(
        "Config stream connection established",
        extra={
            "connection_id": connection.connection_id,
            "config_id": sanitize_for_log(config_id),
            "ticker_filters": (
                [sanitize_for_log(t) for t in ticker_filters] if ticker_filters else []
            ),
            "total_connections": connection_manager.count,
        },
    )
    metrics_emitter.emit_connection_count(connection_manager.count)

    # Yield SSE metadata prelude with no-store for authenticated streams
    yield _streaming_metadata(
        extra_headers={
            "Cache-Control": "no-store, no-cache, private, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Pragma": "no-cache",
        },
    )

    # Bridge async generator to sync yields
    try:
        yield from _consume_async_stream(
            get_stream_generator().generate_config_stream(connection, last_event_id),
            connection.connection_id,
        )
    finally:
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


# =============================================================================
# Async-to-Sync Bridge
# =============================================================================


def _consume_async_stream(
    async_gen,
    connection_id: str,
) -> Generator[bytes]:
    """Bridge async SSE generator to sync byte yields.

    Runs the async generator in a new event loop and yields SSE-formatted
    bytes for each event. Handles client disconnection gracefully.

    Args:
        async_gen: Async generator yielding event dicts
        connection_id: Connection ID for logging
    """
    loop = asyncio.new_event_loop()
    try:
        # Collect events from async generator one at a time
        # We use __anext__() in a sync loop to yield between events
        async def _get_next():
            return await async_gen.__anext__()

        while True:
            try:
                event_dict = loop.run_until_complete(_get_next())
                yield _format_sse_event(event_dict)
            except StopAsyncIteration:
                break
            except (OSError, BrokenPipeError, RuntimeError) as e:
                logger.info(
                    "Client disconnected during streaming",
                    extra={"connection_id": connection_id, "error": str(e)},
                )
                break
    finally:
        # Clean up the async generator
        try:
            loop.run_until_complete(async_gen.aclose())
        except Exception as exc:
            logger.debug("Async generator cleanup: %s", exc)
        loop.close()


# =============================================================================
# Lambda Handler Entry Point
# =============================================================================


def handler(event: dict, context) -> Generator[bytes]:
    """Lambda handler for RESPONSE_STREAM invoke mode (custom runtime).

    Called by bootstrap.py which streams yielded bytes to the Lambda Runtime API.
    Returns a generator that yields bytes for streaming, or yields a single
    complete response for non-streaming endpoints.

    Args:
        event: Lambda event dict (Function URL format)
        context: Lambda context (unused, passed by bootstrap as None)

    Yields:
        Response bytes — metadata prelude followed by body chunks
    """
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
        path = event.get("rawPath", event.get("path", "/"))

        # Normalize double slashes in request paths
        if "//" in path:
            path = re.sub(r"/+", "/", path)

        if method == "GET" and path == "/api/v2/stream/status":
            yield from _handle_stream_status()
            return

        if method == "GET" and path == "/api/v2/stream":
            yield from _handle_global_stream(event)
            return

        if method == "GET":
            config_id = _match_config_stream_path(path)
            if config_id:
                yield from _handle_config_stream(event, config_id)
                return

        logger.warning(
            "Route not found",
            extra={"method": method, "path": sanitize_for_log(path)},
        )
        yield _error_metadata_and_body(404, "Not found")

    except Exception as e:
        logger.error(
            "Unhandled exception in handler",
            extra={
                "path": sanitize_for_log(event.get("rawPath", event.get("path", ""))),
                "error": str(e),
            },
            exc_info=True,
        )
        yield _error_metadata_and_body(500, "Internal server error")

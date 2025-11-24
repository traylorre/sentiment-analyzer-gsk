"""
Dashboard Lambda Handler
========================

FastAPI application serving the sentiment analyzer dashboard with SSE updates.

For On-Call Engineers:
    If dashboard is not accessible:
    1. Check Lambda Function URL is configured correctly
    2. Verify CORS is enabled in Lambda response
    3. Check API_KEY environment variable is set
    4. Verify DynamoDB table exists and Lambda has permissions

    If SSE stream disconnects:
    1. Check Lambda timeout (must be > 30s for SSE)
    2. Verify client is reconnecting on disconnect
    3. Check CloudWatch for Lambda errors

    See SC-05 in ON_CALL_SOP.md for dashboard-related incidents.

For Developers:
    - Uses Mangum adapter for Lambda Function URL compatibility
    - SSE endpoint polls DynamoDB every 5 seconds
    - API key validation uses constant-time comparison
    - Static files served from /static/ prefix
    - CORS enabled for all origins (demo configuration)

Security Notes:
    - API key required for all /api/* endpoints
    - Use secrets.compare_digest() to prevent timing attacks
    - Static files served without authentication
    - No sensitive data in SSE stream (already sanitized by metrics module)
"""

import asyncio
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import APIKeyHeader
from mangum import Mangum
from sse_starlette.sse import EventSourceResponse

from src.lambdas.dashboard.metrics import (
    aggregate_dashboard_metrics,
    get_recent_items,
    sanitize_item_for_response,
)
from src.lambdas.shared.dynamodb import get_table, parse_dynamodb_item
from src.lambdas.shared.logging_utils import (
    get_safe_error_info,
    get_safe_error_message_for_user,
    sanitize_path_component,
)

# Structured logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configuration from environment
# CRITICAL: These must be set - no defaults to prevent wrong-environment data corruption
# Cloud-agnostic: Use DATABASE_TABLE, fallback to DYNAMODB_TABLE for backward compatibility
DYNAMODB_TABLE = os.environ.get("DATABASE_TABLE") or os.environ["DYNAMODB_TABLE"]
SSE_POLL_INTERVAL = int(
    os.environ.get("SSE_POLL_INTERVAL", "5")
)  # Safe default: polling frequency
ENVIRONMENT = os.environ["ENVIRONMENT"]

# SSE connection tracking (P0-2 mitigation: prevent concurrency exhaustion)
MAX_SSE_CONNECTIONS_PER_IP = int(os.environ.get("MAX_SSE_CONNECTIONS_PER_IP", "2"))
sse_connections: dict[str, int] = {}  # ip_address -> active_connection_count


def get_api_key() -> str:
    """Get API key from environment (lazy load to support test mocking)."""
    return os.environ.get("API_KEY", "")


def get_cors_origins() -> list[str]:
    """
    Get CORS allowed origins from environment.

    Returns localhost for dev/test, specific domains for production.
    Production REQUIRES explicit CORS_ORIGINS configuration.
    """
    cors_origins = os.environ.get("CORS_ORIGINS", "")
    if cors_origins:
        return [origin.strip() for origin in cors_origins.split(",")]

    # Default: environment-based CORS (dev/test only)
    if ENVIRONMENT in ("dev", "test", "preprod"):
        # Allow localhost for local development and preprod testing
        return ["http://localhost:3000", "http://127.0.0.1:3000"]
    else:
        # Production: no defaults, must be explicitly configured via CORS_ORIGINS
        logger.error(
            "CORS_ORIGINS not configured for production - dashboard will reject cross-origin requests",
            extra={"environment": ENVIRONMENT},
        )
        return []


# Path to static dashboard files
STATIC_DIR = Path(__file__).parent.parent.parent / "dashboard"

# API key header
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Logs startup and shutdown events for monitoring.
    """
    logger.info(
        "Dashboard Lambda starting",
        extra={
            "environment": ENVIRONMENT,
            "table": DYNAMODB_TABLE,
        },
    )
    yield
    logger.info("Dashboard Lambda shutting down")


# Create FastAPI app
app = FastAPI(
    title="Sentiment Analyzer Dashboard",
    description="Real-time sentiment analysis dashboard with SSE updates",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS (P0-5 mitigation: no wildcard in production)
# Environment-based CORS configuration
cors_origins = get_cors_origins()
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,  # Not needed for Bearer token auth
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    logger.info(
        "CORS configured",
        extra={"allowed_origins": cors_origins, "environment": ENVIRONMENT},
    )
else:
    logger.error(
        "CORS not configured - API will reject cross-origin requests",
        extra={"environment": ENVIRONMENT},
    )


def verify_api_key(
    request: Request,
    authorization: str | None = Depends(api_key_header),
) -> bool:
    """
    Verify API key from Authorization header.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        request: FastAPI request object (for IP logging)
        authorization: Authorization header value (Bearer <key>)

    Returns:
        True if valid

    Raises:
        HTTPException: If API key is invalid or missing

    On-Call Note:
        If all API requests return 401:
        1. Verify API_KEY environment variable is set
        2. Check client is sending correct Authorization header
        3. Format: "Bearer <api-key>"

    Security Note (P1-2):
        Logs client IP on authentication failures for forensics.
    """
    # Get client IP for logging (behind Lambda Function URL / API Gateway)
    client_ip = request.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()

    api_key = get_api_key()

    if not api_key:
        # No API key configured - allow access (dev mode only)
        logger.warning(
            "API_KEY not configured - allowing unauthenticated access",
            extra={"environment": ENVIRONMENT, "client_ip": client_ip},
        )
        return True

    if not authorization:
        logger.warning(
            "Missing Authorization header",
            extra={"client_ip": client_ip, "path": request.url.path},
        )
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning(
            "Invalid Authorization header format",
            extra={"client_ip": client_ip, "path": request.url.path},
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Use: Bearer <api-key>",
        )

    provided_key = parts[1]

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(provided_key, api_key):
        logger.warning(
            "Invalid API key attempt",
            extra={
                "environment": ENVIRONMENT,
                "client_ip": client_ip,
                "path": request.url.path,
                "key_prefix": provided_key[:8] if len(provided_key) >= 8 else "short",
            },
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    return True


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """
    Serve the main dashboard HTML page.

    Returns:
        HTML content of index.html

    On-Call Note:
        If this returns 404, verify:
        1. src/dashboard/index.html exists
        2. Lambda deployment includes dashboard files
    """
    index_path = STATIC_DIR / "index.html"

    if not index_path.exists():
        logger.error(
            "index.html not found",
            extra={"path": str(index_path)},
        )
        raise HTTPException(
            status_code=404,
            detail="Dashboard index.html not found",
        )

    return FileResponse(index_path, media_type="text/html")


@app.get("/static/{filepath:path}")
async def serve_static(filepath: str):
    """
    Serve static dashboard files (CSS, JS, vendor libraries).

    Supports subdirectories for vendor libraries (e.g., /static/vendor/htmx.min.js).

    Args:
        filepath: Path to static file (may include subdirectories)

    Returns:
        File content with appropriate media type

    Security Note:
        Path traversal prevented using sanitize_path_component() utility.
        Each path component validated separately to prevent directory traversal.
    """
    # Split path and sanitize each component
    path_parts = filepath.split("/")
    sanitized_parts = []

    for part in path_parts:
        sanitized = sanitize_path_component(part)
        if not sanitized:
            logger.warning(
                "Path traversal attempt blocked",
                extra={"client_ip": "unknown", "attempted_path": filepath},
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid file path",
            )
        sanitized_parts.append(sanitized)

    # Build safe file path
    file_path = STATIC_DIR
    for part in sanitized_parts:
        file_path = file_path / part

    # Verify path is within STATIC_DIR (defense in depth)
    try:
        file_path.resolve().relative_to(STATIC_DIR.resolve())
    except ValueError as e:
        logger.error(
            "Path traversal attempt escaped STATIC_DIR",
            extra={"attempted_path": filepath, "resolved_path": str(file_path)},
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid file path",
        ) from e

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Static file not found",  # Don't expose user input in error
        )

    # Determine media type
    media_types = {
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".ico": "image/x-icon",
    }

    suffix = file_path.suffix.lower()
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(file_path, media_type=media_type)


@app.get("/health")
async def health_check():
    """
    Health check endpoint with DynamoDB connectivity test.

    Returns:
        JSON with status and optional error details

    On-Call Note:
        If health check fails:
        1. Check DynamoDB table exists
        2. Verify Lambda IAM role has dynamodb:DescribeTable permission
        3. Check network connectivity (VPC configuration)
    """
    try:
        table = get_table(DYNAMODB_TABLE)

        # Test connectivity by describing table
        _ = table.table_status  # This triggers a DescribeTable call

        return JSONResponse(
            {
                "status": "healthy",
                "table": DYNAMODB_TABLE,
                "environment": ENVIRONMENT,
            }
        )

    except Exception as e:
        logger.error(
            "Health check failed",
            extra={"table": DYNAMODB_TABLE, **get_safe_error_info(e)},
        )

        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": get_safe_error_message_for_user(e),
                "table": DYNAMODB_TABLE,
            },
        )


@app.get("/api/metrics")
async def get_metrics(
    hours: int = 24,
    _: bool = Depends(verify_api_key),
):
    """
    Get aggregated dashboard metrics.

    Args:
        hours: Time window for metrics (default: 24)

    Returns:
        JSON with sentiment distribution, tag distribution, rates, recent items

    On-Call Note:
        If metrics are all zeros:
        1. Check DynamoDB GSIs exist (by_sentiment, by_tag, by_status)
        2. Verify items have been ingested and analyzed
        3. Check time window covers expected data
    """
    if hours < 1 or hours > 168:  # Max 7 days
        raise HTTPException(
            status_code=400,
            detail="Hours must be between 1 and 168",
        )

    try:
        table = get_table(DYNAMODB_TABLE)
        metrics = aggregate_dashboard_metrics(table, hours)

        # Sanitize recent items
        metrics["recent_items"] = [
            sanitize_item_for_response(parse_dynamodb_item(item))
            for item in metrics.get("recent_items", [])
        ]

        logger.info(
            "Metrics retrieved",
            extra={
                "total": metrics.get("total", 0),
                "hours": hours,
            },
        )

        return JSONResponse(metrics)

    except Exception as e:
        logger.error(
            "Failed to get metrics",
            extra={"hours": hours, **get_safe_error_info(e)},
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve metrics",
        ) from e


@app.get("/api/stream")
async def stream_metrics(
    request: Request,
    _: bool = Depends(verify_api_key),
):
    """
    Server-Sent Events endpoint for real-time dashboard updates.

    Polls DynamoDB every SSE_POLL_INTERVAL seconds and sends metrics.

    Returns:
        EventSourceResponse with metrics updates

    On-Call Note:
        If SSE disconnects frequently:
        1. Check Lambda timeout (should be > 30s)
        2. Verify client reconnects on disconnect
        3. Check for Lambda cold starts causing delays

    Security Note (P0-2):
        Connection limits enforced per IP to prevent concurrency exhaustion.
        Max connections per IP: MAX_SSE_CONNECTIONS_PER_IP (default: 2)
    """
    # Get client IP from headers (behind Lambda Function URL / API Gateway)
    client_ip = request.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()

    # P0-2 mitigation: Enforce SSE connection limit per IP
    current_connections = sse_connections.get(client_ip, 0)
    if current_connections >= MAX_SSE_CONNECTIONS_PER_IP:
        logger.warning(
            "SSE connection limit exceeded",
            extra={
                "client_ip": client_ip,
                "current_connections": current_connections,
                "max_allowed": MAX_SSE_CONNECTIONS_PER_IP,
            },
        )
        raise HTTPException(
            status_code=429,
            detail=f"Too many SSE connections from your IP. Max: {MAX_SSE_CONNECTIONS_PER_IP}",
        )

    # Increment connection count
    sse_connections[client_ip] = current_connections + 1
    logger.info(
        "SSE connection established",
        extra={
            "client_ip": client_ip,
            "total_connections": sse_connections[client_ip],
        },
    )

    async def event_generator():
        """Generate SSE events with metrics updates."""
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(
                        "SSE client disconnected",
                        extra={"client_ip": client_ip},
                    )
                    break

                try:
                    table = get_table(DYNAMODB_TABLE)
                    metrics = aggregate_dashboard_metrics(table, hours=24)

                    # Sanitize recent items
                    metrics["recent_items"] = [
                        sanitize_item_for_response(parse_dynamodb_item(item))
                        for item in metrics.get("recent_items", [])
                    ]

                    # Send metrics event
                    yield {
                        "event": "metrics",
                        "data": json.dumps(metrics),
                    }

                except Exception as e:
                    logger.error(
                        "SSE metrics error",
                        extra={**get_safe_error_info(e)},
                    )
                    # Send error event but keep connection alive
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": "Failed to retrieve metrics"}),
                    }

                # Wait before next poll
                await asyncio.sleep(SSE_POLL_INTERVAL)

        except asyncio.CancelledError:
            logger.info(
                "SSE stream cancelled",
                extra={"client_ip": client_ip},
            )
            raise
        finally:
            # Decrement connection count when stream ends
            if client_ip in sse_connections:
                sse_connections[client_ip] -= 1
                if sse_connections[client_ip] <= 0:
                    del sse_connections[client_ip]
                logger.info(
                    "SSE connection closed",
                    extra={
                        "client_ip": client_ip,
                        "remaining_connections": sse_connections.get(client_ip, 0),
                    },
                )

    return EventSourceResponse(event_generator())


@app.get("/api/items")
async def get_items(
    limit: int = 20,
    status: str = "analyzed",
    _: bool = Depends(verify_api_key),
):
    """
    Get recent items with optional filtering.

    Args:
        limit: Maximum items to return (default: 20, max: 100)
        status: Filter by status (default: analyzed)

    Returns:
        JSON array of recent items
    """
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100",
        )

    if status not in ["pending", "analyzed", "failed"]:
        raise HTTPException(
            status_code=400,
            detail="Status must be: pending, analyzed, or failed",
        )

    try:
        table = get_table(DYNAMODB_TABLE)
        items = get_recent_items(table, limit=limit, status=status)

        # Sanitize items
        sanitized = [
            sanitize_item_for_response(parse_dynamodb_item(item)) for item in items
        ]

        return JSONResponse(sanitized)

    except Exception as e:
        logger.error(
            "Failed to get items",
            extra={"limit": limit, "status": status, **get_safe_error_info(e)},
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve items",
        ) from e


# Mangum adapter for AWS Lambda
handler = Mangum(app, lifespan="off")


# Lambda handler function
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda entry point.

    Wraps the FastAPI app with Mangum for Lambda Function URL compatibility.

    Args:
        event: Lambda event (API Gateway or Function URL format)
        context: Lambda context

    Returns:
        HTTP response dict

    On-Call Note:
        If Lambda returns 500 errors:
        1. Check CloudWatch logs for detailed error
        2. Verify all environment variables are set
        3. Check IAM permissions for DynamoDB access
    """
    logger.info(
        "Dashboard Lambda invoked",
        extra={
            "path": event.get("rawPath", event.get("path", "unknown")),
            "method": event.get("requestContext", {})
            .get("http", {})
            .get("method", "unknown"),
        },
    )

    return handler(event, context)

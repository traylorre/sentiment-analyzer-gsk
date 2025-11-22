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


def get_api_key() -> str:
    """Get API key from environment (lazy load to support test mocking)."""
    return os.environ.get("API_KEY", "")


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

# Configure CORS
# Note: In production, restrict origins to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Demo configuration - restrict in production
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def verify_api_key(authorization: str | None = Depends(api_key_header)) -> bool:
    """
    Verify API key from Authorization header.

    Uses constant-time comparison to prevent timing attacks.

    Args:
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
    """
    api_key = get_api_key()

    if not api_key:
        # No API key configured - allow access (dev mode only)
        logger.warning(
            "API_KEY not configured - allowing unauthenticated access",
            extra={"environment": ENVIRONMENT},
        )
        return True

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Use: Bearer <api-key>",
        )

    provided_key = parts[1]

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(provided_key, api_key):
        logger.warning(
            "Invalid API key attempt",
            extra={"environment": ENVIRONMENT},
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


@app.get("/static/{filename}")
async def serve_static(filename: str):
    """
    Serve static dashboard files (CSS, JS).

    Args:
        filename: Name of static file

    Returns:
        File content with appropriate media type

    Security Note:
        Path traversal prevented by only allowing filenames, not paths.
    """
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename",
        )

    file_path = STATIC_DIR / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Static file not found: {filename}",
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
            extra={"error": str(e), "table": DYNAMODB_TABLE},
        )

        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
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
            extra={"hours": hours, "error": str(e)},
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
    """

    async def event_generator():
        """Generate SSE events with metrics updates."""
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected")
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
                        extra={"error": str(e)},
                    )
                    # Send error event but keep connection alive
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": "Failed to retrieve metrics"}),
                    }

                # Wait before next poll
                await asyncio.sleep(SSE_POLL_INTERVAL)

        except asyncio.CancelledError:
            logger.info("SSE stream cancelled")
            raise

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
            extra={"limit": limit, "status": status, "error": str(e)},
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

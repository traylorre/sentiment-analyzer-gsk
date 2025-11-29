"""
Dashboard Lambda Handler
========================

FastAPI application serving the sentiment analyzer dashboard API v2.

For On-Call Engineers:
    If dashboard is not accessible:
    1. Check Lambda Function URL is configured correctly
    2. Verify CORS is enabled in Lambda response
    3. Check API_KEY environment variable is set
    4. Verify DynamoDB table exists and Lambda has permissions

    See SC-05 in ON_CALL_SOP.md for dashboard-related incidents.

For Developers:
    - Uses Mangum adapter for Lambda Function URL compatibility
    - API key validation uses constant-time comparison
    - Static files served from /static/ prefix
    - CORS enabled for all origins (demo configuration)

Security Notes:
    - API key required for all /api/* endpoints
    - Use secrets.compare_digest() to prevent timing attacks
    - Static files served without authentication

X-Ray Tracing:
    X-Ray is enabled for distributed tracing across all Lambda invocations.
    This is Day 1 mandatory per constitution v1.1.
"""

# X-Ray must be imported and patched before other imports
from aws_xray_sdk.core import patch_all  # noqa: E402

patch_all()

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

from src.lambdas.dashboard.api_v2 import (
    get_articles_by_tags,
    get_sentiment_by_tags,
    get_trend_data,
)
from src.lambdas.dashboard.chaos import (
    ChaosError,
    EnvironmentNotAllowedError,
    create_experiment,
    delete_experiment,
    get_experiment,
    get_fis_experiment_status,
    list_experiments,
    start_experiment,
    stop_experiment,
)
from src.lambdas.dashboard.metrics import sanitize_item_for_response
from src.lambdas.shared.dynamodb import get_table, parse_dynamodb_item
from src.lambdas.shared.logging_utils import (
    get_safe_error_info,
    get_safe_error_message_for_user,
    sanitize_for_log,
)

# Structured logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configuration from environment
# CRITICAL: These must be set - no defaults to prevent wrong-environment data corruption
# Cloud-agnostic: Use DATABASE_TABLE, fallback to DYNAMODB_TABLE for backward compatibility
DYNAMODB_TABLE = os.environ.get("DATABASE_TABLE") or os.environ["DYNAMODB_TABLE"]
CHAOS_EXPERIMENTS_TABLE = os.environ.get("CHAOS_EXPERIMENTS_TABLE", "")
ENVIRONMENT = os.environ["ENVIRONMENT"]


def get_api_key() -> str:
    """
    Get API key from environment or Secrets Manager.

    Fallback chain:
    1. API_KEY environment variable (set by CI or for testing)
    2. DASHBOARD_API_KEY_SECRET_ARN -> fetch from Secrets Manager

    Returns:
        API key string, or empty string if not configured
    """
    # First check env var (takes precedence, allows test mocking)
    api_key = os.environ.get("API_KEY", "")
    if api_key:
        return api_key

    # Fall back to Secrets Manager if ARN is provided
    secret_arn = os.environ.get("DASHBOARD_API_KEY_SECRET_ARN", "")
    if secret_arn:
        try:
            from src.lambdas.shared.secrets import get_api_key as fetch_api_key

            return fetch_api_key(secret_arn)
        except Exception as e:
            logger.error(
                "Failed to fetch API key from Secrets Manager",
                extra={"error": str(e)},
            )
            # Don't expose error details - just return empty to enforce auth
            return ""

    return ""


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
# In Lambda, handler.py is at ROOT (/var/task/) and static files are at /var/task/src/dashboard/
# Locally, handler.py is at src/lambdas/dashboard/ and static files are at src/dashboard/
_handler_dir = Path(__file__).parent
if _handler_dir.name == "task" or str(_handler_dir) == "/var/task":
    # Lambda runtime: handler.py at ROOT
    STATIC_DIR = _handler_dir / "src" / "dashboard"
else:
    # Local development: handler.py at src/lambdas/dashboard/
    STATIC_DIR = _handler_dir.parent.parent / "dashboard"

# Whitelist of allowed static files (path injection defense - CodeQL py/path-injection)
# Only these files can be served via /static/ endpoint
ALLOWED_STATIC_FILES: dict[str, str] = {
    "app.js": "application/javascript",
    "config.js": "application/javascript",
    "styles.css": "text/css",
}

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

# Include Feature 006 API v2 routers
from src.lambdas.dashboard.router_v2 import include_routers

include_routers(app)
logger.info("Feature 006 API v2 routers included")


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


@app.get("/chaos", response_class=HTMLResponse)
async def serve_chaos():
    """
    Serve the chaos testing UI page.

    Returns:
        HTML content of chaos.html

    On-Call Note:
        If this returns 404, verify:
        1. src/dashboard/chaos.html exists
        2. Lambda deployment includes chaos.html
    """
    chaos_path = STATIC_DIR / "chaos.html"

    if not chaos_path.exists():
        logger.error(
            "chaos.html not found",
            extra={"path": str(chaos_path)},
        )
        raise HTTPException(
            status_code=404,
            detail="Chaos testing page not found",
        )

    return FileResponse(chaos_path, media_type="text/html")


@app.get("/static/{filename}")
async def serve_static(filename: str):
    """
    Serve static dashboard files (CSS, JS).

    Args:
        filename: Name of static file

    Returns:
        File content with appropriate media type

    Security Note:
        Path injection prevented using strict whitelist (ALLOWED_STATIC_FILES).
        Only pre-approved files can be served - no user input reaches filesystem.
    """
    # Whitelist-based routing - completely eliminates path injection risk
    # CodeQL py/path-injection: Use explicit string literals for file paths
    # Each case uses a hardcoded string, not user input
    if filename == "app.js":
        safe_path = STATIC_DIR / "app.js"
        media_type = "application/javascript"
    elif filename == "config.js":
        safe_path = STATIC_DIR / "config.js"
        media_type = "application/javascript"
    elif filename == "styles.css":
        safe_path = STATIC_DIR / "styles.css"
        media_type = "text/css"
    else:
        logger.warning(
            "Static file request for non-whitelisted file",
            extra={"requested": sanitize_for_log(filename)},
        )
        raise HTTPException(
            status_code=404,
            detail="Static file not found",
        )

    if not safe_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Static file not found",
        )

    return FileResponse(safe_path, media_type=media_type)


@app.get("/api")
async def api_index():
    """
    API index listing all available endpoints.

    Returns:
        JSON with categorized list of all API endpoints
    """
    return JSONResponse(
        {
            "name": "Sentiment Analyzer API",
            "version": "2.0",
            "endpoints": {
                "health": {
                    "GET /health": "Health check with DynamoDB connectivity test",
                },
                "sentiment": {
                    "GET /api/v2/sentiment": "Get sentiment data by tags",
                    "GET /api/v2/trends": "Get sentiment trends",
                    "GET /api/v2/articles": "Get news articles",
                },
                "auth": {
                    "POST /api/v2/auth/anonymous": "Create anonymous session",
                    "GET /api/v2/auth/validate": "Validate token",
                    "POST /api/v2/auth/extend": "Extend session",
                    "POST /api/v2/auth/magic-link": "Send magic link email",
                    "GET /api/v2/auth/magic-link/verify": "Verify magic link",
                    "GET /api/v2/auth/oauth/urls": "Get OAuth authorization URLs",
                    "POST /api/v2/auth/oauth/callback": "OAuth callback",
                    "POST /api/v2/auth/refresh": "Refresh access token",
                    "POST /api/v2/auth/signout": "Sign out",
                    "GET /api/v2/auth/session": "Get current session",
                    "GET /api/v2/auth/me": "Get current user profile",
                },
                "configurations": {
                    "POST /api/v2/configurations": "Create configuration",
                    "GET /api/v2/configurations": "List configurations",
                    "GET /api/v2/configurations/{id}": "Get configuration",
                    "PATCH /api/v2/configurations/{id}": "Update configuration",
                    "DELETE /api/v2/configurations/{id}": "Delete configuration",
                    "GET /api/v2/configurations/{id}/sentiment": "Get sentiment data",
                    "GET /api/v2/configurations/{id}/sentiment/{ticker}/history": "Get ticker sentiment history",
                    "GET /api/v2/configurations/{id}/heatmap": "Get heat map data",
                    "GET /api/v2/configurations/{id}/volatility": "Get volatility data",
                    "GET /api/v2/configurations/{id}/correlation": "Get correlation data",
                    "GET /api/v2/configurations/{id}/alerts": "Get config alerts",
                    "POST /api/v2/configurations/{id}/refresh": "Trigger refresh",
                    "GET /api/v2/configurations/{id}/refresh/status": "Get refresh status",
                    "GET /api/v2/configurations/{id}/premarket": "Get pre-market data",
                },
                "tickers": {
                    "GET /api/v2/tickers/search": "Search tickers",
                    "GET /api/v2/tickers/validate": "Validate ticker symbol",
                },
                "alerts": {
                    "POST /api/v2/alerts": "Create alert",
                    "GET /api/v2/alerts": "List alerts",
                    "GET /api/v2/alerts/{id}": "Get alert",
                    "PATCH /api/v2/alerts/{id}": "Update alert",
                    "DELETE /api/v2/alerts/{id}": "Delete alert",
                    "POST /api/v2/alerts/{id}/toggle": "Toggle alert enabled",
                },
                "notifications": {
                    "GET /api/v2/notifications": "List notifications",
                    "GET /api/v2/notifications/{id}": "Get notification",
                    "GET /api/v2/notifications/preferences": "Get notification preferences",
                    "PATCH /api/v2/notifications/preferences": "Update preferences",
                    "POST /api/v2/notifications/disable-all": "Disable all notifications",
                    "GET /api/v2/notifications/unsubscribe": "Unsubscribe from notifications",
                    "POST /api/v2/notifications/resubscribe": "Resubscribe to notifications",
                    "GET /api/v2/notifications/digest": "Get digest settings",
                    "PATCH /api/v2/notifications/digest": "Update digest settings",
                    "POST /api/v2/notifications/digest/test": "Send test digest",
                },
                "market": {
                    "GET /api/v2/market/status": "Get market status",
                },
                "chaos": {
                    "POST /chaos/experiments": "Create chaos experiment",
                    "GET /chaos/experiments": "List experiments",
                    "GET /chaos/experiments/{id}": "Get experiment",
                    "POST /chaos/experiments/{id}/start": "Start experiment",
                    "POST /chaos/experiments/{id}/stop": "Stop experiment",
                    "DELETE /chaos/experiments/{id}": "Delete experiment",
                },
            },
            "docs": {
                "openapi": "/docs",
                "redoc": "/redoc",
            },
        }
    )


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


# ===================================================================
# API v2 Endpoints (POWERPLAN Mobile Dashboard)
# ===================================================================


@app.get("/api/v2/sentiment")
async def get_sentiment_v2(
    request: Request,
    tags: str,
    start: str | None = None,
    end: str | None = None,
    _: bool = Depends(verify_api_key),
):
    """
    Get aggregated sentiment for multiple tags (POWERPLAN).

    Query Parameters:
        tags: Comma-separated list of topic tags (max 5)
        start: ISO8601 start timestamp (default: 24 hours ago)
        end: ISO8601 end timestamp (default: now)

    Returns:
        JSON with per-tag sentiment breakdown and overall aggregate

    Example:
        GET /api/v2/sentiment?tags=AI,climate,economy&start=2025-11-24T00:00:00Z

    On-Call Note:
        If all sentiment values are 0:
        1. Verify by_tag GSI exists on the table
        2. Check items exist with matching tags
        3. Verify time range covers existing data
    """
    from datetime import UTC, datetime, timedelta

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        raise HTTPException(
            status_code=400,
            detail="At least one tag is required",
        )
    if len(tag_list) > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 tags allowed",
        )

    # Parse time range
    now = datetime.now(UTC)
    if not end:
        end_time = now.isoformat()
    else:
        end_time = end

    if not start:
        start_time = (now - timedelta(hours=24)).isoformat()
    else:
        start_time = start

    try:
        table = get_table(DYNAMODB_TABLE)
        result = get_sentiment_by_tags(table, tag_list, start_time, end_time)
        return JSONResponse(result)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    except Exception as e:
        logger.error(
            "Failed to get sentiment by tags",
            extra={
                "tags": sanitize_for_log(",".join(tag_list)),
                **get_safe_error_info(e),
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve sentiment data",
        ) from e


@app.get("/api/v2/trends")
async def get_trends_v2(
    request: Request,
    tags: str,
    interval: str = "1h",
    range: str = "24h",
    _: bool = Depends(verify_api_key),
):
    """
    Get trend data for sparkline visualizations (POWERPLAN).

    Query Parameters:
        tags: Comma-separated list of topic tags (max 5)
        interval: Time interval for aggregation (1h, 6h, 1d)
        range: Time range to look back (e.g., 24h, 7d)

    Returns:
        JSON with time-series data for each tag

    Example:
        GET /api/v2/trends?tags=AI,climate&interval=1h&range=7d

    On-Call Note:
        If trend data is empty or sparse:
        1. Verify ingestion is running
        2. Check time range covers data ingestion period
        3. Verify by_tag GSI exists
    """
    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        raise HTTPException(
            status_code=400,
            detail="At least one tag is required",
        )
    if len(tag_list) > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 tags allowed",
        )

    # Validate interval
    if interval not in ["1h", "6h", "1d"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid interval. Use: 1h, 6h, or 1d",
        )

    # Parse range to hours
    range_hours = 24  # default
    if range.endswith("h"):
        try:
            range_hours = int(range[:-1])
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail="Invalid range format. Use: Nh (e.g., 24h) or Nd (e.g., 7d)",
            ) from e
    elif range.endswith("d"):
        try:
            range_hours = int(range[:-1]) * 24
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail="Invalid range format. Use: Nh (e.g., 24h) or Nd (e.g., 7d)",
            ) from e
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid range format. Use: Nh (e.g., 24h) or Nd (e.g., 7d)",
        )

    # Cap at 7 days
    if range_hours > 168:
        range_hours = 168

    try:
        table = get_table(DYNAMODB_TABLE)
        result = get_trend_data(table, tag_list, interval, range_hours)
        return JSONResponse(result)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    except Exception as e:
        logger.error(
            "Failed to get trend data",
            extra={
                "tags": sanitize_for_log(",".join(tag_list)),
                "interval": interval,
                **get_safe_error_info(e),
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve trend data",
        ) from e


@app.get("/api/v2/articles")
async def get_articles_v2(
    request: Request,
    tags: str,
    limit: int = 20,
    sentiment: str | None = None,
    _: bool = Depends(verify_api_key),
):
    """
    Get recent articles for specified tags (POWERPLAN).

    Query Parameters:
        tags: Comma-separated list of topic tags (max 5)
        limit: Maximum articles to return (default: 20, max: 100)
        sentiment: Optional filter (positive, neutral, negative)

    Returns:
        JSON array of articles sorted by timestamp descending

    Example:
        GET /api/v2/articles?tags=AI,climate&limit=10&sentiment=positive

    On-Call Note:
        If articles list is empty:
        1. Verify by_tag GSI exists
        2. Check ingestion is working
        3. Verify sentiment filter matches existing data
    """
    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        raise HTTPException(
            status_code=400,
            detail="At least one tag is required",
        )
    if len(tag_list) > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 tags allowed",
        )

    # Validate limit
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100",
        )

    # Validate sentiment filter
    if sentiment and sentiment.lower() not in ["positive", "neutral", "negative"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid sentiment. Use: positive, neutral, or negative",
        )

    try:
        table = get_table(DYNAMODB_TABLE)
        articles = get_articles_by_tags(
            table,
            tag_list,
            limit=limit,
            sentiment_filter=sentiment,
        )

        # Sanitize articles for response
        sanitized = [
            sanitize_item_for_response(parse_dynamodb_item(item)) for item in articles
        ]

        return JSONResponse(sanitized)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    except Exception as e:
        logger.error(
            "Failed to get articles by tags",
            extra={
                "tags": sanitize_for_log(",".join(tag_list)),
                **get_safe_error_info(e),
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve articles",
        ) from e


# ===================================================================
# Chaos Testing Endpoints (Phase 1b)
# ===================================================================


@app.post("/chaos/experiments")
async def create_chaos_experiment(
    request: Request,
    _: bool = Depends(verify_api_key),
):
    """
    Create a new chaos experiment.

    Request body:
        {
            "scenario_type": "dynamodb_throttle|newsapi_failure|lambda_cold_start",
            "blast_radius": 10-100,
            "duration_seconds": 5-300,
            "parameters": {}
        }

    Returns:
        Created experiment JSON

    Security Note:
        Environment gating enforced in chaos module (preprod only).
    """
    try:
        body = await request.json()

        experiment = create_experiment(
            scenario_type=body["scenario_type"],
            blast_radius=body["blast_radius"],
            duration_seconds=body["duration_seconds"],
            parameters=body.get("parameters"),
        )

        return JSONResponse(experiment, status_code=201)

    except EnvironmentNotAllowedError as e:
        logger.warning(
            "Chaos testing attempted in disallowed environment",
            extra={"environment": ENVIRONMENT},
        )
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e

    except (KeyError, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {e}",
        ) from e

    except ChaosError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create experiment: {e}",
        ) from e


@app.get("/chaos/experiments")
async def list_chaos_experiments(
    status: str | None = None,
    limit: int = 20,
    _: bool = Depends(verify_api_key),
):
    """
    List chaos experiments with optional status filter.

    Query parameters:
        status: Optional filter (pending|running|completed|failed|stopped)
        limit: Maximum experiments to return (default: 20, max: 100)

    Returns:
        Array of experiment JSON objects
    """
    try:
        experiments = list_experiments(status=status, limit=limit)
        return JSONResponse(experiments)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e


@app.get("/chaos/experiments/{experiment_id}")
async def get_chaos_experiment(
    experiment_id: str,
    _: bool = Depends(verify_api_key),
):
    """
    Get chaos experiment by ID with enriched FIS status.

    Path parameters:
        experiment_id: Experiment UUID

    Returns:
        Experiment JSON with FIS status (if applicable) or 404 if not found

    Phase 2.2 Enhancement:
        Enriches response with real-time FIS experiment status for DynamoDB throttle scenarios.
    """
    experiment = get_experiment(experiment_id)

    if not experiment:
        raise HTTPException(
            status_code=404,
            detail="Experiment not found",
        )

    # Enrich with FIS status if experiment is running and has FIS experiment ID
    if (
        experiment.get("status") == "running"
        and experiment.get("scenario_type") == "dynamodb_throttle"
        and experiment.get("results", {}).get("fis_experiment_id")
    ):
        try:
            fis_experiment_id = experiment["results"]["fis_experiment_id"]
            fis_status = get_fis_experiment_status(fis_experiment_id)
            experiment["fis_status"] = fis_status
        except Exception as e:
            logger.warning(
                "Failed to fetch FIS experiment status",
                extra={
                    "experiment_id": sanitize_for_log(experiment_id),
                    "fis_experiment_id": sanitize_for_log(fis_experiment_id),
                    "error": sanitize_for_log(str(e)),
                },
            )
            # Don't fail the request if FIS status fetch fails
            experiment["fis_status"] = {"error": "Failed to fetch FIS status"}

    return JSONResponse(experiment)


@app.post("/chaos/experiments/{experiment_id}/start")
async def start_chaos_experiment(
    experiment_id: str,
    _: bool = Depends(verify_api_key),
):
    """
    Start a chaos experiment.

    Path parameters:
        experiment_id: Experiment UUID

    Returns:
        Updated experiment JSON

    Phase 2 Note:
        This endpoint now integrates with AWS FIS for DynamoDB throttling.
        Other scenarios (NewsAPI failure, Lambda delay) will be implemented in Phase 3-4.
    """
    try:
        updated_experiment = start_experiment(experiment_id)
        return JSONResponse(updated_experiment)

    except ChaosError as e:
        logger.error(
            "Chaos experiment start failed",
            extra={
                "experiment_id": sanitize_for_log(experiment_id),
                "error": sanitize_for_log(str(e)),
            },
        )
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e

    except EnvironmentNotAllowedError as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e


@app.post("/chaos/experiments/{experiment_id}/stop")
async def stop_chaos_experiment(
    experiment_id: str,
    _: bool = Depends(verify_api_key),
):
    """
    Stop a running chaos experiment.

    Path parameters:
        experiment_id: Experiment UUID

    Returns:
        Updated experiment JSON

    Phase 2 Note:
        This endpoint now integrates with AWS FIS to stop experiments.
    """
    try:
        updated_experiment = stop_experiment(experiment_id)
        return JSONResponse(updated_experiment)

    except ChaosError as e:
        logger.error(
            "Chaos experiment stop failed",
            extra={
                "experiment_id": sanitize_for_log(experiment_id),
                "error": sanitize_for_log(str(e)),
            },
        )
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e

    except EnvironmentNotAllowedError as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e


@app.delete("/chaos/experiments/{experiment_id}")
async def delete_chaos_experiment(
    experiment_id: str,
    _: bool = Depends(verify_api_key),
):
    """
    Delete a chaos experiment.

    Path parameters:
        experiment_id: Experiment UUID

    Returns:
        Success message
    """
    success = delete_experiment(experiment_id)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete experiment",
        )

    return JSONResponse({"message": "Experiment deleted successfully"})


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

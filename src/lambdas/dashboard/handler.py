"""
Dashboard Lambda Handler
========================

Powertools-based Lambda handler serving the sentiment analyzer dashboard API v2.

For On-Call Engineers:
    If dashboard is not accessible:
    1. Check Lambda Function URL is configured correctly
    2. Verify CORS is enabled in Lambda response
    3. Verify DynamoDB table exists and Lambda has permissions

    See SC-05 in ON_CALL_SOP.md for dashboard-related incidents.

For Developers:
    - Uses AWS Lambda Powertools APIGatewayRestResolver for routing
    - Static files served from /static/ prefix
    - CORS enabled for all origins (demo configuration)

Auth (Feature 1039):
    - All /api/* endpoints use session-based auth via Bearer token
    - Public endpoints (metrics, sentiment, trends, articles) accept anonymous sessions
    - Chaos endpoints require authenticated (non-anonymous) sessions

X-Ray Tracing:
    X-Ray is enabled for distributed tracing across all Lambda invocations.
    This is Day 1 mandatory per constitution v1.1.
"""

# X-Ray must be imported and patched before other imports (FR-034, T017)
from aws_xray_sdk.core import patch_all

patch_all()

import base64
import os
from pathlib import Path
from typing import Any

import orjson
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    Response,
)

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
from src.lambdas.shared.middleware.auth_middleware import (
    AuthType,
    extract_auth_context,
    extract_auth_context_typed,
)
from src.lambdas.shared.utils.event_helpers import get_query_params

# Structured logging (FR-028: module-level logging replaces lifespan)
logger = Logger(service="dashboard")
tracer = Tracer(service="dashboard")

# Configuration from environment
# CRITICAL: These must be set - no defaults to prevent wrong-environment data corruption
USERS_TABLE = os.environ["USERS_TABLE"]
SENTIMENTS_TABLE = os.environ["SENTIMENTS_TABLE"]
CHAOS_EXPERIMENTS_TABLE = os.environ.get("CHAOS_EXPERIMENTS_TABLE", "")
ENVIRONMENT = os.environ["ENVIRONMENT"]
SSE_LAMBDA_URL = os.environ.get("SSE_LAMBDA_URL", "")

# Module-level init logging (FR-028: replaces FastAPI lifespan no-op)
logger.info(
    "Dashboard Lambda starting",
    extra={
        "environment": ENVIRONMENT,
        "table": SENTIMENTS_TABLE,
    },
)

# Path to static dashboard files
_handler_dir = Path(__file__).parent
if _handler_dir.name == "task" or str(_handler_dir) == "/var/task":
    STATIC_DIR = _handler_dir / "src" / "dashboard"
else:
    STATIC_DIR = _handler_dir.parent.parent / "dashboard"

# Whitelist of allowed static files (path injection defense)
ALLOWED_STATIC_FILES: dict[str, str] = {
    "app.js": "application/javascript",
    "cache.js": "application/javascript",
    "config.js": "application/javascript",
    "ohlc.js": "application/javascript",
    "timeseries.js": "application/javascript",
    "unified-resolution.js": "application/javascript",
    "styles.css": "text/css",
    "favicon.ico": "image/x-icon",
}

# Create Powertools resolver (FR-001, R1)
app = APIGatewayRestResolver()

# Include all routers
from src.lambdas.dashboard.router_v2 import include_routers

include_routers(app)
logger.info("API v2 routers included")


# ===================================================================
# Static file and root endpoints (defined on app directly)
# ===================================================================


def _get_user_id_from_event(event: dict, validate_session: bool = True) -> str:
    """Extract user_id from event headers.

    Args:
        event: API Gateway event dict.
        validate_session: Whether to validate session (unused currently).

    Returns:
        user_id string.

    Raises:
        ValueError: If no valid user ID found.
    """
    auth_context = extract_auth_context(event)
    user_id = auth_context.get("user_id")
    if not user_id:
        return ""
    return user_id


def _get_authenticated_user_id_from_event(event: dict) -> str | None:
    """Extract authenticated (non-anonymous) user_id from event.

    Returns:
        user_id string or None if not authenticated.
    """
    auth_context = extract_auth_context_typed(event)
    if auth_context.user_id is None:
        return None
    if auth_context.auth_type == AuthType.ANONYMOUS:
        return None
    return auth_context.user_id


@app.get("/")
def serve_index():
    """Serve the main dashboard HTML page."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        logger.error("index.html not found", extra={"path": str(index_path)})
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps({"detail": "Dashboard index.html not found"}).decode(),
        )
    content = index_path.read_bytes()
    return Response(
        status_code=200,
        content_type="text/html",
        body=content.decode("utf-8"),
    )


@app.get("/favicon.ico")
def serve_favicon():
    """Serve the favicon.ico file (Feature 1096)."""
    favicon_path = STATIC_DIR / "favicon.ico"
    if not favicon_path.exists():
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps({"detail": "Favicon not found"}).decode(),
        )
    content = favicon_path.read_bytes()
    return Response(
        status_code=200,
        content_type="image/x-icon",
        body=base64.b64encode(content).decode("utf-8"),
        headers={"isBase64Encoded": "true"},
    )


@app.get("/chaos")
def serve_chaos():
    """Serve the chaos testing UI page."""
    chaos_path = STATIC_DIR / "chaos.html"
    if not chaos_path.exists():
        logger.error("chaos.html not found", extra={"path": str(chaos_path)})
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps({"detail": "Chaos testing page not found"}).decode(),
        )
    content = chaos_path.read_bytes()
    return Response(
        status_code=200,
        content_type="text/html",
        body=content.decode("utf-8"),
    )


@app.get("/static/<filename>")
def serve_static(filename: str):
    """Serve static dashboard files (CSS, JS) from whitelist."""
    if filename not in ALLOWED_STATIC_FILES:
        logger.warning(
            "Static file request for non-whitelisted file",
            extra={"requested": sanitize_for_log(filename)},
        )
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps({"detail": "Static file not found"}).decode(),
        )

    media_type = ALLOWED_STATIC_FILES[filename]
    # Security: Use hardcoded path lookup to prevent path injection
    safe_path = STATIC_DIR / filename

    if not safe_path.exists():
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps({"detail": "Static file not found"}).decode(),
        )

    content = safe_path.read_bytes()

    # Binary files (favicon) need base64 encoding
    if media_type.startswith("image/"):
        return Response(
            status_code=200,
            content_type=media_type,
            body=base64.b64encode(content).decode("utf-8"),
            headers={"isBase64Encoded": "true"},
        )

    return Response(
        status_code=200,
        content_type=media_type,
        body=content.decode("utf-8"),
    )


@app.get("/api")
def api_index():
    """API index listing all available endpoints."""
    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps(
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
                        "GET /api/v2/tickers/{ticker}/ohlc": "Get OHLC price data",
                        "GET /api/v2/tickers/{ticker}/sentiment/history": "Get sentiment history",
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
            }
        ).decode(),
    )


@app.get("/health")
def health_check():
    """Health check endpoint with DynamoDB connectivity test."""
    try:
        table = get_table(SENTIMENTS_TABLE)
        _ = table.table_status

        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(
                {
                    "status": "healthy",
                    "table": SENTIMENTS_TABLE,
                    "environment": ENVIRONMENT,
                }
            ).decode(),
        )
    except Exception as e:
        logger.error(
            "Health check failed",
            extra={"table": SENTIMENTS_TABLE, **get_safe_error_info(e)},
        )
        return Response(
            status_code=503,
            content_type="application/json",
            body=orjson.dumps(
                {
                    "status": "unhealthy",
                    "error": get_safe_error_message_for_user(e),
                    "table": SENTIMENTS_TABLE,
                }
            ).decode(),
        )


@app.get("/api/v2/runtime")
def get_runtime_config():
    """Get runtime configuration for the frontend (Feature 1097)."""
    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps(
            {
                "sse_url": SSE_LAMBDA_URL or None,
                "environment": ENVIRONMENT,
            }
        ).decode(),
    )


@app.get("/api/v2/metrics")
def get_metrics_v2():
    """Get aggregated dashboard metrics."""
    from src.lambdas.dashboard.metrics import aggregate_dashboard_metrics

    event = app.current_event.raw_event
    _user_id = _get_user_id_from_event(event, validate_session=False)
    if not _user_id:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Missing user identification"}).decode(),
        )

    params = get_query_params(event)
    hours = int(params.get("hours", "24"))
    if hours < 1:
        hours = 1
    elif hours > 168:
        hours = 168

    try:
        table = get_table(SENTIMENTS_TABLE)
        metrics = aggregate_dashboard_metrics(table, hours=hours)

        if "recent_items" in metrics:
            metrics["recent_items"] = [
                sanitize_item_for_response(item) for item in metrics["recent_items"]
            ]

        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(metrics).decode(),
        )
    except Exception as e:
        logger.error(
            "Failed to get dashboard metrics",
            extra={
                "hours": sanitize_for_log(hours),
                **get_safe_error_info(e),
            },
        )
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": "Failed to retrieve dashboard metrics"}
            ).decode(),
        )


@app.get("/api/v2/sentiment")
def get_sentiment_v2():
    """Get aggregated sentiment for multiple tags."""
    from datetime import UTC, datetime, timedelta

    event = app.current_event.raw_event
    _user_id = _get_user_id_from_event(event, validate_session=False)
    if not _user_id:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Missing user identification"}).decode(),
        )

    params = get_query_params(event)
    tags = params.get("tags", "")
    start = params.get("start")
    end = params.get("end")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": "At least one tag is required"}).decode(),
        )
    if len(tag_list) > 5:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": "Maximum 5 tags allowed"}).decode(),
        )

    now = datetime.now(UTC)
    end_time = end if end else now.isoformat()
    start_time = start if start else (now - timedelta(hours=24)).isoformat()

    try:
        table = get_table(SENTIMENTS_TABLE)
        result = get_sentiment_by_tags(table, tag_list, start_time, end_time)
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(result).decode(),
        )
    except ValueError as e:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except Exception as e:
        logger.error(
            "Failed to get sentiment by tags",
            extra={
                "tags": sanitize_for_log(",".join(tag_list)),
                **get_safe_error_info(e),
            },
        )
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": "Failed to retrieve sentiment data"}).decode(),
        )


@app.get("/api/v2/trends")
def get_trends_v2():
    """Get trend data for sparkline visualizations."""
    event = app.current_event.raw_event
    _user_id = _get_user_id_from_event(event, validate_session=False)
    if not _user_id:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Missing user identification"}).decode(),
        )

    params = get_query_params(event)
    tags = params.get("tags", "")
    interval = params.get("interval", "1h")
    range_str = params.get("range", "24h")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": "At least one tag is required"}).decode(),
        )
    if len(tag_list) > 5:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": "Maximum 5 tags allowed"}).decode(),
        )

    if interval not in ["1h", "6h", "1d"]:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": "Invalid interval. Use: 1h, 6h, or 1d"}
            ).decode(),
        )

    range_hours = 24
    if range_str.endswith("h"):
        try:
            range_hours = int(range_str[:-1])
        except ValueError:
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps(
                    {
                        "detail": "Invalid range format. Use: Nh (e.g., 24h) or Nd (e.g., 7d)"
                    }
                ).decode(),
            )
    elif range_str.endswith("d"):
        try:
            range_hours = int(range_str[:-1]) * 24
        except ValueError:
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps(
                    {
                        "detail": "Invalid range format. Use: Nh (e.g., 24h) or Nd (e.g., 7d)"
                    }
                ).decode(),
            )
    else:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": "Invalid range format. Use: Nh (e.g., 24h) or Nd (e.g., 7d)"}
            ).decode(),
        )

    if range_hours > 168:
        range_hours = 168

    try:
        table = get_table(SENTIMENTS_TABLE)
        result = get_trend_data(table, tag_list, interval, range_hours)
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(result).decode(),
        )
    except ValueError as e:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except Exception as e:
        logger.error(
            "Failed to get trend data",
            extra={
                "tags": sanitize_for_log(",".join(tag_list)),
                "interval": interval,
                **get_safe_error_info(e),
            },
        )
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": "Failed to retrieve trend data"}).decode(),
        )


@app.get("/api/v2/articles")
def get_articles_v2():
    """Get recent articles for specified tags."""
    event = app.current_event.raw_event
    _user_id = _get_user_id_from_event(event, validate_session=False)
    if not _user_id:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Missing user identification"}).decode(),
        )

    params = get_query_params(event)
    tags = params.get("tags", "")
    limit = int(params.get("limit", "20"))
    sentiment = params.get("sentiment")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": "At least one tag is required"}).decode(),
        )
    if len(tag_list) > 5:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": "Maximum 5 tags allowed"}).decode(),
        )

    if limit < 1 or limit > 100:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": "Limit must be between 1 and 100"}).decode(),
        )

    if sentiment and sentiment.lower() not in ["positive", "neutral", "negative"]:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": "Invalid sentiment. Use: positive, neutral, or negative"}
            ).decode(),
        )

    try:
        table = get_table(SENTIMENTS_TABLE)
        articles = get_articles_by_tags(
            table,
            tag_list,
            limit=limit,
            sentiment_filter=sentiment,
        )

        sanitized = [
            sanitize_item_for_response(parse_dynamodb_item(item)) for item in articles
        ]

        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(sanitized).decode(),
        )
    except ValueError as e:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except Exception as e:
        logger.error(
            "Failed to get articles by tags",
            extra={
                "tags": sanitize_for_log(",".join(tag_list)),
                **get_safe_error_info(e),
            },
        )
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": "Failed to retrieve articles"}).decode(),
        )


# ===================================================================
# Chaos Testing Endpoints
# ===================================================================


@app.post("/chaos/experiments")
def create_chaos_experiment():
    """Create a new chaos experiment."""
    event = app.current_event.raw_event
    user_id = _get_authenticated_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    try:
        body = app.current_event.json_body

        experiment = create_experiment(
            scenario_type=body["scenario_type"],
            blast_radius=body["blast_radius"],
            duration_seconds=body["duration_seconds"],
            parameters=body.get("parameters"),
        )

        return Response(
            status_code=201,
            content_type="application/json",
            body=orjson.dumps(experiment).decode(),
        )
    except EnvironmentNotAllowedError as e:
        logger.warning(
            "Chaos testing attempted in disallowed environment",
            extra={"environment": ENVIRONMENT},
        )
        return Response(
            status_code=403,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except (KeyError, ValueError) as e:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": f"Invalid request: {e}"}).decode(),
        )
    except ChaosError as e:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": f"Failed to create experiment: {e}"}).decode(),
        )


@app.get("/chaos/experiments")
def list_chaos_experiments():
    """List chaos experiments with optional status filter."""
    event = app.current_event.raw_event
    user_id = _get_authenticated_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    params = get_query_params(event)
    status = params.get("status")
    limit = int(params.get("limit", "20"))

    try:
        experiments = list_experiments(status=status, limit=limit)
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(experiments).decode(),
        )
    except ValueError as e:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.get("/chaos/experiments/<experiment_id>")
def get_chaos_experiment(experiment_id: str):
    """Get chaos experiment by ID with enriched FIS status."""
    event = app.current_event.raw_event
    user_id = _get_authenticated_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    experiment = get_experiment(experiment_id)
    if not experiment:
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps({"detail": "Experiment not found"}).decode(),
        )

    # Enrich with FIS status if applicable
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
            experiment["fis_status"] = {"error": "Failed to fetch FIS status"}

    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps(experiment).decode(),
    )


@app.post("/chaos/experiments/<experiment_id>/start")
def start_chaos_experiment(experiment_id: str):
    """Start a chaos experiment."""
    event = app.current_event.raw_event
    user_id = _get_authenticated_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    try:
        updated_experiment = start_experiment(experiment_id)
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(updated_experiment).decode(),
        )
    except ChaosError as e:
        logger.error(
            "Chaos experiment start failed",
            extra={
                "experiment_id": sanitize_for_log(experiment_id),
                "error": sanitize_for_log(str(e)),
            },
        )
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except EnvironmentNotAllowedError as e:
        return Response(
            status_code=403,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.post("/chaos/experiments/<experiment_id>/stop")
def stop_chaos_experiment(experiment_id: str):
    """Stop a running chaos experiment."""
    event = app.current_event.raw_event
    user_id = _get_authenticated_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    try:
        updated_experiment = stop_experiment(experiment_id)
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(updated_experiment).decode(),
        )
    except ChaosError as e:
        logger.error(
            "Chaos experiment stop failed",
            extra={
                "experiment_id": sanitize_for_log(experiment_id),
                "error": sanitize_for_log(str(e)),
            },
        )
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except EnvironmentNotAllowedError as e:
        return Response(
            status_code=403,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.delete("/chaos/experiments/<experiment_id>")
def delete_chaos_experiment(experiment_id: str):
    """Delete a chaos experiment."""
    event = app.current_event.raw_event
    user_id = _get_authenticated_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    success = delete_experiment(experiment_id)
    if not success:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": "Failed to delete experiment"}).decode(),
        )

    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps({"message": "Experiment deleted successfully"}).decode(),
    )


# Lambda handler entry point
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point.

    Uses Powertools APIGatewayRestResolver for routing.

    Args:
        event: Lambda event (API Gateway Proxy Integration format)
        context: Lambda context

    Returns:
        HTTP response dict (API Gateway Proxy Integration format)
    """
    logger.info(
        "Dashboard Lambda invoked",
        extra={
            "path": event.get("rawPath", event.get("path", "unknown")),
            "method": event.get(
                "httpMethod",
                event.get("requestContext", {})
                .get("http", {})
                .get("method", "unknown"),
            ),
        },
    )

    return app.resolve(event, context)

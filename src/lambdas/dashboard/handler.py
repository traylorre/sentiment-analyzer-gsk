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
    - Uses AWS Lambda Powertools LambdaFunctionUrlResolver for routing
    - Static files served from /static/ prefix
    - CORS handled at infrastructure level (Lambda Function URL config)
    - Exception: env-gated 404 responses include application-level CORS
      headers (Feature 1268) because neither API Gateway nor Function URL
      adds CORS to Lambda-returned responses

Auth (Feature 1039):
    - All /api/* endpoints use session-based auth via Bearer token
    - Public endpoints (metrics, sentiment, trends, articles) accept anonymous sessions
    - Chaos endpoints require authenticated (non-anonymous) sessions

X-Ray Tracing:
    X-Ray is enabled for distributed tracing across all Lambda invocations.
    This is Day 1 mandatory per constitution v1.1.
"""

import base64
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import orjson
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import (
    LambdaFunctionUrlResolver,
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
    RateLimitError,
    compare_reports,
    create_experiment,
    delete_experiment,
    delete_report,
    generate_plan_report,
    get_experiment,
    get_experiment_report,
    get_gate_state,
    get_metrics,
    get_report,
    get_system_health,
    get_trends,
    list_experiments,
    list_reports,
    persist_report,
    pull_andon_cord,
    set_gate_state,
    start_experiment,
    stop_experiment,
)
from src.lambdas.dashboard.metrics import sanitize_item_for_response
from src.lambdas.shared.dynamodb import get_table, parse_dynamodb_item
from src.lambdas.shared.errors.session_errors import SessionRevokedException
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

# Feature 1268: Allowed CORS origins for env-gated responses
# Parsed from comma-separated CORS_ORIGINS env var (set by Terraform from var.cors_allowed_origins)
_CORS_ALLOWED_ORIGINS: set[str] = {
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
}

# Module-level init logging (FR-028)
logger.info(
    "Dashboard Lambda starting",
    extra={
        "environment": ENVIRONMENT,
        "table": SENTIMENTS_TABLE,
    },
)

# Feature 1250: Environment gating for chaos endpoints (defense in depth).
# Fail-closed: only local/dev/test serve chaos. Prod/preprod/unknown → 404.
_DEV_ENVIRONMENTS = {"local", "dev", "test"}


def _is_dev_environment() -> bool:
    """Check if current environment allows admin dashboard access.

    Fail-closed: returns True ONLY for explicitly allowed dev environments.
    Uses module-level ENVIRONMENT constant (set at import time from os.environ).
    Unset, empty, unknown, 'preprod', 'prod' all return False.
    """
    return ENVIRONMENT.lower() in _DEV_ENVIRONMENTS


def _get_request_origin() -> str | None:
    """Extract Origin header from current Powertools request.

    Returns None if Origin header is missing or if called outside
    a request context (defensive).
    """
    try:
        return app.current_event.headers.get("origin")
    except Exception:
        return None


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
# LambdaFunctionUrlResolver handles Function URL v2 events (rawPath, requestContext.http.method)
# Previously APIGatewayRestResolver only handled REST v1 events, causing 502 on Function URL
app = LambdaFunctionUrlResolver()

# Include all routers
from src.lambdas.dashboard.router_v2 import include_routers

include_routers(app)
logger.info("API v2 routers included")


# ===================================================================
# Static file and root endpoints (defined on app directly)
# ===================================================================


def _get_user_id_from_event(event: dict, validate_session: bool = True) -> str:
    """Extract user_id from event headers and optionally validate session.

    Args:
        event: API Gateway event dict.
        validate_session: When True, checks DynamoDB session is active/not revoked.

    Returns:
        user_id string, or "" if missing/invalid/expired.
    """
    from src.lambdas.dashboard import auth as auth_service

    auth_context = extract_auth_context(event)
    user_id = auth_context.get("user_id")
    if not user_id:
        return ""
    if validate_session:
        try:
            table = get_table(USERS_TABLE)
            validation = auth_service.validate_session(
                table=table, anonymous_id=user_id
            )
            if not validation.valid:
                return ""
        except SessionRevokedException:
            return ""
        except Exception:
            logger.warning("Session validation failed", exc_info=True)
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


def _get_chaos_user_id_from_event(event: dict) -> str | None:
    """Extract authenticated (non-anonymous) user_id for chaos endpoints.

    Feature 1250: Anonymous sessions are rejected in ALL environments.
    Only JWT-authenticated users can execute chaos operations.
    """
    auth_context = extract_auth_context_typed(event)
    if auth_context.user_id is None:
        return None
    if auth_context.auth_type == AuthType.ANONYMOUS:
        return None
    return auth_context.user_id


def _make_not_found_response(origin: str | None = None) -> Response:
    """Create 404 response with conditional CORS headers for env-gated routes.

    Feature 1268: When the requesting origin is in the allowed CORS origins
    list, includes Access-Control-Allow-Origin and related headers so browsers
    can read the response body. Without these headers, browsers block the
    response entirely (opaque CORS failure).

    This is intentionally application-level CORS for a specific case:
    env-gated routes return 404 BEFORE the normal pipeline processes the
    request, and neither API Gateway (AWS_PROXY pass-through) nor Lambda
    Function URL (AWS_IAM auth only) adds CORS headers to Lambda-returned
    responses.

    Args:
        origin: The Origin header from the request, or None.

    Returns:
        Response with 404 status, JSON body, and conditional CORS headers.
    """
    headers: dict[str, str] = {"Vary": "Origin"}

    if origin and origin in _CORS_ALLOWED_ORIGINS:
        headers.update(
            {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS",
                "Access-Control-Allow-Headers": (
                    "Content-Type,Authorization,Accept,Cache-Control,"
                    "Last-Event-ID,X-Amzn-Trace-Id,X-User-ID"
                ),
            }
        )
        logger.debug(
            "Env-gated 404 with CORS",
            extra={"origin": origin},
        )

    return Response(
        status_code=404,
        content_type="application/json",
        body=orjson.dumps({"detail": "Not found"}).decode(),
        headers=headers,
    )


@app.get("/")
def serve_index():
    """Serve the main dashboard HTML page (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
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
    """Serve the favicon.ico file (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
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
    """Serve the chaos testing UI page (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
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
    """Serve static dashboard files (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
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
    """API index listing all available endpoints (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
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
                        "GET /chaos/experiments/{id}/report": "Get experiment report",
                        "DELETE /chaos/experiments/{id}": "Delete experiment",
                    },
                },
            }
        ).decode(),
    )


@app.get("/health")
def health_check():
    """Health check endpoint with DynamoDB connectivity test.

    In non-dev environments, returns only {"status":"healthy"} to prevent
    information leakage (table names, environment). Deploy smoke tests
    only check valid JSON + "status" key presence (verified: deploy.yml:1167, 2033).
    """
    try:
        table = get_table(SENTIMENTS_TABLE)
        _ = table.table_status

        if _is_dev_environment():
            body = {
                "status": "healthy",
                "table": SENTIMENTS_TABLE,
                "environment": ENVIRONMENT,
            }
        else:
            body = {"status": "healthy"}

        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(body).decode(),
        )
    except Exception as e:
        logger.error(
            "Health check failed",
            extra={"table": SENTIMENTS_TABLE, **get_safe_error_info(e)},
        )
        if _is_dev_environment():
            err_body = {
                "status": "unhealthy",
                "error": get_safe_error_message_for_user(e),
                "table": SENTIMENTS_TABLE,
            }
        else:
            err_body = {"status": "unhealthy"}

        return Response(
            status_code=503,
            content_type="application/json",
            body=orjson.dumps(err_body).decode(),
        )


@app.get("/api/v2/runtime")
def get_runtime_config():
    """Get runtime configuration for the frontend (Feature 1097).

    In non-dev environments, returns generic values to prevent leaking
    the SSE Lambda Function URL and real environment name.
    """
    if _is_dev_environment():
        body = {
            "sse_url": SSE_LAMBDA_URL or None,
            "environment": ENVIRONMENT,
        }
    else:
        body = {
            "sse_url": None,
            "environment": "production",
        }
    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps(body).decode(),
    )


@app.get("/api/v2/metrics")
def get_metrics_v2():
    """Get aggregated dashboard metrics."""
    from src.lambdas.dashboard.metrics import aggregate_dashboard_metrics

    event = app.current_event.raw_event
    _user_id = _get_user_id_from_event(event)
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
    _user_id = _get_user_id_from_event(event)
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
    _user_id = _get_user_id_from_event(event)
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
    _user_id = _get_user_id_from_event(event)
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
    """Create a new chaos experiment (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
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
            user_id=user_id,
        )

        return Response(
            status_code=201,
            content_type="application/json",
            body=orjson.dumps(experiment).decode(),
        )
    except RateLimitError:
        return Response(
            status_code=429,
            content_type="application/json",
            body=orjson.dumps(
                {"detail": "Rate limit exceeded. Max 1 experiment per 60 seconds."}
            ).decode(),
            headers={"Retry-After": "60"},
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
    """List chaos experiments (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
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
    """Get chaos experiment by ID (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
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

    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps(experiment).decode(),
    )


@app.post("/chaos/experiments/<experiment_id>/start")
def start_chaos_experiment(experiment_id: str):
    """Start a chaos experiment (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
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
        error_msg = str(e)
        if "already running" in error_msg.lower():
            return Response(
                status_code=409,
                content_type="application/json",
                body=orjson.dumps({"detail": error_msg}).decode(),
            )
        logger.error(
            "Chaos experiment start failed",
            extra={
                "experiment_id": sanitize_for_log(experiment_id),
                "error": sanitize_for_log(error_msg),
            },
        )
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": error_msg}).decode(),
        )
    except EnvironmentNotAllowedError as e:
        return Response(
            status_code=403,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.post("/chaos/experiments/<experiment_id>/stop")
def stop_chaos_experiment(experiment_id: str):
    """Stop a running chaos experiment (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
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


@app.get("/chaos/experiments/<experiment_id>/report")
def get_chaos_experiment_report(experiment_id: str):
    """Get chaos experiment report (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    try:
        report = get_experiment_report(experiment_id)
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(report).decode(),
        )
    except ChaosError as e:
        logger.error(
            "Chaos experiment report failed",
            extra={
                "experiment_id": sanitize_for_log(experiment_id),
                "error": sanitize_for_log(str(e)),
            },
        )
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.delete("/chaos/experiments/<experiment_id>")
def delete_chaos_experiment(experiment_id: str):
    """Delete a chaos experiment (locked down in prod/preprod)."""
    if not _is_dev_environment():
        return _make_not_found_response(_get_request_origin())
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
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


# --- Chaos Reports (Feature 1240) ---


@app.post("/chaos/reports")
def create_chaos_report():
    """Persist an experiment report (Feature 1240)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    try:
        body = app.current_event.json_body
        experiment_id = body.get("experiment_id")
        if not experiment_id:
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps({"detail": "experiment_id required"}).decode(),
            )

        # Check for duplicate report
        existing = list_reports(limit=100)
        for r in existing.get("reports", []):
            if (
                r.get("experiment_id") == experiment_id
                and r.get("report_type") == "experiment"
            ):
                return Response(
                    status_code=409,
                    content_type="application/json",
                    body=orjson.dumps(
                        {
                            "detail": f"Report already exists for experiment {experiment_id}"
                        }
                    ).decode(),
                )

        report_data = get_experiment_report(experiment_id)
        # Map ephemeral report keys
        if "scenario" in report_data and "scenario_type" not in report_data:
            report_data["scenario_type"] = report_data.pop("scenario")

        result = persist_report(report_data)
        return Response(
            status_code=201,
            content_type="application/json",
            body=orjson.dumps(result, default=str).decode(),
        )
    except ChaosError as e:
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except Exception as e:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.post("/chaos/reports/plan")
def create_chaos_plan_report():
    """Generate plan-level report (Feature 1240)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    try:
        body = app.current_event.json_body
        plan_name = body.get("plan_name")
        experiment_ids = body.get("experiment_ids", [])

        if not plan_name or not experiment_ids:
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps(
                    {"detail": "plan_name and experiment_ids required"}
                ).decode(),
            )

        result = generate_plan_report(plan_name, experiment_ids)
        return Response(
            status_code=201,
            content_type="application/json",
            body=orjson.dumps(result, default=str).decode(),
        )
    except ChaosError as e:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except Exception as e:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.get("/chaos/reports")
def list_chaos_reports():
    """List reports with optional filters (Feature 1240)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    try:
        params = app.current_event.query_string_parameters or {}
        result = list_reports(
            scenario_type=params.get("scenario_type"),
            verdict=params.get("verdict"),
            report_type=params.get("report_type"),
            from_date=params.get("from_date"),
            to_date=params.get("to_date"),
            limit=int(params.get("limit", "20")),
            cursor=params.get("cursor"),
        )
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(result, default=str).decode(),
        )
    except Exception as e:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.get("/chaos/reports/trends/<scenario_type>")
def get_chaos_report_trends(scenario_type: str):
    """Get trend data for scenario type (Feature 1240)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    try:
        params = app.current_event.query_string_parameters or {}
        limit = int(params.get("limit", "20"))
        result = get_trends(scenario_type, limit)
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(result, default=str).decode(),
        )
    except Exception as e:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.get("/chaos/reports/<report_id>")
def get_chaos_report(report_id: str):
    """Get single report by ID (Feature 1240)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    report = get_report(report_id)
    if not report:
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps({"detail": f"Report not found: {report_id}"}).decode(),
        )

    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps(report, default=str).decode(),
    )


@app.get("/chaos/reports/<report_id>/compare")
def compare_chaos_reports(report_id: str):
    """Compare report against baseline (Feature 1240)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    try:
        params = app.current_event.query_string_parameters or {}
        baseline_id = params.get("baseline_id")

        result = compare_reports(report_id, baseline_id)

        if result.get("is_first_baseline"):
            return Response(
                status_code=422,
                content_type="application/json",
                body=orjson.dumps(result, default=str).decode(),
            )

        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(result, default=str).decode(),
        )
    except ChaosError as e:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except Exception as e:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.delete("/chaos/reports/<report_id>")
def delete_chaos_report(report_id: str):
    """Delete report by ID (Feature 1240)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )

    deleted = delete_report(report_id)
    if not deleted:
        return Response(
            status_code=404,
            content_type="application/json",
            body=orjson.dumps({"detail": f"Report not found: {report_id}"}).decode(),
        )

    return Response(
        status_code=204,
        content_type="application/json",
        body="",
    )


# --- Safety Controls & Metrics (Features 1244, 1245, 1246) ---


@app.get("/chaos/health")
def get_chaos_health():
    """Pre-flight health check (Feature 1244)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )
    try:
        health = get_system_health()
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(health, default=str).decode(),
        )
    except EnvironmentNotAllowedError as e:
        return Response(
            status_code=403,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except ChaosError as e:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.get("/chaos/gate")
def get_chaos_gate():
    """Get current gate state (Feature 1245)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )
    try:
        state = get_gate_state()
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps({"state": state}).decode(),
        )
    except EnvironmentNotAllowedError as e:
        return Response(
            status_code=403,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except ChaosError as e:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.put("/chaos/gate")
def set_chaos_gate():
    """Set gate state to armed or disarmed (Feature 1245)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )
    try:
        body = app.current_event.json_body
        new_state = body.get("state")
        if new_state not in ("armed", "disarmed"):
            return Response(
                status_code=400,
                content_type="application/json",
                body=orjson.dumps(
                    {"detail": "state must be 'armed' or 'disarmed'"}
                ).decode(),
            )
        result = set_gate_state(new_state)
        return Response(
            status_code=200,
            content_type="application/json",
            body=orjson.dumps(result).decode(),
        )
    except EnvironmentNotAllowedError as e:
        return Response(
            status_code=403,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except ChaosError as e:
        return Response(
            status_code=409,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except ValueError as e:
        return Response(
            status_code=400,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


@app.post("/chaos/andon-cord")
def pull_chaos_andon_cord():
    """Emergency stop -- pull the andon cord (Feature 1246)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )
    try:
        result = pull_andon_cord()
        status = 200 if result["kill_switch_set"] else 500
        return Response(
            status_code=status,
            content_type="application/json",
            body=orjson.dumps(result, default=str).decode(),
        )
    except EnvironmentNotAllowedError as e:
        return Response(
            status_code=403,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except Exception as e:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": f"Andon cord failed: {e}"}).decode(),
        )


@app.get("/chaos/metrics")
def get_chaos_metrics():
    """Real-time CloudWatch metrics for chaos dashboard (Feature 1247)."""
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(
            status_code=401,
            content_type="application/json",
            body=orjson.dumps({"detail": "Authentication required"}).decode(),
        )
    try:
        params = app.current_event.query_string_parameters or {}

        # Parse time parameters
        now = datetime.now(UTC)
        if "start_time" in params:
            start_time = datetime.fromisoformat(params["start_time"])
        else:
            start_time = now - timedelta(minutes=30)

        if "end_time" in params:
            end_time = datetime.fromisoformat(params["end_time"])
        else:
            end_time = now

        period = int(params.get("period", "60"))
        period = max(60, min(3600, period))  # Clamp between 60s and 1hr

        status_code, data = get_metrics(start_time, end_time, period)

        headers = {}
        if status_code == 429:
            headers["Retry-After"] = str(data.get("retry_after", 5))

        return Response(
            status_code=status_code,
            content_type="application/json",
            body=orjson.dumps(data, default=str).decode(),
            headers=headers,
        )
    except EnvironmentNotAllowedError as e:
        return Response(
            status_code=403,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )
    except Exception as e:
        return Response(
            status_code=500,
            content_type="application/json",
            body=orjson.dumps({"detail": str(e)}).decode(),
        )


def _handle_auto_restore(experiment_id: str) -> dict[str, Any]:
    """Handle EventBridge Scheduler auto-restore callback (Feature 1250).

    Called directly from lambda_handler for raw (non-HTTP) events.
    Returns a dict (not a Powertools Response).
    """
    from src.lambdas.dashboard.chaos import get_experiment, stop_experiment

    if not experiment_id:
        logger.warning("Auto-restore called without experiment_id")
        return {"statusCode": 400, "body": '{"status":"missing_experiment_id"}'}

    experiment = get_experiment(experiment_id)
    if not experiment or experiment.get("status") != "running":
        logger.info(
            "Auto-restore no-op: experiment not running",
            extra={
                "experiment_id": experiment_id,
                "status": experiment.get("status") if experiment else "not_found",
            },
        )
        return {"statusCode": 200, "body": '{"status":"no-op"}'}

    try:
        stop_experiment(experiment_id, auto_stopped=True)
        logger.info(
            "Auto-restore completed",
            extra={"experiment_id": experiment_id},
        )
        return {
            "statusCode": 200,
            "body": f'{{"status":"restored","experiment_id":"{experiment_id}"}}',
        }
    except Exception as e:
        logger.error(
            "Auto-restore failed",
            extra={"experiment_id": experiment_id, "error": str(e)},
        )
        return {"statusCode": 500, "body": f'{{"status":"error","detail":"{e}"}}'}


# Lambda handler entry point
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point.

    Uses Powertools LambdaFunctionUrlResolver for routing.

    Args:
        event: Lambda event (Lambda Function URL v2 format)
        context: Lambda context

    Returns:
        HTTP response dict (Lambda Function URL v2 format)
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

    # Feature 1250: Handle EventBridge Scheduler auto-restore callback.
    # Scheduler invokes Lambda directly with raw JSON (not HTTP), so this
    # MUST be checked before Powertools routing which expects HTTP events.
    if event.get("action") == "chaos-auto-restore":
        return _handle_auto_restore(event.get("experiment_id", ""))

    response = app.resolve(event, context)

    # Feature 1224: Flush cache metrics to CloudWatch if interval elapsed
    try:
        from src.lib.cache_utils import get_global_emitter

        get_global_emitter().flush_to_cloudwatch()
    except Exception:
        logger.warning("Cache metrics flush failed", exc_info=True)

    return response

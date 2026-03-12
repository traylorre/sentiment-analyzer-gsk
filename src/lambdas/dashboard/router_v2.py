"""Feature 006 API v2 Router (Powertools).

Wires all Feature 006 service functions to Powertools Router endpoints.
This router is included by handler.py to expose the endpoints.

Endpoint Groups:
- /api/v2/auth/* - Authentication (anonymous, magic link, OAuth)
- /api/v2/configurations/* - Configuration CRUD
- /api/v2/configurations/{id}/sentiment - Sentiment data
- /api/v2/configurations/{id}/volatility - Volatility data
- /api/v2/configurations/{id}/heatmap - Heat map visualization
- /api/v2/configurations/{id}/correlation - Correlation analysis
- /api/v2/configurations/{id}/refresh - Data refresh
- /api/v2/configurations/{id}/premarket - Pre-market estimates
- /api/v2/tickers/* - Ticker validation and search
- /api/v2/alerts/* - Alert rule CRUD
- /api/v2/notifications/* - Notification management
- /api/v2/market/status - Market status
"""

import logging
from typing import Literal

import orjson
from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.api_gateway import Router
from botocore.exceptions import ClientError
from pydantic import BaseModel, EmailStr, ValidationError

from src.lambdas.dashboard import alerts as alert_service

# Import service modules
from src.lambdas.dashboard import auth as auth_service
from src.lambdas.dashboard import configurations as config_service
from src.lambdas.dashboard import market as market_service
from src.lambdas.dashboard import notifications as notification_service
from src.lambdas.dashboard import quota as quota_service
from src.lambdas.dashboard import sentiment as sentiment_service
from src.lambdas.dashboard import tickers as ticker_service
from src.lambdas.dashboard import timeseries as timeseries_service
from src.lambdas.dashboard import volatility as volatility_service
from src.lambdas.shared.auth.csrf import (
    CSRF_COOKIE_MAX_AGE,
    CSRF_COOKIE_NAME,
    generate_csrf_token,
)
from src.lambdas.shared.dependencies import (
    get_ticker_cache_dependency,
    get_users_table,
)
from src.lambdas.shared.errors import (
    SessionRevokedException,
    TokenAlreadyUsedError,
    TokenExpiredError,
)
from src.lambdas.shared.logging_utils import get_safe_error_info
from src.lambdas.shared.middleware import extract_auth_context
from src.lambdas.shared.middleware.auth_middleware import (
    AuthType,
    extract_auth_context_typed,
)
from src.lambdas.shared.middleware.csrf_middleware import require_csrf_middleware
from src.lambdas.shared.middleware.require_role import require_role_middleware
from src.lambdas.shared.response_models import (
    UserMeResponse,
    mask_email,
    seconds_until,
)
from src.lambdas.shared.utils.cookie_helpers import make_set_cookie, parse_cookies
from src.lambdas.shared.utils.event_helpers import get_header, get_query_params
from src.lambdas.shared.utils.response_builder import (
    error_response,
    json_response,
    validation_error_response,
)


# Request models for router endpoints
class NotificationPreferencesUpdate(BaseModel):
    """Request body for PATCH /api/v2/notifications/preferences."""

    email_enabled: bool | None = None
    digest_enabled: bool | None = None
    digest_time: str | None = None


class DigestSettingsUpdate(BaseModel):
    """Request body for PATCH /api/v2/notifications/digest."""

    enabled: bool | None = None
    time: str | None = None
    timezone: str | None = None
    include_all_configs: bool | None = None
    config_ids: list[str] | None = None


class ConfigAlertCreateRequest(BaseModel):
    """Request body for POST /api/v2/configurations/{config_id}/alerts.

    Maps test-style field names to AlertRuleCreate fields:
    - type -> alert_type (with "_threshold" suffix)
    - threshold -> threshold_value
    - condition -> threshold_direction
    """

    type: Literal["sentiment", "volatility"]
    ticker: str
    threshold: float
    condition: Literal["above", "below"]
    enabled: bool | None = True


logger = logging.getLogger(__name__)

REFRESH_TOKEN_COOKIE_NAME = "refresh_token"  # noqa: S105 - cookie name, not a password


# =============================================================================
# Create Powertools routers (FR-001, R1)
# =============================================================================

auth_router = Router()
config_router = Router()
ticker_router = Router()
alert_router = Router()
notification_router = Router()
market_router = Router()
# Feature 014: Users router for email lookup (T044)
users_router = Router()
# Feature 1009: Timeseries router for multi-resolution sentiment time-series
timeseries_router = Router()
# Admin router for bulk operations
admin_router = Router()


# =============================================================================
# Helper functions for raw API Gateway event dicts
# =============================================================================


def _get_no_cache_headers() -> dict[str, str]:
    """Get cache-busting headers for auth responses (Feature 1157)."""
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }


def _make_csrf_set_cookie() -> str:
    """Build Set-Cookie header value for CSRF token (Feature 1158)."""
    return make_set_cookie(
        CSRF_COOKIE_NAME,
        generate_csrf_token(),
        httponly=False,  # JS must read this
        secure=True,
        samesite="None",  # Required for cross-origin
        max_age=CSRF_COOKIE_MAX_AGE,
        path="/api/v2",
    )


def _make_refresh_token_cookie(token: str) -> str:
    """Build Set-Cookie header value for refresh token (Feature 1160)."""
    return make_set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        token,
        httponly=True,
        secure=True,
        samesite="Strict",  # Will be "None" after Feature 1159 merges
        max_age=30 * 24 * 60 * 60,  # 30 days
        path="/api/v2/auth",
    )


def _extract_refresh_token_from_event(event: dict) -> str | None:
    """Extract refresh_token from httpOnly cookie in raw event (Feature 1160)."""
    cookies = parse_cookies(event)
    return cookies.get(REFRESH_TOKEN_COOKIE_NAME)


def _json_response_with_cookies(
    body: dict,
    status_code: int = 200,
    cookies: list[str] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> Response:
    """Build a JSON response with optional Set-Cookie headers.

    Returns a Powertools Response object. Set-Cookie headers are passed
    via the headers dict as a list, which Powertools serializes into
    multiValueHeaders in the API Gateway response format.
    """
    headers: dict[str, str | list[str]] = {}
    if extra_headers:
        headers.update(extra_headers)

    if cookies:
        headers["Set-Cookie"] = cookies

    return Response(
        status_code=status_code,
        content_type="application/json",
        body=orjson.dumps(body).decode(),
        headers=headers,
    )


def get_user_id_from_event(
    event: dict, table=None, validate_session: bool = True
) -> str:
    """Extract user_id from event headers/session and optionally validate.

    Feature 014: Supports hybrid authentication approach:
    1. Authorization: Bearer {token} - preferred for new code
    2. X-User-ID header - legacy, backward compatible

    Args:
        event: API Gateway Proxy Integration event dict
        table: DynamoDB table for session validation (optional)
        validate_session: Whether to validate session is still active

    Returns:
        user_id if valid, or raises and returns an error_response tuple

    Note:
        On error, this function returns None and callers should check and
        return the appropriate error response. We use a sentinel pattern
        to avoid exception-based flow control with HTTP exceptions.
    """
    auth_context = extract_auth_context(event)

    user_id = auth_context.get("user_id")
    if not user_id:
        return None

    # Validate session is still active (not signed out/expired)
    if validate_session and table is not None:
        try:
            validation = auth_service.validate_session(
                table=table, anonymous_id=user_id
            )
            if not validation.valid:
                return None
        except SessionRevokedException:
            return None

    return user_id


def _require_user_id(
    event: dict, table=None, validate_session: bool = True
) -> tuple[str | None, dict | None]:
    """Get user_id or return (None, error_response).

    Returns:
        (user_id, None) on success
        (None, error_dict) on failure — caller should return the error_dict
    """
    auth_context = extract_auth_context(event)
    user_id = auth_context.get("user_id")
    if not user_id:
        return None, error_response(401, "Missing user identification")

    if validate_session and table is not None:
        try:
            validation = auth_service.validate_session(
                table=table, anonymous_id=user_id
            )
            if not validation.valid:
                return None, error_response(401, "Session expired or invalid")
        except SessionRevokedException as e:
            return None, error_response(
                403, f"Session revoked: {e.reason or 'Security policy'}"
            )

    return user_id, None


def _require_authenticated_user_id(event: dict) -> tuple[str | None, dict | None]:
    """Get authenticated (non-anonymous) user_id or return error.

    Feature 1048: Auth type is determined by token validation, NOT request headers.

    Returns:
        (user_id, None) on success
        (None, error_dict) on failure
    """
    auth_context = extract_auth_context_typed(event)

    if auth_context.user_id is None:
        return None, error_response(401, "Authentication required")

    if auth_context.auth_type == AuthType.ANONYMOUS:
        return None, error_response(403, "This endpoint requires authenticated user")

    return auth_context.user_id, None


def _get_config_with_tickers(
    table, user_id: str, config_id: str
) -> tuple[tuple[str, list[str]] | None, dict | None]:
    """Fetch configuration and extract ticker symbols.

    Returns:
        ((config_id, tickers), None) on success
        (None, error_dict) on failure
    """
    config = config_service.get_configuration(
        table=table, user_id=user_id, config_id=config_id
    )
    if config is None:
        return None, error_response(404, "Configuration not found")
    if isinstance(config, config_service.ErrorResponse):
        return None, error_response(404, config.error.message)

    tickers = [t.symbol for t in config.tickers]
    return (config_id, tickers), None


def _parse_request_body(
    event: dict, model_class: type[BaseModel], allow_none: bool = False
):
    """Parse and validate JSON body from event using a Pydantic model.

    Args:
        event: API Gateway event dict
        model_class: Pydantic model class to validate against
        allow_none: If True, return None for empty/missing body

    Returns:
        (model_instance, None) on success
        (None, error_dict) on validation failure
        (None, None) if allow_none=True and body is empty
    """
    body_str = event.get("body")
    if not body_str:
        if allow_none:
            return None, None
        return None, error_response(400, "Request body is required")

    try:
        if isinstance(body_str, str):
            body_data = orjson.loads(body_str)
        else:
            body_data = body_str
    except (orjson.JSONDecodeError, ValueError):
        return None, error_response(400, "Invalid JSON in request body")

    try:
        return model_class.model_validate(body_data), None
    except ValidationError as exc:
        return None, validation_error_response(exc)


# ===================================================================
# Authentication Endpoints
# ===================================================================


@auth_router.post("/api/v2/auth/anonymous", middlewares=[require_csrf_middleware])
def create_anonymous_session():
    """Create anonymous session (T047, Feature 1119).

    Accepts:
    - No request body (uses defaults: timezone=America/New_York)
    - Empty body {} (uses defaults)
    - Body with optional fields (uses provided values)
    """
    event = auth_router.current_event.raw_event
    table = get_users_table()

    body, err = _parse_request_body(
        event, auth_service.AnonymousSessionRequest, allow_none=True
    )
    if err:
        return err
    if body is None:
        body = auth_service.AnonymousSessionRequest()

    try:
        result = auth_service.create_anonymous_session(table=table, request=body)
        return json_response(201, result.model_dump(), _get_no_cache_headers())
    except Exception as e:
        logger.error("Failed to create anonymous session", extra=get_safe_error_info(e))
        return error_response(500, "Failed to create session")


@auth_router.get("/api/v2/auth/validate", middlewares=[require_csrf_middleware])
def validate_session():
    """Validate session (T048).

    Feature 1146: Uses Bearer token authentication (X-User-ID fallback removed).
    """
    event = auth_router.current_event.raw_event
    table = get_users_table()

    user_id = get_user_id_from_event(event)
    if not user_id:
        return json_response(
            200, {"valid": False, "reason": "missing_user_id"}, _get_no_cache_headers()
        )

    result = auth_service.validate_session(table=table, anonymous_id=user_id)
    return json_response(200, result.model_dump(), _get_no_cache_headers())


@auth_router.post("/api/v2/auth/extend", middlewares=[require_csrf_middleware])
def extend_session():
    """Extend session by 30 days."""
    event = auth_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    user = auth_service.extend_session(table=table, user_id=user_id)
    if not user:
        return error_response(404, "User not found")
    return json_response(
        200,
        {
            "message": "Session extended",
            "expires_at": user.session_expires_at.isoformat(),
        },
        _get_no_cache_headers(),
    )


class MagicLinkRequest(BaseModel):
    email: EmailStr
    redirect_url: str | None = None


@auth_router.post("/api/v2/auth/magic-link", middlewares=[require_csrf_middleware])
def request_magic_link():
    """Request magic link email (T090).

    Feature 1146: Uses Bearer token authentication (X-User-ID fallback removed).
    The anonymous_user_id is optional - used for linking anonymous to authenticated.
    """
    event = auth_router.current_event.raw_event
    table = get_users_table()

    body, err = _parse_request_body(event, MagicLinkRequest)
    if err:
        return err

    # Optional: user may not have an anonymous session yet
    user_id = get_user_id_from_event(event)

    result = auth_service.request_magic_link(
        table=table,
        request=auth_service.MagicLinkRequest(
            email=body.email,
            anonymous_user_id=user_id,
        ),
    )
    return json_response(200, result.model_dump(), _get_no_cache_headers())


@auth_router.get(
    "/api/v2/auth/magic-link/verify", middlewares=[require_csrf_middleware]
)
def verify_magic_link():
    """Verify magic link token (T091).

    Security: refresh_token is set as HttpOnly cookie, NEVER in body.

    Feature 014 (T034): Returns appropriate error codes for race conditions:
    - 409 Conflict: Token already used by another request
    - 410 Gone: Token has expired

    Feature 1129: Passes client_ip for atomic consumption audit trail.
    """
    event = auth_router.current_event.raw_event
    table = get_users_table()

    query_params = get_query_params(event)
    token = query_params.get("token")
    if not token:
        return error_response(400, "Missing token parameter")

    # Feature 1129: Extract client IP for audit trail
    client_ip = get_header(event, "X-Forwarded-For", "")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    if not client_ip:
        client_ip = (
            (event.get("requestContext") or {})
            .get("identity", {})
            .get("sourceIp", "unknown")
        )

    try:
        result = auth_service.verify_magic_link(
            table=table, token=token, client_ip=client_ip
        )
    except TokenAlreadyUsedError:
        return error_response(409, "This magic link has already been verified")
    except TokenExpiredError:
        return error_response(
            410, "This magic link has expired. Please request a new one."
        )

    if isinstance(result, auth_service.ErrorResponse):
        return error_response(400, result.error.message)

    # Extract refresh_token for HttpOnly cookie
    refresh_token = result.refresh_token_for_cookie

    # Build response WITHOUT refresh_token in body
    response_data = result.model_dump(exclude={"refresh_token_for_cookie"})

    cookies = []
    if refresh_token:
        # Feature 1159: SameSite=None for cross-origin cookie transmission
        cookies.append(
            make_set_cookie(
                REFRESH_TOKEN_COOKIE_NAME,
                refresh_token,
                httponly=True,
                secure=True,
                samesite="None",  # Cross-origin; CSRF protected by Feature 1158
                max_age=30 * 24 * 60 * 60,
                path="/api/v2/auth",
            )
        )
        # Feature 1158: Set CSRF token cookie for double-submit pattern
        cookies.append(_make_csrf_set_cookie())

    return _json_response_with_cookies(
        response_data, cookies=cookies, extra_headers=_get_no_cache_headers()
    )


@auth_router.get("/api/v2/auth/oauth/urls", middlewares=[require_csrf_middleware])
def get_oauth_urls():
    """Get OAuth provider URLs (T092).

    Feature 1185: Generates OAuth state for CSRF protection.
    """
    table = get_users_table()
    result = auth_service.get_oauth_urls(table)
    return json_response(200, result.model_dump(), _get_no_cache_headers())


class OAuthCallbackRequest(BaseModel):
    code: str
    provider: str
    redirect_uri: str
    state: str  # Feature 1185: OAuth state for CSRF protection


@auth_router.post("/api/v2/auth/oauth/callback", middlewares=[require_csrf_middleware])
def handle_oauth_callback():
    """Handle OAuth callback (T093).

    Security: refresh_token is set as HttpOnly cookie, NEVER in body.
    Feature 1146: Uses Bearer token authentication (X-User-ID fallback removed).
    The anonymous_user_id is optional - used for linking anonymous to authenticated.
    """
    event = auth_router.current_event.raw_event
    table = get_users_table()

    body, err = _parse_request_body(event, OAuthCallbackRequest)
    if err:
        return err

    # Optional: user may not have an anonymous session yet
    user_id = get_user_id_from_event(event)

    result = auth_service.handle_oauth_callback(
        table=table,
        code=body.code,
        provider=body.provider,
        redirect_uri=body.redirect_uri,
        state=body.state,
        anonymous_user_id=user_id,
    )
    if isinstance(result, auth_service.ErrorResponse):
        return error_response(400, result.error.message)

    # Extract refresh_token for HttpOnly cookie
    refresh_token = result.refresh_token_for_cookie

    # Build response WITHOUT refresh_token in body
    response_data = result.model_dump(exclude={"refresh_token_for_cookie"})

    cookies = []
    if refresh_token:
        # Feature 1159: SameSite=None for cross-origin cookie transmission
        cookies.append(
            make_set_cookie(
                REFRESH_TOKEN_COOKIE_NAME,
                refresh_token,
                httponly=True,
                secure=True,
                samesite="None",  # Cross-origin; CSRF protected by Feature 1158
                max_age=30 * 24 * 60 * 60,
                path="/api/v2/auth",
            )
        )
        cookies.append(_make_csrf_set_cookie())

    return _json_response_with_cookies(
        response_data, cookies=cookies, extra_headers=_get_no_cache_headers()
    )


class RefreshTokenRequest(BaseModel):
    """Request body for refresh endpoint (backwards compatibility)."""

    refresh_token: str | None = None  # Optional - prefer cookie


@auth_router.post("/api/v2/auth/refresh", middlewares=[require_csrf_middleware])
def refresh_tokens():
    """Refresh access tokens (T094).

    Feature 1160: Extract refresh token from httpOnly cookie.
    The browser sends the cookie automatically - no JavaScript handling needed.
    Falls back to request body for backwards compatibility.

    Feature 1158: Also refreshes CSRF token on successful refresh.
    Note: This endpoint is exempt from CSRF validation because it uses
    cookie-only authentication (no JavaScript access needed).

    Feature 1188 (FR-007): Checks blocklist BEFORE issuing new tokens.
    """
    event = auth_router.current_event.raw_event
    table = get_users_table()

    # Feature 1160: Try cookie first (preferred), fall back to body
    refresh_token = _extract_refresh_token_from_event(event)
    if not refresh_token:
        body, _ = _parse_request_body(event, RefreshTokenRequest, allow_none=True)
        if body and body.refresh_token:
            refresh_token = body.refresh_token

    if not refresh_token:
        return error_response(401, "Refresh token not found in cookie or request body")

    # Feature 1188: Pass table for blocklist check (FR-007)
    result = auth_service.refresh_access_tokens(
        refresh_token=refresh_token, table=table
    )
    if isinstance(result, auth_service.ErrorResponse):
        return error_response(401, result.error.message)

    response_data = result.model_dump()

    cookies = []
    # Feature 1160: Set rotated refresh token as httpOnly cookie
    if hasattr(result, "refresh_token_for_cookie") and result.refresh_token_for_cookie:
        cookies.append(_make_refresh_token_cookie(result.refresh_token_for_cookie))

    # Feature 1158: Refresh CSRF token along with session
    cookies.append(_make_csrf_set_cookie())

    return _json_response_with_cookies(
        response_data, cookies=cookies, extra_headers=_get_no_cache_headers()
    )


@auth_router.post("/api/v2/auth/signout", middlewares=[require_csrf_middleware])
def sign_out():
    """Sign out current device (T095)."""
    event = auth_router.current_event.raw_event
    table = get_users_table()

    # Extract access token from Authorization header
    auth_header = get_header(event, "Authorization", "")
    access_token = auth_header.replace("Bearer ", "") if auth_header else ""

    user_id, err = _require_user_id(event)
    if err:
        return err

    result = auth_service.sign_out(
        table=table,
        user_id=user_id,
        access_token=access_token,
    )
    return json_response(200, result.model_dump(), _get_no_cache_headers())


@auth_router.get("/api/v2/auth/session", middlewares=[require_csrf_middleware])
def get_session_info():
    """Get session info (T096)."""
    event = auth_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    result = auth_service.get_session_info(table=table, user_id=user_id)
    if isinstance(result, auth_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, result.model_dump(), _get_no_cache_headers())


@auth_router.post("/api/v2/auth/session/refresh", middlewares=[require_csrf_middleware])
def refresh_session():
    """Refresh session expiry (T056).

    Feature 014: Extends session by 30 days (sliding window pattern).
    Returns new expiry time and remaining seconds.
    """
    event = auth_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event, table=table, validate_session=False)
    if err:
        return err

    result = auth_service.refresh_session(table=table, user_id=user_id)
    if result is None:
        return error_response(401, "Session expired or invalid. Please sign in again.")
    return json_response(200, result.model_dump(), _get_no_cache_headers())


class BulkRevocationRequest(BaseModel):
    """Request for POST /api/v2/admin/sessions/revoke."""

    user_ids: list[str]
    reason: str


@admin_router.post(
    "/api/v2/admin/sessions/revoke",
    middlewares=[require_role_middleware("operator")],
)
def revoke_sessions_bulk():
    """Bulk session revocation - andon cord pattern (T057).

    Feature 014: Revoke multiple sessions at once for security incidents.
    Protected by require_role_middleware("operator") - Feature 1148.
    """
    event = admin_router.current_event.raw_event
    table = get_users_table()

    body, err = _parse_request_body(event, BulkRevocationRequest)
    if err:
        return err

    result = auth_service.revoke_sessions_bulk(
        table=table,
        user_ids=body.user_ids,
        reason=body.reason,
    )
    return json_response(200, result.model_dump())


class CheckEmailRequest(BaseModel):
    email: EmailStr


@auth_router.post("/api/v2/auth/check-email", middlewares=[require_csrf_middleware])
def check_email_conflict():
    """Check for email account conflict (T097)."""
    event = auth_router.current_event.raw_event
    table = get_users_table()

    body, err = _parse_request_body(event, CheckEmailRequest)
    if err:
        return err

    result = auth_service.check_email_conflict(table=table, email=body.email)
    return json_response(200, result.model_dump(), _get_no_cache_headers())


class LinkAccountsRequest(BaseModel):
    email: EmailStr
    confirmation_token: str


@auth_router.post("/api/v2/auth/link-accounts", middlewares=[require_csrf_middleware])
def link_accounts():
    """Link accounts (T098)."""
    event = auth_router.current_event.raw_event
    table = get_users_table()

    body, err = _parse_request_body(event, LinkAccountsRequest)
    if err:
        return err

    user_id, err = _require_user_id(event)
    if err:
        return err

    result = auth_service.link_accounts(
        table=table,
        anonymous_user_id=user_id,
        email=body.email,
        confirmation_token=body.confirmation_token,
    )
    if isinstance(result, auth_service.ErrorResponse):
        return error_response(400, result.error.message)
    return json_response(200, result.model_dump(), _get_no_cache_headers())


@auth_router.get("/api/v2/auth/merge-status", middlewares=[require_csrf_middleware])
def get_merge_status():
    """Get merge status (T099)."""
    event = auth_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    result = auth_service.get_merge_status_endpoint(table=table, user_id=user_id)
    return json_response(200, result.model_dump(), _get_no_cache_headers())


class MergeRequest(BaseModel):
    """Request body for POST /api/v2/auth/merge."""

    anonymous_user_id: str


@auth_router.post("/api/v2/auth/merge", middlewares=[require_csrf_middleware])
def merge_anonymous_data():
    """Merge anonymous session data into authenticated account (T069).

    Feature 014 (US5): Atomic and idempotent account merge.
    - FR-013: Idempotent - retrying has no side effects
    - FR-014: Uses tombstone pattern for audit trail
    - FR-015: Safe for concurrent calls

    Requires authenticated session.

    Returns:
        MergeResponse with status and counts of merged items
    """
    from src.lambdas.shared.auth.merge import merge_anonymous_data as do_merge

    event = auth_router.current_event.raw_event
    table = get_users_table()

    body, err = _parse_request_body(event, MergeRequest)
    if err:
        return err

    user_id, err = _require_user_id(event)
    if err:
        return err

    # Validate the authenticated user exists and is authenticated (not anonymous)
    user = auth_service.get_user_by_id(table=table, user_id=user_id)
    if not user:
        return error_response(401, "Authentication required")

    if user.auth_type == "anonymous":
        return error_response(
            400, "Cannot merge into anonymous account. Please authenticate first."
        )

    # Perform the merge
    result = do_merge(
        table=table,
        anonymous_user_id=body.anonymous_user_id,
        authenticated_user_id=user_id,
    )

    # Map result status to HTTP status
    if result.status == "failed" and result.error == "merge_conflict":
        return error_response(409, result.message or "Merge conflict")

    if result.status == "failed":
        return error_response(500, result.message or "Merge failed")

    # Return successful response
    response_data = {
        "status": result.status,
        "merged_at": result.merged_at.isoformat() if result.merged_at else None,
        "configurations": result.configurations,
        "alert_rules": result.alert_rules,
        "preferences": result.preferences,
        "message": result.message,
    }

    return json_response(200, response_data, _get_no_cache_headers())


# ===================================================================
# Users Endpoints (Feature 014)
# ===================================================================


class UserLookupResponse(BaseModel):
    """Response for GET /api/v2/users/lookup."""

    found: bool
    user_id: str | None = None
    auth_type: str | None = None
    email_masked: str | None = None


@users_router.get(
    "/api/v2/users/lookup",
    middlewares=[require_role_middleware("operator")],
)
def lookup_user_by_email():
    """Look up user by email address (T044).

    Feature 014: Uses GSI for O(1) lookup performance.
    Protected by require_role_middleware("operator") - Feature 1149.

    Returns:
        UserLookupResponse with found=true if user exists
    """
    event = users_router.current_event.raw_event
    table = get_users_table()

    query_params = get_query_params(event)
    email = query_params.get("email")
    if not email:
        return error_response(400, "Missing email query parameter")

    # Validate email format
    try:
        EmailStr._validate(email)
    except Exception:
        return error_response(400, "Invalid email format")

    user = auth_service.get_user_by_email_gsi(table=table, email=email)

    if user:
        return json_response(
            200,
            UserLookupResponse(
                found=True,
                user_id=user.user_id,
                auth_type=user.auth_type,
                email_masked=auth_service._mask_email(user.email),
            ).model_dump(),
        )

    return json_response(
        200,
        UserLookupResponse(
            found=False,
            user_id=None,
            auth_type=None,
            email_masked=None,
        ).model_dump(),
    )


# ===================================================================
# Configuration Endpoints
# ===================================================================


@config_router.post("/api/v2/configurations")
def create_configuration():
    """Create configuration (T049).

    Root cause fix (Feature 077): Service function create_configuration()
    re-raises DynamoDB exceptions. Without try/except here, these propagate
    as HTTP 500. Now we catch exceptions and return appropriate status codes.
    """
    event = config_router.current_event.raw_event
    table = get_users_table()
    ticker_cache = get_ticker_cache_dependency()

    user_id, err = _require_user_id(event)
    if err:
        return err

    body, err = _parse_request_body(event, config_service.ConfigurationCreate)
    if err:
        return err

    # FR-006: Log only safe fields (counts, booleans), NEVER user content
    logger.info(
        "Config creation attempt",
        extra={
            "operation": "create_configuration",
            "ticker_count": len(body.tickers),
            "ticker_cache_available": ticker_cache is not None,
        },
    )

    try:
        result = config_service.create_configuration(
            table=table,
            user_id=user_id,
            request=body,
            ticker_cache=ticker_cache,
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        logger.error(
            "Config creation DynamoDB error",
            extra={"error_code": error_code, **get_safe_error_info(e)},
        )
        if error_code in (
            "ProvisionedThroughputExceededException",
            "ThrottlingException",
        ):
            return json_response(
                429,
                {"detail": "Service busy. Please retry in a few seconds."},
                {"Retry-After": "3"},
            )
        if error_code in ("ServiceUnavailable", "InternalServerError"):
            return json_response(
                503,
                {"detail": "Service temporarily unavailable. Please retry."},
                {"Retry-After": "5"},
            )
        return error_response(500, "Failed to create configuration. Please try again.")
    except ValueError as e:
        logger.warning(
            "Config creation failed due to validation",
            extra=get_safe_error_info(e),
        )
        return json_response(
            503,
            {"detail": "Ticker validation service temporarily unavailable."},
            {"Retry-After": "5"},
        )
    except Exception as e:
        logger.error(
            "Config creation failed with exception",
            extra=get_safe_error_info(e),
        )
        return error_response(500, "Failed to create configuration. Please try again.")

    if isinstance(result, config_service.ErrorResponse):
        if result.error.code == "MAX_CONFIGS_REACHED":
            return error_response(409, result.error.message)
        if result.error.code == "CONFLICT":
            return error_response(409, result.error.message)
        return error_response(400, result.error.message)
    return json_response(201, result.model_dump())


@config_router.get("/api/v2/configurations")
def list_configurations():
    """List configurations (T050)."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event, table=table)
    if err:
        return err

    result = config_service.list_configurations(table=table, user_id=user_id)
    return json_response(200, result.model_dump())


@config_router.get("/api/v2/configurations/<config_id>")
def get_configuration(config_id: str):
    """Get configuration (T051)."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    result = config_service.get_configuration(
        table=table,
        user_id=user_id,
        config_id=config_id,
    )
    if result is None:
        return error_response(404, "Configuration not found")
    if isinstance(result, config_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, result.model_dump())


def _update_configuration_impl(event: dict, config_id: str):
    """Internal implementation for config update (supports both PUT and PATCH)."""
    table = get_users_table()
    ticker_cache = get_ticker_cache_dependency()

    user_id, err = _require_user_id(event)
    if err:
        return err

    body, err = _parse_request_body(event, config_service.ConfigurationUpdate)
    if err:
        return err

    result = config_service.update_configuration(
        table=table,
        user_id=user_id,
        config_id=config_id,
        request=body,
        ticker_cache=ticker_cache,
    )
    if result is None:
        return error_response(404, "Configuration not found")
    if isinstance(result, config_service.ErrorResponse):
        return error_response(400, result.error.message)
    return json_response(200, result.model_dump())


@config_router.patch("/api/v2/configurations/<config_id>")
def update_configuration_patch(config_id: str):
    """Update configuration via PATCH (T052)."""
    event = config_router.current_event.raw_event
    return _update_configuration_impl(event, config_id)


@config_router.put("/api/v2/configurations/<config_id>")
def update_configuration_put(config_id: str):
    """Update configuration via PUT (T052)."""
    event = config_router.current_event.raw_event
    return _update_configuration_impl(event, config_id)


@config_router.delete("/api/v2/configurations/<config_id>")
def delete_configuration(config_id: str):
    """Delete configuration (T053)."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    result = config_service.delete_configuration(
        table=table,
        user_id=user_id,
        config_id=config_id,
    )
    if not result:
        return error_response(404, "Configuration not found")
    return json_response(200, {"message": "Configuration deleted"})


# Configuration data endpoints


@config_router.get("/api/v2/configurations/<config_id>/sentiment")
def get_sentiment(config_id: str):
    """Get sentiment data for configuration (T056)."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    config_data, err = _get_config_with_tickers(table, user_id, config_id)
    if err:
        return err
    _, tickers = config_data

    result = sentiment_service.get_sentiment_by_configuration(
        config_id=config_id,
        tickers=tickers,
    )
    return json_response(200, result.model_dump())


@config_router.get("/api/v2/configurations/<config_id>/heatmap")
def get_heatmap(config_id: str):
    """Get heat map data (T057)."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    query_params = get_query_params(event)
    view = query_params.get("view", "sources")
    # Validate view parameter
    if view not in ("sources", "time_periods", "timeperiods"):
        return error_response(
            400,
            "Invalid view parameter. Must be: sources, time_periods, or timeperiods",
        )

    config_data, err = _get_config_with_tickers(table, user_id, config_id)
    if err:
        return err
    _, tickers = config_data

    # Normalize view parameter
    normalized_view = "timeperiods" if view == "time_periods" else view
    result = sentiment_service.get_heatmap_data(
        config_id=config_id,
        tickers=tickers,
        view=normalized_view,
    )
    return json_response(200, result.model_dump())


@config_router.get("/api/v2/configurations/<config_id>/volatility")
def get_volatility(config_id: str):
    """Get volatility data (T058)."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    config_data, err = _get_config_with_tickers(table, user_id, config_id)
    if err:
        return err
    _, tickers = config_data

    result = volatility_service.get_volatility_by_configuration(
        config_id=config_id,
        tickers=tickers,
    )
    return json_response(200, result.model_dump())


@config_router.get("/api/v2/configurations/<config_id>/correlation")
def get_correlation(config_id: str):
    """Get correlation data (T059)."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    config_data, err = _get_config_with_tickers(table, user_id, config_id)
    if err:
        return err
    _, tickers = config_data

    result = volatility_service.get_correlation_data(
        config_id=config_id,
        tickers=tickers,
    )
    return json_response(200, result.model_dump())


@config_router.get("/api/v2/configurations/<config_id>/refresh/status")
def get_refresh_status(config_id: str):
    """Get refresh status (T060)."""
    result = market_service.get_refresh_status(config_id=config_id)
    return json_response(200, result.model_dump())


@config_router.post("/api/v2/configurations/<config_id>/refresh")
def trigger_refresh(config_id: str):
    """Trigger manual refresh (T061)."""
    result = market_service.trigger_refresh(config_id=config_id)
    return json_response(202, result.model_dump())


@config_router.get("/api/v2/configurations/<config_id>/premarket")
def get_premarket(config_id: str):
    """Get pre-market estimates (T063)."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    result = market_service.get_premarket_estimates(
        table=table,
        user_id=user_id,
        config_id=config_id,
    )
    if isinstance(result, market_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, result.model_dump())


@config_router.get("/api/v2/configurations/<config_id>/sentiment/<ticker>/history")
def get_ticker_sentiment_history(config_id: str, ticker: str):
    """Get sentiment history for a specific ticker within a configuration."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    query_params = get_query_params(event)
    source = query_params.get("source")
    if source and source not in ("tiingo", "finnhub"):
        return error_response(400, "Invalid source. Must be: tiingo or finnhub")

    days_str = query_params.get("days", "7")
    try:
        days = int(days_str)
        if days < 1 or days > 30:
            return error_response(400, "days must be between 1 and 30")
    except ValueError:
        return error_response(400, "days must be an integer")

    result = sentiment_service.get_ticker_sentiment_history(
        table=table,
        user_id=user_id,
        config_id=config_id,
        ticker=ticker,
        source=source,
        days=days,
    )
    if isinstance(result, sentiment_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, result.model_dump())


@config_router.get("/api/v2/configurations/<config_id>/alerts")
def get_config_alerts(config_id: str):
    """Get alerts for a specific configuration."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    result = alert_service.get_alerts_by_config(
        table=table,
        user_id=user_id,
        config_id=config_id,
    )
    if isinstance(result, alert_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, result.model_dump())


@config_router.post("/api/v2/configurations/<config_id>/alerts")
def create_config_alert(config_id: str):
    """Create alert for a specific configuration.

    Maps test-style request fields to AlertRuleCreate:
    - type (sentiment/volatility) -> alert_type (sentiment_threshold/volatility_threshold)
    - threshold -> threshold_value
    - condition -> threshold_direction
    """
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    body, err = _parse_request_body(event, ConfigAlertCreateRequest)
    if err:
        return err

    # Map test-style fields to AlertRuleCreate fields
    alert_type = f"{body.type}_threshold"
    alert_request = alert_service.AlertRuleCreate(
        config_id=config_id,
        ticker=body.ticker,
        alert_type=alert_type,
        threshold_value=body.threshold,
        threshold_direction=body.condition,
    )
    result = alert_service.create_alert(
        table=table,
        user_id=user_id,
        request=alert_request,
    )
    if isinstance(result, alert_service.ErrorResponse):
        if result.error.code == "MAX_ALERTS_REACHED":
            return error_response(409, result.error.message)
        return error_response(400, result.error.message)
    # Map response fields to match test expectations
    response_data = result.model_dump()
    if "alert_type" in response_data:
        response_data["type"] = response_data["alert_type"].replace("_threshold", "")
    if "is_enabled" in response_data:
        response_data["enabled"] = response_data["is_enabled"]
    return json_response(201, response_data)


@config_router.patch("/api/v2/configurations/<config_id>/alerts/<alert_id>")
def update_config_alert(config_id: str, alert_id: str):
    """Update alert for a specific configuration."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    body, err = _parse_request_body(event, alert_service.AlertUpdateRequest)
    if err:
        return err

    result = alert_service.update_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
        request=body,
    )
    if isinstance(result, alert_service.ErrorResponse):
        return error_response(404, result.error.message)
    if result is None:
        return error_response(404, "Alert not found")
    # Map internal field names to client-facing names
    response_data = result.model_dump()
    if "is_enabled" in response_data:
        response_data["enabled"] = response_data["is_enabled"]
    if "threshold_value" in response_data:
        response_data["threshold"] = response_data["threshold_value"]
    if "threshold_direction" in response_data:
        response_data["condition"] = response_data["threshold_direction"]
    return json_response(200, response_data)


@config_router.delete("/api/v2/configurations/<config_id>/alerts/<alert_id>")
def delete_config_alert(config_id: str, alert_id: str):
    """Delete alert for a specific configuration."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = alert_service.delete_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
    )
    if isinstance(result, alert_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, {"message": "Alert deleted"})


@config_router.post("/api/v2/configurations/<config_id>/alerts/<alert_id>/toggle")
def toggle_config_alert(config_id: str, alert_id: str):
    """Toggle alert enabled status for a specific configuration."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = alert_service.toggle_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
    )
    if isinstance(result, alert_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, result.model_dump())


# ===================================================================
# Ticker Endpoints
# ===================================================================


@ticker_router.get("/api/v2/tickers/validate")
def validate_ticker():
    """Validate ticker symbol (T054)."""
    event = ticker_router.current_event.raw_event
    ticker_cache = get_ticker_cache_dependency()

    query_params = get_query_params(event)
    symbol = query_params.get("symbol", "")
    if not symbol or len(symbol) > 5:
        return error_response(400, "symbol must be 1-5 characters")

    result = ticker_service.validate_ticker(
        symbol=symbol,
        ticker_cache=ticker_cache,
    )
    return json_response(200, result.model_dump())


@ticker_router.get("/api/v2/tickers/search")
def search_tickers():
    """Search tickers (T055)."""
    event = ticker_router.current_event.raw_event
    ticker_cache = get_ticker_cache_dependency()

    query_params = get_query_params(event)
    q = query_params.get("q", "")
    if not q or len(q) > 50:
        return error_response(400, "q must be 1-50 characters")

    limit_str = query_params.get("limit", "10")
    try:
        limit = int(limit_str)
        if limit < 1 or limit > 20:
            return error_response(400, "limit must be between 1 and 20")
    except ValueError:
        return error_response(400, "limit must be an integer")

    result = ticker_service.search_tickers(
        query=q,
        limit=limit,
        ticker_cache=ticker_cache,
    )
    return json_response(200, result.model_dump())


# ===================================================================
# Market Endpoints
# ===================================================================


@market_router.get("/api/v2/market/status")
def get_market_status():
    """Get market status (T062)."""
    result = market_service.get_market_status()
    return json_response(200, result.model_dump())


# ===================================================================
# Timeseries Endpoints (Feature 1009)
# ===================================================================


@timeseries_router.get("/api/v2/timeseries/<ticker>")
def get_timeseries(ticker: str):
    """Get time-series sentiment data for a ticker (T035, T042).

    Feature 1009: Multi-resolution sentiment time-series with pagination.
    Canonical: [CS-001] DynamoDB best practices, [CS-005] Lambda caching

    Pagination:
        Use `limit` to control page size and `cursor` to fetch next page.
        Response includes `next_cursor` and `has_more` for iteration.
    """
    from datetime import datetime

    from src.lib.timeseries import Resolution

    event = timeseries_router.current_event.raw_event
    query_params = get_query_params(event)

    resolution = query_params.get("resolution", "")
    if not resolution:
        return error_response(400, "Missing resolution parameter")

    # Parse resolution
    try:
        res = Resolution(resolution)
    except ValueError:
        return error_response(
            400,
            f"Invalid resolution: {resolution}. Valid: 1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h",
        )

    # Parse time range
    start = query_params.get("start")
    end = query_params.get("end")
    start_dt = None
    end_dt = None
    if start:
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            return error_response(400, "Invalid start time format")
    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError:
            return error_response(400, "Invalid end time format")

    limit_str = query_params.get("limit")
    limit = None
    if limit_str:
        try:
            limit = int(limit_str)
            if limit < 1 or limit > 1000:
                return error_response(400, "limit must be between 1 and 1000")
        except ValueError:
            return error_response(400, "limit must be an integer")

    cursor = query_params.get("cursor")

    response = timeseries_service.query_timeseries(
        ticker=ticker.upper(),
        resolution=res,
        start=start_dt,
        end=end_dt,
        limit=limit,
        cursor=cursor,
    )

    return json_response(200, response.to_dict())


@timeseries_router.get("/api/v2/timeseries/batch")
def get_timeseries_batch():
    """Get time-series sentiment data for multiple tickers in parallel (T050, T052).

    Feature 1009 Phase 6: Multi-ticker comparison view with batch queries.
    Performance target: SC-006 - 10 tickers in <1 second via parallel I/O.
    """
    from datetime import datetime

    from src.lib.timeseries import Resolution

    event = timeseries_router.current_event.raw_event
    query_params = get_query_params(event)

    tickers_str = query_params.get("tickers", "")
    if not tickers_str:
        return error_response(400, "Missing tickers parameter")

    resolution = query_params.get("resolution", "")
    if not resolution:
        return error_response(400, "Missing resolution parameter")

    try:
        res = Resolution(resolution)
    except ValueError:
        return error_response(
            400,
            f"Invalid resolution: {resolution}. Valid: 1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h",
        )

    ticker_list = [t.strip().upper() for t in tickers_str.split(",") if t.strip()]
    if not ticker_list:
        return error_response(400, "No valid tickers provided")
    if len(ticker_list) > 20:
        return error_response(400, "Maximum 20 tickers per batch request")

    start = query_params.get("start")
    end = query_params.get("end")
    start_dt = None
    end_dt = None
    if start:
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            return error_response(400, "Invalid start time format")
    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError:
            return error_response(400, "Invalid end time format")

    limit_str = query_params.get("limit")
    limit = None
    if limit_str:
        try:
            limit = int(limit_str)
            if limit < 1 or limit > 1000:
                return error_response(400, "limit must be between 1 and 1000")
        except ValueError:
            return error_response(400, "limit must be an integer")

    results = timeseries_service.query_batch(
        tickers=ticker_list,
        resolution=res,
        start=start_dt,
        end=end_dt,
        limit=limit,
    )

    response_dict = {ticker: response.to_dict() for ticker, response in results.items()}
    return json_response(200, response_dict)


# ===================================================================
# Alert Endpoints
# ===================================================================


@alert_router.post("/api/v2/alerts")
def create_alert():
    """Create alert rule (T131)."""
    event = alert_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    body, err = _parse_request_body(event, alert_service.AlertRuleCreate)
    if err:
        return err

    result = alert_service.create_alert(
        table=table,
        user_id=user_id,
        request=body,
    )
    if isinstance(result, alert_service.ErrorResponse):
        if result.error.code == "MAX_ALERTS_REACHED":
            return error_response(409, result.error.message)
        return error_response(400, result.error.message)
    return json_response(201, result.model_dump())


@alert_router.get("/api/v2/alerts")
def list_alerts():
    """List alerts (T132)."""
    event = alert_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    query_params = get_query_params(event)
    config_id = query_params.get("config_id")

    result = alert_service.list_alerts(
        table=table,
        user_id=user_id,
        config_id=config_id,
    )
    return json_response(200, result.model_dump())


@alert_router.get("/api/v2/alerts/<alert_id>")
def get_alert(alert_id: str):
    """Get alert (T133)."""
    event = alert_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = alert_service.get_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
    )
    if result is None:
        return error_response(404, "Alert not found")
    if isinstance(result, alert_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, result.model_dump())


@alert_router.patch("/api/v2/alerts/<alert_id>")
def update_alert(alert_id: str):
    """Update alert (T134)."""
    event = alert_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    body, err = _parse_request_body(event, alert_service.AlertUpdateRequest)
    if err:
        return err

    result = alert_service.update_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
        request=body,
    )
    if isinstance(result, alert_service.ErrorResponse):
        return error_response(404, result.error.message)
    if result is None:
        return error_response(404, "Alert not found")
    response_data = result.model_dump()
    if "is_enabled" in response_data:
        response_data["enabled"] = response_data["is_enabled"]
    if "threshold_value" in response_data:
        response_data["threshold"] = response_data["threshold_value"]
    if "threshold_direction" in response_data:
        response_data["condition"] = response_data["threshold_direction"]
    return json_response(200, response_data)


@alert_router.delete("/api/v2/alerts/<alert_id>")
def delete_alert(alert_id: str):
    """Delete alert (T135)."""
    event = alert_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = alert_service.delete_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
    )
    if isinstance(result, alert_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, {"message": "Alert deleted"})


@alert_router.post("/api/v2/alerts/<alert_id>/toggle")
def toggle_alert(alert_id: str):
    """Toggle alert enabled status (T136)."""
    event = alert_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = alert_service.toggle_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
    )
    if isinstance(result, alert_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, result.model_dump())


@alert_router.get("/api/v2/alerts/quota")
def get_alert_quota():
    """Get alert email quota usage (T145).

    Returns daily email quota status including:
    - used: Number of emails sent today
    - limit: Maximum emails per day
    - remaining: Emails left today
    - resets_at: When quota resets (ISO datetime)
    """
    event = alert_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = quota_service.get_daily_quota(
        table=table,
        user_id=user_id,
    )
    return json_response(200, result.model_dump())


# ===================================================================
# Notification Endpoints
# ===================================================================


@notification_router.get("/api/v2/notifications")
def list_notifications():
    """List notification history (T137)."""
    event = notification_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    query_params = get_query_params(event)

    limit_str = query_params.get("limit", "20")
    try:
        limit = int(limit_str)
        if limit < 1 or limit > 100:
            return error_response(400, "limit must be between 1 and 100")
    except ValueError:
        return error_response(400, "limit must be an integer")

    offset_str = query_params.get("offset", "0")
    try:
        offset = int(offset_str)
        if offset < 0:
            return error_response(400, "offset must be >= 0")
    except ValueError:
        return error_response(400, "offset must be an integer")

    status = query_params.get("status")
    alert_id = query_params.get("alert_id")

    result = notification_service.list_notifications(
        table=table,
        user_id=user_id,
        limit=limit,
        offset=offset,
        status=status,
        alert_id=alert_id,
    )
    return json_response(200, result.model_dump())


@notification_router.get("/api/v2/notifications/preferences")
def get_preferences():
    """Get notification preferences (T139)."""
    event = notification_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = notification_service.get_notification_preferences(
        table=table,
        user_id=user_id,
    )
    return json_response(200, result.model_dump())


@notification_router.patch("/api/v2/notifications/preferences")
def update_preferences():
    """Update notification preferences (T140)."""
    event = notification_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    body, err = _parse_request_body(event, NotificationPreferencesUpdate)
    if err:
        return err

    result = notification_service.update_notification_preferences(
        table=table,
        user_id=user_id,
        email_notifications_enabled=body.email_enabled,
        daily_digest_enabled=body.digest_enabled,
        digest_time=body.digest_time,
    )
    if isinstance(result, notification_service.ErrorResponse):
        return error_response(400, result.error.message)
    return json_response(200, result.model_dump())


@notification_router.post("/api/v2/notifications/disable-all")
def disable_all_notifications():
    """Disable all notifications (T141)."""
    event = notification_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = notification_service.disable_all_notifications(
        table=table,
        user_id=user_id,
    )
    return json_response(200, result.model_dump())


@notification_router.get("/api/v2/notifications/unsubscribe")
def unsubscribe():
    """Unsubscribe via email token (T142)."""
    event = notification_router.current_event.raw_event
    table = get_users_table()

    query_params = get_query_params(event)
    token = query_params.get("token")
    if not token:
        return error_response(400, "Missing token parameter")

    result = notification_service.unsubscribe_via_token(
        table=table,
        token=token,
    )
    if isinstance(result, notification_service.ErrorResponse):
        return error_response(400, result.error.message)
    return json_response(200, result.model_dump())


@notification_router.post("/api/v2/notifications/resubscribe")
def resubscribe():
    """Resubscribe to notifications (T143)."""
    event = notification_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = notification_service.resubscribe(
        table=table,
        user_id=user_id,
    )
    return json_response(200, result.model_dump())


@notification_router.get("/api/v2/notifications/digest")
def get_digest_settings():
    """Get digest settings (T144a)."""
    event = notification_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = notification_service.get_digest_settings(
        table=table,
        user_id=user_id,
    )
    return json_response(200, result.model_dump())


@notification_router.patch("/api/v2/notifications/digest")
def update_digest_settings():
    """Update digest settings (T144b)."""
    event = notification_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    body, err = _parse_request_body(event, DigestSettingsUpdate)
    if err:
        return err

    result = notification_service.update_digest_settings(
        table=table,
        user_id=user_id,
        enabled=body.enabled,
        time=body.time,
        timezone=body.timezone,
        include_all_configs=body.include_all_configs,
        config_ids=body.config_ids,
    )
    if isinstance(result, notification_service.ErrorResponse):
        return error_response(400, result.error.message)
    return json_response(200, result.model_dump())


@notification_router.post("/api/v2/notifications/digest/test")
def trigger_test_digest():
    """Trigger test digest (T144c)."""
    event = notification_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = notification_service.trigger_test_digest(
        table=table,
        user_id=user_id,
    )
    return json_response(202, result.model_dump())


@notification_router.get("/api/v2/notifications/<notification_id>")
def get_notification(notification_id: str):
    """Get notification detail (T138)."""
    event = notification_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_authenticated_user_id(event)
    if err:
        return err

    result = notification_service.get_notification(
        table=table,
        user_id=user_id,
        notification_id=notification_id,
    )
    if isinstance(result, notification_service.ErrorResponse):
        return error_response(404, result.error.message)
    return json_response(200, result.model_dump())


# ===================================================================
# Users Endpoint (for frontend)
# ===================================================================


@auth_router.get("/api/v2/auth/me", middlewares=[require_csrf_middleware])
def get_current_user():
    """Get current user info - MINIMAL response to prevent data leakage.

    Returns ONLY what frontend needs:
    - auth_type: For UI conditional rendering
    - email_masked: For display (j***@example.com)
    - configs_count/max_configs: For quota display
    - session_expires_in_seconds: For session countdown

    NEVER returns: user_id, cognito_sub, created_at, daily_email_count
    """
    event = auth_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event)
    if err:
        return err

    user = auth_service.get_user_by_id(table=table, user_id=user_id)
    if not user:
        return error_response(404, "User not found")

    # Count configurations
    config_result = config_service.list_configurations(table=table, user_id=user_id)
    config_count = (
        len(config_result.configurations)
        if hasattr(config_result, "configurations")
        else 0
    )

    response = UserMeResponse(
        auth_type=user.auth_type,
        email_masked=mask_email(user.email),
        configs_count=config_count,
        max_configs=2,
        session_expires_in_seconds=seconds_until(user.session_expires_at),
        # Feature 1172: Federation fields for RBAC-aware UI
        role=user.role,
        linked_providers=user.linked_providers,
        verification=user.verification,
        last_provider_used=user.last_provider_used,
    )

    return json_response(200, response.model_dump(), _get_no_cache_headers())


def include_routers(app):
    """Include all v2 routers in the Powertools app."""
    app.include_router(auth_router)
    app.include_router(config_router)
    app.include_router(ticker_router)
    app.include_router(alert_router)
    app.include_router(notification_router)
    app.include_router(market_router)
    # Feature 014: Users router for email lookup
    app.include_router(users_router)
    # Feature 014: Admin router for bulk operations
    app.include_router(admin_router)
    # Feature 1009: Multi-resolution sentiment time-series
    app.include_router(timeseries_router)
    # OHLC router (migrated to Powertools in T020)
    from src.lambdas.dashboard.ohlc import router as ohlc_router

    app.include_router(ohlc_router)
    # SSE router (migrated to Powertools in T023)
    from src.lambdas.dashboard.sse import router as sse_router

    app.include_router(sse_router)

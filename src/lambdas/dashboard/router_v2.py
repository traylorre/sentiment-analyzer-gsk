"""Feature 006 API v2 Router.

Wires all Feature 006 service functions to FastAPI endpoints.
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
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from src.lambdas.dashboard import alerts as alert_service

# Import service modules
from src.lambdas.dashboard import auth as auth_service
from src.lambdas.dashboard import configurations as config_service
from src.lambdas.dashboard import market as market_service
from src.lambdas.dashboard import notifications as notification_service
from src.lambdas.dashboard import ohlc as ohlc_module
from src.lambdas.dashboard import quota as quota_service
from src.lambdas.dashboard import sentiment as sentiment_service
from src.lambdas.dashboard import tickers as ticker_service
from src.lambdas.dashboard import volatility as volatility_service
from src.lambdas.shared.cache.ticker_cache import TickerCache, get_ticker_cache
from src.lambdas.shared.dynamodb import get_table
from src.lambdas.shared.errors import (
    SessionRevokedException,
    TokenAlreadyUsedError,
    TokenExpiredError,
)
from src.lambdas.shared.logging_utils import get_safe_error_info
from src.lambdas.shared.middleware import extract_auth_context
from src.lambdas.shared.response_models import (
    UserMeResponse,
    mask_email,
    seconds_until,
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

# Environment config
DYNAMODB_TABLE = os.environ.get("DATABASE_TABLE") or os.environ.get(
    "DYNAMODB_TABLE", ""
)
TICKER_CACHE_BUCKET = os.environ.get("TICKER_CACHE_BUCKET", "")

# Create routers
auth_router = APIRouter(prefix="/api/v2/auth", tags=["auth"])
config_router = APIRouter(prefix="/api/v2/configurations", tags=["configurations"])
ticker_router = APIRouter(prefix="/api/v2/tickers", tags=["tickers"])
alert_router = APIRouter(prefix="/api/v2/alerts", tags=["alerts"])
notification_router = APIRouter(prefix="/api/v2/notifications", tags=["notifications"])
market_router = APIRouter(prefix="/api/v2/market", tags=["market"])
# Feature 014: Users router for email lookup (T044)
users_router = APIRouter(prefix="/api/v2/users", tags=["users"])


def get_dynamodb_table():
    """Dependency to get DynamoDB table."""
    return get_table(DYNAMODB_TABLE)


def get_ticker_cache_dependency() -> TickerCache | None:
    """Dependency to get ticker cache instance.

    Returns None if TICKER_CACHE_BUCKET is not configured,
    allowing graceful degradation (service functions will
    fall back to external API validation).
    """
    if not TICKER_CACHE_BUCKET:
        logger.debug("TICKER_CACHE_BUCKET not configured, ticker cache disabled")
        return None
    try:
        return get_ticker_cache(TICKER_CACHE_BUCKET)
    except Exception as e:
        logger.warning(f"Failed to load ticker cache: {e}")
        return None


def get_user_id_from_request(
    request: Request, table=None, validate_session: bool = True
) -> str:
    """Extract user_id from request headers/session and optionally validate.

    Feature 014: Supports hybrid authentication approach:
    1. Authorization: Bearer {token} - preferred for new code
    2. X-User-ID header - legacy, backward compatible

    Args:
        request: FastAPI Request object
        table: DynamoDB table for session validation (optional)
        validate_session: Whether to validate session is still active

    Returns:
        user_id if valid

    Raises:
        HTTPException 401 if user_id missing or session expired
        HTTPException 403 if session has been revoked
    """
    # Feature 014: Use hybrid auth middleware to extract user_id
    # Build event dict for middleware compatibility
    event = {"headers": dict(request.headers)}
    auth_context = extract_auth_context(event)

    user_id = auth_context.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user identification")

    # Validate session is still active (not signed out/expired)
    if validate_session and table is not None:
        try:
            validation = auth_service.validate_session(
                table=table, anonymous_id=user_id
            )
            if not validation.valid:
                raise HTTPException(
                    status_code=401, detail="Session expired or invalid"
                )
        except SessionRevokedException as e:
            # Feature 014: Handle server-side session revocation
            raise HTTPException(
                status_code=403,
                detail=f"Session revoked: {e.reason or 'Security policy'}",
            ) from e

    return user_id


def get_authenticated_user_id(request: Request) -> str:
    """Get authenticated user ID (non-anonymous).

    For endpoints that require authenticated users (not anonymous).
    """
    user_id = get_user_id_from_request(request)
    auth_type = request.headers.get("X-Auth-Type", "anonymous")
    if auth_type == "anonymous":
        raise HTTPException(
            status_code=403, detail="This endpoint requires authenticated user"
        )
    return user_id


async def get_config_with_tickers(
    table, user_id: str, config_id: str
) -> tuple[str, list[str]]:
    """Fetch configuration and extract ticker symbols.

    Returns:
        Tuple of (config_id, list of ticker symbols)

    Raises:
        HTTPException 404 if config not found
    """
    config = config_service.get_configuration(
        table=table, user_id=user_id, config_id=config_id
    )
    if config is None:
        raise HTTPException(status_code=404, detail="Configuration not found")
    if isinstance(config, config_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=config.error.message)

    # Extract ticker symbols from configuration
    tickers = [t.symbol for t in config.tickers]
    return config_id, tickers


# ===================================================================
# Authentication Endpoints
# ===================================================================


@auth_router.post("/anonymous")
async def create_anonymous_session(
    request: Request,
    body: auth_service.AnonymousSessionRequest,
    table=Depends(get_dynamodb_table),
):
    """Create anonymous session (T047)."""
    try:
        result = auth_service.create_anonymous_session(
            table=table,
            request=body,
        )
        return JSONResponse(result.model_dump(), status_code=201)
    except Exception as e:
        logger.error("Failed to create anonymous session", extra=get_safe_error_info(e))
        raise HTTPException(status_code=500, detail="Failed to create session") from e


@auth_router.get("/validate")
async def validate_session(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Validate session (T048)."""
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        return JSONResponse({"valid": False, "reason": "missing_user_id"})

    result = auth_service.validate_session(table=table, user_id=user_id)
    return JSONResponse(result.model_dump())


@auth_router.post("/extend")
async def extend_session(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Extend session by 30 days."""
    user_id = get_user_id_from_request(request)
    user = auth_service.extend_session(table=table, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return JSONResponse(
        {
            "message": "Session extended",
            "expires_at": user.session_expires_at.isoformat(),
        }
    )


class MagicLinkRequest(BaseModel):
    email: EmailStr
    redirect_url: str | None = None


@auth_router.post("/magic-link")
async def request_magic_link(
    request: Request,
    body: MagicLinkRequest,
    table=Depends(get_dynamodb_table),
):
    """Request magic link email (T090)."""
    user_id = request.headers.get("X-User-ID")  # Optional for linking
    result = auth_service.request_magic_link(
        table=table,
        request=auth_service.MagicLinkRequest(
            email=body.email,
            anonymous_user_id=user_id,
        ),
    )
    return JSONResponse(result.model_dump())


@auth_router.get("/magic-link/verify")
async def verify_magic_link(
    token: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Verify magic link token (T091).

    Security: refresh_token is set as HttpOnly cookie, NEVER in body.

    Feature 014 (T034): Returns appropriate error codes for race conditions:
    - 409 Conflict: Token already used by another request
    - 410 Gone: Token has expired
    """
    # Try atomic verification first for race condition protection
    try:
        result = auth_service.verify_magic_link(table=table, token=token)
    except TokenAlreadyUsedError as e:
        # Feature 014 (FR-005): 409 for token already used
        raise HTTPException(
            status_code=409,
            detail="This magic link has already been verified",
        ) from e
    except TokenExpiredError as e:
        # Feature 014 (FR-006): 410 for expired token
        raise HTTPException(
            status_code=410,
            detail="This magic link has expired. Please request a new one.",
        ) from e

    if isinstance(result, auth_service.ErrorResponse):
        raise HTTPException(status_code=400, detail=result.error.message)

    # Extract refresh_token for HttpOnly cookie
    refresh_token = result.refresh_token_for_cookie

    # Build response WITHOUT refresh_token in body
    response_data = result.model_dump(exclude={"refresh_token_for_cookie"})
    response = JSONResponse(response_data)

    # Set refresh_token as HttpOnly, Secure cookie (NOT in response body)
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,  # HTTPS only
            samesite="strict",
            max_age=30 * 24 * 60 * 60,  # 30 days
            path="/api/v2/auth",  # Only sent to auth endpoints
        )

    return response


@auth_router.get("/oauth/urls")
async def get_oauth_urls():
    """Get OAuth provider URLs (T092)."""
    result = auth_service.get_oauth_urls()
    return JSONResponse(result.model_dump())


class OAuthCallbackRequest(BaseModel):
    code: str
    provider: str
    redirect_uri: str


@auth_router.post("/oauth/callback")
async def handle_oauth_callback(
    request: Request,
    body: OAuthCallbackRequest,
    table=Depends(get_dynamodb_table),
):
    """Handle OAuth callback (T093).

    Security: refresh_token is set as HttpOnly cookie, NEVER in body.
    """
    user_id = request.headers.get("X-User-ID")  # Optional for linking
    result = auth_service.handle_oauth_callback(
        table=table,
        code=body.code,
        provider=body.provider,
        redirect_uri=body.redirect_uri,
        anonymous_user_id=user_id,
    )
    if isinstance(result, auth_service.ErrorResponse):
        raise HTTPException(status_code=400, detail=result.error.message)

    # Extract refresh_token for HttpOnly cookie
    refresh_token = result.refresh_token_for_cookie

    # Build response WITHOUT refresh_token in body
    response_data = result.model_dump(exclude={"refresh_token_for_cookie"})
    response = JSONResponse(response_data)

    # Set refresh_token as HttpOnly, Secure cookie (NOT in response body)
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,  # HTTPS only
            samesite="strict",
            max_age=30 * 24 * 60 * 60,  # 30 days
            path="/api/v2/auth",  # Only sent to auth endpoints
        )

    return response


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@auth_router.post("/refresh")
async def refresh_tokens(body: RefreshTokenRequest):
    """Refresh access tokens (T094)."""
    result = auth_service.refresh_access_tokens(refresh_token=body.refresh_token)
    if isinstance(result, auth_service.ErrorResponse):
        raise HTTPException(status_code=401, detail=result.error.message)
    return JSONResponse(result.model_dump())


@auth_router.post("/signout")
async def sign_out(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Sign out current device (T095)."""
    # Extract access token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    access_token = auth_header.replace("Bearer ", "") if auth_header else ""
    user_id = get_user_id_from_request(request)
    result = auth_service.sign_out(
        table=table,
        user_id=user_id,
        access_token=access_token,
    )
    return JSONResponse(result.model_dump())


@auth_router.get("/session")
async def get_session_info(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get session info (T096)."""
    user_id = get_user_id_from_request(request)
    result = auth_service.get_session_info(table=table, user_id=user_id)
    if isinstance(result, auth_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse(result.model_dump())


@auth_router.post("/session/refresh")
async def refresh_session(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Refresh session expiry (T056).

    Feature 014: Extends session by 30 days (sliding window pattern).
    Returns new expiry time and remaining seconds.
    """
    user_id = get_user_id_from_request(request, table=table, validate_session=False)
    result = auth_service.refresh_session(table=table, user_id=user_id)
    if result is None:
        raise HTTPException(
            status_code=401, detail="Session expired or invalid. Please sign in again."
        )
    return JSONResponse(result.model_dump())


class BulkRevocationRequest(BaseModel):
    """Request for POST /api/v2/admin/sessions/revoke."""

    user_ids: list[str]
    reason: str


# Admin router for bulk operations
admin_router = APIRouter(prefix="/api/v2/admin", tags=["admin"])


@admin_router.post("/sessions/revoke")
async def revoke_sessions_bulk(
    body: BulkRevocationRequest,
    table=Depends(get_dynamodb_table),
):
    """Bulk session revocation - andon cord pattern (T057).

    Feature 014: Revoke multiple sessions at once for security incidents.
    Requires admin authentication in production.
    """
    result = auth_service.revoke_sessions_bulk(
        table=table,
        user_ids=body.user_ids,
        reason=body.reason,
    )
    return JSONResponse(result.model_dump())


class CheckEmailRequest(BaseModel):
    email: EmailStr


@auth_router.post("/check-email")
async def check_email_conflict(
    body: CheckEmailRequest,
    table=Depends(get_dynamodb_table),
):
    """Check for email account conflict (T097)."""
    result = auth_service.check_email_conflict(table=table, email=body.email)
    return JSONResponse(result.model_dump())


class LinkAccountsRequest(BaseModel):
    email: EmailStr
    confirmation_token: str


@auth_router.post("/link-accounts")
async def link_accounts(
    request: Request,
    body: LinkAccountsRequest,
    table=Depends(get_dynamodb_table),
):
    """Link accounts (T098)."""
    user_id = get_user_id_from_request(request)
    result = auth_service.link_accounts(
        table=table,
        anonymous_user_id=user_id,
        email=body.email,
        confirmation_token=body.confirmation_token,
    )
    if isinstance(result, auth_service.ErrorResponse):
        raise HTTPException(status_code=400, detail=result.error.message)
    return JSONResponse(result.model_dump())


@auth_router.get("/merge-status")
async def get_merge_status(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get merge status (T099)."""
    user_id = get_user_id_from_request(request)
    result = auth_service.get_merge_status_endpoint(table=table, user_id=user_id)
    return JSONResponse(result.model_dump())


class MergeRequest(BaseModel):
    """Request body for POST /api/v2/auth/merge."""

    anonymous_user_id: str


@auth_router.post("/merge")
async def merge_anonymous_data(
    request: Request,
    body: MergeRequest,
    table=Depends(get_dynamodb_table),
):
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

    authenticated_user_id = get_user_id_from_request(request)

    # Validate the authenticated user exists and is authenticated (not anonymous)
    user = auth_service.get_user_by_id(table=table, user_id=authenticated_user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    if user.auth_type == "anonymous":
        raise HTTPException(
            status_code=400,
            detail="Cannot merge into anonymous account. Please authenticate first.",
        )

    # Perform the merge
    result = do_merge(
        table=table,
        anonymous_user_id=body.anonymous_user_id,
        authenticated_user_id=authenticated_user_id,
    )

    # Map result status to HTTP status
    if result.status == "failed" and result.error == "merge_conflict":
        raise HTTPException(
            status_code=409,
            detail=result.message or "Merge conflict",
        )

    if result.status == "failed":
        raise HTTPException(
            status_code=500,
            detail=result.message or "Merge failed",
        )

    # Return successful response
    response_data = {
        "status": result.status,
        "merged_at": result.merged_at.isoformat() if result.merged_at else None,
        "configurations": result.configurations,
        "alert_rules": result.alert_rules,
        "preferences": result.preferences,
        "message": result.message,
    }

    return JSONResponse(response_data)


# ===================================================================
# Users Endpoints (Feature 014)
# ===================================================================


class UserLookupResponse(BaseModel):
    """Response for GET /api/v2/users/lookup."""

    found: bool
    user_id: str | None = None
    auth_type: str | None = None
    email_masked: str | None = None


@users_router.get("/lookup")
async def lookup_user_by_email(
    email: EmailStr = Query(..., description="Email address to look up"),
    table=Depends(get_dynamodb_table),
):
    """Look up user by email address (T044).

    Feature 014: Uses GSI for O(1) lookup performance.
    Requires admin authentication in production.

    Returns:
        UserLookupResponse with found=true if user exists
    """
    user = auth_service.get_user_by_email_gsi(table=table, email=email)

    if user:
        return JSONResponse(
            UserLookupResponse(
                found=True,
                user_id=user.user_id,
                auth_type=user.auth_type,
                email_masked=auth_service._mask_email(user.email),
            ).model_dump()
        )

    return JSONResponse(
        UserLookupResponse(
            found=False,
            user_id=None,
            auth_type=None,
            email_masked=None,
        ).model_dump()
    )


# ===================================================================
# Configuration Endpoints
# ===================================================================


@config_router.post("")
async def create_configuration(
    request: Request,
    body: config_service.ConfigurationCreate,
    table=Depends(get_dynamodb_table),
    ticker_cache: TickerCache | None = Depends(get_ticker_cache_dependency),
):
    """Create configuration (T049)."""
    user_id = get_user_id_from_request(request)
    result = config_service.create_configuration(
        table=table,
        user_id=user_id,
        request=body,
        ticker_cache=ticker_cache,
    )
    if isinstance(result, config_service.ErrorResponse):
        if result.error.code == "MAX_CONFIGS_REACHED":
            raise HTTPException(status_code=409, detail=result.error.message)
        raise HTTPException(status_code=400, detail=result.error.message)
    return JSONResponse(result.model_dump(), status_code=201)


@config_router.get("")
async def list_configurations(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """List configurations (T050)."""
    user_id = get_user_id_from_request(request, table=table)
    result = config_service.list_configurations(table=table, user_id=user_id)
    return JSONResponse(result.model_dump())


@config_router.get("/{config_id}")
async def get_configuration(
    config_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get configuration (T051)."""
    user_id = get_user_id_from_request(request)
    result = config_service.get_configuration(
        table=table,
        user_id=user_id,
        config_id=config_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Configuration not found")
    if isinstance(result, config_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse(result.model_dump())


async def _update_configuration_impl(
    config_id: str,
    request: Request,
    body: config_service.ConfigurationUpdate,
    table,
    ticker_cache: TickerCache | None,
):
    """Internal implementation for config update (supports both PUT and PATCH)."""
    user_id = get_user_id_from_request(request)
    result = config_service.update_configuration(
        table=table,
        user_id=user_id,
        config_id=config_id,
        request=body,
        ticker_cache=ticker_cache,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Configuration not found")
    if isinstance(result, config_service.ErrorResponse):
        raise HTTPException(status_code=400, detail=result.error.message)
    return JSONResponse(result.model_dump())


@config_router.patch("/{config_id}")
async def update_configuration_patch(
    config_id: str,
    request: Request,
    body: config_service.ConfigurationUpdate,
    table=Depends(get_dynamodb_table),
    ticker_cache: TickerCache | None = Depends(get_ticker_cache_dependency),
):
    """Update configuration via PATCH (T052)."""
    return await _update_configuration_impl(
        config_id, request, body, table, ticker_cache
    )


@config_router.put("/{config_id}")
async def update_configuration_put(
    config_id: str,
    request: Request,
    body: config_service.ConfigurationUpdate,
    table=Depends(get_dynamodb_table),
    ticker_cache: TickerCache | None = Depends(get_ticker_cache_dependency),
):
    """Update configuration via PUT (T052)."""
    return await _update_configuration_impl(
        config_id, request, body, table, ticker_cache
    )


@config_router.delete("/{config_id}")
async def delete_configuration(
    config_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Delete configuration (T053)."""
    user_id = get_user_id_from_request(request)
    result = config_service.delete_configuration(
        table=table,
        user_id=user_id,
        config_id=config_id,
    )
    # delete_configuration returns bool: True if deleted, False if not found
    if not result:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return JSONResponse({"message": "Configuration deleted"})


# Configuration data endpoints


@config_router.get("/{config_id}/sentiment")
async def get_sentiment(
    config_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get sentiment data for configuration (T056)."""
    user_id = get_user_id_from_request(request)
    # Fetch config to get tickers
    _, tickers = await get_config_with_tickers(table, user_id, config_id)
    result = sentiment_service.get_sentiment_by_configuration(
        config_id=config_id,
        tickers=tickers,
    )
    return JSONResponse(result.model_dump())


@config_router.get("/{config_id}/heatmap")
async def get_heatmap(
    config_id: str,
    request: Request,
    view: str = Query("sources", pattern="^(sources|time_periods|timeperiods)$"),
    table=Depends(get_dynamodb_table),
):
    """Get heat map data (T057)."""
    user_id = get_user_id_from_request(request)
    # Fetch config to get tickers
    _, tickers = await get_config_with_tickers(table, user_id, config_id)
    # Normalize view parameter (accept both "timeperiods" and "time_periods")
    # Service expects "timeperiods" (no underscore)
    normalized_view = "timeperiods" if view == "time_periods" else view
    result = sentiment_service.get_heatmap_data(
        config_id=config_id,
        tickers=tickers,
        view=normalized_view,
    )
    return JSONResponse(result.model_dump())


@config_router.get("/{config_id}/volatility")
async def get_volatility(
    config_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get volatility data (T058)."""
    user_id = get_user_id_from_request(request)
    # Fetch config to get tickers
    _, tickers = await get_config_with_tickers(table, user_id, config_id)
    result = volatility_service.get_volatility_by_configuration(
        config_id=config_id,
        tickers=tickers,
    )
    return JSONResponse(result.model_dump())


@config_router.get("/{config_id}/correlation")
async def get_correlation(
    config_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get correlation data (T059)."""
    user_id = get_user_id_from_request(request)
    # Fetch config to get tickers
    _, tickers = await get_config_with_tickers(table, user_id, config_id)
    result = volatility_service.get_correlation_data(
        config_id=config_id,
        tickers=tickers,
    )
    return JSONResponse(result.model_dump())


@config_router.get("/{config_id}/refresh/status")
async def get_refresh_status(
    config_id: str,
    request: Request,
):
    """Get refresh status (T060)."""
    result = market_service.get_refresh_status(config_id=config_id)
    return JSONResponse(result.model_dump())


@config_router.post("/{config_id}/refresh")
async def trigger_refresh(
    config_id: str,
    request: Request,
):
    """Trigger manual refresh (T061)."""
    result = market_service.trigger_refresh(config_id=config_id)
    return JSONResponse(result.model_dump(), status_code=202)


@config_router.get("/{config_id}/premarket")
async def get_premarket(
    config_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get pre-market estimates (T063)."""
    user_id = get_user_id_from_request(request)
    result = market_service.get_premarket_estimates(
        table=table,
        user_id=user_id,
        config_id=config_id,
    )
    if isinstance(result, market_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse(result.model_dump())


@config_router.get("/{config_id}/sentiment/{ticker}/history")
async def get_ticker_sentiment_history(
    config_id: str,
    ticker: str,
    request: Request,
    source: str = Query(None, pattern="^(tiingo|finnhub)$"),
    days: int = Query(7, ge=1, le=30),
    table=Depends(get_dynamodb_table),
):
    """Get sentiment history for a specific ticker within a configuration."""
    user_id = get_user_id_from_request(request)
    result = sentiment_service.get_ticker_sentiment_history(
        table=table,
        user_id=user_id,
        config_id=config_id,
        ticker=ticker,
        source=source,
        days=days,
    )
    if isinstance(result, sentiment_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse(result.model_dump())


@config_router.get("/{config_id}/alerts")
async def get_config_alerts(
    config_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get alerts for a specific configuration."""
    user_id = get_user_id_from_request(request)
    result = alert_service.get_alerts_by_config(
        table=table,
        user_id=user_id,
        config_id=config_id,
    )
    if isinstance(result, alert_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse(result.model_dump())


@config_router.post("/{config_id}/alerts")
async def create_config_alert(
    config_id: str,
    request: Request,
    body: ConfigAlertCreateRequest,
    table=Depends(get_dynamodb_table),
):
    """Create alert for a specific configuration.

    Maps test-style request fields to AlertRuleCreate:
    - type (sentiment/volatility) -> alert_type (sentiment_threshold/volatility_threshold)
    - threshold -> threshold_value
    - condition -> threshold_direction
    """
    user_id = get_authenticated_user_id(request)
    # Map test-style fields to AlertRuleCreate fields
    alert_type = f"{body.type}_threshold"  # "sentiment" -> "sentiment_threshold"
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
            raise HTTPException(status_code=409, detail=result.error.message)
        raise HTTPException(status_code=400, detail=result.error.message)
    # Map response fields to match test expectations
    response_data = result.model_dump()
    # Map alert_type back to type (remove "_threshold" suffix)
    if "alert_type" in response_data:
        response_data["type"] = response_data["alert_type"].replace("_threshold", "")
    if "is_enabled" in response_data:
        response_data["enabled"] = response_data["is_enabled"]
    return JSONResponse(response_data, status_code=201)


@config_router.patch("/{config_id}/alerts/{alert_id}")
async def update_config_alert(
    config_id: str,
    alert_id: str,
    request: Request,
    body: alert_service.AlertUpdateRequest,
    table=Depends(get_dynamodb_table),
):
    """Update alert for a specific configuration."""
    user_id = get_authenticated_user_id(request)
    result = alert_service.update_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
        request=body,
    )
    if isinstance(result, alert_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    # Map internal field names to client-facing names
    response_data = result.model_dump()
    if "is_enabled" in response_data:
        response_data["enabled"] = response_data["is_enabled"]
    if "threshold_value" in response_data:
        response_data["threshold"] = response_data["threshold_value"]
    if "threshold_direction" in response_data:
        response_data["condition"] = response_data["threshold_direction"]
    return JSONResponse(response_data)


@config_router.delete("/{config_id}/alerts/{alert_id}")
async def delete_config_alert(
    config_id: str,
    alert_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Delete alert for a specific configuration."""
    user_id = get_authenticated_user_id(request)
    result = alert_service.delete_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
    )
    if isinstance(result, alert_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse({"message": "Alert deleted"})


@config_router.post("/{config_id}/alerts/{alert_id}/toggle")
async def toggle_config_alert(
    config_id: str,
    alert_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Toggle alert enabled status for a specific configuration."""
    user_id = get_authenticated_user_id(request)
    result = alert_service.toggle_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
    )
    if isinstance(result, alert_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse(result.model_dump())


# ===================================================================
# Ticker Endpoints
# ===================================================================


@ticker_router.get("/validate")
async def validate_ticker(
    symbol: str = Query(..., min_length=1, max_length=5),
    ticker_cache: TickerCache | None = Depends(get_ticker_cache_dependency),
):
    """Validate ticker symbol (T054)."""
    result = ticker_service.validate_ticker(
        symbol=symbol,
        ticker_cache=ticker_cache,
    )
    return JSONResponse(result.model_dump())


@ticker_router.get("/search")
async def search_tickers(
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(10, ge=1, le=20),
    ticker_cache: TickerCache | None = Depends(get_ticker_cache_dependency),
):
    """Search tickers (T055)."""
    result = ticker_service.search_tickers(
        query=q,
        limit=limit,
        ticker_cache=ticker_cache,
    )
    return JSONResponse(result.model_dump())


# ===================================================================
# Market Endpoints
# ===================================================================


@market_router.get("/status")
async def get_market_status():
    """Get market status (T062)."""
    result = market_service.get_market_status()
    return JSONResponse(result.model_dump())


# ===================================================================
# Alert Endpoints
# ===================================================================


@alert_router.post("")
async def create_alert(
    request: Request,
    body: alert_service.AlertRuleCreate,
    table=Depends(get_dynamodb_table),
):
    """Create alert rule (T131)."""
    user_id = get_authenticated_user_id(request)
    result = alert_service.create_alert(
        table=table,
        user_id=user_id,
        request=body,
    )
    if isinstance(result, alert_service.ErrorResponse):
        if result.error.code == "MAX_ALERTS_REACHED":
            raise HTTPException(status_code=409, detail=result.error.message)
        raise HTTPException(status_code=400, detail=result.error.message)
    return JSONResponse(result.model_dump(), status_code=201)


@alert_router.get("")
async def list_alerts(
    request: Request,
    config_id: str | None = None,
    table=Depends(get_dynamodb_table),
):
    """List alerts (T132)."""
    user_id = get_authenticated_user_id(request)
    result = alert_service.list_alerts(
        table=table,
        user_id=user_id,
        config_id=config_id,
    )
    return JSONResponse(result.model_dump())


@alert_router.get("/{alert_id}")
async def get_alert(
    alert_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get alert (T133)."""
    user_id = get_authenticated_user_id(request)
    result = alert_service.get_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if isinstance(result, alert_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse(result.model_dump())


@alert_router.patch("/{alert_id}")
async def update_alert(
    alert_id: str,
    request: Request,
    body: alert_service.AlertUpdateRequest,
    table=Depends(get_dynamodb_table),
):
    """Update alert (T134)."""
    user_id = get_authenticated_user_id(request)
    result = alert_service.update_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
        request=body,
    )
    if isinstance(result, alert_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    # Map internal field names to client-facing names
    response_data = result.model_dump()
    if "is_enabled" in response_data:
        response_data["enabled"] = response_data["is_enabled"]
    if "threshold_value" in response_data:
        response_data["threshold"] = response_data["threshold_value"]
    if "threshold_direction" in response_data:
        response_data["condition"] = response_data["threshold_direction"]
    return JSONResponse(response_data)


@alert_router.delete("/{alert_id}")
async def delete_alert(
    alert_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Delete alert (T135)."""
    user_id = get_authenticated_user_id(request)
    result = alert_service.delete_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
    )
    if isinstance(result, alert_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse({"message": "Alert deleted"})


@alert_router.post("/{alert_id}/toggle")
async def toggle_alert(
    alert_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Toggle alert enabled status (T136)."""
    user_id = get_authenticated_user_id(request)
    result = alert_service.toggle_alert(
        table=table,
        user_id=user_id,
        alert_id=alert_id,
    )
    if isinstance(result, alert_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse(result.model_dump())


@alert_router.get("/quota")
async def get_alert_quota(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get alert email quota usage (T145).

    Returns daily email quota status including:
    - used: Number of emails sent today
    - limit: Maximum emails per day
    - remaining: Emails left today
    - resets_at: When quota resets (ISO datetime)
    """
    user_id = get_authenticated_user_id(request)
    result = quota_service.get_daily_quota(
        table=table,
        user_id=user_id,
    )
    return JSONResponse(result.model_dump())


# ===================================================================
# Notification Endpoints
# ===================================================================


@notification_router.get("")
async def list_notifications(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    alert_id: str | None = None,
    table=Depends(get_dynamodb_table),
):
    """List notification history (T137)."""
    user_id = get_authenticated_user_id(request)
    result = notification_service.list_notifications(
        table=table,
        user_id=user_id,
        limit=limit,
        offset=offset,
        status=status,
        alert_id=alert_id,
    )
    return JSONResponse(result.model_dump())


@notification_router.get("/preferences")
async def get_preferences(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get notification preferences (T139)."""
    user_id = get_authenticated_user_id(request)
    result = notification_service.get_notification_preferences(
        table=table,
        user_id=user_id,
    )
    return JSONResponse(result.model_dump())


@notification_router.patch("/preferences")
async def update_preferences(
    request: Request,
    body: NotificationPreferencesUpdate,
    table=Depends(get_dynamodb_table),
):
    """Update notification preferences (T140)."""
    user_id = get_authenticated_user_id(request)
    result = notification_service.update_notification_preferences(
        table=table,
        user_id=user_id,
        email_notifications_enabled=body.email_enabled,
        daily_digest_enabled=body.digest_enabled,
        digest_time=body.digest_time,
    )
    if isinstance(result, notification_service.ErrorResponse):
        raise HTTPException(status_code=400, detail=result.error.message)
    return JSONResponse(result.model_dump())


@notification_router.post("/disable-all")
async def disable_all_notifications(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Disable all notifications (T141)."""
    user_id = get_authenticated_user_id(request)
    result = notification_service.disable_all_notifications(
        table=table,
        user_id=user_id,
    )
    return JSONResponse(result.model_dump())


@notification_router.get("/unsubscribe")
async def unsubscribe(
    token: str,
    table=Depends(get_dynamodb_table),
):
    """Unsubscribe via email token (T142)."""
    result = notification_service.unsubscribe_via_token(
        table=table,
        token=token,
    )
    if isinstance(result, notification_service.ErrorResponse):
        raise HTTPException(status_code=400, detail=result.error.message)
    return JSONResponse(result.model_dump())


@notification_router.post("/resubscribe")
async def resubscribe(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Resubscribe to notifications (T143)."""
    user_id = get_authenticated_user_id(request)
    result = notification_service.resubscribe(
        table=table,
        user_id=user_id,
    )
    return JSONResponse(result.model_dump())


@notification_router.get("/digest")
async def get_digest_settings(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get digest settings (T144a)."""
    user_id = get_authenticated_user_id(request)
    result = notification_service.get_digest_settings(
        table=table,
        user_id=user_id,
    )
    return JSONResponse(result.model_dump())


@notification_router.patch("/digest")
async def update_digest_settings(
    request: Request,
    body: DigestSettingsUpdate,
    table=Depends(get_dynamodb_table),
):
    """Update digest settings (T144b)."""
    user_id = get_authenticated_user_id(request)
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
        raise HTTPException(status_code=400, detail=result.error.message)
    return JSONResponse(result.model_dump())


@notification_router.post("/digest/test")
async def trigger_test_digest(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Trigger test digest (T144c)."""
    user_id = get_authenticated_user_id(request)
    result = notification_service.trigger_test_digest(
        table=table,
        user_id=user_id,
    )
    return JSONResponse(result.model_dump(), status_code=202)


@notification_router.get("/{notification_id}")
async def get_notification(
    notification_id: str,
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get notification detail (T138)."""
    user_id = get_authenticated_user_id(request)
    result = notification_service.get_notification(
        table=table,
        user_id=user_id,
        notification_id=notification_id,
    )
    if isinstance(result, notification_service.ErrorResponse):
        raise HTTPException(status_code=404, detail=result.error.message)
    return JSONResponse(result.model_dump())


# ===================================================================
# Users Endpoint (for frontend)
# ===================================================================


@auth_router.get("/me")
async def get_current_user(
    request: Request,
    table=Depends(get_dynamodb_table),
):
    """Get current user info - MINIMAL response to prevent data leakage.

    Returns ONLY what frontend needs:
    - auth_type: For UI conditional rendering
    - email_masked: For display (j***@example.com)
    - configs_count/max_configs: For quota display
    - session_expires_in_seconds: For session countdown

    NEVER returns: user_id, cognito_sub, created_at, daily_email_count
    """
    user_id = get_user_id_from_request(request)
    user = auth_service.get_user_by_id(table=table, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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
    )

    return JSONResponse(response.model_dump())


def include_routers(app):
    """Include all v2 routers in the FastAPI app."""
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
    # Feature 011: Price-Sentiment Overlay
    app.include_router(ohlc_module.router)

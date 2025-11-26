"""Authentication endpoints for Feature 006.

Implements authentication for User Story 1 & 2:
- POST /api/v2/auth/anonymous - Create anonymous session (T047)
- GET /api/v2/auth/validate - Validate session (T048)
- POST /api/v2/auth/magic-link - Request magic link (T090)
- GET /api/v2/auth/magic-link/verify - Verify magic link (T091)
- GET /api/v2/auth/oauth/urls - Get OAuth URLs (T092)
- POST /api/v2/auth/oauth/callback - OAuth callback (T093)
- POST /api/v2/auth/refresh - Refresh tokens (T094)
- POST /api/v2/auth/signout - Sign out (T095)
- GET /api/v2/auth/session - Get session info (T096)
- POST /api/v2/auth/check-email - Check for account conflict (T097)
- POST /api/v2/auth/link-accounts - Link accounts (T098)
- GET /api/v2/auth/merge-status - Get merge status (T099)

For On-Call Engineers:
    Anonymous sessions are stored in DynamoDB with 30-day TTL.
    If sessions are not persisting:
    1. Verify DynamoDB table permissions
    2. Check TTL attribute is correctly set
    3. Verify UUID generation is working

Security Notes:
    - Anonymous IDs are UUIDs, not predictable
    - Session expiry is enforced server-side
    - Rate limiting prevents brute force
    - Magic link tokens are HMAC-signed
    - OAuth tokens come from Cognito (verified via userinfo)
"""

import hashlib
import hmac
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from src.lambdas.shared.auth.cognito import (
    CognitoConfig,
    TokenError,
    decode_id_token,
    exchange_code_for_tokens,
)
from src.lambdas.shared.auth.cognito import (
    refresh_tokens as cognito_refresh_tokens,
)
from src.lambdas.shared.auth.merge import (
    get_merge_status,
    merge_anonymous_data,
)
from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
from src.lambdas.shared.models.magic_link_token import MagicLinkToken
from src.lambdas.shared.models.user import User

logger = logging.getLogger(__name__)


# Request/Response schemas


class AnonymousSessionRequest(BaseModel):
    """Request body for POST /api/v2/auth/anonymous."""

    timezone: str = Field(default="America/New_York")
    device_fingerprint: str | None = Field(default=None)


class AnonymousSessionResponse(BaseModel):
    """Response for POST /api/v2/auth/anonymous."""

    user_id: str
    auth_type: str = "anonymous"
    created_at: str
    session_expires_at: str
    storage_hint: str = "localStorage"


class ValidateSessionResponse(BaseModel):
    """Response for GET /api/v2/auth/validate (valid session)."""

    valid: bool = True
    user_id: str
    auth_type: str
    expires_at: str


class InvalidSessionResponse(BaseModel):
    """Response for GET /api/v2/auth/validate (invalid session)."""

    valid: bool = False
    error: str
    message: str


# Constants

SESSION_DURATION_DAYS = 30


# Service functions


def create_anonymous_session(
    table: Any,
    request: AnonymousSessionRequest,
) -> AnonymousSessionResponse:
    """Create a new anonymous session.

    Args:
        table: DynamoDB Table resource
        request: Session creation request

    Returns:
        AnonymousSessionResponse with user details
    """
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=SESSION_DURATION_DAYS)

    # Generate new user
    user_id = str(uuid.uuid4())

    user = User(
        user_id=user_id,
        email=None,
        cognito_sub=None,
        auth_type="anonymous",
        created_at=now,
        last_active_at=now,
        session_expires_at=expires_at,
        timezone=request.timezone,
        email_notifications_enabled=True,
        daily_email_count=0,
    )

    try:
        # Store in DynamoDB
        item = user.to_dynamodb_item()

        # Add TTL for automatic cleanup
        item["ttl"] = int(expires_at.timestamp())

        table.put_item(Item=item)

        logger.info(
            "Created anonymous session",
            extra={
                "user_id": sanitize_for_log(user_id[:8] + "..."),
                "timezone": sanitize_for_log(request.timezone),
            },
        )

        return AnonymousSessionResponse(
            user_id=user_id,
            auth_type="anonymous",
            created_at=now.isoformat().replace("+00:00", "Z"),
            session_expires_at=expires_at.isoformat().replace("+00:00", "Z"),
            storage_hint="localStorage",
        )

    except Exception as e:
        logger.error(
            "Failed to create anonymous session",
            extra=get_safe_error_info(e),
        )
        raise


def validate_session(
    table: Any,
    anonymous_id: str | None,
) -> ValidateSessionResponse | InvalidSessionResponse:
    """Validate an anonymous session.

    Args:
        table: DynamoDB Table resource
        anonymous_id: User ID from X-Anonymous-ID header

    Returns:
        ValidateSessionResponse if valid, InvalidSessionResponse if not
    """
    if not anonymous_id:
        return InvalidSessionResponse(
            valid=False,
            error="missing_user_id",
            message="X-Anonymous-ID header is required.",
        )

    # Validate UUID format
    try:
        uuid.UUID(anonymous_id)
    except ValueError:
        logger.warning(
            "Invalid user ID format",
            extra={
                "user_id_prefix": sanitize_for_log(
                    anonymous_id[:8] if anonymous_id else ""
                )
            },
        )
        return InvalidSessionResponse(
            valid=False,
            error="invalid_user_id",
            message="Invalid user ID format.",
        )

    try:
        # Look up user in DynamoDB
        response = table.get_item(
            Key={
                "PK": f"USER#{anonymous_id}",
                "SK": "PROFILE",
            }
        )

        item = response.get("Item")

        if not item:
            logger.warning(
                "User not found",
                extra={"user_id_prefix": sanitize_for_log(anonymous_id[:8])},
            )
            return InvalidSessionResponse(
                valid=False,
                error="user_not_found",
                message="User not found.",
            )

        user = User.from_dynamodb_item(item)

        # Check if session has expired
        now = datetime.now(UTC)
        if user.session_expires_at < now:
            logger.info(
                "Session expired",
                extra={
                    "user_id_prefix": sanitize_for_log(anonymous_id[:8]),
                    "expired_at": user.session_expires_at.isoformat(),
                },
            )
            return InvalidSessionResponse(
                valid=False,
                error="session_expired",
                message="Session has expired. Please create a new session.",
            )

        # Update last_active_at
        _update_last_active(table, user)

        logger.debug(
            "Session validated",
            extra={"user_id_prefix": sanitize_for_log(anonymous_id[:8])},
        )

        return ValidateSessionResponse(
            valid=True,
            user_id=user.user_id,
            auth_type=user.auth_type,
            expires_at=user.session_expires_at.isoformat().replace("+00:00", "Z"),
        )

    except Exception as e:
        logger.error(
            "Failed to validate session",
            extra=get_safe_error_info(e),
        )
        raise


def _update_last_active(table: Any, user: User) -> None:
    """Update user's last_active_at timestamp.

    Silent failure - don't break validation on update failure.
    """
    try:
        now = datetime.now(UTC)
        table.update_item(
            Key={
                "PK": user.pk,
                "SK": user.sk,
            },
            UpdateExpression="SET last_active_at = :now",
            ExpressionAttributeValues={
                ":now": now.isoformat(),
            },
        )
    except Exception as e:
        # Log but don't fail the validation
        logger.warning(
            "Failed to update last_active_at",
            extra=get_safe_error_info(e),
        )


def get_user_by_id(table: Any, user_id: str) -> User | None:
    """Get user by ID.

    Args:
        table: DynamoDB Table resource
        user_id: User UUID

    Returns:
        User if found and session valid, None otherwise
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": "PROFILE",
            }
        )

        item = response.get("Item")
        if not item:
            return None

        user = User.from_dynamodb_item(item)

        # Check session validity
        if user.session_expires_at < datetime.now(UTC):
            return None

        return user

    except Exception as e:
        logger.error(
            "Failed to get user",
            extra=get_safe_error_info(e),
        )
        return None


def get_user_by_email(table: Any, email: str) -> User | None:
    """Get user by email address.

    Args:
        table: DynamoDB Table resource
        email: User's email

    Returns:
        User if found, None otherwise
    """
    try:
        # Scan for user with matching email (would be GSI in production)
        response = table.scan(
            FilterExpression="email = :email AND entity_type = :type",
            ExpressionAttributeValues={
                ":email": email.lower(),
                ":type": "USER",
            },
        )

        items = response.get("Items", [])
        if not items:
            return None

        return User.from_dynamodb_item(items[0])

    except Exception as e:
        logger.error(
            "Failed to get user by email",
            extra=get_safe_error_info(e),
        )
        return None


def extend_session(table: Any, user_id: str) -> User | None:
    """Extend user session by 30 days.

    Args:
        table: DynamoDB Table resource
        user_id: User UUID

    Returns:
        Updated User if successful, None otherwise
    """
    user = get_user_by_id(table, user_id)
    if not user:
        return None

    now = datetime.now(UTC)
    new_expiry = now + timedelta(days=SESSION_DURATION_DAYS)

    try:
        table.update_item(
            Key={
                "PK": user.pk,
                "SK": user.sk,
            },
            UpdateExpression="SET session_expires_at = :expires, last_active_at = :now, #ttl = :ttl",
            ExpressionAttributeNames={
                "#ttl": "ttl",
            },
            ExpressionAttributeValues={
                ":expires": new_expiry.isoformat(),
                ":now": now.isoformat(),
                ":ttl": int(new_expiry.timestamp()),
            },
        )

        user.session_expires_at = new_expiry
        user.last_active_at = now

        logger.info(
            "Extended session",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "new_expiry": new_expiry.isoformat(),
            },
        )

        return user

    except Exception as e:
        logger.error(
            "Failed to extend session",
            extra=get_safe_error_info(e),
        )
        return None


# =============================================================================
# User Story 2: Magic Link, OAuth, and Session Management
# =============================================================================


# Request/Response schemas for User Story 2


class MagicLinkRequest(BaseModel):
    """Request body for POST /api/v2/auth/magic-link."""

    email: EmailStr
    anonymous_user_id: str | None = None


class MagicLinkResponse(BaseModel):
    """Response for POST /api/v2/auth/magic-link."""

    status: str = "email_sent"
    email: str
    expires_in_seconds: int = 3600
    message: str = "Check your email for a sign-in link"


class MagicLinkVerifyResponse(BaseModel):
    """Response for GET /api/v2/auth/magic-link/verify."""

    status: str
    user_id: str | None = None
    email: str | None = None
    auth_type: str | None = None
    tokens: dict | None = None
    merged_anonymous_data: bool = False
    error: str | None = None
    message: str | None = None


class OAuthURLsResponse(BaseModel):
    """Response for GET /api/v2/auth/oauth/urls."""

    providers: dict


class OAuthCallbackRequest(BaseModel):
    """Request body for POST /api/v2/auth/oauth/callback."""

    code: str
    provider: Literal["google", "github"]
    anonymous_user_id: str | None = None


class OAuthCallbackResponse(BaseModel):
    """Response for POST /api/v2/auth/oauth/callback."""

    status: str
    user_id: str | None = None
    email: str | None = None
    auth_type: str | None = None
    tokens: dict | None = None
    merged_anonymous_data: bool = False
    is_new_user: bool = False
    conflict: bool = False
    existing_provider: str | None = None
    message: str | None = None
    error: str | None = None


class RefreshTokenRequest(BaseModel):
    """Request body for POST /api/v2/auth/refresh."""

    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Response for POST /api/v2/auth/refresh."""

    id_token: str | None = None
    access_token: str | None = None
    expires_in: int = 3600
    error: str | None = None
    message: str | None = None


class SignOutResponse(BaseModel):
    """Response for POST /api/v2/auth/signout."""

    status: str = "signed_out"
    message: str = "Signed out from this device"


class SessionInfoResponse(BaseModel):
    """Response for GET /api/v2/auth/session."""

    user_id: str
    email: str | None
    auth_type: str
    session_started_at: str
    session_expires_at: str
    last_activity_at: str
    linked_providers: list[str]


class CheckEmailRequest(BaseModel):
    """Request body for POST /api/v2/auth/check-email."""

    email: EmailStr
    current_provider: Literal["email", "google", "github"]


class CheckEmailResponse(BaseModel):
    """Response for POST /api/v2/auth/check-email."""

    conflict: bool
    existing_provider: str | None = None
    message: str | None = None


class LinkAccountsRequest(BaseModel):
    """Request body for POST /api/v2/auth/link-accounts."""

    link_to_user_id: str
    confirmation: bool


class LinkAccountsResponse(BaseModel):
    """Response for POST /api/v2/auth/link-accounts."""

    status: str
    user_id: str | None = None
    linked_providers: list[str] | None = None
    message: str | None = None
    error: str | None = None


class MergeStatusResponse(BaseModel):
    """Response for GET /api/v2/auth/merge-status."""

    status: str
    merged_at: str | None = None
    items_merged: dict | None = None
    message: str | None = None


# Magic link secret key from environment
MAGIC_LINK_SECRET = os.environ.get(
    "MAGIC_LINK_SECRET", "default-dev-secret-change-in-prod"
)
MAGIC_LINK_EXPIRY_HOURS = 1


def _generate_magic_link_signature(token_id: str, email: str) -> str:
    """Generate HMAC-SHA256 signature for magic link."""
    message = f"{token_id}:{email}"
    return hmac.new(
        MAGIC_LINK_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


def _verify_magic_link_signature(token_id: str, email: str, signature: str) -> bool:
    """Verify magic link signature."""
    expected = _generate_magic_link_signature(token_id, email)
    return hmac.compare_digest(expected, signature)


# T090: Magic Link Request
def request_magic_link(
    table: Any,
    request: MagicLinkRequest,
    send_email_callback: Any = None,
) -> MagicLinkResponse:
    """Request a magic link for email authentication.

    Args:
        table: DynamoDB Table resource
        request: Magic link request with email
        send_email_callback: Optional callback to send email

    Returns:
        MagicLinkResponse with status
    """
    email = request.email.lower()

    logger.info(
        "Magic link requested",
        extra={"email_domain": sanitize_for_log(email.split("@")[1])},
    )

    # Invalidate any existing tokens for this email
    _invalidate_existing_tokens(table, email)

    # Create new token
    token_id = str(uuid.uuid4())
    signature = _generate_magic_link_signature(token_id, email)
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=MAGIC_LINK_EXPIRY_HOURS)

    token = MagicLinkToken(
        token_id=token_id,
        email=email,
        signature=signature,
        created_at=now,
        expires_at=expires_at,
        used=False,
        anonymous_user_id=request.anonymous_user_id,
    )

    # Store token
    table.put_item(Item=token.to_dynamodb_item())

    # Send email (if callback provided)
    if send_email_callback:
        send_email_callback(email, token_id, signature)

    return MagicLinkResponse(
        status="email_sent",
        email=email,
        expires_in_seconds=3600,
        message="Check your email for a sign-in link",
    )


def _invalidate_existing_tokens(table: Any, email: str) -> None:
    """Invalidate any existing magic link tokens for an email."""
    try:
        # Scan for existing tokens (would use GSI in production)
        response = table.scan(
            FilterExpression="email = :email AND entity_type = :type AND used = :used",
            ExpressionAttributeValues={
                ":email": email,
                ":type": "MAGIC_LINK_TOKEN",
                ":used": False,
            },
        )

        for item in response.get("Items", []):
            table.update_item(
                Key={"PK": item["PK"], "SK": item["SK"]},
                UpdateExpression="SET used = :used",
                ExpressionAttributeValues={":used": True},
            )

    except Exception as e:
        logger.warning(
            "Failed to invalidate existing tokens",
            extra=get_safe_error_info(e),
        )


# T091: Magic Link Verification
def verify_magic_link(
    table: Any,
    token_id: str,
    signature: str,
) -> MagicLinkVerifyResponse:
    """Verify a magic link token.

    Args:
        table: DynamoDB Table resource
        token_id: Token UUID from URL
        signature: HMAC signature from URL

    Returns:
        MagicLinkVerifyResponse with user info and tokens
    """
    logger.info(
        "Verifying magic link",
        extra={"token_prefix": sanitize_for_log(token_id[:8])},
    )

    # Get token from database
    try:
        response = table.get_item(
            Key={
                "PK": f"TOKEN#{token_id}",
                "SK": "MAGIC_LINK",
            }
        )
    except Exception as e:
        logger.error("Failed to get token", extra=get_safe_error_info(e))
        return MagicLinkVerifyResponse(
            status="invalid",
            error="token_not_found",
            message="Invalid link. Please request a new one.",
        )

    item = response.get("Item")
    if not item:
        return MagicLinkVerifyResponse(
            status="invalid",
            error="token_not_found",
            message="Invalid link. Please request a new one.",
        )

    token = MagicLinkToken.from_dynamodb_item(item)

    # Check if token already used
    if token.used:
        return MagicLinkVerifyResponse(
            status="invalid",
            error="token_used",
            message="This link has already been used.",
        )

    # Check if token expired
    if datetime.now(UTC) > token.expires_at.replace(tzinfo=UTC):
        return MagicLinkVerifyResponse(
            status="invalid",
            error="token_expired",
            message="This link has expired. Please request a new one.",
        )

    # Verify signature
    if not _verify_magic_link_signature(token_id, token.email, signature):
        logger.warning(
            "Invalid magic link signature",
            extra={"token_prefix": sanitize_for_log(token_id[:8])},
        )
        return MagicLinkVerifyResponse(
            status="invalid",
            error="invalid_signature",
            message="Invalid link. Please request a new one.",
        )

    # Mark token as used
    table.update_item(
        Key={"PK": f"TOKEN#{token_id}", "SK": "MAGIC_LINK"},
        UpdateExpression="SET used = :used",
        ExpressionAttributeValues={":used": True},
    )

    # Find or create user
    existing_user = get_user_by_email(table, token.email)
    merged_data = False

    if existing_user:
        user = existing_user
        # Merge anonymous data if provided
        if token.anonymous_user_id:
            result = merge_anonymous_data(table, token.anonymous_user_id, user.user_id)
            merged_data = result.status == "completed"
    else:
        # Create new user
        user = _create_authenticated_user(
            table, token.email, "email", token.anonymous_user_id
        )
        if token.anonymous_user_id:
            result = merge_anonymous_data(table, token.anonymous_user_id, user.user_id)
            merged_data = result.status == "completed"

    # Generate tokens (in production, these would come from Cognito)
    tokens = _generate_tokens(user)

    return MagicLinkVerifyResponse(
        status="verified",
        user_id=user.user_id,
        email=user.email,
        auth_type="email",
        tokens=tokens,
        merged_anonymous_data=merged_data,
    )


def _create_authenticated_user(
    table: Any,
    email: str,
    auth_type: str,
    anonymous_user_id: str | None = None,
) -> User:
    """Create a new authenticated user."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=SESSION_DURATION_DAYS)

    user = User(
        user_id=str(uuid.uuid4()),
        email=email.lower(),
        cognito_sub=None,
        auth_type=auth_type,
        created_at=now,
        last_active_at=now,
        session_expires_at=expires_at,
        timezone="America/New_York",
        email_notifications_enabled=True,
        daily_email_count=0,
    )

    item = user.to_dynamodb_item()
    item["ttl"] = int(expires_at.timestamp()) + (
        90 * 24 * 3600
    )  # 90 days for auth users
    table.put_item(Item=item)

    return user


def _generate_tokens(user: User) -> dict:
    """Generate mock tokens for testing.

    In production, tokens come from Cognito.
    """
    return {
        "id_token": f"mock_id_token_{user.user_id[:8]}",
        "access_token": f"mock_access_token_{user.user_id[:8]}",
        "refresh_token": f"mock_refresh_token_{user.user_id[:8]}",
        "expires_in": 3600,
    }


# T092: OAuth URLs
def get_oauth_urls() -> OAuthURLsResponse:
    """Get OAuth authorization URLs for supported providers.

    Returns:
        OAuthURLsResponse with provider URLs
    """
    config = CognitoConfig.from_env()

    return OAuthURLsResponse(
        providers={
            "google": {
                "authorize_url": config.get_authorize_url("Google"),
                "icon": "google",
            },
            "github": {
                "authorize_url": config.get_authorize_url("GitHub"),
                "icon": "github",
            },
        }
    )


# T093: OAuth Callback
def handle_oauth_callback(
    table: Any,
    request: OAuthCallbackRequest,
) -> OAuthCallbackResponse:
    """Handle OAuth callback from Cognito.

    Args:
        table: DynamoDB Table resource
        request: OAuth callback request with code

    Returns:
        OAuthCallbackResponse with user info and tokens
    """
    logger.info(
        "Processing OAuth callback",
        extra={"provider": request.provider},
    )

    config = CognitoConfig.from_env()

    # Exchange code for tokens
    try:
        tokens = exchange_code_for_tokens(config, request.code)
    except TokenError as e:
        logger.warning(
            "OAuth token exchange failed",
            extra={"error": e.error},
        )
        return OAuthCallbackResponse(
            status="error",
            error=e.error,
            message=e.message,
        )

    # Decode ID token to get user info
    claims = decode_id_token(tokens.id_token)
    email = claims.get("email", "").lower()
    cognito_sub = claims.get("sub")

    if not email:
        return OAuthCallbackResponse(
            status="error",
            error="missing_email",
            message="Email not provided by OAuth provider.",
        )

    # Check for existing user with this email
    existing_user = get_user_by_email(table, email)

    if existing_user and existing_user.auth_type != request.provider:
        # Account conflict
        return OAuthCallbackResponse(
            status="conflict",
            conflict=True,
            existing_provider=existing_user.auth_type,
            email=email,
            message=f"An account with this email exists via {existing_user.auth_type}. Would you like to link your {request.provider.capitalize()} account?",
        )

    merged_data = False
    is_new_user = False

    if existing_user:
        user = existing_user
        # Update cognito_sub if not set
        if not user.cognito_sub:
            _update_cognito_sub(table, user, cognito_sub)
        # Merge anonymous data
        if request.anonymous_user_id:
            result = merge_anonymous_data(
                table, request.anonymous_user_id, user.user_id
            )
            merged_data = result.status == "completed"
    else:
        # Create new user
        is_new_user = True
        user = _create_authenticated_user(
            table, email, request.provider, request.anonymous_user_id
        )
        _update_cognito_sub(table, user, cognito_sub)
        if request.anonymous_user_id:
            result = merge_anonymous_data(
                table, request.anonymous_user_id, user.user_id
            )
            merged_data = result.status == "completed"

    return OAuthCallbackResponse(
        status="authenticated",
        user_id=user.user_id,
        email=user.email,
        auth_type=request.provider,
        tokens={
            "id_token": tokens.id_token,
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_in": tokens.expires_in,
        },
        merged_anonymous_data=merged_data,
        is_new_user=is_new_user,
    )


def _update_cognito_sub(table: Any, user: User, cognito_sub: str | None) -> None:
    """Update user's Cognito sub."""
    if not cognito_sub:
        return
    try:
        table.update_item(
            Key={"PK": user.pk, "SK": user.sk},
            UpdateExpression="SET cognito_sub = :sub",
            ExpressionAttributeValues={":sub": cognito_sub},
        )
    except Exception as e:
        logger.warning(
            "Failed to update cognito_sub",
            extra=get_safe_error_info(e),
        )


# T094: Token Refresh
def refresh_access_tokens(
    refresh_token: str,
) -> RefreshTokenResponse:
    """Refresh access and ID tokens.

    Args:
        refresh_token: Current refresh token

    Returns:
        RefreshTokenResponse with new tokens
    """
    config = CognitoConfig.from_env()

    try:
        tokens = cognito_refresh_tokens(config, refresh_token)
        return RefreshTokenResponse(
            id_token=tokens.id_token,
            access_token=tokens.access_token,
            expires_in=tokens.expires_in,
        )
    except TokenError as e:
        return RefreshTokenResponse(
            error=e.error,
            message=e.message,
        )


# T095: Sign Out
def sign_out(
    access_token: str,  # noqa: ARG001 - reserved for future Cognito integration
) -> SignOutResponse:
    """Sign out user (current device only).

    Args:
        access_token: User's access token

    Returns:
        SignOutResponse
    """
    # In production, could revoke the refresh token via Cognito
    # In practice, client should also clear localStorage
    logger.info("User signed out")

    return SignOutResponse(
        status="signed_out",
        message="Signed out from this device",
    )


# T096: Session Info
def get_session_info(
    table: Any,
    user_id: str,
) -> SessionInfoResponse | None:
    """Get session information for a user.

    Args:
        table: DynamoDB Table resource
        user_id: User UUID

    Returns:
        SessionInfoResponse or None if not found
    """
    user = get_user_by_id(table, user_id)
    if not user:
        return None

    # Determine linked providers
    linked_providers = [user.auth_type]
    if user.auth_type in ["google", "github"] and user.email:
        # User might also have email auth
        linked_providers.append(user.auth_type)

    return SessionInfoResponse(
        user_id=user.user_id,
        email=user.email,
        auth_type=user.auth_type,
        session_started_at=user.created_at.isoformat().replace("+00:00", "Z"),
        session_expires_at=user.session_expires_at.isoformat().replace("+00:00", "Z"),
        last_activity_at=user.last_active_at.isoformat().replace("+00:00", "Z"),
        linked_providers=linked_providers,
    )


# T097: Check Email for Conflict
def check_email_conflict(
    table: Any,
    request: CheckEmailRequest,
) -> CheckEmailResponse:
    """Check if email has existing account with different provider.

    Args:
        table: DynamoDB Table resource
        request: Check email request

    Returns:
        CheckEmailResponse with conflict status
    """
    existing_user = get_user_by_email(table, request.email)

    if not existing_user:
        return CheckEmailResponse(conflict=False)

    if existing_user.auth_type == request.current_provider:
        return CheckEmailResponse(conflict=False)

    return CheckEmailResponse(
        conflict=True,
        existing_provider=existing_user.auth_type,
        message=f"An account with this email exists via {existing_user.auth_type}. Would you like to link your {request.current_provider.capitalize()} account?",
    )


# T098: Link Accounts
def link_accounts(
    table: Any,
    current_user_id: str,
    request: LinkAccountsRequest,
) -> LinkAccountsResponse:
    """Link current account to an existing account.

    Args:
        table: DynamoDB Table resource
        current_user_id: Current user's ID
        request: Link accounts request

    Returns:
        LinkAccountsResponse with status
    """
    if not request.confirmation:
        return LinkAccountsResponse(
            status="error",
            error="confirmation_required",
            message="Explicit confirmation is required to link accounts.",
        )

    current_user = get_user_by_id(table, current_user_id)
    target_user = get_user_by_id(table, request.link_to_user_id)

    if not current_user or not target_user:
        return LinkAccountsResponse(
            status="error",
            error="user_not_found",
            message="One or both users not found.",
        )

    # Merge current user's data into target user
    result = merge_anonymous_data(table, current_user_id, request.link_to_user_id)

    if result.status != "completed":
        return LinkAccountsResponse(
            status="error",
            error="merge_failed",
            message="Failed to merge account data.",
        )

    # Determine linked providers
    linked_providers = list({target_user.auth_type, current_user.auth_type})

    return LinkAccountsResponse(
        status="linked",
        user_id=target_user.user_id,
        linked_providers=linked_providers,
        message="Accounts successfully linked",
    )


# T099: Merge Status
def get_merge_status_endpoint(
    table: Any,
    authenticated_user_id: str,
    anonymous_user_id: str,
) -> MergeStatusResponse:
    """Get status of data merge from anonymous to authenticated.

    Args:
        table: DynamoDB Table resource
        authenticated_user_id: Authenticated user's ID
        anonymous_user_id: Anonymous user's ID to check

    Returns:
        MergeStatusResponse with status and counts
    """
    result = get_merge_status(table, authenticated_user_id, anonymous_user_id)

    if result.status == "completed":
        return MergeStatusResponse(
            status="completed",
            merged_at=result.merged_at.isoformat().replace("+00:00", "Z")
            if result.merged_at
            else None,
            items_merged={
                "configurations": result.configurations,
                "alert_rules": result.alert_rules,
                "preferences": result.preferences,
            },
        )

    return MergeStatusResponse(
        status=result.status,
        message=result.message,
    )

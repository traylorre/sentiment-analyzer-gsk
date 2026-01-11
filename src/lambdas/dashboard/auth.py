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

X-Ray tracing enabled (T103) for:
- request_magic_link, verify_magic_link
- handle_oauth_callback
- link_accounts, merge operations

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
    - Magic link tokens verified via atomic DB consumption (Feature 1166)
    - OAuth tokens come from Cognito (verified via userinfo)
"""

import hashlib
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import boto3
from aws_xray_sdk.core import xray_recorder
from botocore.exceptions import ClientError
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
from src.lambdas.shared.auth.oauth_state import (
    generate_state,
    store_oauth_state,
    validate_oauth_state,
)
from src.lambdas.shared.errors.session_errors import (
    SessionLimitRaceError,
    SessionRevokedException,
    TokenAlreadyUsedError,
    TokenExpiredError,
)
from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
from src.lambdas.shared.models.magic_link_token import MagicLinkToken
from src.lambdas.shared.models.user import ProviderMetadata, User

logger = logging.getLogger(__name__)


# Request/Response schemas


class AnonymousSessionRequest(BaseModel):
    """Request body for POST /api/v2/auth/anonymous."""

    timezone: str = Field(default="America/New_York")
    device_fingerprint: str | None = Field(default=None)


class AnonymousSessionResponse(BaseModel):
    """Response for POST /api/v2/auth/anonymous."""

    user_id: str
    token: str  # Alias for user_id - used by clients as auth token
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
SESSION_LIMIT = 5  # Maximum concurrent sessions per user (A11)


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
            token=user_id,  # Token is the same as user_id for anonymous sessions
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
    extend_on_valid: bool = False,
) -> ValidateSessionResponse | InvalidSessionResponse:
    """Validate an anonymous session.

    Feature 014 (T052, T055): Checks for revocation and optionally extends
    session expiry on valid sessions (sliding window).

    Args:
        table: DynamoDB Table resource
        anonymous_id: User ID from X-Anonymous-ID header
        extend_on_valid: If True, extend session expiry when session is valid (FR-011)

    Returns:
        ValidateSessionResponse if valid, InvalidSessionResponse if not

    Raises:
        SessionRevokedException: If session has been revoked (FR-016)
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

        # Feature 014: Check if session has been revoked (FR-016, FR-017)
        if user.revoked:
            logger.info(
                "Session revoked",
                extra={
                    "user_id_prefix": sanitize_for_log(anonymous_id[:8]),
                    "revoked_at": (
                        user.revoked_at.isoformat() if user.revoked_at else None
                    ),
                    "reason": (
                        sanitize_for_log(user.revoked_reason)
                        if user.revoked_reason
                        else None
                    ),
                },
            )
            raise SessionRevokedException(
                reason=user.revoked_reason,
                revoked_at=user.revoked_at,
            )

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

        # Feature 014 (T052): Extend session expiry on valid session (sliding window)
        if extend_on_valid:
            _extend_session_expiry_on_validation(table, user)

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


def _extend_session_expiry_on_validation(table: Any, user: User) -> None:
    """Extend session expiry during validation (FR-011, T052).

    Called when extend_on_valid=True in validate_session.
    Silent failure - don't break validation on extension failure.
    """
    try:
        now = datetime.now(UTC)
        new_expiry = now + timedelta(days=SESSION_DURATION_DAYS)

        table.update_item(
            Key={"PK": user.pk, "SK": user.sk},
            UpdateExpression="SET session_expires_at = :expires, #ttl = :ttl",
            ExpressionAttributeNames={"#ttl": "ttl"},
            ExpressionAttributeValues={
                ":expires": new_expiry.isoformat(),
                ":ttl": int(new_expiry.timestamp()) + (90 * 24 * 3600),
            },
        )

        # Update the user object in place
        user.session_expires_at = new_expiry

        logger.debug(
            "Extended session during validation",
            extra={"user_id_prefix": sanitize_for_log(user.user_id[:8])},
        )
    except Exception as e:
        # Log but don't fail the validation
        logger.warning(
            "Failed to extend session during validation",
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
    """DEPRECATED: Use get_user_by_email_gsi() instead for O(1) lookup.

    This function used table.scan() which has O(table) performance.
    The GSI-based version provides O(1) lookup via the by_email GSI.

    (502-gsi-query-optimization: Deprecated to prevent accidental scan usage)

    Args:
        table: DynamoDB Table resource (unused)
        email: User's email (unused)

    Raises:
        NotImplementedError: Always raised with guidance to use GSI version
    """
    raise NotImplementedError(
        "get_user_by_email() is deprecated due to O(n) table scan. "
        "Use get_user_by_email_gsi() for O(1) lookup via the by_email GSI."
    )


# =============================================================================
# Feature 014 User Story 3: Email Uniqueness (T040-T044)
# =============================================================================


@xray_recorder.capture("get_user_by_email_gsi")
def get_user_by_email_gsi(table: Any, email: str) -> User | None:
    """Get user by email using GSI query (FR-009, T040, T076).

    Uses the by_email GSI for O(1) lookup performance instead of table scan.
    Case-insensitive: all emails are normalized to lowercase.

    Feature 014 (T076): X-Ray subsegment for timing and performance monitoring.

    Args:
        table: DynamoDB Table resource
        email: User's email address

    Returns:
        User if found, None otherwise
    """
    normalized_email = email.lower()

    logger.debug(
        "GSI email lookup",
        extra={"email_domain": sanitize_for_log(normalized_email.split("@")[-1])},
    )

    try:
        # GSI by_email has email as HASH and SK as RANGE
        # Filter by entity_type to only return USER records
        response = table.query(
            IndexName="by_email",
            KeyConditionExpression="email = :email",
            FilterExpression="entity_type = :type",
            ExpressionAttributeValues={
                ":email": normalized_email,
                ":type": "USER",
            },
            Limit=1,  # We only need one result for uniqueness check
        )

        items = response.get("Items", [])
        if not items:
            return None

        return User.from_dynamodb_item(items[0])

    except Exception as e:
        logger.error(
            "Failed GSI email lookup",
            extra=get_safe_error_info(e),
        )
        return None


@xray_recorder.capture("get_user_by_provider_sub")
def get_user_by_provider_sub(
    table: Any,
    provider: Literal["google", "github"],
    sub: str,
) -> User | None:
    """Get user by OAuth provider sub using GSI query (Feature 1180).

    Uses the by_provider_sub GSI for O(1) lookup performance.
    Essential for account linking flows to detect duplicate provider linking.

    Args:
        table: DynamoDB Table resource
        provider: OAuth provider ("google" or "github")
        sub: OAuth subject claim (provider's user ID)

    Returns:
        User if found, None otherwise
    """
    if not provider or not sub:
        logger.warning(
            "Invalid provider_sub lookup - missing provider or sub",
            extra={"has_provider": bool(provider), "has_sub": bool(sub)},
        )
        return None

    # Build composite key: "{provider}:{sub}"
    provider_sub = f"{provider}:{sub}"

    logger.debug(
        "GSI provider_sub lookup",
        extra={"provider": provider, "sub_prefix": sanitize_for_log(sub[:8])},
    )

    try:
        # GSI by_provider_sub has provider_sub as HASH
        # Filter by entity_type to only return USER records
        response = table.query(
            IndexName="by_provider_sub",
            KeyConditionExpression="provider_sub = :provider_sub",
            FilterExpression="entity_type = :type",
            ExpressionAttributeValues={
                ":provider_sub": provider_sub,
                ":type": "USER",
            },
            Limit=1,  # One provider:sub should map to at most one user
        )

        items = response.get("Items", [])
        if not items:
            return None

        return User.from_dynamodb_item(items[0])

    except Exception as e:
        logger.error(
            "Failed GSI provider_sub lookup",
            extra=get_safe_error_info(e),
        )
        return None


# Feature 1181: OAuth Auto-Link Detection
def can_auto_link_oauth(
    oauth_email: str,
    oauth_email_verified: bool,
    provider: str,
    existing_user_email: str,
) -> bool:
    """Determine if OAuth can be auto-linked to existing email account (Feature 1181).

    Auto-linking is allowed when:
    1. OAuth email is verified by the provider
    2. Provider is Google AND existing user email is @gmail.com

    All other cases require manual confirmation (GitHub, cross-domain, unverified).

    Args:
        oauth_email: Email returned by OAuth provider
        oauth_email_verified: Whether provider verified the email
        provider: OAuth provider name ("google", "github")
        existing_user_email: Existing user's email address

    Returns:
        True if auto-link is allowed, False if manual confirmation required
    """
    # Rule 1: Never auto-link unverified OAuth email
    if not oauth_email_verified:
        logger.debug(
            "Auto-link rejected: OAuth email not verified",
            extra={"provider": provider},
        )
        return False

    # Rule 2: GitHub is opaque - never auto-link by email
    if provider.lower() == "github":
        logger.debug(
            "Auto-link rejected: GitHub requires manual confirmation",
            extra={"provider": provider},
        )
        return False

    # Rule 3: Google verifying @gmail.com is authoritative
    if provider.lower() == "google" and existing_user_email.lower().endswith(
        "@gmail.com"
    ):
        logger.debug(
            "Auto-link allowed: Google + @gmail.com domain match",
            extra={"provider": provider},
        )
        return True

    # Rule 4: All other cases require manual confirmation (cross-domain)
    logger.debug(
        "Auto-link rejected: Cross-domain requires manual confirmation",
        extra={"provider": provider},
    )
    return False


@xray_recorder.capture("create_user_with_email")
def create_user_with_email(
    table: Any,
    email: str,
    auth_type: str,
    cognito_sub: str | None = None,
) -> User:
    """Create user with email uniqueness enforcement (FR-007, T041).

    Checks for existing user via GSI first, then creates with conditional write
    to prevent race conditions where two requests try to create the same email.

    Args:
        table: DynamoDB Table resource
        email: User's email (case-insensitive)
        auth_type: Authentication type (email, google, github)
        cognito_sub: Optional Cognito sub identifier

    Returns:
        Created User

    Raises:
        EmailAlreadyExistsError: If email already registered
    """
    from src.lambdas.shared.errors.session_errors import EmailAlreadyExistsError

    normalized_email = email.lower()

    # First check via GSI (fast O(1) lookup)
    existing_user = get_user_by_email_gsi(table, normalized_email)
    if existing_user:
        logger.info(
            "Email already exists during creation",
            extra={
                "email_domain": sanitize_for_log(normalized_email.split("@")[-1]),
                "existing_user_id_prefix": sanitize_for_log(existing_user.user_id[:8]),
            },
        )
        raise EmailAlreadyExistsError(
            email=normalized_email,
            existing_user_id=existing_user.user_id,
        )

    # Create new user
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=SESSION_DURATION_DAYS)

    user = User(
        user_id=str(uuid.uuid4()),
        email=normalized_email,
        cognito_sub=cognito_sub,
        auth_type=auth_type,
        created_at=now,
        last_active_at=now,
        session_expires_at=expires_at,
        timezone="America/New_York",
        email_notifications_enabled=True,
        daily_email_count=0,
        entity_type="USER",
    )

    item = user.to_dynamodb_item()
    item["ttl"] = int(expires_at.timestamp()) + (90 * 24 * 3600)  # 90 days for auth

    try:
        # Conditional write to prevent race condition
        # This fails if another request created a user with the same PK
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PK)",
        )

        logger.info(
            "Created user with email",
            extra={
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
                "email_domain": sanitize_for_log(normalized_email.split("@")[-1]),
                "auth_type": auth_type,
            },
        )

        return user

    except table.meta.client.exceptions.ConditionalCheckFailedException:
        # Race condition - another request created the user
        logger.warning(
            "User creation race condition detected",
            extra={"email_domain": sanitize_for_log(normalized_email.split("@")[-1])},
        )
        raise EmailAlreadyExistsError(email=normalized_email) from None

    except Exception as e:
        logger.error(
            "Failed to create user with email",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("get_or_create_user_by_email")
def get_or_create_user_by_email(
    table: Any,
    email: str,
    auth_type: str,
    cognito_sub: str | None = None,
) -> tuple[User, bool]:
    """Get existing user or create new one by email (FR-008, T042).

    Atomically handles the get-or-create pattern to prevent race conditions.
    If multiple requests try to create the same email concurrently, exactly
    one will succeed and others will return the existing user.

    Args:
        table: DynamoDB Table resource
        email: User's email (case-insensitive)
        auth_type: Authentication type for new user
        cognito_sub: Optional Cognito sub identifier

    Returns:
        Tuple of (User, is_new) where is_new=True if user was created
    """
    from src.lambdas.shared.errors.session_errors import EmailAlreadyExistsError

    normalized_email = email.lower()

    # First try to find existing user
    existing_user = get_user_by_email_gsi(table, normalized_email)
    if existing_user:
        logger.debug(
            "Found existing user by email",
            extra={
                "user_id_prefix": sanitize_for_log(existing_user.user_id[:8]),
                "auth_type": existing_user.auth_type,
            },
        )
        return existing_user, False

    # Try to create new user
    try:
        user = create_user_with_email(
            table=table,
            email=normalized_email,
            auth_type=auth_type,
            cognito_sub=cognito_sub,
        )
        return user, True

    except EmailAlreadyExistsError:
        # Race condition - another request created the user, fetch it
        logger.info(
            "Race condition handled - fetching created user",
            extra={"email_domain": sanitize_for_log(normalized_email.split("@")[-1])},
        )
        user = get_user_by_email_gsi(table, normalized_email)
        if user:
            return user, False

        # Extremely rare: creation failed but user still not found
        # This could happen if the other request also failed
        logger.error(
            "User not found after race condition",
            extra={"email_domain": sanitize_for_log(normalized_email.split("@")[-1])},
        )
        raise RuntimeError(
            "Failed to get or create user: concurrent creation failed"
        ) from None


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
# Feature 014 User Story 4: Session Refresh & Revocation (T051-T059)
# =============================================================================


class SessionRefreshResponse(BaseModel):
    """Response for POST /api/v2/auth/session/refresh."""

    user_id: str
    session_expires_at: str
    remaining_seconds: int
    refreshed: bool


class BulkRevocationResponse(BaseModel):
    """Response for POST /api/v2/admin/sessions/revoke."""

    revoked_count: int
    failed_count: int
    failed_user_ids: list[str]


@xray_recorder.capture("extend_session_expiry")
def extend_session_expiry(table: Any, user_id: str) -> User | None:
    """Extend session expiry by 30 days (FR-010, T051).

    Only extends if session is valid (not expired, not revoked).

    Args:
        table: DynamoDB Table resource
        user_id: User UUID

    Returns:
        Updated User if successful, None if invalid/expired/revoked
    """
    user = get_user_by_id(table, user_id)
    if not user:
        logger.debug(
            "User not found for session extension",
            extra={"user_id_prefix": sanitize_for_log(user_id[:8])},
        )
        return None

    now = datetime.now(UTC)

    # Check if session is expired
    if user.session_expires_at < now:
        logger.debug(
            "Cannot extend expired session",
            extra={"user_id_prefix": sanitize_for_log(user_id[:8])},
        )
        return None

    # Check if session is revoked
    if user.revoked:
        logger.debug(
            "Cannot extend revoked session",
            extra={"user_id_prefix": sanitize_for_log(user_id[:8])},
        )
        return None

    new_expiry = now + timedelta(days=SESSION_DURATION_DAYS)

    try:
        table.update_item(
            Key={"PK": user.pk, "SK": user.sk},
            UpdateExpression="SET session_expires_at = :expires, last_active_at = :last_active, #ttl = :ttl",
            ExpressionAttributeNames={"#ttl": "ttl"},
            ExpressionAttributeValues={
                ":expires": new_expiry.isoformat(),
                ":last_active": now.isoformat(),
                ":ttl": int(new_expiry.timestamp()) + (90 * 24 * 3600),
            },
        )

        user.session_expires_at = new_expiry
        user.last_active_at = now

        logger.info(
            "Extended session expiry",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "new_expiry_days": SESSION_DURATION_DAYS,
            },
        )

        return user

    except Exception as e:
        logger.error("Failed to extend session expiry", extra=get_safe_error_info(e))
        return None


# Session Limit Enforcement (Feature 1188 - A11)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for blocklist lookup.

    Uses SHA-256 to create a deterministic, non-reversible hash.

    Args:
        token: The refresh token string

    Returns:
        Hex-encoded hash string
    """
    return hashlib.sha256(token.encode()).hexdigest()


def get_user_sessions(table: Any, user_id: str) -> list[dict]:
    """Get all active sessions for a user (T004).

    Queries the users table for all session records belonging to a user,
    ordered by creation time (oldest first).

    Args:
        table: DynamoDB Table resource
        user_id: User UUID

    Returns:
        List of session items sorted by created_at ascending
    """
    try:
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"USER#{user_id}",
                ":sk_prefix": "SESSION#",
            },
        )
        sessions = response.get("Items", [])
        # Sort by created_at ascending (oldest first)
        return sorted(sessions, key=lambda x: x.get("created_at", ""))
    except Exception as e:
        logger.error(
            "Failed to get user sessions",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                **get_safe_error_info(e),
            },
        )
        return []


def is_token_blocklisted(table: Any, refresh_token_hash: str) -> bool:
    """Check if a refresh token has been blocklisted (FR-007, T009).

    Args:
        table: DynamoDB Table resource
        refresh_token_hash: SHA-256 hash of the refresh token

    Returns:
        True if token is blocklisted (evicted or revoked)
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"BLOCK#refresh#{refresh_token_hash}",
                "SK": "BLOCK",
            },
            ProjectionExpression="PK",
        )
        return "Item" in response
    except Exception as e:
        logger.error(
            "Failed to check token blocklist",
            extra=get_safe_error_info(e),
        )
        # Fail closed - treat as blocklisted on error
        return True


@xray_recorder.capture("evict_oldest_session_atomic")
def evict_oldest_session_atomic(
    table: Any,
    user_id: str,
    oldest_session: dict,
    new_session_item: dict,
    refresh_token_hash: str,
) -> None:
    """Atomically evict oldest session and create new one (FR-001 to FR-005, T005).

    Uses DynamoDB TransactWriteItems to ensure all-or-nothing execution:
    1. ConditionCheck: Verify oldest session still exists
    2. Delete: Remove oldest session
    3. Put: Add refresh token to blocklist
    4. Put: Create new session

    Args:
        table: DynamoDB Table resource
        user_id: User UUID
        oldest_session: The session item to evict
        new_session_item: The new session item to create
        refresh_token_hash: Hash of the evicted session's refresh token

    Raises:
        SessionLimitRaceError: If transaction fails due to concurrent modification
    """
    table_name = table.name
    now = datetime.now(UTC)
    blocklist_ttl = int((now + timedelta(days=SESSION_DURATION_DAYS)).timestamp())

    oldest_pk = oldest_session["PK"]
    oldest_sk = oldest_session["SK"]

    transact_items = [
        # 1. Verify oldest session still exists (prevents double-eviction)
        {
            "ConditionCheck": {
                "TableName": table_name,
                "Key": {
                    "PK": {"S": oldest_pk},
                    "SK": {"S": oldest_sk},
                },
                "ConditionExpression": "attribute_exists(PK)",
            }
        },
        # 2. Delete the oldest session
        {
            "Delete": {
                "TableName": table_name,
                "Key": {
                    "PK": {"S": oldest_pk},
                    "SK": {"S": oldest_sk},
                },
            }
        },
        # 3. Add evicted token to blocklist (FR-004, FR-006)
        {
            "Put": {
                "TableName": table_name,
                "Item": {
                    "PK": {"S": f"BLOCK#refresh#{refresh_token_hash}"},
                    "SK": {"S": "BLOCK"},
                    "ttl": {"N": str(blocklist_ttl)},
                    "evicted_at": {"S": now.isoformat()},
                    "user_id": {"S": user_id},
                    "reason": {"S": "session_limit_eviction"},
                },
            }
        },
        # 4. Create new session (fails if somehow already exists)
        {
            "Put": {
                "TableName": table_name,
                "Item": _serialize_for_transaction(new_session_item),
                "ConditionExpression": "attribute_not_exists(PK)",
            }
        },
    ]

    try:
        dynamodb = boto3.client("dynamodb")
        dynamodb.transact_write_items(TransactItems=transact_items)
        logger.info(
            "Atomic session eviction completed",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "evicted_session": sanitize_for_log(oldest_sk[:20]),
            },
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "TransactionCanceledException":
            reasons = e.response.get("CancellationReasons", [])
            logger.warning(
                "Session eviction race condition",
                extra={
                    "user_id_prefix": sanitize_for_log(user_id[:8]),
                    "cancellation_reasons": str(reasons)[:100],
                },
            )
            raise SessionLimitRaceError(user_id, reasons) from e
        raise


def _serialize_for_transaction(item: dict) -> dict:
    """Convert a high-level DynamoDB item to low-level format for transactions.

    TransactWriteItems requires low-level attribute format (e.g., {"S": "value"}).

    Args:
        item: High-level item dict (from Table resource format)

    Returns:
        Low-level format dict for use with DynamoDB client
    """
    result = {}
    for key, value in item.items():
        if isinstance(value, str):
            result[key] = {"S": value}
        elif isinstance(value, bool):
            result[key] = {"BOOL": value}
        elif isinstance(value, int | float):
            result[key] = {"N": str(value)}
        elif isinstance(value, list):
            if all(isinstance(v, str) for v in value):
                result[key] = {"SS": value} if value else {"L": []}
            else:
                result[key] = {"L": [_serialize_value(v) for v in value]}
        elif isinstance(value, dict):
            result[key] = {"M": _serialize_for_transaction(value)}
        elif value is None:
            result[key] = {"NULL": True}
    return result


def _serialize_value(value: Any) -> dict:
    """Serialize a single value to DynamoDB low-level format."""
    if isinstance(value, str):
        return {"S": value}
    elif isinstance(value, bool):
        return {"BOOL": value}
    elif isinstance(value, int | float):
        return {"N": str(value)}
    elif isinstance(value, dict):
        return {"M": _serialize_for_transaction(value)}
    elif value is None:
        return {"NULL": True}
    return {"S": str(value)}


@xray_recorder.capture("create_session_with_limit_enforcement")
def create_session_with_limit_enforcement(
    table: Any,
    user_id: str,
    session_item: dict,
    refresh_token: str | None = None,
) -> bool:
    """Create a new session, enforcing the session limit (T006).

    If user is at or over SESSION_LIMIT, evicts the oldest session atomically
    before creating the new one.

    Args:
        table: DynamoDB Table resource
        user_id: User UUID
        session_item: The session item to create
        refresh_token: Optional refresh token to hash for blocklist

    Returns:
        True if session created successfully

    Raises:
        SessionLimitRaceError: If atomic eviction fails (client should retry)
    """
    sessions = get_user_sessions(table, user_id)

    if len(sessions) >= SESSION_LIMIT:
        oldest_session = sessions[0]

        # Get refresh token hash from oldest session or use placeholder
        oldest_token_hash = oldest_session.get("refresh_token_hash", "")
        if not oldest_token_hash:
            # Generate deterministic hash from session ID as fallback
            oldest_token_hash = hash_refresh_token(oldest_session.get("SK", ""))

        evict_oldest_session_atomic(
            table=table,
            user_id=user_id,
            oldest_session=oldest_session,
            new_session_item=session_item,
            refresh_token_hash=oldest_token_hash,
        )
        return True

    # Under limit - simple create
    try:
        table.put_item(
            Item=session_item,
            ConditionExpression="attribute_not_exists(PK)",
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning(
                "Session already exists (race condition)",
                extra={"user_id_prefix": sanitize_for_log(user_id[:8])},
            )
            return True  # Session exists, treat as success
        raise


@xray_recorder.capture("refresh_session")
def refresh_session(table: Any, user_id: str) -> SessionRefreshResponse | None:
    """Refresh session and return new expiry info (T056).

    Args:
        table: DynamoDB Table resource
        user_id: User UUID

    Returns:
        SessionRefreshResponse if successful, None if invalid
    """
    user = extend_session_expiry(table, user_id)
    if not user:
        return None

    remaining = int((user.session_expires_at - datetime.now(UTC)).total_seconds())

    return SessionRefreshResponse(
        user_id=user.user_id,
        session_expires_at=user.session_expires_at.isoformat(),
        remaining_seconds=max(0, remaining),
        refreshed=True,
    )


@xray_recorder.capture("revoke_user_session")
def revoke_user_session(
    table: Any,
    user_id: str,
    reason: str,
) -> bool:
    """Revoke a single user's session (FR-016, T053).

    Args:
        table: DynamoDB Table resource
        user_id: User UUID
        reason: Reason for revocation (audit trail)

    Returns:
        True if revoked (or already revoked), False if user not found
    """
    user = get_user_by_id(table, user_id)
    if not user:
        logger.warning(
            "Cannot revoke session - user not found",
            extra={"user_id_prefix": sanitize_for_log(user_id[:8])},
        )
        return False

    # Idempotent: if already revoked, just return success
    if user.revoked:
        logger.debug(
            "Session already revoked",
            extra={"user_id_prefix": sanitize_for_log(user_id[:8])},
        )
        return True

    now = datetime.now(UTC)

    try:
        table.update_item(
            Key={"PK": user.pk, "SK": user.sk},
            UpdateExpression="SET revoked = :revoked, revoked_at = :revoked_at, revoked_reason = :reason",
            ExpressionAttributeValues={
                ":revoked": True,
                ":revoked_at": now.isoformat(),
                ":reason": reason,
            },
        )

        logger.info(
            "Revoked user session",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "reason": sanitize_for_log(reason[:50]),
            },
        )

        return True

    except Exception as e:
        logger.error("Failed to revoke session", extra=get_safe_error_info(e))
        return False


@xray_recorder.capture("revoke_sessions_bulk")
def revoke_sessions_bulk(
    table: Any,
    user_ids: list[str],
    reason: str,
) -> BulkRevocationResponse:
    """Revoke multiple sessions (andon cord pattern) (FR-017, T054).

    Args:
        table: DynamoDB Table resource
        user_ids: List of user UUIDs to revoke
        reason: Reason for revocation (audit trail)

    Returns:
        BulkRevocationResponse with counts and failed IDs
    """
    if not user_ids:
        return BulkRevocationResponse(
            revoked_count=0,
            failed_count=0,
            failed_user_ids=[],
        )

    revoked_count = 0
    failed_count = 0
    failed_user_ids = []

    for user_id in user_ids:
        success = revoke_user_session(table, user_id, reason)
        if success:
            revoked_count += 1
        else:
            failed_count += 1
            failed_user_ids.append(user_id)

    logger.info(
        "Bulk session revocation completed",
        extra={
            "revoked_count": revoked_count,
            "failed_count": failed_count,
            "reason": sanitize_for_log(reason[:50]),
        },
    )

    return BulkRevocationResponse(
        revoked_count=revoked_count,
        failed_count=failed_count,
        failed_user_ids=failed_user_ids,
    )


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
    """Response for GET /api/v2/auth/magic-link/verify.

    Security: email is MASKED, refresh_token is NEVER in body.
    """

    status: str
    # user_id intentionally removed - frontend doesn't need it
    email_masked: str | None = None  # j***@example.com
    auth_type: str | None = None
    tokens: dict | None = None  # NO refresh_token - that's HttpOnly cookie
    refresh_token_for_cookie: str | None = None  # Router sets this as HttpOnly cookie
    merged_anonymous_data: bool = False
    error: str | None = None
    message: str | None = None


class OAuthURLsResponse(BaseModel):
    """Response for GET /api/v2/auth/oauth/urls."""

    providers: dict
    state: str  # Feature 1185: OAuth state for CSRF protection


class OAuthCallbackRequest(BaseModel):
    """Request body for POST /api/v2/auth/oauth/callback."""

    code: str
    provider: Literal["google", "github"]
    redirect_uri: str  # Feature 1185: For state validation
    state: str  # Feature 1185: OAuth state for CSRF protection
    anonymous_user_id: str | None = None


class OAuthCallbackResponse(BaseModel):
    """Response for POST /api/v2/auth/oauth/callback.

    Security: email is MASKED, refresh_token is NEVER in body.
    """

    status: str
    # user_id intentionally removed - frontend doesn't need it
    email_masked: str | None = None  # j***@example.com
    auth_type: str | None = None
    tokens: dict | None = None  # NO refresh_token - that's HttpOnly cookie
    refresh_token_for_cookie: str | None = None  # Router sets this as HttpOnly cookie
    merged_anonymous_data: bool = False
    is_new_user: bool = False
    conflict: bool = False
    existing_provider: str | None = None
    message: str | None = None
    error: str | None = None

    # Feature 1176: Federation fields - enables frontend RBAC decisions
    role: str = "anonymous"
    verification: str = "none"
    linked_providers: list[str] = Field(default_factory=list)
    last_provider_used: str | None = None


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
    """Response for GET /api/v2/auth/session - MINIMAL.

    Security: No user_id, no absolute timestamps.
    """

    # user_id intentionally removed - frontend doesn't need internal ID
    email_masked: str | None = None
    auth_type: str
    # Relative time instead of absolute
    session_expires_in_seconds: int
    linked_providers: list[str]
    # session_started_at, last_activity_at removed - not needed by frontend


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


# Feature 1182: Email-to-OAuth Link (Flow 4)
class LinkEmailRequest(BaseModel):
    """Request body for POST /api/v2/auth/link-email."""

    email: EmailStr


class LinkEmailResponse(BaseModel):
    """Response for email linking operations (Flow 4)."""

    status: str
    message: str | None = None
    linked_providers: list[str] | None = None
    error: str | None = None


class CompleteEmailLinkRequest(BaseModel):
    """Request body for POST /api/v2/auth/complete-email-link."""

    token: str


# Feature 1166: HMAC completely removed - token security via:
# 1. 256-bit random token (secrets.token_urlsafe) - unguessable
# 2. Atomic DynamoDB consumption (ConditionExpression) - no replay
# 3. Short expiry (1 hour) + rate limiting
MAGIC_LINK_EXPIRY_HOURS = 1


# T090: Magic Link Request
@xray_recorder.capture("request_magic_link")
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

    # Feature 1166: Create token with random UUID (no HMAC signature)
    # Security: 122-bit UUID entropy + atomic DB consumption prevents guessing/replay
    token_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=MAGIC_LINK_EXPIRY_HOURS)

    token = MagicLinkToken(
        token_id=token_id,
        email=email,
        created_at=now,
        expires_at=expires_at,
        used=False,
        anonymous_user_id=request.anonymous_user_id,
    )

    # Store token
    table.put_item(Item=token.to_dynamodb_item())

    # Send email (if callback provided)
    if send_email_callback:
        send_email_callback(email, token_id)

    return MagicLinkResponse(
        status="email_sent",
        email=email,
        expires_in_seconds=3600,
        message="Check your email for a sign-in link",
    )


def _invalidate_existing_tokens(table: Any, email: str) -> None:
    """Invalidate any existing magic link tokens for an email.

    Uses by_email GSI for O(result) query performance.
    (502-gsi-query-optimization: Replaced scan with GSI query)
    """
    try:
        # Query using by_email GSI, filter by entity_type and used
        response = table.query(
            IndexName="by_email",
            KeyConditionExpression="email = :email",
            FilterExpression="entity_type = :type AND used = :used",
            ExpressionAttributeValues={
                ":email": email.lower(),
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

        # Handle pagination with LastEvaluatedKey
        while "LastEvaluatedKey" in response:
            response = table.query(
                IndexName="by_email",
                KeyConditionExpression="email = :email",
                FilterExpression="entity_type = :type AND used = :used",
                ExpressionAttributeValues={
                    ":email": email.lower(),
                    ":type": "MAGIC_LINK_TOKEN",
                    ":used": False,
                },
                ExclusiveStartKey=response["LastEvaluatedKey"],
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


# Feature 014 (T031): Atomic Token Verification
@xray_recorder.capture("verify_and_consume_token")
def verify_and_consume_token(
    table: Any,
    token_id: str,
    client_ip: str,
) -> MagicLinkToken | None:
    """Atomically verify and consume a magic link token (FR-004, FR-005, FR-006).

    Uses DynamoDB conditional update to ensure token can only be consumed once,
    even under concurrent verification attempts. This prevents race conditions
    where multiple requests try to use the same token.

    Args:
        table: DynamoDB Table resource
        token_id: Token UUID from magic link URL
        client_ip: Client IP address for audit logging

    Returns:
        MagicLinkToken if successfully consumed, None if token not found

    Raises:
        TokenAlreadyUsedError: If token was already consumed (FR-005)
        TokenExpiredError: If token has expired (FR-006)
    """
    logger.info(
        "Attempting atomic token verification",
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
        return None

    item = response.get("Item")
    if not item:
        logger.warning(
            "Token not found",
            extra={"token_prefix": sanitize_for_log(token_id[:8])},
        )
        return None

    token = MagicLinkToken.from_dynamodb_item(item)

    # Check if already used (before attempting update)
    if token.used:
        logger.warning(
            "Token already used",
            extra={
                "token_prefix": sanitize_for_log(token_id[:8]),
                "used_at": token.used_at.isoformat() if token.used_at else None,
            },
        )
        raise TokenAlreadyUsedError(token_id=token_id, used_at=token.used_at)

    # Check expiry (before attempting update - saves a write)
    now = datetime.now(UTC)
    token_expires = (
        token.expires_at.replace(tzinfo=UTC)
        if token.expires_at.tzinfo is None
        else token.expires_at
    )
    if now > token_expires:
        logger.info(
            "Token expired",
            extra={
                "token_prefix": sanitize_for_log(token_id[:8]),
                "expired_at": token.expires_at.isoformat(),
            },
        )
        raise TokenExpiredError(token_id=token_id, expired_at=token.expires_at)

    # Atomic conditional update - only succeeds if used=false
    try:
        table.update_item(
            Key={
                "PK": f"TOKEN#{token_id}",
                "SK": "MAGIC_LINK",
            },
            UpdateExpression="SET used = :true, used_at = :now, used_by_ip = :ip",
            ConditionExpression="used = :false",
            ExpressionAttributeValues={
                ":true": True,
                ":false": False,
                ":now": now.isoformat(),
                ":ip": client_ip,
            },
        )

        logger.info(
            "Token consumed successfully",
            extra={
                "token_prefix": sanitize_for_log(token_id[:8]),
                "client_ip": sanitize_for_log(client_ip),
            },
        )

        # Update token object with consumed state
        token.used = True
        token.used_at = now
        token.used_by_ip = client_ip

        return token

    except table.meta.client.exceptions.ConditionalCheckFailedException:
        # Race condition - another request consumed the token
        logger.warning(
            "Token consumption race condition detected",
            extra={"token_prefix": sanitize_for_log(token_id[:8])},
        )
        raise TokenAlreadyUsedError(token_id=token_id, used_at=None) from None

    except Exception as e:
        logger.error(
            "Failed to consume token",
            extra=get_safe_error_info(e),
        )
        raise RuntimeError("Failed to consume token") from e


# T091: Magic Link Verification (Feature 1129: Atomic consumption)
@xray_recorder.capture("verify_magic_link")
def verify_magic_link(
    table: Any,
    token_id: str,
    client_ip: str = "unknown",
) -> MagicLinkVerifyResponse:
    """Verify a magic link token using atomic consumption.

    Feature 1129: Uses verify_and_consume_token() internally to prevent
    race condition token reuse via DynamoDB conditional update.

    Args:
        table: DynamoDB Table resource
        token_id: Token UUID from URL
        client_ip: Client IP for audit trail (Feature 1129)

    Returns:
        MagicLinkVerifyResponse with user info and tokens

    Raises:
        TokenAlreadyUsedError: If token was already consumed (409)
        TokenExpiredError: If token has expired (410)
    """
    logger.info(
        "Verifying magic link",
        extra={"token_prefix": sanitize_for_log(token_id[:8])},
    )

    # Feature 1129: Use atomic token consumption to prevent race conditions
    # verify_and_consume_token uses ConditionExpression="used = :false"
    # to ensure only one request can consume the token
    token = verify_and_consume_token(table, token_id, client_ip)

    if token is None:
        return MagicLinkVerifyResponse(
            status="invalid",
            error="token_not_found",
            message="Invalid link. Please request a new one.",
        )

    # TokenAlreadyUsedError and TokenExpiredError propagate up to router
    # which converts them to 409 and 410 respectively

    # Find or create user (use GSI version for O(1) lookup)
    existing_user = get_user_by_email_gsi(table, token.email)
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
    body_tokens, refresh_token = _generate_tokens(user)

    return MagicLinkVerifyResponse(
        status="verified",
        # user_id removed - frontend doesn't need it
        email_masked=_mask_email(user.email),
        auth_type="email",
        tokens=body_tokens,  # NO refresh_token in body
        refresh_token_for_cookie=refresh_token,  # Router sets HttpOnly cookie
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


def _generate_tokens(user: User) -> tuple[dict, str]:
    """Generate mock tokens for testing.

    In production, tokens come from Cognito.
    SECURITY: Blocked in Lambda environment to prevent authentication bypass.

    Returns:
        Tuple of (tokens_for_body, refresh_token_for_cookie)
        - tokens_for_body: NEVER contains refresh_token
        - refresh_token_for_cookie: For HttpOnly cookie

    Raises:
        RuntimeError: If called in Lambda environment (AWS_LAMBDA_FUNCTION_NAME is set)
    """
    # SECURITY GUARD: Block mock tokens in Lambda environment
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        logger.error(
            "SECURITY: Mock token generation blocked in Lambda environment. "
            "Production must use Cognito tokens."
        )
        raise RuntimeError(
            "Mock token generation is disabled in Lambda environment. "
            "Use real Cognito tokens in production."
        )

    refresh_token = f"mock_refresh_token_{user.user_id[:8]}"

    # Body tokens - NO refresh_token (that goes in HttpOnly cookie)
    body_tokens = {
        "id_token": f"mock_id_token_{user.user_id[:8]}",
        "access_token": f"mock_access_token_{user.user_id[:8]}",
        "expires_in": 3600,
    }

    return body_tokens, refresh_token


def _mask_email(email: str | None) -> str | None:
    """Mask email for frontend: john@example.com -> j***@example.com"""
    if not email:
        return None
    try:
        local, domain = email.split("@")
        if len(local) <= 1:
            return f"*@{domain}"
        return f"{local[0]}***@{domain}"
    except ValueError:
        return "***"


# T092: OAuth URLs
def get_oauth_urls(table: Any) -> OAuthURLsResponse:
    """Get OAuth authorization URLs for supported providers.

    Feature 1185: Generates and stores OAuth state for CSRF protection.
    Each provider gets its own state to prevent provider confusion attacks.
    State is included in authorize URLs and must be validated on callback.

    Args:
        table: DynamoDB Table resource for storing state

    Returns:
        OAuthURLsResponse with provider URLs and state
    """
    config = CognitoConfig.from_env()

    # Feature 1185: Generate separate state per provider for A13 validation
    google_state = generate_state()
    github_state = generate_state()

    # Store state for Google
    store_oauth_state(
        table=table,
        state_id=google_state,
        provider="google",
        redirect_uri=config.redirect_uri,
    )

    # Store state for GitHub
    store_oauth_state(
        table=table,
        state_id=github_state,
        provider="github",
        redirect_uri=config.redirect_uri,
    )

    return OAuthURLsResponse(
        providers={
            "google": {
                "authorize_url": config.get_authorize_url("Google", state=google_state),
                "icon": "google",
                "state": google_state,  # Provider-specific state
            },
            "github": {
                "authorize_url": config.get_authorize_url("GitHub", state=github_state),
                "icon": "github",
                "state": github_state,  # Provider-specific state
            },
        },
        state=google_state,  # Default for backward compatibility
    )


# T093: OAuth Callback
@xray_recorder.capture("handle_oauth_callback")
def handle_oauth_callback(
    table: Any,
    code: str,
    provider: str,
    redirect_uri: str,
    state: str,
    anonymous_user_id: str | None = None,
) -> OAuthCallbackResponse:
    """Handle OAuth callback from Cognito.

    Feature 1185: Validates OAuth state to prevent CSRF and redirect attacks.

    Args:
        table: DynamoDB Table resource
        code: Authorization code from OAuth provider
        provider: OAuth provider ("google" | "github")
        redirect_uri: Callback redirect URI
        state: OAuth state for CSRF protection
        anonymous_user_id: Optional anonymous user ID to link

    Returns:
        OAuthCallbackResponse with user info and tokens
    """
    logger.info(
        "Processing OAuth callback",
        extra={"provider": provider},
    )

    # Feature 1190 A23: Validate OAuth provider (AUTH_015)
    valid_providers = {"google", "github"}
    if provider not in valid_providers:
        logger.warning(
            "Unknown OAuth provider (AUTH_015)",
            extra={"provider": provider},
        )
        return OAuthCallbackResponse(
            status="error",
            error="AUTH_015",
            message="Unknown OAuth provider",
        )

    # Feature 1185: Validate OAuth state (A12-A13)
    is_valid, error_msg = validate_oauth_state(
        table=table,
        state_id=state,
        provider=provider,
        redirect_uri=redirect_uri,
    )
    if not is_valid:
        logger.warning(
            "OAuth state validation failed",
            extra={"provider": provider},
        )
        return OAuthCallbackResponse(
            status="error",
            error="invalid_state",
            message=error_msg,
        )

    config = CognitoConfig.from_env()

    # Exchange code for tokens
    try:
        tokens = exchange_code_for_tokens(config, code)
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

    # Check for existing user with this email (use GSI for O(1) lookup)
    existing_user = get_user_by_email_gsi(table, email)

    # Feature 1181: Check for duplicate provider_sub before linking (AUTH_023)
    oauth_email_verified = claims.get("email_verified", False)
    if cognito_sub:
        existing_by_sub = get_user_by_provider_sub(table, provider, cognito_sub)
        if existing_by_sub and (
            not existing_user or existing_by_sub.user_id != existing_user.user_id
        ):
            # OAuth account already linked to a different user
            logger.warning(
                "OAuth account already linked to different user (AUTH_023)",
                extra={
                    "provider": provider,
                    "sub_prefix": sanitize_for_log(cognito_sub[:8]),
                },
            )
            return OAuthCallbackResponse(
                status="error",
                error="AUTH_023",
                message="This OAuth account is already linked to another user.",
            )

    if existing_user and existing_user.auth_type != provider:
        # Feature 1181: Flow 3 - Check if email not verified by OAuth (AUTH_022)
        if not oauth_email_verified:
            logger.warning(
                "OAuth email not verified by provider (AUTH_022)",
                extra={"provider": provider},
            )
            return OAuthCallbackResponse(
                status="error",
                error="AUTH_022",
                message="Email not verified by provider. Cannot link accounts.",
            )

        # Feature 1183: Flow 5 - OAuth-to-OAuth auto-link
        # If existing user is OAuth (google, github) and new provider is also OAuth,
        # auto-link since both providers verify their emails
        oauth_providers = {"google", "github"}
        is_existing_oauth = existing_user.auth_type in oauth_providers
        is_new_oauth = provider in oauth_providers

        if is_existing_oauth and is_new_oauth:
            # Auto-link: both are OAuth providers, proceed silently
            logger.info(
                "Auto-linking OAuth to existing OAuth account (Flow 5)",
                extra={
                    "existing_provider": existing_user.auth_type,
                    "new_provider": provider,
                    "link_type": "auto",
                },
            )
            # Fall through to link the provider below
        elif can_auto_link_oauth(
            # Feature 1181: Flow 3 - Check if auto-link is possible (email → OAuth)
            oauth_email=email,
            oauth_email_verified=oauth_email_verified,
            provider=provider,
            existing_user_email=existing_user.email,
        ):
            # Auto-link: proceed silently (don't return conflict)
            logger.info(
                "Auto-linking OAuth to existing email account (Flow 3)",
                extra={
                    "provider": provider,
                    "link_type": "auto",
                },
            )
            # Fall through to link the provider below
        else:
            # Manual link required - return conflict for user confirmation
            return OAuthCallbackResponse(
                status="conflict",
                conflict=True,
                existing_provider=existing_user.auth_type,
                email_masked=_mask_email(email),
                message=f"An account with this email exists via {existing_user.auth_type}. Would you like to link your {provider.capitalize()} account?",
            )

    merged_data = False
    is_new_user = False

    if existing_user:
        user = existing_user
        # Update cognito_sub if not set
        if not user.cognito_sub:
            _update_cognito_sub(table, user, cognito_sub)
        # Link provider metadata (Feature 1169)
        _link_provider(
            table=table,
            user=user,
            provider=provider,
            sub=cognito_sub,
            email=email,
            avatar=claims.get("picture"),
            email_verified=claims.get("email_verified", False),
        )
        # Mark email as verified from OAuth (Feature 1171)
        _mark_email_verified(
            table=table,
            user=user,
            provider=provider,
            email=email,
            email_verified=claims.get("email_verified", False),
        )
        # Advance role from anonymous to free (Feature 1170)
        _advance_role(table=table, user=user, provider=provider)
        # Merge anonymous data
        if anonymous_user_id:
            result = merge_anonymous_data(table, anonymous_user_id, user.user_id)
            merged_data = result.status == "completed"
    else:
        # Create new user
        is_new_user = True
        user = _create_authenticated_user(table, email, provider, anonymous_user_id)
        _update_cognito_sub(table, user, cognito_sub)
        # Link provider metadata (Feature 1169)
        _link_provider(
            table=table,
            user=user,
            provider=provider,
            sub=cognito_sub,
            email=email,
            avatar=claims.get("picture"),
            email_verified=claims.get("email_verified", False),
        )
        # Mark email as verified from OAuth (Feature 1171)
        _mark_email_verified(
            table=table,
            user=user,
            provider=provider,
            email=email,
            email_verified=claims.get("email_verified", False),
        )
        # Advance role from anonymous to free (Feature 1170)
        _advance_role(table=table, user=user, provider=provider)
        if anonymous_user_id:
            result = merge_anonymous_data(table, anonymous_user_id, user.user_id)
            merged_data = result.status == "completed"

    # Security: NO refresh_token in body, masked email
    # Feature 1176: Compute federation state after mutations
    # - _link_provider sets: linked_providers, last_provider_used
    # - _mark_email_verified sets: verification="verified" if email_verified
    # - _advance_role sets: role="free" if was "anonymous"
    final_linked_providers = (
        user.linked_providers
        if provider in user.linked_providers
        else user.linked_providers + [provider]
    )
    final_verification = (
        "verified" if claims.get("email_verified", False) else user.verification
    )
    final_role = "free" if user.role == "anonymous" else user.role

    return OAuthCallbackResponse(
        status="authenticated",
        # user_id removed - frontend doesn't need it
        email_masked=_mask_email(user.email),
        auth_type=provider,
        tokens={
            "id_token": tokens.id_token,
            "access_token": tokens.access_token,
            # NO refresh_token in body
            "expires_in": tokens.expires_in,
        },
        refresh_token_for_cookie=tokens.refresh_token,  # Router sets HttpOnly cookie
        merged_anonymous_data=merged_data,
        is_new_user=is_new_user,
        # Feature 1176: Federation fields
        role=final_role,
        verification=final_verification,
        linked_providers=final_linked_providers,
        last_provider_used=provider,
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


def _link_provider(
    table: Any,
    user: User,
    provider: str,
    sub: str | None,
    email: str | None,
    avatar: str | None = None,
    email_verified: bool = False,
) -> None:
    """Link OAuth provider metadata to user account (Feature 1169).

    Populates federation fields: linked_providers, provider_metadata, last_provider_used.
    Follows silent failure pattern - logs warning but doesn't break OAuth flow.

    Args:
        table: DynamoDB table resource
        user: User to update
        provider: OAuth provider name (google, github)
        sub: OAuth subject claim (provider's user ID)
        email: Email from provider (may differ from account email)
        avatar: Profile picture URL from provider
        email_verified: Whether provider verified the email
    """
    if not sub:
        logger.warning(
            "Cannot link provider without sub claim",
            extra={
                "provider": provider,
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
            },
        )
        return

    try:
        # Build provider metadata
        now = datetime.now(UTC)
        metadata = ProviderMetadata(
            sub=sub,
            email=email,
            avatar=avatar,
            linked_at=now,
            verified_at=now if email_verified else None,
        )

        # Serialize metadata for DynamoDB
        metadata_dict = {
            "sub": metadata.sub,
            "email": metadata.email,
            "avatar": metadata.avatar,
            "linked_at": metadata.linked_at.isoformat(),
            "verified_at": metadata.verified_at.isoformat()
            if metadata.verified_at
            else None,
        }

        # Build update expression
        # Always update provider_metadata, last_provider_used, and provider_sub (Feature 1180)
        # provider_sub enables GSI lookup for account linking flows
        provider_sub_value = f"{provider}:{sub}"
        update_expr = (
            "SET provider_metadata.#provider = :metadata, "
            "last_provider_used = :provider_name, "
            "provider_sub = :provider_sub"
        )
        attr_names = {"#provider": provider}
        attr_values = {
            ":metadata": metadata_dict,
            ":provider_name": provider,
            ":provider_sub": provider_sub_value,
        }

        # Add provider to linked_providers if not already present
        if provider not in user.linked_providers:
            update_expr += ", linked_providers = list_append(if_not_exists(linked_providers, :empty), :new_provider)"
            attr_values[":empty"] = []
            attr_values[":new_provider"] = [provider]

        table.update_item(
            Key={"PK": user.pk, "SK": user.sk},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values,
        )

        logger.info(
            "Provider linked to account",
            extra={
                "provider": provider,
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
                "is_new_link": provider not in user.linked_providers,
            },
        )
    except Exception as e:
        logger.warning(
            "Failed to link provider",
            extra={
                "provider": provider,
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
                **get_safe_error_info(e),
            },
        )


def _advance_role(
    table: Any,
    user: User,
    provider: str,
) -> None:
    """Advance user role from anonymous to free after OAuth (Feature 1170).

    When a user completes OAuth authentication with role="anonymous", advance
    them to role="free" and populate audit fields for compliance tracking.
    Higher roles (free/paid/operator) are preserved without modification.

    Follows silent failure pattern - logs warning but doesn't break OAuth flow.

    Args:
        table: DynamoDB table resource
        user: User to potentially upgrade
        provider: OAuth provider name (google, github) for audit trail
    """
    # Only advance from anonymous to free
    if user.role != "anonymous":
        logger.debug(
            "Role advancement skipped - user already has role",
            extra={
                "current_role": user.role,
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
            },
        )
        return

    try:
        now = datetime.now(UTC)
        role_assigned_by = f"oauth:{provider}"

        table.update_item(
            Key={"PK": user.pk, "SK": user.sk},
            UpdateExpression="SET #role = :new_role, role_assigned_at = :assigned_at, role_assigned_by = :assigned_by",
            ExpressionAttributeNames={"#role": "role"},
            ExpressionAttributeValues={
                ":new_role": "free",
                ":assigned_at": now.isoformat(),
                ":assigned_by": role_assigned_by,
            },
        )

        logger.info(
            "Role advanced from anonymous to free",
            extra={
                "provider": provider,
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
                "role_assigned_by": role_assigned_by,
            },
        )
    except Exception as e:
        logger.warning(
            "Failed to advance role",
            extra={
                "provider": provider,
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
                **get_safe_error_info(e),
            },
        )


def _mark_email_verified(
    table: Any,
    user: User,
    provider: str,
    email: str,
    email_verified: bool,
) -> None:
    """Mark email as verified from OAuth provider (Feature 1171).

    Updates user.verification field based on JWT email_verified claim.
    Must be called BEFORE _advance_role() to maintain state machine invariant:
    verification should be set before role is advanced from anonymous to free.

    Follows silent failure pattern - logs warning but doesn't break OAuth flow.

    Args:
        table: DynamoDB table resource
        user: User to potentially update
        provider: OAuth provider name (google, github) for audit trail
        email: Email address from OAuth JWT
        email_verified: email_verified claim from OAuth JWT (True/False)
    """
    # Only mark if provider says email is verified
    if not email_verified:
        logger.debug(
            "Email verification skipped - provider did not verify",
            extra={
                "provider": provider,
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
            },
        )
        return

    # Skip if already verified (idempotent)
    if user.verification == "verified":
        logger.debug(
            "Email verification skipped - already verified",
            extra={
                "provider": provider,
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
            },
        )
        return

    try:
        now = datetime.now(UTC)
        verification_marked_by = f"oauth:{provider}"

        table.update_item(
            Key={"PK": user.pk, "SK": user.sk},
            UpdateExpression="SET verification = :verified, primary_email = :email, verification_marked_at = :marked_at, verification_marked_by = :marked_by",
            ExpressionAttributeValues={
                ":verified": "verified",
                ":email": email,
                ":marked_at": now.isoformat(),
                ":marked_by": verification_marked_by,
            },
        )

        logger.info(
            "Email marked as verified from OAuth provider",
            extra={
                "provider": provider,
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
                "verification_marked_by": verification_marked_by,
            },
        )
    except Exception as e:
        logger.warning(
            "Failed to mark email verified",
            extra={
                "provider": provider,
                "user_id_prefix": sanitize_for_log(user.user_id[:8]),
                **get_safe_error_info(e),
            },
        )


# T094: Token Refresh
def refresh_access_tokens(
    refresh_token: str,
    table: Any | None = None,
) -> RefreshTokenResponse:
    """Refresh access and ID tokens.

    FR-007 (Feature 1188): Checks blocklist BEFORE issuing new tokens.

    Args:
        refresh_token: Current refresh token
        table: DynamoDB Table resource (optional, for blocklist check)

    Returns:
        RefreshTokenResponse with new tokens
    """
    # FR-007: Check blocklist BEFORE issuing new tokens (T010)
    if table is not None:
        token_hash = hash_refresh_token(refresh_token)
        if is_token_blocklisted(table, token_hash):
            logger.warning(
                "Blocked refresh attempt for evicted token",
                extra={"token_hash_prefix": token_hash[:8]},
            )
            return RefreshTokenResponse(
                error="token_revoked",
                message="Session has been revoked",
            )

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
    table: Any,
    user_id: str,
    access_token: str,
) -> SignOutResponse:
    """Sign out user (current device only).

    Args:
        table: DynamoDB Table resource
        user_id: User ID from session
        access_token: User's access token

    Returns:
        SignOutResponse
    """
    # Invalidate the session by setting expiry to past
    try:
        now = datetime.now(UTC)
        past_time = now - timedelta(days=1)

        table.update_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": "PROFILE",
            },
            UpdateExpression="SET session_expires_at = :expires",
            ExpressionAttributeValues={
                ":expires": past_time.isoformat(),
            },
        )

        logger.info(
            "User signed out - session invalidated",
            extra={"user_id_prefix": sanitize_for_log(user_id[:8])},
        )

    except Exception as e:
        logger.warning(
            "Failed to invalidate session in database",
            extra=get_safe_error_info(e),
        )
        # Still return success - client will clear tokens

    return SignOutResponse(
        status="signed_out",
        message="Signed out from this device",
    )


# T096: Session Info
def get_session_info(
    table: Any,
    user_id: str,
) -> SessionInfoResponse | None:
    """Get session information for a user - MINIMAL response.

    Args:
        table: DynamoDB Table resource
        user_id: User UUID

    Returns:
        SessionInfoResponse or None if not found

    Security:
        - No user_id in response (frontend has it in header)
        - Relative time (expires_in_seconds) not absolute timestamp
        - Email masked
    """
    user = get_user_by_id(table, user_id)
    if not user:
        return None

    # Determine linked providers
    linked_providers = [user.auth_type]
    if user.auth_type in ["google", "github"] and user.email:
        # User might also have email auth
        linked_providers.append(user.auth_type)

    # Calculate relative expiry time
    now = datetime.now(UTC)
    expires_in = max(0, int((user.session_expires_at - now).total_seconds()))

    return SessionInfoResponse(
        # user_id removed - frontend doesn't need it, they have it in header
        email_masked=_mask_email(user.email),
        auth_type=user.auth_type,
        session_expires_in_seconds=expires_in,  # Relative, not absolute
        linked_providers=linked_providers,
        # session_started_at, last_activity_at removed - not needed by frontend
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
    # Use GSI for O(1) lookup
    existing_user = get_user_by_email_gsi(table, request.email)

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
@xray_recorder.capture("link_accounts")
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
            merged_at=(
                result.merged_at.isoformat().replace("+00:00", "Z")
                if result.merged_at
                else None
            ),
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


# =============================================================================
# Feature 1182: Email-to-OAuth Link (Federation Flow 4)
# =============================================================================


@xray_recorder.capture("link_email_to_oauth_user")
def link_email_to_oauth_user(
    table: Any,
    user: User,
    email: str,
    send_email_callback: Any = None,
) -> LinkEmailResponse:
    """Initiate email linking for an OAuth-authenticated user.

    Flow 4: OAuth user (e.g., Google) wants to add email as additional auth method.
    Stores pending_email on user record and sends magic link for verification.

    Args:
        table: DynamoDB Table resource
        user: Authenticated OAuth user
        email: Email address to link
        send_email_callback: Optional callback to send magic link email

    Returns:
        LinkEmailResponse with status

    Raises:
        ValueError: If email is already linked to user
    """
    # Validate email not already linked
    if "email" in user.linked_providers:
        raise ValueError("Email already linked to this account")

    normalized_email = email.lower()

    logger.info(
        "Email linking initiated",
        extra={
            "user_id_prefix": sanitize_for_log(user.user_id[:8]),
            "email_domain": sanitize_for_log(normalized_email.split("@")[1]),
        },
    )

    # Generate magic link token with user_id context
    token_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=MAGIC_LINK_EXPIRY_HOURS)

    # Store token in DynamoDB
    token_item = {
        "PK": f"TOKEN#{token_id}",
        "SK": "EMAIL_LINK",
        "entity_type": "EMAIL_LINK_TOKEN",
        "token_id": token_id,
        "email": normalized_email,
        "user_id": user.user_id,  # Link token to authenticated user
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "used": False,
        "ttl": int(expires_at.timestamp()) + 3600,  # 1 hour buffer
    }

    try:
        table.put_item(Item=token_item)
    except Exception as e:
        logger.error("Failed to store email link token", extra=get_safe_error_info(e))
        raise

    # Update user's pending_email
    try:
        table.update_item(
            Key={"PK": f"USER#{user.user_id}", "SK": "PROFILE"},
            UpdateExpression="SET pending_email = :pending_email",
            ExpressionAttributeValues={":pending_email": normalized_email},
        )
    except Exception as e:
        logger.warning("Failed to update pending_email", extra=get_safe_error_info(e))
        # Continue anyway - token is created

    # Send magic link email
    if send_email_callback:
        try:
            send_email_callback(normalized_email, token_id)
        except Exception as e:
            logger.error(
                "Failed to send magic link email", extra=get_safe_error_info(e)
            )
            # Don't raise - token exists, user can retry

    logger.info(
        "Email link token created",
        extra={"token_prefix": sanitize_for_log(token_id[:8])},
    )

    return LinkEmailResponse(
        status="pending",
        message="Verification email sent",
    )


@xray_recorder.capture("complete_email_link")
def complete_email_link(
    table: Any,
    user: User,
    token_id: str,
    client_ip: str,
) -> LinkEmailResponse:
    """Complete email linking after magic link verification.

    Flow 4 completion: Verifies the magic link token and adds email to
    user's linked_providers with provider_metadata.

    Args:
        table: DynamoDB Table resource
        user: Authenticated OAuth user
        token_id: Magic link token ID from email
        client_ip: Client IP for audit logging

    Returns:
        LinkEmailResponse with updated linked_providers

    Raises:
        ValueError: If token is invalid, expired, or belongs to different user
        TokenAlreadyUsedError: If token was already consumed
        TokenExpiredError: If token has expired
    """
    # Retrieve token
    try:
        response = table.get_item(Key={"PK": f"TOKEN#{token_id}", "SK": "EMAIL_LINK"})
    except Exception as e:
        logger.error(
            "Failed to retrieve email link token", extra=get_safe_error_info(e)
        )
        raise ValueError("Invalid or expired link") from None

    item = response.get("Item")
    if not item:
        logger.warning(
            "Email link token not found",
            extra={"token_prefix": sanitize_for_log(token_id[:8])},
        )
        raise ValueError("Invalid or expired link")

    # Validate token
    now = datetime.now(UTC)
    expires_at = datetime.fromisoformat(item["expires_at"].replace("Z", "+00:00"))

    # Check already used
    if item.get("used"):
        used_at = item.get("used_at")
        raise TokenAlreadyUsedError(
            token_id=token_id,
            used_at=datetime.fromisoformat(used_at) if used_at else None,
        )

    # Check expiry
    if now > expires_at:
        raise TokenExpiredError(token_id=token_id, expired_at=expires_at)

    # Check user_id matches (security: prevent token theft)
    if item.get("user_id") != user.user_id:
        logger.warning(
            "Email link token user mismatch",
            extra={
                "token_user_prefix": sanitize_for_log(item.get("user_id", "")[:8]),
                "request_user_prefix": sanitize_for_log(user.user_id[:8]),
            },
        )
        raise ValueError("Token does not belong to this user")

    email = item["email"]

    # Atomically consume token
    try:
        table.update_item(
            Key={"PK": f"TOKEN#{token_id}", "SK": "EMAIL_LINK"},
            UpdateExpression="SET used = :true, used_at = :now, used_by_ip = :ip",
            ConditionExpression="used = :false",
            ExpressionAttributeValues={
                ":true": True,
                ":false": False,
                ":now": now.isoformat(),
                ":ip": client_ip,
            },
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        raise TokenAlreadyUsedError(token_id=token_id, used_at=None) from None

    # Build provider metadata
    metadata_dict = {
        "sub": None,  # Email provider has no sub
        "email": email,
        "avatar": None,
        "linked_at": now.isoformat(),
        "verified_at": now.isoformat(),  # Verified by magic link click
    }

    # Update user: add email to linked_providers and provider_metadata
    try:
        # Build update expression
        update_parts = [
            "provider_metadata.#email = :metadata",
            "pending_email = :null",
            "verification = :verified",
        ]

        attr_names = {"#email": "email"}
        attr_values = {
            ":metadata": metadata_dict,
            ":null": None,
            ":verified": "verified",
        }

        # Add to linked_providers if not present
        if "email" not in user.linked_providers:
            update_parts.append(
                "linked_providers = list_append(if_not_exists(linked_providers, :empty), :new_provider)"
            )
            attr_values[":empty"] = []
            attr_values[":new_provider"] = ["email"]

        # Set primary_email if not set
        if not user.primary_email:
            update_parts.append("primary_email = :email")
            attr_values[":email"] = email

        update_expr = "SET " + ", ".join(update_parts)

        table.update_item(
            Key={"PK": f"USER#{user.user_id}", "SK": "PROFILE"},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values,
        )

    except Exception as e:
        logger.error(
            "Failed to update user with email link", extra=get_safe_error_info(e)
        )
        raise

    # Log audit event
    logger.info(
        "AUTH_METHOD_LINKED",
        extra={
            "event_type": "AUTH_METHOD_LINKED",
            "user_id_prefix": sanitize_for_log(user.user_id[:8]),
            "provider": "email",
            "link_type": "manual",
            "email_domain": sanitize_for_log(email.split("@")[1]),
        },
    )

    # Build updated linked_providers for response
    updated_providers = list(user.linked_providers)
    if "email" not in updated_providers:
        updated_providers.append("email")

    logger.info(
        "Email linked to OAuth user",
        extra={
            "user_id_prefix": sanitize_for_log(user.user_id[:8]),
            "email_domain": sanitize_for_log(email.split("@")[1]),
            "linked_providers": updated_providers,
        },
    )

    return LinkEmailResponse(
        status="linked",
        message="Email linked successfully",
        linked_providers=updated_providers,
    )

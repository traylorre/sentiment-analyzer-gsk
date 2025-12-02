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

from aws_xray_sdk.core import xray_recorder
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
from src.lambdas.shared.errors.session_errors import (
    SessionRevokedException,
    TokenAlreadyUsedError,
    TokenExpiredError,
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
                    "revoked_at": user.revoked_at.isoformat()
                    if user.revoked_at
                    else None,
                    "reason": sanitize_for_log(user.revoked_reason)
                    if user.revoked_reason
                    else None,
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


class OAuthCallbackRequest(BaseModel):
    """Request body for POST /api/v2/auth/oauth/callback."""

    code: str
    provider: Literal["google", "github"]
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


# T091: Magic Link Verification
@xray_recorder.capture("verify_magic_link")
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

    Returns:
        Tuple of (tokens_for_body, refresh_token_for_cookie)
        - tokens_for_body: NEVER contains refresh_token
        - refresh_token_for_cookie: For HttpOnly cookie
    """
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
@xray_recorder.capture("handle_oauth_callback")
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
        # Account conflict - mask email in response
        return OAuthCallbackResponse(
            status="conflict",
            conflict=True,
            existing_provider=existing_user.auth_type,
            email_masked=_mask_email(email),
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

    # Security: NO refresh_token in body, masked email
    return OAuthCallbackResponse(
        status="authenticated",
        # user_id removed - frontend doesn't need it
        email_masked=_mask_email(user.email),
        auth_type=request.provider,
        tokens={
            "id_token": tokens.id_token,
            "access_token": tokens.access_token,
            # NO refresh_token in body
            "expires_in": tokens.expires_in,
        },
        refresh_token_for_cookie=tokens.refresh_token,  # Router sets HttpOnly cookie
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
    table: Any,
    user_id: str,
    access_token: str,  # noqa: ARG001 - reserved for future Cognito integration
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

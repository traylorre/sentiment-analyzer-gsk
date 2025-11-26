"""Authentication endpoints for Feature 006.

Implements anonymous session management (T047-T048):
- POST /api/v2/auth/anonymous - Create anonymous session
- GET /api/v2/auth/validate - Validate session

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
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
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

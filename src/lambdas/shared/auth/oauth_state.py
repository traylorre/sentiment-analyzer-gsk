"""OAuth state management for CSRF protection (Feature 1185).

This module provides secure OAuth state generation, storage, and validation
to prevent redirect attacks (A12) and provider confusion attacks (A13).

State is stored in DynamoDB with TTL for automatic cleanup.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

logger = logging.getLogger(__name__)

# Configuration
OAUTH_STATE_TTL_SECONDS = 300  # 5 minutes
OAUTH_STATE_PREFIX = "OAUTH_STATE#"


@dataclass(frozen=True)
class OAuthState:
    """OAuth state for CSRF protection.

    Attributes:
        state_id: Cryptographically secure random string
        provider: OAuth provider ("google" | "github")
        redirect_uri: Expected callback redirect URI
        created_at: When state was generated
        user_id: Optional anonymous user ID to link
        used: Whether state has been consumed
    """

    state_id: str
    provider: str
    redirect_uri: str
    created_at: datetime
    user_id: str | None = None
    used: bool = False


def generate_state() -> str:
    """Generate a cryptographically secure OAuth state string.

    Returns:
        43-character URL-safe base64 string (256 bits of entropy)
    """
    return secrets.token_urlsafe(32)


def store_oauth_state(
    table: Table,
    state_id: str,
    provider: str,
    redirect_uri: str,
    user_id: str | None = None,
) -> OAuthState:
    """Store OAuth state in DynamoDB.

    Args:
        table: DynamoDB table resource
        state_id: The generated state string
        provider: OAuth provider ("google" | "github")
        redirect_uri: Expected callback redirect URI
        user_id: Optional anonymous user ID to link

    Returns:
        OAuthState object representing stored state
    """
    now = datetime.now(UTC)
    ttl = int((now + timedelta(seconds=OAUTH_STATE_TTL_SECONDS)).timestamp())

    item = {
        "PK": f"{OAUTH_STATE_PREFIX}{state_id}",
        "SK": "STATE",
        "provider": provider,
        "redirect_uri": redirect_uri,
        "created_at": now.isoformat(),
        "used": False,
        "ttl": ttl,
    }
    if user_id:
        item["user_id"] = user_id

    table.put_item(Item=item)

    logger.info(
        "OAuth state stored",
        extra={
            "provider": provider,
            "has_user_id": user_id is not None,
            "ttl_seconds": OAUTH_STATE_TTL_SECONDS,
        },
    )

    return OAuthState(
        state_id=state_id,
        provider=provider,
        redirect_uri=redirect_uri,
        created_at=now,
        user_id=user_id,
        used=False,
    )


def get_oauth_state(table: Table, state_id: str) -> OAuthState | None:
    """Retrieve OAuth state from DynamoDB.

    Args:
        table: DynamoDB table resource
        state_id: The state string to look up

    Returns:
        OAuthState if found, None otherwise
    """
    try:
        response = table.get_item(
            Key={"PK": f"{OAUTH_STATE_PREFIX}{state_id}", "SK": "STATE"}
        )
        item = response.get("Item")
        if not item:
            return None

        return OAuthState(
            state_id=state_id,
            provider=item["provider"],
            redirect_uri=item["redirect_uri"],
            created_at=datetime.fromisoformat(item["created_at"]),
            user_id=item.get("user_id"),
            used=item.get("used", False),
        )
    except Exception:
        logger.exception("Failed to get OAuth state")
        return None


def validate_oauth_state(
    table: Table,
    state_id: str,
    provider: str,
    redirect_uri: str,
) -> tuple[bool, str]:
    """Validate OAuth state and mark as used.

    Performs all validation checks:
    1. State exists
    2. State not expired (created_at < 5 min ago)
    3. State not already used
    4. Provider matches
    5. Redirect URI matches

    Args:
        table: DynamoDB table resource
        state_id: The state string from callback
        provider: The provider claimed in callback
        redirect_uri: The redirect_uri in callback

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, "")
        If invalid: (False, "Invalid OAuth state")  # Generic message always
    """
    generic_error = "Invalid OAuth state"

    # Get state from DynamoDB
    state = get_oauth_state(table, state_id)
    if state is None:
        logger.warning("OAuth state validation failed: state not found")
        return False, generic_error

    # Check expiry
    now = datetime.now(UTC)
    expiry_time = state.created_at + timedelta(seconds=OAUTH_STATE_TTL_SECONDS)
    if now > expiry_time:
        logger.warning("OAuth state validation failed: state expired")
        return False, generic_error

    # Check already used
    if state.used:
        logger.warning("OAuth state validation failed: state already used")
        return False, generic_error

    # Check provider match
    if state.provider != provider:
        logger.warning(
            "OAuth state validation failed: provider mismatch",
            extra={"expected": state.provider, "received": provider},
        )
        return False, generic_error

    # Check redirect_uri match
    if state.redirect_uri != redirect_uri:
        logger.warning(
            "OAuth state validation failed: redirect_uri mismatch",
            extra={"expected": state.redirect_uri, "received": redirect_uri},
        )
        return False, generic_error

    # Mark as used with conditional update to prevent race conditions
    try:
        table.update_item(
            Key={"PK": f"{OAUTH_STATE_PREFIX}{state_id}", "SK": "STATE"},
            UpdateExpression="SET used = :true",
            ConditionExpression="used = :false",
            ExpressionAttributeValues={":true": True, ":false": False},
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        # Race condition - another request already used this state
        logger.warning("OAuth state validation failed: concurrent use detected")
        return False, generic_error

    logger.info(
        "OAuth state validated successfully",
        extra={"provider": provider},
    )
    return True, ""

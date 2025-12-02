"""Hybrid authentication middleware for Feature 014.

Supports both X-User-ID header (legacy) and Authorization: Bearer token
formats for backward compatibility and gradual migration.
"""

import logging
import uuid
from typing import Any

from aws_xray_sdk.core import xray_recorder

logger = logging.getLogger(__name__)


def extract_user_id(event: dict[str, Any]) -> str | None:
    """Extract user ID from either header format.

    Supports hybrid authentication approach:
    1. Authorization: Bearer {token} - preferred for new code
    2. X-User-ID header - legacy, backward compatible

    Args:
        event: Lambda event dict with headers

    Returns:
        User ID string if found and valid, None otherwise
    """
    headers = event.get("headers", {}) or {}

    # Normalize header keys to lowercase for case-insensitive matching
    normalized_headers = {k.lower(): v for k, v in headers.items()}

    # Try Bearer token first (preferred)
    auth_header = normalized_headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_id = _extract_user_id_from_token(token)
        if user_id:
            logger.debug(f"Extracted user_id from Bearer token: {user_id[:8]}...")
            return user_id

    # Fall back to X-User-ID (legacy)
    user_id = normalized_headers.get("x-user-id")
    if user_id:
        if _is_valid_uuid(user_id):
            logger.debug(f"Extracted user_id from X-User-ID header: {user_id[:8]}...")
            return user_id
        else:
            logger.warning(f"Invalid X-User-ID format: {user_id[:20]}...")
            return None

    logger.debug("No user_id found in request headers")
    return None


def _extract_user_id_from_token(token: str) -> str | None:
    """Extract user ID from Bearer token.

    Currently treats the token as a direct user ID for anonymous sessions.
    For authenticated sessions with JWTs, this would decode and validate
    the token to extract the user ID claim.

    Args:
        token: Bearer token value

    Returns:
        User ID if token is valid, None otherwise
    """
    # For anonymous sessions, the token IS the user_id
    # This supports the current traffic generator and test patterns
    if _is_valid_uuid(token):
        return token

    # TODO: Add JWT validation for authenticated sessions
    # This would decode the token and extract the 'sub' or 'user_id' claim
    # For now, we only support UUID tokens for anonymous sessions

    logger.debug("Token is not a valid UUID, JWT validation not yet implemented")
    return None


def _is_valid_uuid(value: str) -> bool:
    """Validate UUID v4 format.

    Args:
        value: String to validate

    Returns:
        True if valid UUID, False otherwise
    """
    try:
        uuid.UUID(value, version=4)
        return True
    except (ValueError, AttributeError):
        return False


@xray_recorder.capture("extract_auth_context")
def extract_auth_context(event: dict[str, Any]) -> dict[str, Any]:
    """Extract full authentication context from request.

    Returns a dict with:
    - user_id: Extracted user ID or None
    - auth_method: 'bearer' | 'x-user-id' | None
    - is_authenticated: Whether user ID was found

    Args:
        event: Lambda event dict

    Returns:
        Auth context dictionary
    """
    headers = event.get("headers", {}) or {}
    normalized_headers = {k.lower(): v for k, v in headers.items()}

    context = {
        "user_id": None,
        "auth_method": None,
        "is_authenticated": False,
    }

    # Try Bearer token first
    auth_header = normalized_headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_id = _extract_user_id_from_token(token)
        if user_id:
            context["user_id"] = user_id
            context["auth_method"] = "bearer"
            context["is_authenticated"] = True
            return context

    # Fall back to X-User-ID
    user_id = normalized_headers.get("x-user-id")
    if user_id and _is_valid_uuid(user_id):
        context["user_id"] = user_id
        context["auth_method"] = "x-user-id"
        context["is_authenticated"] = True
        return context

    return context


def require_auth(event: dict[str, Any]) -> str:
    """Extract user ID or raise error if not authenticated.

    Args:
        event: Lambda event dict

    Returns:
        User ID string

    Raises:
        ValueError: If no valid user ID found in headers
    """
    user_id = extract_user_id(event)
    if not user_id:
        raise ValueError("Authentication required: No valid user ID in request")
    return user_id

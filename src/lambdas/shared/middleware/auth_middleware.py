"""Hybrid authentication middleware for Feature 014.

Supports both X-User-ID header (legacy) and Authorization: Bearer token
formats for backward compatibility and gradual migration.

JWT authentication added in Feature 075 for authenticated sessions.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import jwt
from aws_xray_sdk.core import xray_recorder

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JWTClaim:
    """Represents validated claims from a JWT token.

    Attributes:
        subject: User ID (from 'sub' claim)
        expiration: Token expiration timestamp
        issued_at: Token issued timestamp
        issuer: Token issuer (optional)
    """

    subject: str
    expiration: datetime
    issued_at: datetime
    issuer: str | None = None


@dataclass(frozen=True)
class JWTConfig:
    """Configuration for JWT validation.

    Attributes:
        secret: Secret key for HMAC validation
        algorithm: JWT algorithm (default: HS256)
        issuer: Expected issuer (optional, for validation)
        leeway_seconds: Clock skew tolerance (default: 60s)
        access_token_lifetime_seconds: Expected token lifetime (default: 900s/15min)
    """

    secret: str
    algorithm: str = "HS256"
    issuer: str | None = "sentiment-analyzer"
    leeway_seconds: int = 60
    access_token_lifetime_seconds: int = 900


def _get_jwt_config() -> JWTConfig | None:
    """Load JWT configuration from environment.

    Returns:
        JWTConfig if JWT_SECRET is set, None otherwise
    """
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        return None

    return JWTConfig(
        secret=secret,
        algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        issuer=os.environ.get("JWT_ISSUER", "sentiment-analyzer"),
        leeway_seconds=int(os.environ.get("JWT_LEEWAY_SECONDS", "60")),
    )


def validate_jwt(token: str, config: JWTConfig | None = None) -> JWTClaim | None:
    """Validate a JWT token and extract claims.

    Validates the token signature, expiration, and required claims.

    Args:
        token: JWT token string (without "Bearer " prefix)
        config: Optional JWTConfig, uses environment if not provided

    Returns:
        JWTClaim if valid, None if invalid

    Environment:
        JWT_SECRET: Required secret key for validation
    """
    if config is None:
        config = _get_jwt_config()
        if config is None:
            logger.warning("JWT_SECRET not configured, cannot validate JWT")
            return None

    try:
        payload = jwt.decode(
            token,
            config.secret,
            algorithms=[config.algorithm],
            issuer=config.issuer,
            leeway=config.leeway_seconds,
            options={
                "require": ["sub", "exp", "iat"],
            },
        )

        return JWTClaim(
            subject=payload["sub"],
            expiration=datetime.fromtimestamp(payload["exp"], tz=UTC),
            issued_at=datetime.fromtimestamp(payload["iat"], tz=UTC),
            issuer=payload.get("iss"),
        )

    except jwt.ExpiredSignatureError:
        logger.debug("JWT token has expired")
        return None
    except jwt.InvalidIssuerError:
        logger.debug("JWT token has invalid issuer")
        return None
    except jwt.InvalidSignatureError:
        logger.warning("JWT token has invalid signature")
        return None
    except jwt.DecodeError:
        logger.debug("JWT token is malformed")
        return None
    except jwt.MissingRequiredClaimError as e:
        logger.debug(f"JWT token missing required claim: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error validating JWT: {e}")
        return None


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

    Supports both:
    1. UUID tokens for anonymous sessions (token IS the user_id)
    2. JWT tokens for authenticated sessions (user_id from 'sub' claim)

    Args:
        token: Bearer token value

    Returns:
        User ID if token is valid, None otherwise
    """
    # For anonymous sessions, the token IS the user_id
    # This supports the current traffic generator and test patterns
    if _is_valid_uuid(token):
        return token

    # Try JWT validation for authenticated sessions
    jwt_claim = validate_jwt(token)
    if jwt_claim:
        logger.debug(f"Extracted user_id from JWT token: {jwt_claim.subject[:8]}...")
        return jwt_claim.subject

    logger.debug("Token is not a valid UUID and JWT validation failed")
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

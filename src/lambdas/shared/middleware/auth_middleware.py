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
from enum import Enum
from typing import Any

import jwt
from aws_xray_sdk.core import xray_recorder

logger = logging.getLogger(__name__)


class AuthType(str, Enum):
    """Authentication type determined by token validation (Feature 1048).

    CRITICAL: This is determined by token validation, NOT request headers.
    Anonymous users cannot bypass by sending X-Auth-Type header.

    Values:
        ANONYMOUS: UUID token (no JWT claims) - anonymous session
        AUTHENTICATED: JWT with valid claims - authenticated session
    """

    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"


@dataclass(frozen=True)
class AuthContext:
    """Authentication context from validated token (Feature 1048).

    CRITICAL: auth_type is determined by token validation, not request headers.
    This prevents anonymous users from bypassing auth checks.

    Attributes:
        user_id: Validated user ID (or None if unauthenticated)
        auth_type: ANONYMOUS for UUID tokens, AUTHENTICATED for JWT
        auth_method: Where the credential came from ("bearer", "x-user-id", None)
        roles: List of role strings from JWT 'roles' claim (Feature 1130)
    """

    user_id: str | None
    auth_type: AuthType
    auth_method: str | None = None
    roles: list[str] | None = None


@dataclass(frozen=True)
class JWTClaim:
    """Represents validated claims from a JWT token.

    Attributes:
        subject: User ID (from 'sub' claim)
        expiration: Token expiration timestamp
        issued_at: Token issued timestamp
        issuer: Token issuer (optional)
        roles: List of user roles (from 'roles' claim, Feature 1130)
    """

    subject: str
    expiration: datetime
    issued_at: datetime
    issuer: str | None = None
    roles: list[str] | None = None


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
            roles=payload.get("roles"),
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
    """Extract user ID from Authorization: Bearer header.

    Feature 1146: X-User-ID header fallback REMOVED for security (CVSS 9.1).
    Users MUST use Bearer token for authentication.

    Args:
        event: Lambda event dict with headers

    Returns:
        User ID string if found and valid, None otherwise
    """
    headers = event.get("headers", {}) or {}

    # Normalize header keys to lowercase for case-insensitive matching
    normalized_headers = {k.lower(): v for k, v in headers.items()}

    # Feature 1146: Only Bearer token is accepted (X-User-ID fallback removed)
    auth_header = normalized_headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_id = _extract_user_id_from_token(token)
        if user_id:
            logger.debug(f"Extracted user_id from Bearer token: {user_id[:8]}...")
            return user_id

    # X-User-ID header is intentionally NOT checked (Feature 1146 security fix)
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


@xray_recorder.capture("extract_auth_context_typed")
def extract_auth_context_typed(event: dict[str, Any]) -> AuthContext:
    """Extract typed authentication context from request (Feature 1048, 1146).

    CRITICAL: auth_type is determined by token validation, NOT request headers.
    This prevents the X-Auth-Type header bypass vulnerability (Feature 1048).

    Feature 1146: X-User-ID header fallback REMOVED for security (CVSS 9.1).
    Users MUST use Bearer token for authentication.

    - JWT token with valid claims → AuthType.AUTHENTICATED
    - UUID token (no JWT) → AuthType.ANONYMOUS
    - No valid token → AuthType.ANONYMOUS with user_id=None

    Args:
        event: Lambda event dict with headers

    Returns:
        AuthContext with validated user_id and auth_type
    """
    headers = event.get("headers", {}) or {}
    normalized_headers = {k.lower(): v for k, v in headers.items()}

    # Feature 1146: Only Bearer token is accepted (X-User-ID fallback removed)
    auth_header = normalized_headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

        # Check if it's a JWT first (authenticated)
        jwt_claim = validate_jwt(token)
        if jwt_claim:
            logger.debug(
                f"Authenticated via JWT: {jwt_claim.subject[:8]}... "
                f"(auth_type=AUTHENTICATED)"
            )
            return AuthContext(
                user_id=jwt_claim.subject,
                auth_type=AuthType.AUTHENTICATED,
                auth_method="bearer",
                roles=jwt_claim.roles,
            )

        # Fall back to UUID token (anonymous)
        if _is_valid_uuid(token):
            logger.debug(
                f"Authenticated via UUID Bearer: {token[:8]}... (auth_type=ANONYMOUS)"
            )
            return AuthContext(
                user_id=token,
                auth_type=AuthType.ANONYMOUS,
                auth_method="bearer",
                roles=["anonymous"],
            )

    # X-User-ID header is intentionally NOT checked (Feature 1146 security fix)
    # No valid auth
    logger.debug("No valid auth token found (auth_type=ANONYMOUS, user_id=None)")
    return AuthContext(
        user_id=None,
        auth_type=AuthType.ANONYMOUS,
        auth_method=None,
        roles=None,
    )


@xray_recorder.capture("extract_auth_context")
def extract_auth_context(event: dict[str, Any]) -> dict[str, Any]:
    """Extract full authentication context from request (legacy dict format).

    DEPRECATED: Use extract_auth_context_typed() for new code.

    Feature 1146: X-User-ID header fallback removed - Bearer only.

    Returns a dict with:
    - user_id: Extracted user ID or None
    - auth_method: 'bearer' | None
    - is_authenticated: Whether user ID was found
    - auth_type: 'anonymous' | 'authenticated' (Feature 1048)

    Args:
        event: Lambda event dict

    Returns:
        Auth context dictionary
    """
    # Delegate to typed version for consistent behavior
    typed_context = extract_auth_context_typed(event)

    return {
        "user_id": typed_context.user_id,
        "auth_method": typed_context.auth_method,
        "is_authenticated": typed_context.user_id is not None,
        "auth_type": typed_context.auth_type.value,  # Feature 1048: expose auth_type
    }


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

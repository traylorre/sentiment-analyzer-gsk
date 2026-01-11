"""Role-based access control error types (Feature 1130).

These exceptions are used internally by the require_role decorator.
They are caught and converted to HTTPExceptions with generic messages
to prevent role enumeration attacks.

Auth error codes (Feature 1190 / spec-v2.md A23):
AUTH_013-AUTH_018 for identity flow error handling.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class AuthErrorCode(str, Enum):
    """Numeric auth error codes per spec-v2.md A23.

    These codes are returned in error responses to enable
    client-side error handling without exposing internal details.
    """

    AUTH_013 = "AUTH_013"  # Credentials changed (password reset)
    AUTH_014 = "AUTH_014"  # Session limit exceeded (evicted)
    AUTH_015 = "AUTH_015"  # Unknown OAuth provider
    AUTH_016 = "AUTH_016"  # OAuth provider mismatch
    AUTH_017 = "AUTH_017"  # Password requirements not met
    AUTH_018 = "AUTH_018"  # Token audience invalid (wrong env)


AUTH_ERROR_MESSAGES: dict[AuthErrorCode, str] = {
    AuthErrorCode.AUTH_013: "Credentials have been changed",
    AuthErrorCode.AUTH_014: "Session limit exceeded",
    AuthErrorCode.AUTH_015: "Unknown OAuth provider",
    AuthErrorCode.AUTH_016: "OAuth provider mismatch",
    AuthErrorCode.AUTH_017: "Password requirements not met",
    AuthErrorCode.AUTH_018: "Token audience invalid",
}

AUTH_ERROR_STATUS: dict[AuthErrorCode, int] = {
    AuthErrorCode.AUTH_013: 401,
    AuthErrorCode.AUTH_014: 401,
    AuthErrorCode.AUTH_015: 400,
    AuthErrorCode.AUTH_016: 400,
    AuthErrorCode.AUTH_017: 400,
    AuthErrorCode.AUTH_018: 401,
}


class InvalidRoleError(ValueError):
    """Raised at decoration time for invalid role parameters.

    This error indicates a programming mistake (typo in role name)
    and should cause the application to fail to start.
    """

    def __init__(self, role: str, valid_roles: frozenset[str]) -> None:
        self.role = role
        self.valid_roles = valid_roles
        super().__init__(f"Invalid role '{role}'. Valid roles: {sorted(valid_roles)}")


class MissingRolesClaimError(Exception):
    """Raised when JWT is missing the roles claim.

    Indicates a token structure issue - the user authenticated but
    the token doesn't contain role information.
    """

    pass


class InsufficientRoleError(Exception):
    """Raised when user lacks the required role.

    This is an internal exception caught by the decorator and
    converted to a generic 403 response to prevent enumeration.
    """

    pass


class AuthError(Exception):
    """Auth error with numeric code for client handling (Feature 1190).

    Use raise_auth_error() helper function to raise these errors.
    """

    def __init__(self, code: AuthErrorCode) -> None:
        self.code = code
        self.message = AUTH_ERROR_MESSAGES[code]
        self.status_code = AUTH_ERROR_STATUS[code]
        super().__init__(self.message)


def raise_auth_error(code: AuthErrorCode) -> None:
    """Raise an AuthError with the specified code.

    Args:
        code: The AuthErrorCode to raise.

    Raises:
        AuthError: Always raises with the specified code.

    Example:
        from src.lambdas.shared.errors.auth_errors import (
            AuthErrorCode,
            raise_auth_error,
        )

        # When password was changed
        raise_auth_error(AuthErrorCode.AUTH_013)

        # When session limit exceeded
        raise_auth_error(AuthErrorCode.AUTH_014)
    """
    raise AuthError(code)


def auth_error_response(code: AuthErrorCode) -> dict:
    """Create a JSON response dict for an auth error.

    Args:
        code: The AuthErrorCode for the response.

    Returns:
        Dict suitable for JSONResponse with error details.

    Example:
        return JSONResponse(
            status_code=AUTH_ERROR_STATUS[AuthErrorCode.AUTH_013],
            content=auth_error_response(AuthErrorCode.AUTH_013),
        )
    """
    return {
        "error": {
            "code": code.value,
            "message": AUTH_ERROR_MESSAGES[code],
        }
    }

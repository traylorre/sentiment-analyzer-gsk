"""CSRF middleware for FastAPI endpoints.

This module provides a FastAPI dependency function that validates
CSRF tokens on state-changing requests. It implements the double-submit
cookie pattern where the frontend must send the token in both a cookie
and the X-CSRF-Token header.

Usage:
    from shared.middleware.csrf_middleware import require_csrf

    # Apply to router for all endpoints
    router = APIRouter(dependencies=[Depends(require_csrf)])

    # Or apply to individual endpoints
    @router.post("/endpoint", dependencies=[Depends(require_csrf)])
    async def endpoint():
        ...

Feature: 1158-csrf-double-submit
"""

from fastapi import HTTPException, Request

from src.lambdas.shared.auth.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    is_csrf_exempt,
    validate_csrf_token,
)

# Error code for CSRF validation failure
CSRF_ERROR_CODE = "AUTH_019"


async def require_csrf(request: Request) -> None:
    """FastAPI dependency that validates CSRF tokens.

    Extracts the CSRF token from both the cookie and the X-CSRF-Token
    header, and validates that they match. Raises HTTPException with
    403 status if validation fails.

    Safe methods (GET, HEAD, OPTIONS, TRACE) bypass validation.
    Certain paths are exempt (refresh endpoint, OAuth callbacks).

    Args:
        request: The incoming FastAPI request

    Raises:
        HTTPException: 403 Forbidden if CSRF validation fails
    """
    # Check if request is exempt from CSRF validation
    method = request.method
    path = request.url.path

    if is_csrf_exempt(method, path):
        return

    # Extract token from cookie
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

    # Extract token from header
    header_token = request.headers.get(CSRF_HEADER_NAME)

    # Validate tokens match
    if not validate_csrf_token(cookie_token, header_token):
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": CSRF_ERROR_CODE,
                "message": "CSRF validation failed",
            },
        )

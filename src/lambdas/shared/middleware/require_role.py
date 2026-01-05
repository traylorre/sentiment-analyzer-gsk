"""Role-based access control decorator for FastAPI endpoints (Feature 1130).

This module provides the @require_role decorator for protecting endpoints
based on user roles from JWT claims.

Usage:
    from src.lambdas.shared.middleware import require_role

    @router.post("/admin/sessions/revoke")
    @require_role("operator")
    async def revoke_sessions(request: Request):
        ...

Security:
    - Generic error messages prevent role enumeration attacks
    - Role validation at decoration time catches typos early
    - Integrates with existing auth context extraction
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, Request

from src.lambdas.shared.auth.constants import VALID_ROLES
from src.lambdas.shared.errors.auth_errors import InvalidRoleError
from src.lambdas.shared.middleware.auth_middleware import extract_auth_context_typed

logger = logging.getLogger(__name__)

# Type variable for preserving function signatures
F = TypeVar("F", bound=Callable[..., Any])


def require_role(required_role: str) -> Callable[[F], F]:
    """Decorator factory for role-based access control.

    Creates a decorator that validates the user has the specified role
    before allowing access to the endpoint.

    Args:
        required_role: The role required to access the endpoint.
            Must be one of: 'anonymous', 'free', 'paid', 'operator'

    Returns:
        A decorator function that wraps the endpoint handler.

    Raises:
        InvalidRoleError: At decoration time if role is not valid.
            This causes app startup to fail, catching typos early.

    Example:
        @router.post("/admin/endpoint")
        @require_role("operator")
        async def admin_endpoint(request: Request):
            ...
    """
    # Validate role at decoration time (startup)
    if required_role not in VALID_ROLES:
        raise InvalidRoleError(required_role, VALID_ROLES)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract request from args or kwargs
            request: Request | None = None

            # Check kwargs first
            if "request" in kwargs:
                request = kwargs["request"]
            else:
                # Check positional args for Request object
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                # This shouldn't happen in normal FastAPI usage
                logger.error("require_role: No Request object found in handler args")
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error",
                )

            # Build event dict from request for auth context extraction
            headers_dict = dict(request.headers)
            event = {"headers": headers_dict}

            # Extract auth context
            auth_context = extract_auth_context_typed(event)

            # Check authentication
            if auth_context.user_id is None:
                logger.debug(
                    f"require_role({required_role}): No user_id, returning 401"
                )
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required",
                )

            # Check roles claim exists
            if auth_context.roles is None:
                logger.debug(
                    f"require_role({required_role}): No roles claim, returning 401"
                )
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token structure",
                )

            # Check required role
            if required_role not in auth_context.roles:
                # SECURITY: Generic message prevents role enumeration
                logger.debug(
                    f"require_role({required_role}): User {auth_context.user_id[:8]}... "
                    f"has roles {auth_context.roles}, returning 403"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Access denied",
                )

            # Role check passed
            logger.debug(
                f"require_role({required_role}): User {auth_context.user_id[:8]}... "
                f"authorized with roles {auth_context.roles}"
            )
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator

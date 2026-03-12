"""Role-based access control middleware for Lambda handlers (Feature 1130).

Provides a Powertools middleware factory for protecting endpoints based on
user roles from JWT claims.

Usage (Powertools middleware):
    from src.lambdas.shared.middleware.require_role import require_role_middleware

    @router.post("/api/v2/admin/sessions/revoke",
                 middlewares=[require_role_middleware("operator")])
    def revoke_sessions():
        ...

Security:
    - Generic error messages prevent role enumeration attacks
    - Role validation at factory time catches typos early
    - Integrates with existing auth context extraction
"""

from __future__ import annotations

import logging

from src.lambdas.shared.auth.enums import VALID_ROLES
from src.lambdas.shared.errors.auth_errors import InvalidRoleError
from src.lambdas.shared.middleware.auth_middleware import extract_auth_context_typed
from src.lambdas.shared.utils.response_builder import error_response

logger = logging.getLogger(__name__)


def require_role_middleware(required_role: str):
    """Powertools middleware factory for role-based access control.

    Creates a middleware function that validates the user has the specified
    role before allowing access to the endpoint.

    Args:
        required_role: The role required to access the endpoint.
            Must be one of: 'anonymous', 'free', 'paid', 'operator'

    Returns:
        A Powertools middleware function (app, next_middleware) -> response.

    Raises:
        InvalidRoleError: At factory time if role is not valid.
            This causes app startup to fail, catching typos early.
    """
    # Validate role at factory time (startup)
    if required_role not in VALID_ROLES:
        raise InvalidRoleError(required_role, VALID_ROLES)

    def middleware(app, next_middleware):
        event = app.current_event.raw_event

        # Extract auth context from raw event
        auth_context = extract_auth_context_typed(event)

        # Check authentication
        if auth_context.user_id is None:
            logger.debug(f"require_role({required_role}): No user_id, returning 401")
            return error_response(401, "Authentication required")

        # Check roles claim exists
        if auth_context.roles is None:
            logger.debug(
                f"require_role({required_role}): No roles claim, returning 401"
            )
            return error_response(401, "Invalid token structure")

        # Check required role
        if required_role not in auth_context.roles:
            # SECURITY: Generic message prevents role enumeration
            logger.debug(
                f"require_role({required_role}): User {auth_context.user_id[:8]}... "
                f"has roles {auth_context.roles}, returning 403"
            )
            return error_response(403, "Access denied")

        # Role check passed
        logger.debug(
            f"require_role({required_role}): User {auth_context.user_id[:8]}... "
            f"authorized with roles {auth_context.roles}"
        )
        return next_middleware(app)

    return middleware

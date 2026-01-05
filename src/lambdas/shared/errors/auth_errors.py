"""Role-based access control error types (Feature 1130).

These exceptions are used internally by the require_role decorator.
They are caught and converted to HTTPExceptions with generic messages
to prevent role enumeration attacks.
"""

from __future__ import annotations


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

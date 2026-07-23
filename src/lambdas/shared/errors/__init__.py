"""Shared error types for Lambda handlers.

Feature 014 session-specific error types and Feature 1130 RBAC errors.

Note: the legacy errors_module.py convenience helpers (error_response, ErrorCode,
not_found_error, etc.) were removed in the repo cleanup campaign - they had zero
production callers. Live error responses are built by
src/lambdas/shared/utils/response_builder.py.
"""

# Feature 014: Session-specific error types
from src.lambdas.shared.errors.auth_errors import (
    InsufficientRoleError,
    InvalidRoleError,
    MissingRolesClaimError,
)
from src.lambdas.shared.errors.session_errors import (
    EmailAlreadyExistsError,
    InvalidMergeTargetError,
    MergeConflictError,
    SessionError,
    SessionExpiredError,
    SessionRevokedException,
    TokenAlreadyUsedError,
    TokenExpiredError,
)

__all__ = [
    # Feature 014 session errors
    "EmailAlreadyExistsError",
    "InvalidMergeTargetError",
    "MergeConflictError",
    "SessionError",
    "SessionExpiredError",
    "SessionRevokedException",
    "TokenAlreadyUsedError",
    "TokenExpiredError",
    # Feature 1130: RBAC errors
    "InsufficientRoleError",
    "InvalidRoleError",
    "MissingRolesClaimError",
]

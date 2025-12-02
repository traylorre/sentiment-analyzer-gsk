"""Shared error types for Lambda handlers.

This module re-exports error utilities from the original errors.py module
while adding Feature 014 session-specific error types.
"""

# Re-export original error utilities (backward compatibility)
# Feature 014: Session-specific error types
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
from src.lambdas.shared.errors_module import (
    ErrorCode,
    database_error,
    error_response,
    internal_error,
    model_error,
    not_found_error,
    rate_limit_error,
    secret_error,
    unauthorized_error,
    validation_error,
)

__all__ = [
    # Original error utilities
    "ErrorCode",
    "database_error",
    "error_response",
    "internal_error",
    "model_error",
    "not_found_error",
    "rate_limit_error",
    "secret_error",
    "unauthorized_error",
    "validation_error",
    # Feature 014 session errors
    "EmailAlreadyExistsError",
    "InvalidMergeTargetError",
    "MergeConflictError",
    "SessionError",
    "SessionExpiredError",
    "SessionRevokedException",
    "TokenAlreadyUsedError",
    "TokenExpiredError",
]

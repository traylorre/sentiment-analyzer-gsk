"""Authentication utilities for Feature 006."""

from src.lambdas.shared.auth.cognito import (
    CognitoConfig,
    CognitoTokens,
    decode_id_token,
    exchange_code_for_tokens,
    refresh_tokens,
    revoke_token,
    validate_access_token,
)
from src.lambdas.shared.auth.csrf import (
    CSRF_COOKIE_MAX_AGE,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    generate_csrf_token,
    is_csrf_exempt,
    validate_csrf_token,
)
from src.lambdas.shared.auth.enums import (
    VALID_ROLES,
    Role,
)
from src.lambdas.shared.auth.merge import (
    MergeResult,
    merge_anonymous_data,
)
from src.lambdas.shared.auth.roles import (
    get_roles_for_user,
)

__all__ = [
    "CognitoConfig",
    "CognitoTokens",
    "decode_id_token",
    "exchange_code_for_tokens",
    "refresh_tokens",
    "revoke_token",
    "validate_access_token",
    "MergeResult",
    "merge_anonymous_data",
    # Feature 1130: RBAC constants
    "Role",
    "VALID_ROLES",
    # Feature 1150: Role assignment
    "get_roles_for_user",
    # Feature 1158: CSRF protection
    "CSRF_COOKIE_NAME",
    "CSRF_HEADER_NAME",
    "CSRF_COOKIE_MAX_AGE",
    "generate_csrf_token",
    "validate_csrf_token",
    "is_csrf_exempt",
]

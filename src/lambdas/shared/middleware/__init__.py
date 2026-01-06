"""Shared middleware for Lambda handlers."""

from src.lambdas.shared.middleware.auth_middleware import (
    AuthContext,
    AuthType,
    extract_auth_context,
    extract_auth_context_typed,
    extract_user_id,
    require_auth,
)
from src.lambdas.shared.middleware.csrf_middleware import (
    require_csrf,
)
from src.lambdas.shared.middleware.hcaptcha import (
    CaptchaRequired,
    verify_captcha,
)
from src.lambdas.shared.middleware.rate_limit import (
    RateLimitExceeded,
    check_rate_limit,
    get_client_ip,
)
from src.lambdas.shared.middleware.require_role import (
    require_role,
)
from src.lambdas.shared.middleware.security_headers import (
    add_security_headers,
    get_cors_headers,
)

__all__ = [
    # Auth middleware
    "AuthContext",
    "AuthType",
    "extract_auth_context",
    "extract_auth_context_typed",
    "extract_user_id",
    "require_auth",
    # Feature 1130: Role-based access control
    "require_role",
    # hCaptcha
    "CaptchaRequired",
    "verify_captcha",
    # Rate limiting
    "RateLimitExceeded",
    "check_rate_limit",
    "get_client_ip",
    # Security headers
    "add_security_headers",
    "get_cors_headers",
    # Feature 1158: CSRF protection
    "require_csrf",
]

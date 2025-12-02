"""Shared middleware for Lambda handlers."""

from src.lambdas.shared.middleware.auth_middleware import (
    extract_auth_context,
    extract_user_id,
    require_auth,
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
from src.lambdas.shared.middleware.security_headers import (
    add_security_headers,
    get_cors_headers,
)

__all__ = [
    "CaptchaRequired",
    "RateLimitExceeded",
    "add_security_headers",
    "check_rate_limit",
    "extract_auth_context",
    "extract_user_id",
    "get_client_ip",
    "get_cors_headers",
    "require_auth",
    "verify_captcha",
]

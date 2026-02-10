"""CSRF middleware for Lambda handlers (Feature 1158-csrf-double-submit).

Validates CSRF tokens on state-changing requests using the double-submit
cookie pattern. The frontend reads the token from a non-httpOnly cookie
and sends it back in the X-CSRF-Token header.

Usage (Powertools middleware):
    from src.lambdas.shared.middleware.csrf_middleware import require_csrf_middleware

    @router.post("/endpoint", middlewares=[require_csrf_middleware])
    def endpoint():
        ...
"""

from src.lambdas.shared.auth.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    is_csrf_exempt,
    validate_csrf_token,
)
from src.lambdas.shared.utils.cookie_helpers import parse_cookies
from src.lambdas.shared.utils.event_helpers import get_header
from src.lambdas.shared.utils.response_builder import error_response

# Error code for CSRF validation failure
CSRF_ERROR_CODE = "AUTH_019"


def require_csrf_middleware(app, next_middleware):
    """Powertools middleware that validates CSRF tokens.

    Extracts the CSRF token from both the cookie and the X-CSRF-Token
    header, and validates that they match. Returns 403 proxy response
    on failure.

    Safe methods (GET, HEAD, OPTIONS, TRACE) bypass validation.
    Certain paths are exempt (refresh endpoint, OAuth callbacks).

    Args:
        app: Powertools resolver instance (has current_event).
        next_middleware: Next middleware or handler in the chain.

    Returns:
        Handler response on success, 403 error response on CSRF failure.
    """
    event = app.current_event.raw_event

    # Check if request is exempt from CSRF validation
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    if is_csrf_exempt(method, path):
        return next_middleware(app)

    # Extract token from cookie
    cookies = parse_cookies(event)
    cookie_token = cookies.get(CSRF_COOKIE_NAME)

    # Extract token from header
    header_token = get_header(event, CSRF_HEADER_NAME)

    # Validate tokens match
    if not validate_csrf_token(cookie_token, header_token):
        return error_response(
            403,
            {
                "error_code": CSRF_ERROR_CODE,
                "message": "CSRF validation failed",
            },
        )

    return next_middleware(app)

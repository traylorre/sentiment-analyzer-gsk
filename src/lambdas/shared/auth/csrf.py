"""CSRF double-submit cookie pattern implementation.

This module provides CSRF token generation and validation using the
double-submit cookie pattern. The frontend reads the token from a
non-httpOnly cookie and sends it back in the X-CSRF-Token header.
The backend validates that both values match.

Security considerations:
- Tokens use cryptographically secure random generation (secrets module)
- Validation uses constant-time comparison to prevent timing attacks
- Cookie is not httpOnly so JavaScript can read it
- Cookie is Secure to prevent interception over HTTP

Feature: 1158-csrf-double-submit
"""

import hmac
import secrets

# Cookie and header names
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Token configuration
CSRF_TOKEN_BYTES = 32  # 256 bits of entropy
CSRF_COOKIE_MAX_AGE = 86400  # 24 hours, matches session lifetime

# Safe HTTP methods that don't require CSRF validation
CSRF_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Paths exempt from CSRF validation
# Note: Bearer-token-authenticated endpoints are exempt because:
# - Bearer tokens are NOT automatically attached by browsers (unlike cookies)
# - Attackers cannot forge requests without stealing the token via XSS
# - CSRF only protects cookie-based auth where browsers auto-attach credentials
CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/v2/auth/refresh",  # Cookie-only auth, no JS access needed
        "/api/v2/auth/anonymous",  # Bootstrap endpoint: no session exists to protect
        "/api/v2/auth/magic-link",  # Magic link request (rate-limited separately)
        "/api/v2/auth/signout",  # Bearer token auth - not CSRF-vulnerable (Feature 1161)
        "/api/v2/auth/session/refresh",  # Bearer token auth - not CSRF-vulnerable (Feature 1161)
    }
)

# Path prefixes exempt from CSRF validation
CSRF_EXEMPT_PATH_PREFIXES = (
    "/api/v2/auth/oauth/callback",  # OAuth state provides CSRF protection
)


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token.

    Uses secrets.token_urlsafe() which generates URL-safe base64-encoded
    random bytes from the operating system's CSPRNG.

    Returns:
        43-character URL-safe string (32 bytes = 256 bits of entropy)
    """
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def validate_csrf_token(cookie_value: str | None, header_value: str | None) -> bool:
    """Validate that CSRF cookie and header values match.

    Uses constant-time comparison via hmac.compare_digest to prevent
    timing attacks that could leak token information.

    Args:
        cookie_value: The CSRF token from the cookie
        header_value: The CSRF token from the X-CSRF-Token header

    Returns:
        True if both values are present and match, False otherwise
    """
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)


def is_csrf_exempt(method: str, path: str) -> bool:
    """Check if a request is exempt from CSRF validation.

    Safe methods (GET, HEAD, OPTIONS, TRACE) are always exempt.
    Certain paths are exempt due to alternative CSRF protections.

    Args:
        method: HTTP method (uppercase)
        path: Request path

    Returns:
        True if request is exempt from CSRF validation
    """
    # Safe methods don't modify state
    if method.upper() in CSRF_SAFE_METHODS:
        return True

    # Exact path matches
    if path in CSRF_EXEMPT_PATHS:
        return True

    # Path prefix matches (for parameterized paths like OAuth callbacks)
    for prefix in CSRF_EXEMPT_PATH_PREFIXES:
        if path.startswith(prefix):
            return True

    return False

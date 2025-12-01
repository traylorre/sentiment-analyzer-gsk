"""Security headers middleware for Feature 006.

Implements T165: Security headers for all Lambda responses.

For On-Call Engineers:
    All responses should include security headers to prevent common attacks.
    These headers are added automatically by the add_security_headers function.

Security Notes:
    - HSTS: Forces HTTPS connections
    - CSP: Prevents XSS attacks
    - X-Content-Type-Options: Prevents MIME sniffing
    - X-Frame-Options: Prevents clickjacking
    - Referrer-Policy: Controls referrer information

CORS Architecture (as of 2024-12):
    CORS is handled by Lambda Function URL configuration in Terraform, NOT by this
    middleware. This prevents duplicate Access-Control-Allow-Origin headers which
    cause browser errors. The Lambda URL CORS config handles:
    - Access-Control-Allow-Origin (from cors_allowed_origins in tfvars)
    - Access-Control-Allow-Methods
    - Access-Control-Allow-Headers
    - Access-Control-Expose-Headers (rate-limit headers)
    - Access-Control-Max-Age
    - Preflight (OPTIONS) requests are handled automatically by AWS
"""

import os
from typing import Any

# Environment
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://sentiment-analyzer.com")

# Security headers configuration
SECURITY_HEADERS = {
    # HTTP Strict Transport Security - force HTTPS
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    # Prevent MIME type sniffing
    "X-Content-Type-Options": "nosniff",
    # Clickjacking protection
    "X-Frame-Options": "DENY",
    # XSS protection (legacy, but still useful for older browsers)
    "X-XSS-Protection": "1; mode=block",
    # Control referrer information
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Permissions policy (formerly Feature-Policy)
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

# Content Security Policy for API responses
# More restrictive since API should only return JSON
API_CSP = "default-src 'none'; frame-ancestors 'none'"

# Content Security Policy for HTML responses (if any)
HTML_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://hcaptcha.com https://*.hcaptcha.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' https://hcaptcha.com https://*.hcaptcha.com; "
    "frame-src https://hcaptcha.com https://*.hcaptcha.com; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'"
)


def get_cors_headers(
    origin: str | None = None,
    allow_credentials: bool = True,
) -> dict[str, str]:
    """Get CORS headers for response.

    DEPRECATED: CORS is now handled by Lambda Function URL configuration.
    This function is kept for backwards compatibility but returns an empty dict.
    See module docstring for CORS architecture details.

    Args:
        origin: Request origin header (ignored)
        allow_credentials: Whether to allow credentials (ignored)

    Returns:
        Empty dict - CORS headers are added by Lambda Function URL
    """
    # CORS is handled by Lambda Function URL - don't add duplicate headers
    return {}


def add_security_headers(
    response: dict[str, Any],
    is_html: bool = False,
    origin: str | None = None,
) -> dict[str, Any]:
    """Add security headers to Lambda response.

    Args:
        response: Lambda response dict
        is_html: Whether response is HTML (affects CSP)
        origin: Request origin for CORS

    Returns:
        Response with security headers added
    """
    # Ensure headers dict exists
    if "headers" not in response:
        response["headers"] = {}

    headers = response["headers"]

    # Add security headers
    for header, value in SECURITY_HEADERS.items():
        if header not in headers:
            headers[header] = value

    # Add Content-Security-Policy
    if "Content-Security-Policy" not in headers:
        headers["Content-Security-Policy"] = HTML_CSP if is_html else API_CSP

    # NOTE: CORS headers are NOT added here - they are handled by Lambda Function URL
    # configuration in Terraform. Adding them here would cause duplicate headers.

    # Add Cache-Control for API responses (no caching by default)
    if "Cache-Control" not in headers:
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"

    return response


def get_preflight_response(origin: str | None = None) -> dict[str, Any]:
    """Get response for CORS preflight (OPTIONS) request.

    NOTE: When using Lambda Function URL with CORS configured, AWS handles
    OPTIONS preflight requests automatically before invoking the Lambda.
    This function is kept for backwards compatibility but Lambda URL CORS
    should handle preflight in production.

    Args:
        origin: Request origin header (ignored - CORS handled by Lambda URL)

    Returns:
        Lambda response for OPTIONS request with security headers only
    """
    security_headers = dict(SECURITY_HEADERS)

    return {
        "statusCode": 204,
        "headers": {
            **security_headers,
            "Content-Length": "0",
        },
        "body": "",
    }


def sanitize_error_response(
    error_message: str,
    include_details: bool = False,
) -> str:
    """Sanitize error message for response.

    Prevents information leakage in error responses.

    Args:
        error_message: Raw error message
        include_details: Whether to include details (only in dev)

    Returns:
        Sanitized error message
    """
    # In production, don't expose internal error details
    if ENVIRONMENT in ("prod", "preprod") and not include_details:
        # Map common errors to generic messages
        error_mappings = {
            "dynamodb": "Database error",
            "connection": "Service unavailable",
            "timeout": "Request timeout",
            "validation": "Invalid request",
            "permission": "Access denied",
            "not found": "Resource not found",
        }

        error_lower = error_message.lower()
        for key, generic_message in error_mappings.items():
            if key in error_lower:
                return generic_message

        return "An error occurred"

    return error_message

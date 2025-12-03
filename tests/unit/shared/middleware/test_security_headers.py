"""Unit tests for security headers middleware (T165).

CORS Architecture Note:
    CORS is handled by Lambda Function URL configuration in Terraform, NOT by the
    middleware. The get_cors_headers function returns an empty dict (deprecated).
    Tests verify CORS headers are NOT added by the middleware to prevent duplicates.
"""

from unittest.mock import patch

from src.lambdas.shared.middleware.security_headers import (
    API_CSP,
    HTML_CSP,
    SECURITY_HEADERS,
    add_security_headers,
    get_cors_headers,
    get_preflight_response,
    sanitize_error_response,
)


class TestGetCorsHeaders:
    """Tests for get_cors_headers function (deprecated - CORS handled by Lambda URL)."""

    def test_returns_empty_dict(self):
        """Returns empty dict - CORS handled by Lambda Function URL."""
        headers = get_cors_headers()
        assert headers == {}

    def test_returns_empty_dict_with_origin(self):
        """Returns empty dict even with origin - CORS handled by Lambda Function URL."""
        headers = get_cors_headers(origin="http://localhost:3000")
        assert headers == {}

    def test_returns_empty_dict_with_credentials(self):
        """Returns empty dict regardless of credentials setting."""
        headers = get_cors_headers(allow_credentials=True)
        assert headers == {}
        headers = get_cors_headers(allow_credentials=False)
        assert headers == {}


class TestAddSecurityHeaders:
    """Tests for add_security_headers function."""

    def test_adds_all_security_headers(self):
        """Adds all standard security headers."""
        response = {"statusCode": 200, "body": "{}"}

        result = add_security_headers(response)

        for header in SECURITY_HEADERS:
            assert header in result["headers"]

    def test_preserves_existing_headers(self):
        """Preserves existing headers."""
        response = {
            "statusCode": 200,
            "headers": {"X-Custom": "value"},
            "body": "{}",
        }

        result = add_security_headers(response)

        assert result["headers"]["X-Custom"] == "value"

    def test_creates_headers_dict_if_missing(self):
        """Creates headers dict if missing."""
        response = {"statusCode": 200, "body": "{}"}

        result = add_security_headers(response)

        assert "headers" in result

    def test_does_not_overwrite_existing_security_headers(self):
        """Does not overwrite existing security headers."""
        response = {
            "statusCode": 200,
            "headers": {"X-Content-Type-Options": "custom-value"},
            "body": "{}",
        }

        result = add_security_headers(response)

        assert result["headers"]["X-Content-Type-Options"] == "custom-value"

    def test_uses_api_csp_by_default(self):
        """Uses API CSP by default."""
        response = {"statusCode": 200, "body": "{}"}

        result = add_security_headers(response)

        assert result["headers"]["Content-Security-Policy"] == API_CSP

    def test_uses_html_csp_for_html(self):
        """Uses HTML CSP for HTML responses."""
        response = {"statusCode": 200, "body": "<html></html>"}

        result = add_security_headers(response, is_html=True)

        assert result["headers"]["Content-Security-Policy"] == HTML_CSP

    def test_does_not_add_cors_headers(self):
        """Does NOT add CORS headers - handled by Lambda Function URL."""
        response = {"statusCode": 200, "body": "{}"}

        result = add_security_headers(response, origin="http://localhost:3000")

        # CORS headers should NOT be present - Lambda URL handles them
        assert "Access-Control-Allow-Origin" not in result["headers"]
        assert "Access-Control-Allow-Methods" not in result["headers"]
        assert "Access-Control-Allow-Headers" not in result["headers"]

    def test_adds_cache_control(self):
        """Adds Cache-Control header."""
        response = {"statusCode": 200, "body": "{}"}

        result = add_security_headers(response)

        assert "no-store" in result["headers"]["Cache-Control"]

    def test_hsts_header_present(self):
        """Has HSTS header."""
        response = {"statusCode": 200, "body": "{}"}

        result = add_security_headers(response)

        hsts = result["headers"]["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts


class TestGetPreflightResponse:
    """Tests for get_preflight_response function."""

    def test_returns_204_status(self):
        """Returns 204 No Content status."""
        response = get_preflight_response()
        assert response["statusCode"] == 204

    def test_does_not_have_cors_headers(self):
        """Does NOT have CORS headers - Lambda Function URL handles preflight."""
        response = get_preflight_response()
        # CORS headers are NOT added - Lambda URL handles OPTIONS preflight
        assert "Access-Control-Allow-Origin" not in response["headers"]
        assert "Access-Control-Allow-Methods" not in response["headers"]

    def test_has_security_headers(self):
        """Has security headers."""
        response = get_preflight_response()
        assert "Strict-Transport-Security" in response["headers"]
        assert "X-Content-Type-Options" in response["headers"]

    def test_empty_body(self):
        """Has empty body."""
        response = get_preflight_response()
        assert response["body"] == ""

    def test_content_length_zero(self):
        """Has Content-Length: 0."""
        response = get_preflight_response()
        assert response["headers"]["Content-Length"] == "0"


class TestSanitizeErrorResponse:
    """Tests for sanitize_error_response function."""

    @patch("src.lambdas.shared.middleware.security_headers.ENVIRONMENT", "dev")
    def test_shows_details_in_dev(self):
        """Shows full error details in dev."""
        message = sanitize_error_response("DynamoDB connection timeout")
        assert message == "DynamoDB connection timeout"

    @patch("src.lambdas.shared.middleware.security_headers.ENVIRONMENT", "prod")
    def test_hides_details_in_prod(self):
        """Hides error details in prod."""
        message = sanitize_error_response("DynamoDB connection failed: AccessDenied")
        assert message == "Database error"

    @patch("src.lambdas.shared.middleware.security_headers.ENVIRONMENT", "prod")
    def test_maps_connection_errors(self):
        """Maps connection errors to generic message."""
        message = sanitize_error_response("Connection refused")
        assert message == "Service unavailable"

    @patch("src.lambdas.shared.middleware.security_headers.ENVIRONMENT", "prod")
    def test_maps_timeout_errors(self):
        """Maps timeout errors to generic message."""
        message = sanitize_error_response("Request timeout after 30s")
        assert message == "Request timeout"

    @patch("src.lambdas.shared.middleware.security_headers.ENVIRONMENT", "prod")
    def test_maps_validation_errors(self):
        """Maps validation errors to generic message."""
        message = sanitize_error_response("Validation failed for field X")
        assert message == "Invalid request"

    @patch("src.lambdas.shared.middleware.security_headers.ENVIRONMENT", "prod")
    def test_maps_permission_errors(self):
        """Maps permission errors to generic message."""
        message = sanitize_error_response("Permission denied for resource")
        assert message == "Access denied"

    @patch("src.lambdas.shared.middleware.security_headers.ENVIRONMENT", "prod")
    def test_maps_not_found_errors(self):
        """Maps not found errors to generic message."""
        message = sanitize_error_response("Resource not found in table")
        assert message == "Resource not found"

    @patch("src.lambdas.shared.middleware.security_headers.ENVIRONMENT", "prod")
    def test_generic_fallback(self):
        """Uses generic fallback for unknown errors."""
        message = sanitize_error_response("Some internal error with secret details")
        assert message == "An error occurred"

    @patch("src.lambdas.shared.middleware.security_headers.ENVIRONMENT", "prod")
    def test_include_details_override(self):
        """Respects include_details override."""
        message = sanitize_error_response(
            "DynamoDB connection failed", include_details=True
        )
        assert message == "DynamoDB connection failed"


class TestSecurityHeadersConfig:
    """Tests for security headers configuration."""

    def test_hsts_has_max_age(self):
        """HSTS has max-age."""
        assert "max-age=" in SECURITY_HEADERS["Strict-Transport-Security"]

    def test_frame_options_deny(self):
        """X-Frame-Options is DENY."""
        assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"

    def test_content_type_nosniff(self):
        """X-Content-Type-Options is nosniff."""
        assert SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"

    def test_referrer_policy_set(self):
        """Referrer-Policy is set."""
        assert "strict-origin" in SECURITY_HEADERS["Referrer-Policy"]

    def test_permissions_policy_restrictive(self):
        """Permissions-Policy is restrictive."""
        policy = SECURITY_HEADERS["Permissions-Policy"]
        assert "geolocation=()" in policy
        assert "microphone=()" in policy
        assert "camera=()" in policy


class TestApiCsp:
    """Tests for API Content-Security-Policy."""

    def test_default_none(self):
        """Default-src is 'none' for API."""
        assert "default-src 'none'" in API_CSP

    def test_frame_ancestors_none(self):
        """Frame-ancestors is 'none'."""
        assert "frame-ancestors 'none'" in API_CSP


class TestHtmlCsp:
    """Tests for HTML Content-Security-Policy."""

    def test_allows_self(self):
        """Allows 'self' for default-src."""
        assert "default-src 'self'" in HTML_CSP

    def test_allows_hcaptcha(self):
        """Allows hCaptcha domains."""
        # Check hCaptcha domain is in CSP whitelist (not URL validation)
        # CSP domains must match exactly or be subdomains (with leading dot/wildcard)
        # This approach satisfies CodeQL py/incomplete-url-substring-sanitization
        csp_domains = HTML_CSP.split()
        hcaptcha_allowed = any(
            self._is_hcaptcha_domain(domain.rstrip(";")) for domain in csp_domains
        )
        assert hcaptcha_allowed, f"hcaptcha.com not found in CSP: {HTML_CSP}"

    def _is_hcaptcha_domain(self, domain: str) -> bool:
        """Check if domain is hcaptcha.com or a subdomain of it."""
        # Exact match or subdomain pattern (*.hcaptcha.com or .hcaptcha.com)
        return (
            domain == "hcaptcha.com"
            or domain == "*.hcaptcha.com"
            or domain.endswith(".hcaptcha.com")
        )

    def test_frame_ancestors_none(self):
        """Frame-ancestors is 'none' (prevent framing)."""
        assert "frame-ancestors 'none'" in HTML_CSP

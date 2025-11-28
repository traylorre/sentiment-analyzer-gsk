"""Unit tests for security headers middleware (T165)."""

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
    """Tests for get_cors_headers function."""

    def test_returns_cors_headers(self):
        """Returns standard CORS headers."""
        headers = get_cors_headers()

        assert "Access-Control-Allow-Origin" in headers
        assert "Access-Control-Allow-Methods" in headers
        assert "Access-Control-Allow-Headers" in headers
        assert "Access-Control-Max-Age" in headers

    def test_allows_credentials_by_default(self):
        """Allows credentials by default."""
        headers = get_cors_headers()
        assert headers["Access-Control-Allow-Credentials"] == "true"

    def test_no_credentials_when_disabled(self):
        """No credentials header when disabled."""
        headers = get_cors_headers(allow_credentials=False)
        assert "Access-Control-Allow-Credentials" not in headers

    @patch(
        "src.lambdas.shared.middleware.security_headers.DASHBOARD_URL",
        "https://myapp.com",
    )
    def test_uses_dashboard_url_for_unknown_origin(self):
        """Uses dashboard URL for unknown origin."""
        headers = get_cors_headers(origin="https://evil.com")
        assert headers["Access-Control-Allow-Origin"] == "https://myapp.com"

    @patch(
        "src.lambdas.shared.middleware.security_headers.DASHBOARD_URL",
        "https://myapp.com",
    )
    def test_allows_dashboard_url_origin(self):
        """Allows dashboard URL as origin."""
        headers = get_cors_headers(origin="https://myapp.com")
        assert headers["Access-Control-Allow-Origin"] == "https://myapp.com"

    def test_allows_localhost_development(self):
        """Allows localhost for development."""
        headers = get_cors_headers(origin="http://localhost:3000")
        assert headers["Access-Control-Allow-Origin"] == "http://localhost:3000"

    @patch("src.lambdas.shared.middleware.security_headers.ENVIRONMENT", "dev")
    def test_allows_any_localhost_in_dev(self):
        """Allows any localhost port in dev mode."""
        headers = get_cors_headers(origin="http://localhost:8080")
        assert headers["Access-Control-Allow-Origin"] == "http://localhost:8080"

    def test_exposes_rate_limit_headers(self):
        """Exposes rate limit headers."""
        headers = get_cors_headers()
        exposed = headers["Access-Control-Expose-Headers"]
        assert "X-RateLimit-Limit" in exposed
        assert "X-RateLimit-Remaining" in exposed
        assert "Retry-After" in exposed

    def test_allows_custom_headers(self):
        """Allows custom headers for auth tokens."""
        headers = get_cors_headers()
        allowed = headers["Access-Control-Allow-Headers"]
        assert "X-Session-Token" in allowed
        assert "X-Anonymous-Token" in allowed
        assert "X-Captcha-Token" in allowed


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

    def test_adds_cors_headers(self):
        """Adds CORS headers."""
        response = {"statusCode": 200, "body": "{}"}

        result = add_security_headers(response, origin="http://localhost:3000")

        assert "Access-Control-Allow-Origin" in result["headers"]

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

    def test_has_cors_headers(self):
        """Has CORS headers."""
        response = get_preflight_response()
        assert "Access-Control-Allow-Origin" in response["headers"]
        assert "Access-Control-Allow-Methods" in response["headers"]

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
        # Using explicit domain check to avoid CodeQL false positive
        csp_domains = HTML_CSP.split()
        assert any("hcaptcha.com" in domain for domain in csp_domains)

    def test_frame_ancestors_none(self):
        """Frame-ancestors is 'none' (prevent framing)."""
        assert "frame-ancestors 'none'" in HTML_CSP

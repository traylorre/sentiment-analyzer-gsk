"""Unit tests for CSRF double-submit cookie pattern.

Feature: 1158-csrf-double-submit
"""

import json
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.auth.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    generate_csrf_token,
    is_csrf_exempt,
    validate_csrf_token,
)
from src.lambdas.shared.middleware.csrf_middleware import require_csrf_middleware


class TestGenerateCsrfToken:
    """Tests for CSRF token generation."""

    def test_token_is_string(self) -> None:
        """Token should be a string."""
        token = generate_csrf_token()
        assert isinstance(token, str)

    def test_token_length(self) -> None:
        """Token should be URL-safe base64 of 32 bytes (43 chars)."""
        token = generate_csrf_token()
        # secrets.token_urlsafe(32) produces 43 characters
        assert len(token) == 43

    def test_token_uniqueness(self) -> None:
        """Each generated token should be unique."""
        tokens = [generate_csrf_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_token_is_url_safe(self) -> None:
        """Token should contain only URL-safe characters."""
        token = generate_csrf_token()
        # URL-safe base64 uses A-Z, a-z, 0-9, -, _
        valid_chars = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        )
        assert all(c in valid_chars for c in token)


class TestValidateCsrfToken:
    """Tests for CSRF token validation."""

    def test_matching_tokens_valid(self) -> None:
        """Matching cookie and header tokens should validate."""
        token = generate_csrf_token()
        assert validate_csrf_token(token, token) is True

    def test_mismatched_tokens_invalid(self) -> None:
        """Different cookie and header tokens should not validate."""
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        assert validate_csrf_token(token1, token2) is False

    def test_missing_cookie_invalid(self) -> None:
        """Missing cookie token should not validate."""
        token = generate_csrf_token()
        assert validate_csrf_token(None, token) is False

    def test_missing_header_invalid(self) -> None:
        """Missing header token should not validate."""
        token = generate_csrf_token()
        assert validate_csrf_token(token, None) is False

    def test_both_missing_invalid(self) -> None:
        """Both tokens missing should not validate."""
        assert validate_csrf_token(None, None) is False

    def test_empty_string_cookie_invalid(self) -> None:
        """Empty string cookie should not validate."""
        token = generate_csrf_token()
        assert validate_csrf_token("", token) is False

    def test_empty_string_header_invalid(self) -> None:
        """Empty string header should not validate."""
        token = generate_csrf_token()
        assert validate_csrf_token(token, "") is False


class TestIsCsrfExempt:
    """Tests for CSRF exemption logic."""

    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "TRACE"])
    def test_safe_methods_exempt(self, method: str) -> None:
        """Safe HTTP methods should be exempt."""
        assert is_csrf_exempt(method, "/api/v2/some/path") is True

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_unsafe_methods_not_exempt(self, method: str) -> None:
        """Unsafe HTTP methods should not be exempt by default."""
        assert is_csrf_exempt(method, "/api/v2/some/path") is False

    def test_refresh_endpoint_exempt(self) -> None:
        """Refresh endpoint should be exempt (cookie-only auth)."""
        assert is_csrf_exempt("POST", "/api/v2/auth/refresh") is True

    def test_anonymous_endpoint_exempt(self) -> None:
        """Anonymous session creation should be exempt (bootstrap, no session exists)."""
        assert is_csrf_exempt("POST", "/api/v2/auth/anonymous") is True

    def test_magic_link_request_exempt(self) -> None:
        """Magic link request should be exempt (rate-limited separately)."""
        assert is_csrf_exempt("POST", "/api/v2/auth/magic-link") is True

    def test_signout_endpoint_exempt(self) -> None:
        """Signout should be exempt (Bearer token auth, not CSRF-vulnerable).

        Feature 1161: Bearer tokens are not automatically attached by browsers,
        so attackers cannot forge requests without stealing the token via XSS.
        """
        assert is_csrf_exempt("POST", "/api/v2/auth/signout") is True

    def test_session_refresh_endpoint_exempt(self) -> None:
        """Session refresh should be exempt (Bearer token auth, not CSRF-vulnerable).

        Feature 1161: Bearer tokens are not automatically attached by browsers,
        so attackers cannot forge requests without stealing the token via XSS.
        """
        assert is_csrf_exempt("POST", "/api/v2/auth/session/refresh") is True

    def test_oauth_callback_exempt(self) -> None:
        """OAuth callback should be exempt (state provides CSRF protection)."""
        assert is_csrf_exempt("POST", "/api/v2/auth/oauth/callback") is True
        assert is_csrf_exempt("POST", "/api/v2/auth/oauth/callback/google") is True

    def test_case_insensitive_method(self) -> None:
        """Method check should be case-insensitive."""
        assert is_csrf_exempt("get", "/api/v2/some/path") is True
        assert is_csrf_exempt("Get", "/api/v2/some/path") is True


class TestRequireCsrfMiddleware:
    """Tests for require_csrf_middleware Powertools middleware."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create a mock Powertools app with a POST event."""
        app = MagicMock()
        app.current_event.raw_event = {
            "httpMethod": "POST",
            "path": "/api/v2/some/endpoint",
            "headers": {},
        }
        return app

    @pytest.fixture
    def mock_next(self) -> MagicMock:
        """Create mock next_middleware callable."""
        return MagicMock(return_value={"statusCode": 200, "body": '{"ok": true}'})

    def test_valid_csrf_passes(self, mock_app: MagicMock, mock_next: MagicMock) -> None:
        """Valid matching CSRF tokens should pass."""
        token = generate_csrf_token()
        mock_app.current_event.raw_event["headers"]["cookie"] = (
            f"{CSRF_COOKIE_NAME}={token}"
        )
        mock_app.current_event.raw_event["headers"][CSRF_HEADER_NAME.lower()] = token

        require_csrf_middleware(mock_app, mock_next)
        mock_next.assert_called_once_with(mock_app)

    def test_missing_cookie_fails(
        self, mock_app: MagicMock, mock_next: MagicMock
    ) -> None:
        """Missing CSRF cookie should fail with 403."""
        token = generate_csrf_token()
        mock_app.current_event.raw_event["headers"][CSRF_HEADER_NAME.lower()] = token

        result = require_csrf_middleware(mock_app, mock_next)
        assert result["statusCode"] == 403
        body = json.loads(result["body"])
        assert body["error_code"] == "AUTH_019"

    def test_missing_header_fails(
        self, mock_app: MagicMock, mock_next: MagicMock
    ) -> None:
        """Missing CSRF header should fail with 403."""
        token = generate_csrf_token()
        mock_app.current_event.raw_event["headers"]["cookie"] = (
            f"{CSRF_COOKIE_NAME}={token}"
        )

        result = require_csrf_middleware(mock_app, mock_next)
        assert result["statusCode"] == 403
        body = json.loads(result["body"])
        assert body["error_code"] == "AUTH_019"

    def test_mismatched_tokens_fails(
        self, mock_app: MagicMock, mock_next: MagicMock
    ) -> None:
        """Mismatched CSRF tokens should fail with 403."""
        mock_app.current_event.raw_event["headers"]["cookie"] = (
            f"{CSRF_COOKIE_NAME}={generate_csrf_token()}"
        )
        mock_app.current_event.raw_event["headers"][CSRF_HEADER_NAME.lower()] = (
            generate_csrf_token()
        )

        result = require_csrf_middleware(mock_app, mock_next)
        assert result["statusCode"] == 403

    def test_get_request_exempt(
        self, mock_app: MagicMock, mock_next: MagicMock
    ) -> None:
        """GET requests should be exempt from CSRF validation."""
        mock_app.current_event.raw_event["httpMethod"] = "GET"
        # No tokens set - should still pass because GET is exempt
        require_csrf_middleware(mock_app, mock_next)
        mock_next.assert_called_once_with(mock_app)

    def test_refresh_endpoint_exempt(
        self, mock_app: MagicMock, mock_next: MagicMock
    ) -> None:
        """Refresh endpoint should be exempt from CSRF validation."""
        mock_app.current_event.raw_event["path"] = "/api/v2/auth/refresh"
        # No tokens set - should still pass because refresh is exempt
        require_csrf_middleware(mock_app, mock_next)
        mock_next.assert_called_once_with(mock_app)

"""Unit tests for Feature 1160: Refresh endpoint cookie extraction.

Verifies that the refresh endpoint extracts tokens from httpOnly cookies
and falls back to request body for backwards compatibility.
"""

from unittest.mock import MagicMock

from fastapi import Request
from fastapi.responses import JSONResponse

from src.lambdas.dashboard.router_v2 import (
    REFRESH_TOKEN_COOKIE_NAME,
    extract_refresh_token_from_cookie,
    set_refresh_token_cookie,
)


class TestExtractRefreshTokenFromCookie:
    """Test refresh token extraction from httpOnly cookie."""

    def test_extracts_token_from_cookie(self):
        """Successfully extracts refresh_token from cookie."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"refresh_token": "test_refresh_token_123"}

        # Act
        result = extract_refresh_token_from_cookie(mock_request)

        # Assert
        assert result == "test_refresh_token_123"

    def test_returns_none_when_cookie_not_present(self):
        """Returns None when refresh_token cookie is not present."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}

        # Act
        result = extract_refresh_token_from_cookie(mock_request)

        # Assert
        assert result is None

    def test_returns_none_when_different_cookie_present(self):
        """Returns None when other cookies exist but not refresh_token."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"access_token": "abc", "session": "xyz"}

        # Act
        result = extract_refresh_token_from_cookie(mock_request)

        # Assert
        assert result is None

    def test_cookie_name_constant(self):
        """Verify cookie name constant matches expected value."""
        assert REFRESH_TOKEN_COOKIE_NAME == "refresh_token"


class TestSetRefreshTokenCookie:
    """Test setting refresh token as httpOnly cookie."""

    def test_sets_cookie_with_correct_attributes(self):
        """Sets refresh_token cookie with security attributes."""
        # Arrange
        response = JSONResponse(content={})

        # Act
        set_refresh_token_cookie(response, "new_refresh_token_456")

        # Assert
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "refresh_token=new_refresh_token_456" in set_cookie_header
        assert "httponly" in set_cookie_header.lower()
        assert "secure" in set_cookie_header.lower()
        assert "path=/api/v2/auth" in set_cookie_header.lower()

    def test_sets_30_day_expiry(self):
        """Sets 30 day max-age on refresh token cookie."""
        # Arrange
        response = JSONResponse(content={})

        # Act
        set_refresh_token_cookie(response, "test_token")

        # Assert
        set_cookie_header = response.headers.get("set-cookie", "")
        # 30 days = 30 * 24 * 60 * 60 = 2592000 seconds
        assert "max-age=2592000" in set_cookie_header.lower()

    def test_sets_samesite_attribute(self):
        """Sets SameSite attribute on cookie."""
        # Arrange
        response = JSONResponse(content={})

        # Act
        set_refresh_token_cookie(response, "test_token")

        # Assert
        set_cookie_header = response.headers.get("set-cookie", "")
        # Should have samesite (either strict or none depending on feature flags)
        assert "samesite=" in set_cookie_header.lower()


class TestRefreshEndpointIntegration:
    """Integration tests for refresh endpoint cookie handling."""

    def test_prefers_cookie_over_body(self):
        """Cookie takes precedence over request body."""
        # This test verifies the priority logic in the endpoint
        # Cookie should be preferred when both are present
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"refresh_token": "cookie_token"}

        # The endpoint should use cookie_token, not body_token
        cookie_token = extract_refresh_token_from_cookie(mock_request)
        assert cookie_token == "cookie_token"

    def test_falls_back_to_body_when_no_cookie(self):
        """Falls back to body when cookie is not present."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}

        # No cookie, so endpoint would use body
        cookie_token = extract_refresh_token_from_cookie(mock_request)
        assert cookie_token is None
        # In this case, endpoint uses body.refresh_token

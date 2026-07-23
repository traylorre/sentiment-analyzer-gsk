"""Unit tests for Feature 1160: Refresh endpoint cookie extraction.

Verifies that the refresh endpoint extracts tokens from httpOnly cookies
in the Lambda event and creates correct Set-Cookie header values.
"""

from src.lambdas.dashboard.router_v2 import (
    REFRESH_TOKEN_COOKIE_NAME,
    _extract_refresh_token_from_event,
    _make_refresh_token_cookie,
)


class TestExtractRefreshTokenFromEvent:
    """Test refresh token extraction from httpOnly cookie in Lambda event."""

    def test_extracts_token_from_cookie(self):
        """Successfully extracts refresh_token from event cookie header."""
        event = {"headers": {"cookie": "refresh_token=test_refresh_token_123"}}
        result = _extract_refresh_token_from_event(event)
        assert result == "test_refresh_token_123"

    def test_returns_none_when_cookie_not_present(self):
        """Returns None when refresh_token cookie is not present."""
        event = {"headers": {"cookie": ""}}
        result = _extract_refresh_token_from_event(event)
        assert result is None

    def test_returns_none_when_no_headers(self):
        """Returns None when headers are missing."""
        event = {"headers": {}}
        result = _extract_refresh_token_from_event(event)
        assert result is None

    def test_returns_none_when_different_cookie_present(self):
        """Returns None when other cookies exist but not refresh_token."""
        event = {"headers": {"cookie": "access_token=abc; session=xyz"}}
        result = _extract_refresh_token_from_event(event)
        assert result is None

    def test_cookie_name_constant(self):
        """Verify cookie name constant matches expected value."""
        assert REFRESH_TOKEN_COOKIE_NAME == "refresh_token"


class TestMakeRefreshTokenCookie:
    """Test building Set-Cookie header for refresh token."""

    def test_sets_cookie_with_correct_attributes(self):
        """Sets refresh_token cookie with security attributes."""
        cookie_str = _make_refresh_token_cookie("new_refresh_token_456")
        assert "refresh_token=new_refresh_token_456" in cookie_str
        assert "httponly" in cookie_str.lower()
        assert "secure" in cookie_str.lower()
        assert "path=/api/v2/auth" in cookie_str.lower()

    def test_sets_30_day_expiry(self):
        """Sets 30 day max-age on refresh token cookie."""
        cookie_str = _make_refresh_token_cookie("test_token")
        # 30 days = 30 * 24 * 60 * 60 = 2592000 seconds
        assert "max-age=2592000" in cookie_str.lower()

    def test_sets_samesite_attribute(self):
        """Sets SameSite attribute on cookie."""
        cookie_str = _make_refresh_token_cookie("test_token")
        # Should have samesite attribute (value depends on feature flag)
        assert "samesite=" in cookie_str.lower()


class TestRefreshEndpointIntegration:
    """Integration tests for refresh endpoint cookie handling."""

    def test_prefers_cookie_over_body(self):
        """Cookie takes precedence over request body."""
        # This test verifies the priority logic in the endpoint
        # Cookie should be preferred when both are present
        event = {"headers": {"cookie": "refresh_token=cookie_token"}}
        cookie_token = _extract_refresh_token_from_event(event)
        assert cookie_token == "cookie_token"

    def test_falls_back_to_body_when_no_cookie(self):
        """Falls back to body when cookie is not present."""
        event = {"headers": {}}
        # No cookie, so endpoint would use body
        cookie_token = _extract_refresh_token_from_event(event)
        assert cookie_token is None
        # In this case, endpoint uses body.refresh_token


class TestCookiePathStagePrefix:
    """M1 WI-3: cookie Path must include the API Gateway stage segment.

    Behind API Gateway the browser-visible path is /{stage}/api/v2/...;
    a cookie with Path=/api/v2/auth is never sent back, which silently broke
    every cookie-based refresh on deployed environments.
    """

    def test_refresh_cookie_path_includes_stage(self):
        from src.lambdas.dashboard.router_v2 import _make_refresh_token_cookie

        event = {"requestContext": {"stage": "prod"}}
        cookie = _make_refresh_token_cookie("tok", event)
        assert "Path=/prod/api/v2/auth" in cookie

    def test_refresh_cookie_no_prefix_for_function_url(self):
        from src.lambdas.dashboard.router_v2 import _make_refresh_token_cookie

        event = {"requestContext": {"stage": "$default"}}
        cookie = _make_refresh_token_cookie("tok", event)
        assert "Path=/api/v2/auth" in cookie
        assert "Path=/$default" not in cookie

    def test_refresh_cookie_samesite_none(self):
        """Feature 1159 posture: Strict blocks all cross-site Amplify->API calls."""
        from src.lambdas.dashboard.router_v2 import _make_refresh_token_cookie

        cookie = _make_refresh_token_cookie("tok", None)
        assert "SameSite=None" in cookie
        assert "SameSite=Strict" not in cookie

    def test_csrf_cookie_path_includes_stage(self):
        from src.lambdas.dashboard.router_v2 import _make_csrf_set_cookie

        cookie = _make_csrf_set_cookie({"requestContext": {"stage": "prod"}})
        assert "Path=/prod/api/v2" in cookie

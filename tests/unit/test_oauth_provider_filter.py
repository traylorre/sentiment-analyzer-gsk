"""Unit tests for Feature 1245: OAuth provider filtering.

Tests the get_oauth_urls() function behavior when ENABLED_OAUTH_PROVIDERS
controls which providers are returned, and when the origin parameter
controls redirect_uri selection.
"""

import os
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from src.lambdas.dashboard.auth import OAuthURLsResponse, get_oauth_urls

# Common Cognito environment variables used across all tests
COGNITO_ENV = {
    "COGNITO_USER_POOL_ID": "us-east-1_TestPool",
    "COGNITO_CLIENT_ID": "test-client-id",
    "COGNITO_DOMAIN": "testapp",
    "AWS_REGION": "us-east-1",
    "COGNITO_REDIRECT_URI": "https://example.com/auth/callback",
    "FRONTEND_URL": "https://example.com",
}


class TestOAuthProviderFilter:
    """Tests for Feature 1245: ENABLED_OAUTH_PROVIDERS filtering."""

    def test_empty_enabled_providers_returns_empty(self):
        """ENABLED_OAUTH_PROVIDERS='' returns empty providers and empty state."""
        table = MagicMock()

        with patch.dict(os.environ, {**COGNITO_ENV, "ENABLED_OAUTH_PROVIDERS": ""}):
            response = get_oauth_urls(table)

        assert isinstance(response, OAuthURLsResponse)
        assert response.providers == {}
        assert response.state == ""
        # Table should not be called when no providers are enabled
        table.put_item.assert_not_called()

    def test_single_provider_google_only(self):
        """ENABLED_OAUTH_PROVIDERS='google' returns only google provider."""
        table = MagicMock()
        table.put_item.return_value = {}

        with patch.dict(
            os.environ, {**COGNITO_ENV, "ENABLED_OAUTH_PROVIDERS": "google"}
        ):
            response = get_oauth_urls(table)

        assert "google" in response.providers
        assert "github" not in response.providers
        assert response.providers["google"]["icon"] == "google"
        assert "authorize_url" in response.providers["google"]
        assert response.state != ""

    def test_multiple_providers_google_and_github(self):
        """ENABLED_OAUTH_PROVIDERS='google,github' returns both providers."""
        table = MagicMock()
        table.put_item.return_value = {}

        with patch.dict(
            os.environ, {**COGNITO_ENV, "ENABLED_OAUTH_PROVIDERS": "google,github"}
        ):
            response = get_oauth_urls(table)

        assert "google" in response.providers
        assert "github" in response.providers
        assert response.providers["google"]["icon"] == "google"
        assert response.providers["github"]["icon"] == "github"
        assert "authorize_url" in response.providers["google"]
        assert "authorize_url" in response.providers["github"]
        assert response.state != ""


class TestOAuthOriginRedirect:
    """Tests for Feature 1245: Origin-based redirect URI selection."""

    def test_localhost_origin_uses_localhost_redirect(self):
        """Origin http://localhost:3000 produces redirect_uri with localhost."""
        table = MagicMock()
        table.put_item.return_value = {}

        with patch.dict(
            os.environ, {**COGNITO_ENV, "ENABLED_OAUTH_PROVIDERS": "google"}
        ):
            response = get_oauth_urls(table, origin="http://localhost:3000")

        authorize_url = response.providers["google"]["authorize_url"]
        parsed = urlparse(authorize_url)
        params = parse_qs(parsed.query)

        assert "redirect_uri" in params
        assert "localhost:3000" in params["redirect_uri"][0]

    def test_evil_origin_does_not_leak_into_redirect(self):
        """Origin https://evil.com must NOT appear in redirect_uri (open redirect prevention)."""
        table = MagicMock()
        table.put_item.return_value = {}

        with patch.dict(
            os.environ, {**COGNITO_ENV, "ENABLED_OAUTH_PROVIDERS": "google"}
        ):
            response = get_oauth_urls(table, origin="https://evil.com")

        authorize_url = response.providers["google"]["authorize_url"]
        parsed = urlparse(authorize_url)
        params = parse_qs(parsed.query)

        assert "redirect_uri" in params
        redirect_uri = params["redirect_uri"][0]
        assert "evil.com" not in redirect_uri
        # Should fall back to FRONTEND_URL
        assert "example.com" in redirect_uri


class TestOAuthPKCENonRegression:
    """PKCE non-regression: all authorize URLs must include code_challenge params."""

    def test_authorize_urls_contain_pkce_params(self):
        """Every provider authorize_url must have code_challenge and code_challenge_method=S256."""
        table = MagicMock()
        table.put_item.return_value = {}

        with patch.dict(
            os.environ,
            {**COGNITO_ENV, "ENABLED_OAUTH_PROVIDERS": "google,github"},
        ):
            response = get_oauth_urls(table)

        for provider_name, provider_data in response.providers.items():
            authorize_url = provider_data["authorize_url"]
            parsed = urlparse(authorize_url)
            params = parse_qs(parsed.query)

            assert (
                "code_challenge" in params
            ), f"{provider_name} authorize_url missing code_challenge"
            assert (
                params["code_challenge"][0] != ""
            ), f"{provider_name} code_challenge is empty"
            assert (
                "code_challenge_method" in params
            ), f"{provider_name} authorize_url missing code_challenge_method"
            assert params["code_challenge_method"][0] == "S256", (
                f"{provider_name} code_challenge_method is "
                f"{params['code_challenge_method'][0]}, expected S256"
            )

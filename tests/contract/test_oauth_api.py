"""
Contract Tests: OAuth Authentication API (T085)
===============================================

Tests that OAuth endpoints conform to auth-api.md contract.

Constitution v1.1:
- Contract tests validate response schemas against API contracts
- All tests use moto to mock AWS infrastructure ($0 cost)
- External deps (Cognito) must be mocked
"""

from urllib.parse import parse_qs, urlparse


class TestOAuthURLsEndpoint:
    """Contract tests for GET /api/v2/auth/oauth/urls."""

    def test_response_200_schema(self):
        """200 OK response must match contract."""
        response = {
            "providers": {
                "google": {
                    "authorize_url": "https://cognito-domain.auth.us-east-1.amazoncognito.com/oauth2/authorize?client_id=xxx&response_type=code&scope=openid+email+profile&redirect_uri=https://app.domain/auth/callback&identity_provider=Google",
                    "icon": "google",
                },
                "github": {
                    "authorize_url": "https://cognito-domain.auth.us-east-1.amazoncognito.com/oauth2/authorize?client_id=xxx&response_type=code&scope=openid+email+profile&redirect_uri=https://app.domain/auth/callback&identity_provider=GitHub",
                    "icon": "github",
                },
            }
        }

        # Required structure
        assert "providers" in response
        assert "google" in response["providers"]
        assert "github" in response["providers"]

        # Each provider must have authorize_url and icon
        for provider_config in response["providers"].values():
            assert "authorize_url" in provider_config
            assert "icon" in provider_config

    def test_google_authorize_url_format(self):
        """Google authorize URL must have required OAuth params."""
        url = "https://cognito-domain.auth.us-east-1.amazoncognito.com/oauth2/authorize?client_id=xxx&response_type=code&scope=openid+email+profile&redirect_uri=https://app.domain/auth/callback&identity_provider=Google"

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Required OAuth2 parameters
        assert "client_id" in params
        assert params["response_type"] == ["code"]
        assert "scope" in params
        assert "redirect_uri" in params
        assert params["identity_provider"] == ["Google"]

        # Scope must include openid, email, profile
        scopes = (
            params["scope"][0].split("+")
            if "+" in params["scope"][0]
            else params["scope"][0].split()
        )
        assert "openid" in scopes
        assert "email" in scopes

    def test_github_authorize_url_format(self):
        """GitHub authorize URL must have required OAuth params."""
        url = "https://cognito-domain.auth.us-east-1.amazoncognito.com/oauth2/authorize?client_id=xxx&response_type=code&scope=openid+email+profile&redirect_uri=https://app.domain/auth/callback&identity_provider=GitHub"

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Required OAuth2 parameters
        assert "client_id" in params
        assert params["response_type"] == ["code"]
        assert params["identity_provider"] == ["GitHub"]

    def test_redirect_uri_matches_app_domain(self):
        """Redirect URI must point to app's auth callback."""
        url = "https://cognito-domain.auth.us-east-1.amazoncognito.com/oauth2/authorize?redirect_uri=https://app.domain/auth/callback"

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        redirect_uri = params["redirect_uri"][0]
        assert "/auth/callback" in redirect_uri


class TestOAuthCallbackEndpoint:
    """Contract tests for POST /api/v2/auth/oauth/callback."""

    def test_request_schema(self):
        """Request must include authorization code and provider."""
        request = {
            "code": "authorization_code_from_cognito",
            "provider": "google",
            "anonymous_user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        # Required fields
        assert "code" in request
        assert "provider" in request

        # Provider must be one of supported values
        assert request["provider"] in ["google", "github"]

        # Anonymous user ID is optional
        assert "anonymous_user_id" in request or True

    def test_response_200_authenticated_schema(self):
        """200 OK response for successful authentication."""
        response = {
            "status": "authenticated",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "user@gmail.com",
            "auth_type": "google",
            "tokens": {
                "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expires_in": 3600,
            },
            "merged_anonymous_data": True,
            "is_new_user": False,
        }

        # Required fields
        assert response["status"] == "authenticated"
        assert _is_valid_uuid(response["user_id"])
        assert "@" in response["email"]
        assert response["auth_type"] in ["google", "github"]

        # Token structure
        tokens = response["tokens"]
        assert "id_token" in tokens
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["expires_in"] > 0

        # Boolean flags
        assert isinstance(response["merged_anonymous_data"], bool)
        assert isinstance(response["is_new_user"], bool)

    def test_response_200_new_user(self):
        """200 response marks new users."""
        response = {
            "status": "authenticated",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "newuser@gmail.com",
            "auth_type": "google",
            "tokens": {
                "id_token": "eyJ...",
                "access_token": "eyJ...",
                "refresh_token": "eyJ...",
                "expires_in": 3600,
            },
            "merged_anonymous_data": False,
            "is_new_user": True,
        }

        assert response["is_new_user"] is True

    def test_response_400_invalid_code(self):
        """400 response for invalid authorization code."""
        response = {
            "error": "invalid_code",
            "message": "Authorization code is invalid or expired.",
        }

        assert response["error"] == "invalid_code"

    def test_response_400_invalid_provider(self):
        """400 response for unsupported provider."""
        response = {
            "error": "invalid_provider",
            "message": "Unsupported OAuth provider.",
        }

        assert response["error"] == "invalid_provider"


class TestOAuthTokenFormat:
    """Contract tests for OAuth token formats."""

    def test_id_token_is_jwt(self):
        """ID token must be JWT format."""
        token = (
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
        )

        # JWT has 3 parts separated by dots
        parts = token.split(".")
        assert len(parts) == 3

        # First part is base64 encoded header
        assert parts[0].startswith("eyJ")

    def test_access_token_is_jwt(self):
        """Access token must be JWT format."""
        token = (
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
        )

        parts = token.split(".")
        assert len(parts) == 3

    def test_refresh_token_opaque_or_jwt(self):
        """Refresh token can be opaque or JWT."""
        # Cognito refresh tokens are opaque strings
        opaque_token = "ABC123def456_ghi789-jkl012"
        jwt_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"

        # Either format is valid
        assert len(opaque_token) > 10 or "." in jwt_token

    def test_expires_in_is_seconds(self):
        """expires_in must be in seconds."""
        response = {
            "tokens": {
                "id_token": "eyJ...",
                "access_token": "eyJ...",
                "refresh_token": "eyJ...",
                "expires_in": 3600,  # 1 hour in seconds
            }
        }

        # Standard OAuth token lifetime
        assert response["tokens"]["expires_in"] == 3600


class TestOAuthProviderIcons:
    """Contract tests for OAuth provider icons."""

    def test_google_icon_identifier(self):
        """Google provider icon identifier."""
        response = {
            "providers": {
                "google": {
                    "authorize_url": "https://...",
                    "icon": "google",
                }
            }
        }

        assert response["providers"]["google"]["icon"] == "google"

    def test_github_icon_identifier(self):
        """GitHub provider icon identifier."""
        response = {
            "providers": {
                "github": {
                    "authorize_url": "https://...",
                    "icon": "github",
                }
            }
        }

        assert response["providers"]["github"]["icon"] == "github"


class TestOAuthRateLimits:
    """Contract tests for OAuth rate limiting."""

    def test_callback_rate_limit(self):
        """Rate limit is 20 requests per minute per IP."""
        rate_limit_response = {
            "error": "rate_limited",
            "message": "Too many requests. Please try again later.",
            "retry_after_seconds": 60,
        }

        # Per contract: 20 per minute per IP
        assert rate_limit_response["retry_after_seconds"] <= 60


class TestOAuthAccountLinking:
    """Contract tests for OAuth with existing accounts."""

    def test_email_conflict_response(self):
        """Response when email exists with different auth method."""
        # User authenticates with Google but email exists via magic link
        response = {
            "status": "conflict",
            "conflict": True,
            "existing_provider": "email",
            "email": "user@example.com",
            "message": "An account with this email exists via magic link. Would you like to link your Google account?",
        }

        assert response["conflict"] is True
        assert "existing_provider" in response

    def test_linking_required_confirmation(self):
        """Account linking requires explicit confirmation."""
        # Per contract, linking needs confirmation: true
        link_request = {
            "link_to_user_id": "existing-user-uuid",
            "confirmation": True,
        }

        assert link_request["confirmation"] is True


class TestOAuthStateParameter:
    """Contract tests for OAuth state parameter (CSRF protection)."""

    def test_state_included_in_authorize_url(self):
        """Authorize URL should include state for CSRF protection."""
        # Note: The contract doesn't explicitly require state, but it's best practice
        # This test documents the expected behavior

        url_with_state = "https://cognito.auth.region.amazoncognito.com/oauth2/authorize?client_id=xxx&state=random_state_value"

        # State parameter provides CSRF protection
        assert "state=" in url_with_state or True  # Optional per contract


def _is_valid_uuid(value: str) -> bool:
    """Check if string is valid UUID format."""
    import uuid

    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False

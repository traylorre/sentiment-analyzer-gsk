"""Unit tests for Cognito token validation helper (T101)."""

import base64
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.shared.auth.cognito import (
    CognitoConfig,
    CognitoTokens,
    TokenError,
    decode_id_token,
    exchange_code_for_tokens,
    generate_secret_hash,
    get_user_from_token,
    refresh_tokens,
    revoke_token,
    validate_access_token,
)


class TestCognitoConfig:
    """Tests for CognitoConfig dataclass."""

    def test_from_env(self):
        """Creates config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "COGNITO_USER_POOL_ID": "us-east-1_ABC123",
                "COGNITO_CLIENT_ID": "client123",
                "COGNITO_CLIENT_SECRET": "secret456",
                "COGNITO_DOMAIN": "myapp",
                "AWS_REGION": "us-east-1",
                "COGNITO_REDIRECT_URI": "https://app.example.com/callback",
            },
        ):
            config = CognitoConfig.from_env()

            assert config.user_pool_id == "us-east-1_ABC123"
            assert config.client_id == "client123"
            assert config.client_secret == "secret456"
            assert config.domain == "myapp"
            assert config.region == "us-east-1"
            assert config.redirect_uri == "https://app.example.com/callback"

    def test_token_url(self):
        """Generates correct token URL."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret=None,
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        assert (
            config.token_url
            == "https://myapp.auth.us-east-1.amazoncognito.com/oauth2/token"
        )

    def test_revoke_url(self):
        """Generates correct revoke URL."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret=None,
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        assert (
            config.revoke_url
            == "https://myapp.auth.us-east-1.amazoncognito.com/oauth2/revoke"
        )

    def test_jwks_url(self):
        """Generates correct JWKS URL."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret=None,
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        assert (
            config.jwks_url
            == "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_ABC123/.well-known/jwks.json"
        )

    def test_get_authorize_url_google(self):
        """Generates correct authorize URL for Google."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret=None,
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        url = config.get_authorize_url("google")

        assert "identity_provider=Google" in url
        assert "client_id=client123" in url
        assert "response_type=code" in url
        assert "scope=openid+email+profile" in url

    def test_get_authorize_url_with_state(self):
        """Includes state parameter when provided."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret=None,
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        url = config.get_authorize_url("github", state="random_state")

        assert "state=random_state" in url


class TestCognitoTokens:
    """Tests for CognitoTokens model."""

    def test_create_tokens(self):
        """Creates tokens with all fields."""
        tokens = CognitoTokens(
            id_token="id_token_value",
            access_token="access_token_value",
            refresh_token="refresh_token_value",
            expires_in=3600,
        )

        assert tokens.id_token == "id_token_value"
        assert tokens.access_token == "access_token_value"
        assert tokens.refresh_token == "refresh_token_value"
        assert tokens.expires_in == 3600
        assert tokens.token_type == "Bearer"

    def test_create_tokens_minimal(self):
        """Creates tokens with only required fields."""
        tokens = CognitoTokens(
            id_token="id",
            access_token="access",
        )

        assert tokens.id_token == "id"
        assert tokens.access_token == "access"
        assert tokens.refresh_token is None
        assert tokens.expires_in == 3600


class TestExchangeCodeForTokens:
    """Tests for exchange_code_for_tokens function."""

    def test_exchange_success(self):
        """Successfully exchanges code for tokens."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret="secret456",
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id_token": "id_token_value",
            "access_token": "access_token_value",
            "refresh_token": "refresh_token_value",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                mock_response
            )

            tokens = exchange_code_for_tokens(config, "auth_code_123")

            assert tokens.id_token == "id_token_value"
            assert tokens.access_token == "access_token_value"
            assert tokens.refresh_token == "refresh_token_value"
            assert tokens.expires_in == 3600

    def test_exchange_failure(self):
        """Raises TokenError on exchange failure."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret="secret456",
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": "invalid_grant"}'
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Invalid authorization code",
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                mock_response
            )

            with pytest.raises(TokenError) as exc_info:
                exchange_code_for_tokens(config, "invalid_code")

            assert exc_info.value.error == "invalid_grant"

    def test_exchange_includes_auth_header(self):
        """Includes Basic auth header when client secret configured."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret="secret456",
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id_token": "id",
            "access_token": "access",
            "expires_in": 3600,
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                mock_response
            )

            exchange_code_for_tokens(config, "code")

            call_kwargs = (
                mock_client.return_value.__enter__.return_value.post.call_args.kwargs
            )
            assert "Authorization" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Authorization"].startswith("Basic ")


class TestRefreshTokens:
    """Tests for refresh_tokens function."""

    def test_refresh_success(self):
        """Successfully refreshes tokens."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret="secret456",
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id_token": "new_id_token",
            "access_token": "new_access_token",
            "expires_in": 3600,
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                mock_response
            )

            tokens = refresh_tokens(config, "refresh_token_value")

            assert tokens.id_token == "new_id_token"
            assert tokens.access_token == "new_access_token"
            assert tokens.refresh_token is None  # Not rotated

    def test_refresh_invalid_grant(self):
        """Raises TokenError with appropriate message for invalid grant."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret="secret456",
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": "invalid_grant"}'
        mock_response.json.return_value = {
            "error": "invalid_grant",
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                mock_response
            )

            with pytest.raises(TokenError) as exc_info:
                refresh_tokens(config, "expired_token")

            assert exc_info.value.error == "invalid_refresh_token"
            assert "sign in again" in exc_info.value.message


class TestRevokeToken:
    """Tests for revoke_token function."""

    def test_revoke_success(self):
        """Returns True on successful revocation."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret="secret456",
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                mock_response
            )

            result = revoke_token(config, "token_to_revoke")

            assert result is True

    def test_revoke_failure(self):
        """Returns False on revocation failure."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret="secret456",
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                mock_response
            )

            result = revoke_token(config, "token_to_revoke")

            assert result is False


class TestDecodeIdToken:
    """Tests for decode_id_token function."""

    def test_decode_valid_token(self):
        """Decodes valid JWT payload."""
        # Create a fake JWT with base64-encoded payload
        header = (
            base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode())
            .decode()
            .rstrip("=")
        )
        payload_data = {
            "sub": "user123",
            "email": "user@example.com",
            "name": "Test User",
        }
        payload = (
            base64.urlsafe_b64encode(json.dumps(payload_data).encode())
            .decode()
            .rstrip("=")
        )
        signature = "fake_signature"

        token = f"{header}.{payload}.{signature}"

        claims = decode_id_token(token)

        assert claims["sub"] == "user123"
        assert claims["email"] == "user@example.com"
        assert claims["name"] == "Test User"

    def test_decode_invalid_token(self):
        """Returns empty dict for invalid token."""
        claims = decode_id_token("not_a_valid_jwt")

        assert claims == {}

    def test_decode_empty_token(self):
        """Returns empty dict for empty token."""
        claims = decode_id_token("")

        assert claims == {}


class TestValidateAccessToken:
    """Tests for validate_access_token function."""

    def test_validate_success(self):
        """Returns user info for valid token."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret=None,
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sub": "user123",
            "email": "user@example.com",
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = (
                mock_response
            )

            user_info = validate_access_token(config, "valid_token")

            assert user_info["sub"] == "user123"
            assert user_info["email"] == "user@example.com"

    def test_validate_invalid_token(self):
        """Returns None for invalid token."""
        config = CognitoConfig(
            user_pool_id="us-east-1_ABC123",
            client_id="client123",
            client_secret=None,
            domain="myapp",
            region="us-east-1",
            redirect_uri="https://app.example.com/callback",
        )

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = (
                mock_response
            )

            user_info = validate_access_token(config, "invalid_token")

            assert user_info is None


class TestGetUserFromToken:
    """Tests for get_user_from_token function."""

    def test_get_user_success(self):
        """Returns user info for valid token."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sub": "user123",
            "email": "user@example.com",
        }

        with patch.dict(
            os.environ,
            {
                "COGNITO_USER_POOL_ID": "us-east-1_ABC123",
                "COGNITO_CLIENT_ID": "client123",
                "COGNITO_DOMAIN": "myapp",
                "AWS_REGION": "us-east-1",
                "COGNITO_REDIRECT_URI": "https://app.example.com/callback",
            },
        ):
            with patch("httpx.Client") as mock_client:
                mock_client.return_value.__enter__.return_value.get.return_value = (
                    mock_response
                )

                user_info = get_user_from_token("valid_token")

                assert user_info["sub"] == "user123"


class TestGenerateSecretHash:
    """Tests for generate_secret_hash function."""

    def test_generate_hash(self):
        """Generates consistent hash."""
        hash1 = generate_secret_hash("client123", "secret456", "user@example.com")
        hash2 = generate_secret_hash("client123", "secret456", "user@example.com")

        assert hash1 == hash2
        assert len(hash1) > 0

    def test_different_inputs_different_hash(self):
        """Different inputs produce different hashes."""
        hash1 = generate_secret_hash("client123", "secret456", "user1@example.com")
        hash2 = generate_secret_hash("client123", "secret456", "user2@example.com")

        assert hash1 != hash2

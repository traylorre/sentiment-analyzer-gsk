"""Tests for PKCE support in OAuth flow (Feature 1222, US4)."""

import base64
import hashlib
import secrets
from unittest.mock import MagicMock, patch

from src.lambdas.shared.auth.cognito import CognitoConfig


class TestPKCEAuthorizeURL:
    """FR-007: Authorization URLs include code_challenge."""

    def test_authorize_url_includes_code_challenge(self):
        """get_authorize_url() includes code_challenge when provided."""
        config = CognitoConfig(
            user_pool_id="us-east-1_test",
            client_id="test-client",
            client_secret=None,
            domain="test-domain",
            region="us-east-1",
            redirect_uri="https://example.com/callback",
        )

        challenge = "test-challenge-value"
        url = config.get_authorize_url(
            "Google", state="test-state", code_challenge=challenge
        )

        assert "code_challenge=test-challenge-value" in url
        assert "code_challenge_method=S256" in url

    def test_authorize_url_without_code_challenge(self):
        """get_authorize_url() works without code_challenge (backward compat)."""
        config = CognitoConfig(
            user_pool_id="us-east-1_test",
            client_id="test-client",
            client_secret=None,
            domain="test-domain",
            region="us-east-1",
            redirect_uri="https://example.com/callback",
        )

        url = config.get_authorize_url("Google", state="test-state")
        assert "code_challenge" not in url
        assert "code_challenge_method" not in url


class TestPKCETokenExchange:
    """FR-009: Token exchange includes code_verifier."""

    @patch("src.lambdas.shared.auth.cognito.httpx.Client")
    def test_exchange_includes_code_verifier(self, mock_client_cls):
        """exchange_code_for_tokens() includes code_verifier in POST body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id_token": "test-id-token",
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        from src.lambdas.shared.auth.cognito import exchange_code_for_tokens

        config = CognitoConfig(
            user_pool_id="us-east-1_test",
            client_id="test-client",
            client_secret=None,
            domain="test-domain",
            region="us-east-1",
            redirect_uri="https://example.com/callback",
        )

        exchange_code_for_tokens(config, "test-code", code_verifier="my-verifier")

        # Verify code_verifier was in POST data
        call_kwargs = mock_client.post.call_args
        post_data = call_kwargs.kwargs.get("data", {})
        assert post_data.get("code_verifier") == "my-verifier"

    @patch("src.lambdas.shared.auth.cognito.httpx.Client")
    def test_exchange_without_code_verifier(self, mock_client_cls):
        """exchange_code_for_tokens() works without code_verifier (backward compat)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id_token": "test-id-token",
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        from src.lambdas.shared.auth.cognito import exchange_code_for_tokens

        config = CognitoConfig(
            user_pool_id="us-east-1_test",
            client_id="test-client",
            client_secret=None,
            domain="test-domain",
            region="us-east-1",
            redirect_uri="https://example.com/callback",
        )

        exchange_code_for_tokens(config, "test-code")

        call_kwargs = mock_client.post.call_args
        post_data = call_kwargs.kwargs.get("data", {})
        assert "code_verifier" not in post_data


class TestPKCEOAuthState:
    """FR-008: code_verifier stored in OAuth state record."""

    @patch("src.lambdas.shared.auth.oauth_state.secrets")
    def test_store_oauth_state_generates_code_verifier(self, mock_secrets):
        """store_oauth_state() generates and stores code_verifier."""
        mock_secrets.token_urlsafe.return_value = (
            "test-verifier-43chars-padded-out-here123456"
        )

        table = MagicMock()
        table.put_item.return_value = {}

        from src.lambdas.shared.auth.oauth_state import store_oauth_state

        state = store_oauth_state(
            table=table,
            state_id="test-state",
            provider="google",
            redirect_uri="https://example.com/callback",
        )

        assert state.code_verifier == "test-verifier-43chars-padded-out-here123456"
        # Verify put_item included code_verifier
        put_kwargs = table.put_item.call_args
        item = put_kwargs.kwargs.get("Item", {})
        assert "code_verifier" in item

    def test_code_challenge_derivation(self):
        """S256 code_challenge correctly derived from code_verifier."""
        verifier = secrets.token_urlsafe(32)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

        # Verify the challenge is a valid base64url string without padding
        assert "=" not in challenge
        assert len(challenge) == 43  # SHA-256 = 32 bytes → 43 base64url chars

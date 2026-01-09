"""Unit tests for OAuth callback federation response (Feature 1176).

Tests that OAuthCallbackResponse includes federation fields (role, verification,
linked_providers, last_provider_used) populated from user state after mutations.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.lambdas.dashboard.auth import (
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    handle_oauth_callback,
)
from src.lambdas.shared.auth.cognito import CognitoTokens
from src.lambdas.shared.models.user import User


class TestOAuthCallbackResponseModel:
    """Test OAuthCallbackResponse model federation fields."""

    def test_federation_fields_exist(self) -> None:
        """OAuthCallbackResponse has federation fields with defaults."""
        response = OAuthCallbackResponse(status="authenticated")

        assert hasattr(response, "role")
        assert hasattr(response, "verification")
        assert hasattr(response, "linked_providers")
        assert hasattr(response, "last_provider_used")

    def test_federation_defaults(self) -> None:
        """Federation fields have correct defaults."""
        response = OAuthCallbackResponse(status="authenticated")

        assert response.role == "anonymous"
        assert response.verification == "none"
        assert response.linked_providers == []
        assert response.last_provider_used is None

    def test_federation_fields_can_be_set(self) -> None:
        """Federation fields can be set to custom values."""
        response = OAuthCallbackResponse(
            status="authenticated",
            role="free",
            verification="verified",
            linked_providers=["google", "github"],
            last_provider_used="google",
        )

        assert response.role == "free"
        assert response.verification == "verified"
        assert response.linked_providers == ["google", "github"]
        assert response.last_provider_used == "google"


class TestOAuthCallbackFederationFieldsNewUser:
    """Test federation fields for new OAuth users."""

    def _create_test_user(self, role: str = "anonymous") -> User:
        """Create a test user with specified role."""
        return User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role=role,
            verification="none",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

    def _mock_tokens(self) -> CognitoTokens:
        """Create mock Cognito tokens."""
        return CognitoTokens(
            id_token="mock-id-token",
            access_token="mock-access-token",
            refresh_token="mock-refresh-token",
            expires_in=3600,
        )

    @patch("src.lambdas.dashboard.auth._create_authenticated_user")
    @patch("src.lambdas.dashboard.auth._update_cognito_sub")
    @patch("src.lambdas.dashboard.auth._link_provider")
    @patch("src.lambdas.dashboard.auth._mark_email_verified")
    @patch("src.lambdas.dashboard.auth._advance_role")
    @patch("src.lambdas.dashboard.auth.get_user_by_email_gsi")
    @patch("src.lambdas.dashboard.auth.exchange_code_for_tokens")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    def test_new_user_role_advanced_to_free(
        self,
        mock_decode_id_token: MagicMock,
        mock_exchange: MagicMock,
        mock_get_user: MagicMock,
        mock_advance_role: MagicMock,
        mock_mark_verified: MagicMock,
        mock_link_provider: MagicMock,
        mock_update_sub: MagicMock,
        mock_create_user: MagicMock,
    ) -> None:
        """New anonymous user gets role=free in response."""
        table = MagicMock()
        user = self._create_test_user(role="anonymous")
        mock_create_user.return_value = user
        mock_get_user.return_value = None  # New user
        mock_exchange.return_value = self._mock_tokens()
        mock_decode_id_token.return_value = {
            "email": "test@example.com",
            "sub": "google-123",
            "email_verified": True,
        }

        request = OAuthCallbackRequest(code="auth-code", provider="google")
        response = handle_oauth_callback(table, request)

        assert response.role == "free"

    @patch("src.lambdas.dashboard.auth._create_authenticated_user")
    @patch("src.lambdas.dashboard.auth._update_cognito_sub")
    @patch("src.lambdas.dashboard.auth._link_provider")
    @patch("src.lambdas.dashboard.auth._mark_email_verified")
    @patch("src.lambdas.dashboard.auth._advance_role")
    @patch("src.lambdas.dashboard.auth.get_user_by_email_gsi")
    @patch("src.lambdas.dashboard.auth.exchange_code_for_tokens")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    def test_new_user_verification_verified_when_email_verified(
        self,
        mock_decode_id_token: MagicMock,
        mock_exchange: MagicMock,
        mock_get_user: MagicMock,
        mock_advance_role: MagicMock,
        mock_mark_verified: MagicMock,
        mock_link_provider: MagicMock,
        mock_update_sub: MagicMock,
        mock_create_user: MagicMock,
    ) -> None:
        """New user with verified email gets verification=verified."""
        table = MagicMock()
        user = self._create_test_user()
        mock_create_user.return_value = user
        mock_get_user.return_value = None
        mock_exchange.return_value = self._mock_tokens()
        mock_decode_id_token.return_value = {
            "email": "test@example.com",
            "sub": "google-123",
            "email_verified": True,
        }

        request = OAuthCallbackRequest(code="auth-code", provider="google")
        response = handle_oauth_callback(table, request)

        assert response.verification == "verified"

    @patch("src.lambdas.dashboard.auth._create_authenticated_user")
    @patch("src.lambdas.dashboard.auth._update_cognito_sub")
    @patch("src.lambdas.dashboard.auth._link_provider")
    @patch("src.lambdas.dashboard.auth._mark_email_verified")
    @patch("src.lambdas.dashboard.auth._advance_role")
    @patch("src.lambdas.dashboard.auth.get_user_by_email_gsi")
    @patch("src.lambdas.dashboard.auth.exchange_code_for_tokens")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    def test_new_user_verification_none_when_email_not_verified(
        self,
        mock_decode_id_token: MagicMock,
        mock_exchange: MagicMock,
        mock_get_user: MagicMock,
        mock_advance_role: MagicMock,
        mock_mark_verified: MagicMock,
        mock_link_provider: MagicMock,
        mock_update_sub: MagicMock,
        mock_create_user: MagicMock,
    ) -> None:
        """New user without verified email keeps verification=none."""
        table = MagicMock()
        user = self._create_test_user()
        mock_create_user.return_value = user
        mock_get_user.return_value = None
        mock_exchange.return_value = self._mock_tokens()
        mock_decode_id_token.return_value = {
            "email": "test@example.com",
            "sub": "google-123",
            "email_verified": False,
        }

        request = OAuthCallbackRequest(code="auth-code", provider="google")
        response = handle_oauth_callback(table, request)

        assert response.verification == "none"

    @patch("src.lambdas.dashboard.auth._create_authenticated_user")
    @patch("src.lambdas.dashboard.auth._update_cognito_sub")
    @patch("src.lambdas.dashboard.auth._link_provider")
    @patch("src.lambdas.dashboard.auth._mark_email_verified")
    @patch("src.lambdas.dashboard.auth._advance_role")
    @patch("src.lambdas.dashboard.auth.get_user_by_email_gsi")
    @patch("src.lambdas.dashboard.auth.exchange_code_for_tokens")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    def test_new_user_linked_providers_includes_provider(
        self,
        mock_decode_id_token: MagicMock,
        mock_exchange: MagicMock,
        mock_get_user: MagicMock,
        mock_advance_role: MagicMock,
        mock_mark_verified: MagicMock,
        mock_link_provider: MagicMock,
        mock_update_sub: MagicMock,
        mock_create_user: MagicMock,
    ) -> None:
        """New user gets provider added to linked_providers."""
        table = MagicMock()
        user = self._create_test_user()
        mock_create_user.return_value = user
        mock_get_user.return_value = None
        mock_exchange.return_value = self._mock_tokens()
        mock_decode_id_token.return_value = {
            "email": "test@example.com",
            "sub": "google-123",
            "email_verified": True,
        }

        request = OAuthCallbackRequest(code="auth-code", provider="google")
        response = handle_oauth_callback(table, request)

        assert "google" in response.linked_providers

    @patch("src.lambdas.dashboard.auth._create_authenticated_user")
    @patch("src.lambdas.dashboard.auth._update_cognito_sub")
    @patch("src.lambdas.dashboard.auth._link_provider")
    @patch("src.lambdas.dashboard.auth._mark_email_verified")
    @patch("src.lambdas.dashboard.auth._advance_role")
    @patch("src.lambdas.dashboard.auth.get_user_by_email_gsi")
    @patch("src.lambdas.dashboard.auth.exchange_code_for_tokens")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    def test_new_user_last_provider_used_set(
        self,
        mock_decode_id_token: MagicMock,
        mock_exchange: MagicMock,
        mock_get_user: MagicMock,
        mock_advance_role: MagicMock,
        mock_mark_verified: MagicMock,
        mock_link_provider: MagicMock,
        mock_update_sub: MagicMock,
        mock_create_user: MagicMock,
    ) -> None:
        """New user gets last_provider_used set to the OAuth provider."""
        table = MagicMock()
        user = self._create_test_user()
        mock_create_user.return_value = user
        mock_get_user.return_value = None
        mock_exchange.return_value = self._mock_tokens()
        mock_decode_id_token.return_value = {
            "email": "test@example.com",
            "sub": "google-123",
            "email_verified": True,
        }

        request = OAuthCallbackRequest(code="auth-code", provider="google")
        response = handle_oauth_callback(table, request)

        assert response.last_provider_used == "google"


class TestOAuthCallbackFederationFieldsExistingUser:
    """Test federation fields for existing OAuth users."""

    def _create_existing_user(self) -> User:
        """Create an existing user with google already linked."""
        return User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="free",
            verification="verified",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

    def _mock_tokens(self) -> CognitoTokens:
        """Create mock Cognito tokens."""
        return CognitoTokens(
            id_token="mock-id-token",
            access_token="mock-access-token",
            refresh_token="mock-refresh-token",
            expires_in=3600,
        )

    @patch("src.lambdas.dashboard.auth._link_provider")
    @patch("src.lambdas.dashboard.auth._mark_email_verified")
    @patch("src.lambdas.dashboard.auth._advance_role")
    @patch("src.lambdas.dashboard.auth.get_user_by_email_gsi")
    @patch("src.lambdas.dashboard.auth.exchange_code_for_tokens")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    def test_existing_user_role_preserved(
        self,
        mock_decode_id_token: MagicMock,
        mock_exchange: MagicMock,
        mock_get_user: MagicMock,
        mock_advance_role: MagicMock,
        mock_mark_verified: MagicMock,
        mock_link_provider: MagicMock,
    ) -> None:
        """Existing free user keeps role=free."""
        table = MagicMock()
        user = self._create_existing_user()
        mock_get_user.return_value = user
        mock_exchange.return_value = self._mock_tokens()
        mock_decode_id_token.return_value = {
            "email": "test@example.com",
            "sub": "google-123",
            "email_verified": True,
        }

        request = OAuthCallbackRequest(code="auth-code", provider="google")
        response = handle_oauth_callback(table, request)

        assert response.role == "free"

    @patch("src.lambdas.dashboard.auth._link_provider")
    @patch("src.lambdas.dashboard.auth._mark_email_verified")
    @patch("src.lambdas.dashboard.auth._advance_role")
    @patch("src.lambdas.dashboard.auth.get_user_by_email_gsi")
    @patch("src.lambdas.dashboard.auth.exchange_code_for_tokens")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    def test_existing_user_new_provider_triggers_conflict(
        self,
        mock_decode_id_token: MagicMock,
        mock_exchange: MagicMock,
        mock_get_user: MagicMock,
        mock_advance_role: MagicMock,
        mock_mark_verified: MagicMock,
        mock_link_provider: MagicMock,
    ) -> None:
        """Existing user with different provider triggers conflict response.

        When a Google user tries to authenticate with GitHub, it triggers a
        conflict flow requiring user confirmation. Federation fields use defaults
        in conflict responses.
        """
        table = MagicMock()
        user = self._create_existing_user()  # Has google linked
        mock_get_user.return_value = user
        mock_exchange.return_value = self._mock_tokens()
        mock_decode_id_token.return_value = {
            "email": "test@example.com",
            "sub": "github-123",
            "email_verified": True,
        }

        request = OAuthCallbackRequest(code="auth-code", provider="github")
        response = handle_oauth_callback(table, request)

        # Conflict response uses defaults for federation fields
        assert response.status == "conflict"
        assert response.existing_provider == "google"
        assert response.role == "anonymous"  # Default, not populated in conflict
        assert response.linked_providers == []  # Default, not populated in conflict

    @patch("src.lambdas.dashboard.auth._link_provider")
    @patch("src.lambdas.dashboard.auth._mark_email_verified")
    @patch("src.lambdas.dashboard.auth._advance_role")
    @patch("src.lambdas.dashboard.auth.get_user_by_email_gsi")
    @patch("src.lambdas.dashboard.auth.exchange_code_for_tokens")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    def test_existing_user_same_provider_no_duplicate(
        self,
        mock_decode_id_token: MagicMock,
        mock_exchange: MagicMock,
        mock_get_user: MagicMock,
        mock_advance_role: MagicMock,
        mock_mark_verified: MagicMock,
        mock_link_provider: MagicMock,
    ) -> None:
        """Re-authenticating with same provider doesn't duplicate."""
        table = MagicMock()
        user = self._create_existing_user()  # Has google linked
        mock_get_user.return_value = user
        mock_exchange.return_value = self._mock_tokens()
        mock_decode_id_token.return_value = {
            "email": "test@example.com",
            "sub": "google-123",
            "email_verified": True,
        }

        request = OAuthCallbackRequest(code="auth-code", provider="google")
        response = handle_oauth_callback(table, request)

        assert response.linked_providers == ["google"]

    @patch("src.lambdas.dashboard.auth._link_provider")
    @patch("src.lambdas.dashboard.auth._mark_email_verified")
    @patch("src.lambdas.dashboard.auth._advance_role")
    @patch("src.lambdas.dashboard.auth.get_user_by_email_gsi")
    @patch("src.lambdas.dashboard.auth.exchange_code_for_tokens")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    def test_last_provider_used_updated(
        self,
        mock_decode_id_token: MagicMock,
        mock_exchange: MagicMock,
        mock_get_user: MagicMock,
        mock_advance_role: MagicMock,
        mock_mark_verified: MagicMock,
        mock_link_provider: MagicMock,
    ) -> None:
        """last_provider_used set to current OAuth provider on re-auth."""
        table = MagicMock()
        user = self._create_existing_user()  # Has google linked
        mock_get_user.return_value = user
        mock_exchange.return_value = self._mock_tokens()
        mock_decode_id_token.return_value = {
            "email": "test@example.com",
            "sub": "google-123",  # Same provider for successful re-auth
            "email_verified": True,
        }

        request = OAuthCallbackRequest(code="auth-code", provider="google")
        response = handle_oauth_callback(table, request)

        assert response.last_provider_used == "google"

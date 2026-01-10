"""Unit tests for OAuth auto-link functionality (Feature 1181).

Tests the can_auto_link_oauth() function and Flow 3 integration in
handle_oauth_callback() for automatic vs manual account linking.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.auth import (
    can_auto_link_oauth,
    handle_oauth_callback,
)
from src.lambdas.shared.models.user import User


# Feature 1185: Auto-mock OAuth state validation for all tests in this module
@pytest.fixture(autouse=True)
def mock_oauth_state_validation():
    """Mock OAuth state validation to always pass for these tests."""
    with patch(
        "src.lambdas.dashboard.auth.validate_oauth_state",
        return_value=(True, ""),
    ):
        yield


def _create_test_user(
    user_id: str | None = None,
    email: str = "test@gmail.com",
    role: str = "free",
    verification: str = "verified",
    auth_type: str = "email",
    linked_providers: list[str] | None = None,
    provider_sub: str | None = None,
) -> User:
    """Create a test user with all required fields."""
    now = datetime.now(UTC)
    return User(
        user_id=user_id or str(uuid.uuid4()),
        email=email,
        role=role,
        verification=verification,
        auth_type=auth_type,
        linked_providers=linked_providers or ["email"],
        provider_sub=provider_sub,
        created_at=now,
        last_active_at=now,
        session_expires_at=now + timedelta(days=30),
    )


class TestCanAutoLinkOAuth:
    """Tests for can_auto_link_oauth() function."""

    def test_gmail_with_google_returns_true(self):
        """Gmail user with Google OAuth should auto-link."""
        result = can_auto_link_oauth(
            oauth_email="test@gmail.com",
            oauth_email_verified=True,
            provider="google",
            existing_user_email="test@gmail.com",
        )
        assert result is True

    def test_gmail_with_google_case_insensitive(self):
        """Domain check should be case-insensitive."""
        result = can_auto_link_oauth(
            oauth_email="test@GMAIL.COM",
            oauth_email_verified=True,
            provider="Google",
            existing_user_email="TEST@Gmail.com",
        )
        assert result is True

    def test_github_always_returns_false(self):
        """GitHub OAuth should always require manual confirmation."""
        result = can_auto_link_oauth(
            oauth_email="test@gmail.com",
            oauth_email_verified=True,
            provider="github",
            existing_user_email="test@gmail.com",
        )
        assert result is False

    def test_unverified_email_returns_false(self):
        """Unverified OAuth email should never auto-link."""
        result = can_auto_link_oauth(
            oauth_email="test@gmail.com",
            oauth_email_verified=False,
            provider="google",
            existing_user_email="test@gmail.com",
        )
        assert result is False

    def test_cross_domain_returns_false(self):
        """Different email domains should require manual confirmation."""
        result = can_auto_link_oauth(
            oauth_email="test@gmail.com",
            oauth_email_verified=True,
            provider="google",
            existing_user_email="test@hotmail.com",
        )
        assert result is False

    def test_google_with_non_gmail_returns_false(self):
        """Google OAuth with non-gmail existing email requires confirmation."""
        result = can_auto_link_oauth(
            oauth_email="test@company.com",
            oauth_email_verified=True,
            provider="google",
            existing_user_email="test@company.com",
        )
        assert result is False

    def test_googlemail_with_google_returns_false(self):
        """Googlemail (UK variant) requires confirmation (only gmail.com is authoritative)."""
        result = can_auto_link_oauth(
            oauth_email="test@googlemail.com",
            oauth_email_verified=True,
            provider="google",
            existing_user_email="test@googlemail.com",
        )
        assert result is False


class TestHandleOAuthCallbackFlow3:
    """Tests for Flow 3 integration in handle_oauth_callback()."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        return MagicMock()

    @pytest.fixture
    def mock_config(self):
        """Create mock Cognito config."""
        with patch("src.lambdas.dashboard.auth.CognitoConfig.from_env") as mock:
            config = MagicMock()
            mock.return_value = config
            yield config

    @pytest.fixture
    def mock_exchange(self):
        """Mock token exchange."""
        with patch("src.lambdas.dashboard.auth.exchange_code_for_tokens") as mock:
            tokens = MagicMock()
            tokens.id_token = "mock_id_token"
            tokens.refresh_token = "mock_refresh_token"
            mock.return_value = tokens
            yield mock

    @pytest.fixture
    def mock_decode(self):
        """Mock ID token decoding."""
        with patch("src.lambdas.dashboard.auth.decode_id_token") as mock:
            yield mock

    def test_auth_023_duplicate_provider_sub(
        self, mock_table, mock_config, mock_exchange, mock_decode
    ):
        """Should reject when OAuth account is linked to different user."""
        # Arrange
        existing_user = _create_test_user(
            user_id="user-A",
            email="userA@gmail.com",
        )
        different_user = _create_test_user(
            user_id="user-B",
            email="userB@gmail.com",
            provider_sub="google:shared-sub",
        )

        mock_decode.return_value = {
            "email": "userA@gmail.com",
            "sub": "shared-sub",
            "email_verified": True,
        }

        with (
            patch(
                "src.lambdas.dashboard.auth.get_user_by_email_gsi",
                return_value=existing_user,
            ),
            patch(
                "src.lambdas.dashboard.auth.get_user_by_provider_sub",
                return_value=different_user,
            ),
        ):
            # Feature 1185: Use keyword args with required state/redirect_uri
            result = handle_oauth_callback(
                table=mock_table,
                code="test_code",
                provider="google",
                redirect_uri="https://app.example.com/callback",
                state="test_state_abc123",
            )

            # Assert
            assert result.status == "error"
            assert result.error == "AUTH_023"
            assert "already linked" in result.message

    def test_auth_022_unverified_oauth_email(
        self, mock_table, mock_config, mock_exchange, mock_decode
    ):
        """Should reject when OAuth email is not verified."""
        # Arrange
        existing_user = _create_test_user(
            email="test@hotmail.com",
            auth_type="email",
        )

        mock_decode.return_value = {
            "email": "test@hotmail.com",
            "sub": "google-sub",
            "email_verified": False,  # Not verified
        }

        with (
            patch(
                "src.lambdas.dashboard.auth.get_user_by_email_gsi",
                return_value=existing_user,
            ),
            patch(
                "src.lambdas.dashboard.auth.get_user_by_provider_sub",
                return_value=None,
            ),
        ):
            # Feature 1185: Use keyword args with required state/redirect_uri
            result = handle_oauth_callback(
                table=mock_table,
                code="test_code",
                provider="google",
                redirect_uri="https://app.example.com/callback",
                state="test_state_abc123",
            )

            # Assert
            assert result.status == "error"
            assert result.error == "AUTH_022"
            assert "not verified" in result.message.lower()

    def test_auto_link_gmail_google(
        self, mock_table, mock_config, mock_exchange, mock_decode
    ):
        """Should auto-link Gmail user with Google OAuth without conflict."""
        # Arrange
        existing_user = _create_test_user(
            email="test@gmail.com",
            auth_type="email",
            linked_providers=["email"],
        )

        mock_decode.return_value = {
            "email": "test@gmail.com",
            "sub": "google-sub-123",
            "email_verified": True,
            "picture": "https://example.com/avatar.jpg",
        }

        with (
            patch(
                "src.lambdas.dashboard.auth.get_user_by_email_gsi",
                return_value=existing_user,
            ),
            patch(
                "src.lambdas.dashboard.auth.get_user_by_provider_sub",
                return_value=None,
            ),
            patch("src.lambdas.dashboard.auth._update_cognito_sub"),
            patch("src.lambdas.dashboard.auth._link_provider") as mock_link,
            patch("src.lambdas.dashboard.auth._mark_email_verified"),
            patch("src.lambdas.dashboard.auth._advance_role"),
        ):
            # Feature 1185: Use keyword args with required state/redirect_uri
            result = handle_oauth_callback(
                table=mock_table,
                code="test_code",
                provider="google",
                redirect_uri="https://app.example.com/callback",
                state="test_state_abc123",
            )

            # Assert - should authenticate, not return conflict
            assert result.status == "authenticated"
            assert result.conflict is not True
            # Verify _link_provider was called
            mock_link.assert_called_once()

    def test_manual_link_cross_domain(
        self, mock_table, mock_config, mock_exchange, mock_decode
    ):
        """Should require manual confirmation for cross-domain OAuth."""
        # Arrange
        existing_user = _create_test_user(
            email="ceo@hotmail.com",
            auth_type="email",
        )

        mock_decode.return_value = {
            "email": "ceo@gmail.com",
            "sub": "google-sub-456",
            "email_verified": True,
        }

        with (
            patch(
                "src.lambdas.dashboard.auth.get_user_by_email_gsi",
                return_value=existing_user,
            ),
            patch(
                "src.lambdas.dashboard.auth.get_user_by_provider_sub",
                return_value=None,
            ),
        ):
            # Feature 1185: Use keyword args with required state/redirect_uri
            result = handle_oauth_callback(
                table=mock_table,
                code="test_code",
                provider="google",
                redirect_uri="https://app.example.com/callback",
                state="test_state_abc123",
            )

            # Assert - should return conflict for manual linking
            assert result.status == "conflict"
            assert result.conflict is True
            assert "email" in result.existing_provider

    def test_github_always_prompts(
        self, mock_table, mock_config, mock_exchange, mock_decode
    ):
        """GitHub should always require manual confirmation."""
        # Arrange
        existing_user = _create_test_user(
            email="dev@github.io",
            auth_type="email",
        )

        mock_decode.return_value = {
            "email": "dev@github.io",
            "sub": "github-user-id",
            "email_verified": True,
        }

        with (
            patch(
                "src.lambdas.dashboard.auth.get_user_by_email_gsi",
                return_value=existing_user,
            ),
            patch(
                "src.lambdas.dashboard.auth.get_user_by_provider_sub",
                return_value=None,
            ),
        ):
            # Feature 1185: Use keyword args with required state/redirect_uri
            result = handle_oauth_callback(
                table=mock_table,
                code="test_code",
                provider="github",
                redirect_uri="https://app.example.com/callback",
                state="test_state_abc123",
            )

            # Assert - should return conflict even with same email
            assert result.status == "conflict"
            assert result.conflict is True

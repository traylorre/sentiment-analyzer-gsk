"""Unit tests for Flow 5: OAuth-to-OAuth Auto-Link.

Tests for automatic linking when OAuth user authenticates with different OAuth provider.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from freezegun import freeze_time

from src.lambdas.dashboard.auth import (
    OAuthCallbackRequest,
    handle_oauth_callback,
)
from src.lambdas.shared.auth.cognito import CognitoTokens
from src.lambdas.shared.models.user import ProviderMetadata, User


@pytest.fixture
def mock_table():
    """Create a mock DynamoDB table."""
    table = MagicMock()
    table.meta = MagicMock()
    table.meta.client = MagicMock()
    table.meta.client.exceptions = MagicMock()
    table.meta.client.exceptions.ConditionalCheckFailedException = Exception
    return table


@pytest.fixture
def google_oauth_user():
    """Create a test user authenticated via Google OAuth."""
    now = datetime.now(UTC)
    return User(
        user_id=str(uuid4()),
        email="user@gmail.com",
        auth_type="google",
        role="free",
        verification="verified",
        linked_providers=["google"],
        provider_metadata={
            "google": ProviderMetadata(
                sub="google-123456",
                email="user@gmail.com",
                avatar=None,
                linked_at=now,
                verified_at=now,
            )
        },
        pending_email=None,
        primary_email="user@gmail.com",
        created_at=now,
        last_active_at=now,
        session_expires_at=now + timedelta(days=30),
    )


@pytest.fixture
def github_oauth_user():
    """Create a test user authenticated via GitHub OAuth."""
    now = datetime.now(UTC)
    return User(
        user_id=str(uuid4()),
        email="user@github.com",
        auth_type="github",
        role="free",
        verification="verified",
        linked_providers=["github"],
        provider_metadata={
            "github": ProviderMetadata(
                sub="github-789012",
                email="user@github.com",
                avatar=None,
                linked_at=now,
                verified_at=now,
            )
        },
        pending_email=None,
        primary_email="user@github.com",
        created_at=now,
        last_active_at=now,
        session_expires_at=now + timedelta(days=30),
    )


class TestOAuthToOAuthAutoLink:
    """Tests for Flow 5: OAuth-to-OAuth auto-linking."""

    @freeze_time("2026-01-09 12:00:00")
    def test_google_user_links_github_auto(self, mock_table, google_oauth_user):
        """Google OAuth user logging in with GitHub auto-links without conflict."""
        request = OAuthCallbackRequest(
            provider="github",
            code="github-auth-code",
            state="test-state",
        )

        # Mock Cognito token exchange
        github_claims = {
            "sub": "github-new-sub-456",
            "email": "user@gmail.com",
            "email_verified": True,
            "picture": "https://github.com/avatar.jpg",
        }

        # Mock existing user lookup by email
        mock_table.query.return_value = {
            "Items": [google_oauth_user.to_dynamodb_item()]
        }
        mock_table.get_item.return_value = {}  # No existing provider_sub
        mock_table.update_item.return_value = {}
        mock_table.put_item.return_value = {}

        with patch(
            "src.lambdas.dashboard.auth.exchange_code_for_tokens"
        ) as mock_exchange:
            mock_exchange.return_value = CognitoTokens(
                id_token="mock-id-token",
                access_token="mock-access-token",
            )

            with patch("src.lambdas.dashboard.auth.decode_id_token") as mock_decode:
                mock_decode.return_value = github_claims

                with patch(
                    "src.lambdas.dashboard.auth.get_user_by_email_gsi"
                ) as mock_get_user:
                    mock_get_user.return_value = google_oauth_user

                    with patch(
                        "src.lambdas.dashboard.auth.get_user_by_provider_sub"
                    ) as mock_get_by_sub:
                        mock_get_by_sub.return_value = None  # No collision

                        result = handle_oauth_callback(
                            table=mock_table,
                            request=request,
                        )

        # Should succeed, not return conflict
        assert result.status == "authenticated"
        assert result.conflict is not True

    @freeze_time("2026-01-09 12:00:00")
    def test_github_user_links_google_auto(self, mock_table, github_oauth_user):
        """GitHub OAuth user logging in with Google auto-links without conflict."""
        request = OAuthCallbackRequest(
            provider="google",
            code="google-auth-code",
            state="test-state",
        )

        google_claims = {
            "sub": "google-new-sub-789",
            "email": "user@github.com",
            "email_verified": True,
            "picture": "https://google.com/avatar.jpg",
        }

        mock_table.query.return_value = {
            "Items": [github_oauth_user.to_dynamodb_item()]
        }
        mock_table.get_item.return_value = {}
        mock_table.update_item.return_value = {}
        mock_table.put_item.return_value = {}

        with patch(
            "src.lambdas.dashboard.auth.exchange_code_for_tokens"
        ) as mock_exchange:
            mock_exchange.return_value = CognitoTokens(
                id_token="mock-id-token",
                access_token="mock-access-token",
            )

            with patch("src.lambdas.dashboard.auth.decode_id_token") as mock_decode:
                mock_decode.return_value = google_claims

                with patch(
                    "src.lambdas.dashboard.auth.get_user_by_email_gsi"
                ) as mock_get_user:
                    mock_get_user.return_value = github_oauth_user

                    with patch(
                        "src.lambdas.dashboard.auth.get_user_by_provider_sub"
                    ) as mock_get_by_sub:
                        mock_get_by_sub.return_value = None

                        result = handle_oauth_callback(
                            table=mock_table,
                            request=request,
                        )

        assert result.status == "authenticated"
        assert result.conflict is not True

    @freeze_time("2026-01-09 12:00:00")
    def test_oauth_to_oauth_rejects_unverified_email(
        self, mock_table, google_oauth_user
    ):
        """OAuth-to-OAuth link rejects if new provider's email is not verified."""
        request = OAuthCallbackRequest(
            provider="github",
            code="github-auth-code",
            state="test-state",
        )

        github_claims = {
            "sub": "github-new-sub-456",
            "email": "user@gmail.com",
            "email_verified": False,  # NOT verified
            "picture": None,
        }

        with patch(
            "src.lambdas.dashboard.auth.exchange_code_for_tokens"
        ) as mock_exchange:
            mock_exchange.return_value = CognitoTokens(
                id_token="mock-id-token",
                access_token="mock-access-token",
            )

            with patch("src.lambdas.dashboard.auth.decode_id_token") as mock_decode:
                mock_decode.return_value = github_claims

                with patch(
                    "src.lambdas.dashboard.auth.get_user_by_email_gsi"
                ) as mock_get_user:
                    mock_get_user.return_value = google_oauth_user

                    with patch(
                        "src.lambdas.dashboard.auth.get_user_by_provider_sub"
                    ) as mock_get_by_sub:
                        mock_get_by_sub.return_value = None

                        result = handle_oauth_callback(
                            table=mock_table,
                            request=request,
                        )

        assert result.status == "error"
        assert result.error == "AUTH_022"

    @freeze_time("2026-01-09 12:00:00")
    def test_oauth_to_oauth_rejects_duplicate_sub(self, mock_table, google_oauth_user):
        """OAuth-to-OAuth link rejects if provider_sub already linked to different user."""
        request = OAuthCallbackRequest(
            provider="github",
            code="github-auth-code",
            state="test-state",
        )

        github_claims = {
            "sub": "github-already-linked-sub",
            "email": "user@gmail.com",
            "email_verified": True,
        }

        # Different user already has this GitHub sub
        different_user = User(
            user_id=str(uuid4()),  # Different user ID
            email="other@example.com",
            auth_type="github",
            role="free",
            verification="verified",
            linked_providers=["github"],
            provider_metadata={},
            pending_email=None,
            primary_email="other@example.com",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        with patch(
            "src.lambdas.dashboard.auth.exchange_code_for_tokens"
        ) as mock_exchange:
            mock_exchange.return_value = CognitoTokens(
                id_token="mock-id-token",
                access_token="mock-access-token",
            )

            with patch("src.lambdas.dashboard.auth.decode_id_token") as mock_decode:
                mock_decode.return_value = github_claims

                with patch(
                    "src.lambdas.dashboard.auth.get_user_by_email_gsi"
                ) as mock_get_user:
                    mock_get_user.return_value = google_oauth_user

                    with patch(
                        "src.lambdas.dashboard.auth.get_user_by_provider_sub"
                    ) as mock_get_by_sub:
                        mock_get_by_sub.return_value = different_user  # Collision!

                        result = handle_oauth_callback(
                            table=mock_table,
                            request=request,
                        )

        assert result.status == "error"
        assert result.error == "AUTH_023"

    @freeze_time("2026-01-09 12:00:00")
    def test_oauth_to_oauth_logs_auto_link_event(self, mock_table, google_oauth_user):
        """OAuth-to-OAuth auto-link logs the appropriate audit event."""
        request = OAuthCallbackRequest(
            provider="github",
            code="github-auth-code",
            state="test-state",
        )

        github_claims = {
            "sub": "github-new-sub-456",
            "email": "user@gmail.com",
            "email_verified": True,
        }

        mock_table.query.return_value = {
            "Items": [google_oauth_user.to_dynamodb_item()]
        }
        mock_table.get_item.return_value = {}
        mock_table.update_item.return_value = {}
        mock_table.put_item.return_value = {}

        with patch(
            "src.lambdas.dashboard.auth.exchange_code_for_tokens"
        ) as mock_exchange:
            mock_exchange.return_value = CognitoTokens(
                id_token="mock-id-token",
                access_token="mock-access-token",
            )

            with patch("src.lambdas.dashboard.auth.decode_id_token") as mock_decode:
                mock_decode.return_value = github_claims

                with patch(
                    "src.lambdas.dashboard.auth.get_user_by_email_gsi"
                ) as mock_get_user:
                    mock_get_user.return_value = google_oauth_user

                    with patch(
                        "src.lambdas.dashboard.auth.get_user_by_provider_sub"
                    ) as mock_get_by_sub:
                        mock_get_by_sub.return_value = None

                        with patch("src.lambdas.dashboard.auth.logger") as mock_logger:
                            handle_oauth_callback(
                                table=mock_table,
                                request=request,
                            )

                            # Check that Flow 5 auto-link was logged
                            info_calls = list(mock_logger.info.call_args_list)
                            flow5_logged = any(
                                "Flow 5" in str(call) for call in info_calls
                            )
                            assert flow5_logged, "Flow 5 auto-link should be logged"

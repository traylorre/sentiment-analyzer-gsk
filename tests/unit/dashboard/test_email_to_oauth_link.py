"""Unit tests for Flow 4: Email-to-OAuth Link.

Tests for link_email_to_oauth_user() and complete_email_link() functions.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from freezegun import freeze_time

from src.lambdas.dashboard.auth import (
    complete_email_link,
    link_email_to_oauth_user,
)
from src.lambdas.shared.errors.session_errors import (
    TokenAlreadyUsedError,
    TokenExpiredError,
)
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
def oauth_user():
    """Create a test OAuth user (authenticated via Google, no email linked)."""
    now = datetime.now(UTC)
    return User(
        user_id=str(uuid4()),
        email=None,
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
        primary_email=None,
        created_at=now,
        last_active_at=now,
        session_expires_at=now + timedelta(days=30),
    )


@pytest.fixture
def oauth_user_with_email_linked(oauth_user):
    """Create a test OAuth user with email already linked."""
    oauth_user.linked_providers = ["google", "email"]
    oauth_user.provider_metadata["email"] = ProviderMetadata(
        sub=None,
        email="user@example.com",
        avatar=None,
        linked_at=datetime.now(UTC),
        verified_at=datetime.now(UTC),
    )
    return oauth_user


class TestLinkEmailToOAuthUser:
    """Tests for link_email_to_oauth_user() - US1."""

    @freeze_time("2026-01-09 12:00:00")
    def test_initiation_success(self, mock_table, oauth_user):
        """T010: OAuth user can initiate email linking successfully."""
        email = "newuser@example.com"

        # Mock DynamoDB operations
        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}
        mock_table.update_item.return_value = {}

        # Use callback for email sending
        mock_send_callback = MagicMock()

        result = link_email_to_oauth_user(
            table=mock_table,
            user=oauth_user,
            email=email,
            send_email_callback=mock_send_callback,
        )

        # Verify magic link was sent via callback
        mock_send_callback.assert_called_once()

        # Verify pending_email was set via update
        mock_table.update_item.assert_called()

        assert result.status == "pending"
        assert result.message == "Verification email sent"

    def test_reject_if_email_already_linked(
        self, mock_table, oauth_user_with_email_linked
    ):
        """T011: Reject if email already linked to user."""
        email = "another@example.com"

        with pytest.raises(ValueError, match="Email already linked"):
            link_email_to_oauth_user(
                table=mock_table,
                user=oauth_user_with_email_linked,
                email=email,
            )

    @freeze_time("2026-01-09 12:00:00")
    def test_pending_email_set_correctly(self, mock_table, oauth_user):
        """T012: pending_email field set correctly on user record."""
        email = "newuser@example.com"

        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}
        mock_table.update_item.return_value = {}

        link_email_to_oauth_user(
            table=mock_table,
            user=oauth_user,
            email=email,
        )

        # Verify update_item was called with pending_email
        call_args = mock_table.update_item.call_args
        update_expr = call_args.kwargs.get("UpdateExpression", "")
        expr_values = call_args.kwargs.get("ExpressionAttributeValues", {})

        assert "pending_email" in update_expr
        assert expr_values.get(":pending_email") == email.lower()

    @freeze_time("2026-01-09 12:00:00")
    def test_magic_link_generated_with_user_id(self, mock_table, oauth_user):
        """T013: Magic link token includes user_id claim for security."""
        email = "newuser@example.com"

        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}
        mock_table.update_item.return_value = {}

        link_email_to_oauth_user(
            table=mock_table,
            user=oauth_user,
            email=email,
        )

        # Verify put_item was called with token containing user_id
        put_call_args = mock_table.put_item.call_args
        item = put_call_args.kwargs.get("Item", {})

        assert item.get("user_id") == oauth_user.user_id
        assert item.get("email") == email.lower()


class TestCompleteEmailLink:
    """Tests for complete_email_link() - US2."""

    @freeze_time("2026-01-09 12:00:00")
    def test_complete_link_success(self, mock_table, oauth_user):
        """T020: Successfully complete email linking."""
        token_id = str(uuid4())
        email = "newuser@example.com"

        # Mock token retrieval
        token_item = {
            "PK": f"TOKEN#{token_id}",
            "SK": "EMAIL_LINK",
            "token_id": token_id,
            "email": email,
            "user_id": oauth_user.user_id,
            "created_at": "2026-01-09T11:55:00+00:00",
            "expires_at": "2026-01-09T12:30:00+00:00",
            "used": False,
        }
        mock_table.get_item.return_value = {"Item": token_item}
        mock_table.update_item.return_value = {}

        result = complete_email_link(
            table=mock_table,
            user=oauth_user,
            token_id=token_id,
            client_ip="192.168.1.1",
        )

        assert result.status == "linked"
        assert "email" in result.linked_providers

    @freeze_time("2026-01-09 12:00:00")
    def test_linked_providers_updated(self, mock_table, oauth_user):
        """T021: linked_providers list is updated to include 'email'."""
        token_id = str(uuid4())
        email = "newuser@example.com"

        token_item = {
            "PK": f"TOKEN#{token_id}",
            "SK": "EMAIL_LINK",
            "token_id": token_id,
            "email": email,
            "user_id": oauth_user.user_id,
            "created_at": "2026-01-09T11:55:00+00:00",
            "expires_at": "2026-01-09T12:30:00+00:00",
            "used": False,
        }
        mock_table.get_item.return_value = {"Item": token_item}
        mock_table.update_item.return_value = {}

        complete_email_link(
            table=mock_table,
            user=oauth_user,
            token_id=token_id,
            client_ip="192.168.1.1",
        )

        # Check update_item was called with linked_providers update
        calls = mock_table.update_item.call_args_list
        provider_update_found = False
        for call in calls:
            update_expr = call.kwargs.get("UpdateExpression", "")
            if "linked_providers" in update_expr:
                provider_update_found = True
                break

        assert provider_update_found, "linked_providers should be updated"

    @freeze_time("2026-01-09 12:00:00")
    def test_provider_metadata_created(self, mock_table, oauth_user):
        """T022: provider_metadata entry created for email provider."""
        token_id = str(uuid4())
        email = "newuser@example.com"

        token_item = {
            "PK": f"TOKEN#{token_id}",
            "SK": "EMAIL_LINK",
            "token_id": token_id,
            "email": email,
            "user_id": oauth_user.user_id,
            "created_at": "2026-01-09T11:55:00+00:00",
            "expires_at": "2026-01-09T12:30:00+00:00",
            "used": False,
        }
        mock_table.get_item.return_value = {"Item": token_item}
        mock_table.update_item.return_value = {}

        complete_email_link(
            table=mock_table,
            user=oauth_user,
            token_id=token_id,
            client_ip="192.168.1.1",
        )

        # Check update_item was called with provider_metadata
        calls = mock_table.update_item.call_args_list
        metadata_update_found = False
        for call in calls:
            update_expr = call.kwargs.get("UpdateExpression", "")
            if "provider_metadata" in update_expr:
                metadata_update_found = True
                break

        assert metadata_update_found, "provider_metadata should be updated"

    @freeze_time("2026-01-09 12:00:00")
    def test_pending_email_cleared(self, mock_table, oauth_user):
        """T023: pending_email is cleared after successful linking."""
        token_id = str(uuid4())
        email = "newuser@example.com"
        oauth_user.pending_email = email  # Simulate pending state

        token_item = {
            "PK": f"TOKEN#{token_id}",
            "SK": "EMAIL_LINK",
            "token_id": token_id,
            "email": email,
            "user_id": oauth_user.user_id,
            "created_at": "2026-01-09T11:55:00+00:00",
            "expires_at": "2026-01-09T12:30:00+00:00",
            "used": False,
        }
        mock_table.get_item.return_value = {"Item": token_item}
        mock_table.update_item.return_value = {}

        complete_email_link(
            table=mock_table,
            user=oauth_user,
            token_id=token_id,
            client_ip="192.168.1.1",
        )

        # Check update_item was called to clear pending_email
        # Implementation uses `:null` as the attribute value name for None
        calls = mock_table.update_item.call_args_list
        pending_cleared = False
        for call in calls:
            update_expr = call.kwargs.get("UpdateExpression", "")
            expr_values = call.kwargs.get("ExpressionAttributeValues", {})
            # Check that pending_email is set to :null and :null is None
            if "pending_email = :null" in update_expr and ":null" in expr_values:
                if expr_values[":null"] is None:
                    pending_cleared = True
                    break

        assert pending_cleared, "pending_email should be cleared"

    @freeze_time("2026-01-09 12:00:00")
    def test_auth_method_linked_event_logged(self, mock_table, oauth_user):
        """T024: AUTH_METHOD_LINKED audit event is logged."""
        token_id = str(uuid4())
        email = "newuser@example.com"

        token_item = {
            "PK": f"TOKEN#{token_id}",
            "SK": "EMAIL_LINK",
            "token_id": token_id,
            "email": email,
            "user_id": oauth_user.user_id,
            "created_at": "2026-01-09T11:55:00+00:00",
            "expires_at": "2026-01-09T12:30:00+00:00",
            "used": False,
        }
        mock_table.get_item.return_value = {"Item": token_item}
        mock_table.update_item.return_value = {}

        with patch("src.lambdas.dashboard.auth.logger") as mock_logger:
            complete_email_link(
                table=mock_table,
                user=oauth_user,
                token_id=token_id,
                client_ip="192.168.1.1",
            )

            # Check that AUTH_METHOD_LINKED was logged
            info_calls = list(mock_logger.info.call_args_list)
            auth_linked_logged = any(
                "AUTH_METHOD_LINKED" in str(call) for call in info_calls
            )
            assert auth_linked_logged, "AUTH_METHOD_LINKED should be logged"


class TestEmailLinkErrorHandling:
    """Tests for error handling - US3."""

    @freeze_time("2026-01-09 12:00:00")
    def test_expired_token_returns_auth_010(self, mock_table, oauth_user):
        """T030: Expired token returns AUTH_010 error."""
        token_id = str(uuid4())
        email = "newuser@example.com"

        # Token expired 5 minutes ago
        token_item = {
            "PK": f"TOKEN#{token_id}",
            "SK": "EMAIL_LINK",
            "token_id": token_id,
            "email": email,
            "user_id": oauth_user.user_id,
            "created_at": "2026-01-09T11:00:00+00:00",
            "expires_at": "2026-01-09T11:55:00+00:00",  # Expired
            "used": False,
        }
        mock_table.get_item.return_value = {"Item": token_item}

        with pytest.raises(TokenExpiredError):
            complete_email_link(
                table=mock_table,
                user=oauth_user,
                token_id=token_id,
                client_ip="192.168.1.1",
            )

    @freeze_time("2026-01-09 12:00:00")
    def test_already_used_token_returns_auth_010(self, mock_table, oauth_user):
        """T031: Already used token returns AUTH_010 error."""
        token_id = str(uuid4())
        email = "newuser@example.com"

        token_item = {
            "PK": f"TOKEN#{token_id}",
            "SK": "EMAIL_LINK",
            "token_id": token_id,
            "email": email,
            "user_id": oauth_user.user_id,
            "created_at": "2026-01-09T11:55:00+00:00",
            "expires_at": "2026-01-09T12:30:00+00:00",
            "used": True,  # Already used
            "used_at": "2026-01-09T11:58:00+00:00",
        }
        mock_table.get_item.return_value = {"Item": token_item}

        with pytest.raises(TokenAlreadyUsedError):
            complete_email_link(
                table=mock_table,
                user=oauth_user,
                token_id=token_id,
                client_ip="192.168.1.1",
            )

    @freeze_time("2026-01-09 12:00:00")
    def test_wrong_user_id_token_returns_auth_010(self, mock_table, oauth_user):
        """T032: Token with different user_id returns AUTH_010 error."""
        token_id = str(uuid4())
        email = "newuser@example.com"
        different_user_id = str(uuid4())  # Different user

        token_item = {
            "PK": f"TOKEN#{token_id}",
            "SK": "EMAIL_LINK",
            "token_id": token_id,
            "email": email,
            "user_id": different_user_id,  # Different user
            "created_at": "2026-01-09T11:55:00+00:00",
            "expires_at": "2026-01-09T12:30:00+00:00",
            "used": False,
        }
        mock_table.get_item.return_value = {"Item": token_item}

        with pytest.raises(ValueError, match="Token does not belong to this user"):
            complete_email_link(
                table=mock_table,
                user=oauth_user,
                token_id=token_id,
                client_ip="192.168.1.1",
            )

    def test_generic_error_message_no_enumeration(self, mock_table, oauth_user):
        """T033: Error messages are generic to prevent enumeration."""
        token_id = str(uuid4())

        # Token not found
        mock_table.get_item.return_value = {}

        with pytest.raises(ValueError, match="Invalid or expired link"):
            complete_email_link(
                table=mock_table,
                user=oauth_user,
                token_id=token_id,
                client_ip="192.168.1.1",
            )

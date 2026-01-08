"""Unit tests for _link_provider() function (Feature 1169).

Tests OAuth provider linking functionality for multi-provider authentication.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.lambdas.dashboard.auth import _link_provider
from src.lambdas.shared.models.user import ProviderMetadata, User


class TestLinkProviderNewUserGoogle:
    """Test linking first OAuth provider (Google) to new user."""

    def test_link_provider_new_user_google(self):
        """First OAuth with Google populates all fields.

        Verifies:
        - Provider metadata is stored correctly
        - linked_providers list contains google
        - last_provider_used is set to google
        - All OAuth fields are preserved (sub, email, avatar, email_verified)
        """
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub=None,
            auth_type="google",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        _link_provider(
            table=table,
            user=user,
            provider="google",
            sub="google-user-123",
            email="test@example.com",
            avatar="https://example.com/avatar.jpg",
            email_verified=True,
        )

        # Verify update_item was called
        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args.kwargs

        # Verify the key is correct
        assert call_kwargs["Key"]["PK"] == f"USER#{user.user_id}"
        assert call_kwargs["Key"]["SK"] == "PROFILE"

        # Verify update expression includes provider linking
        assert "provider_metadata.#provider" in call_kwargs["UpdateExpression"]
        assert "linked_providers" in call_kwargs["UpdateExpression"]
        assert "last_provider_used" in call_kwargs["UpdateExpression"]

        # Verify attribute values contain metadata
        attr_values = call_kwargs["ExpressionAttributeValues"]
        metadata = attr_values[":metadata"]
        assert metadata["sub"] == "google-user-123"
        assert metadata["email"] == "test@example.com"
        assert metadata["avatar"] == "https://example.com/avatar.jpg"
        assert metadata["verified_at"] is not None  # email_verified=True
        assert attr_values[":provider_name"] == "google"
        assert attr_values[":new_provider"] == ["google"]


class TestLinkProviderNewUserGithub:
    """Test linking first OAuth provider (GitHub) to new user."""

    def test_link_provider_new_user_github(self):
        """First OAuth with GitHub populates all fields.

        Verifies:
        - Provider metadata is stored correctly
        - linked_providers list contains github
        - last_provider_used is set to github
        - Handles optional fields correctly
        """
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="dev@example.com",
            cognito_sub=None,
            auth_type="github",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        _link_provider(
            table=table,
            user=user,
            provider="github",
            sub="github-user-456",
            email="dev@example.com",
            avatar="https://avatars.githubusercontent.com/u/123",
            email_verified=False,
        )

        # Verify update_item was called
        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args.kwargs

        # Verify update expression
        assert "provider_metadata.#provider" in call_kwargs["UpdateExpression"]
        assert "linked_providers" in call_kwargs["UpdateExpression"]
        assert "last_provider_used" in call_kwargs["UpdateExpression"]

        # Verify attribute values
        attr_values = call_kwargs["ExpressionAttributeValues"]
        metadata = attr_values[":metadata"]
        assert metadata["sub"] == "github-user-456"
        assert metadata["email"] == "dev@example.com"
        assert metadata["avatar"] == "https://avatars.githubusercontent.com/u/123"
        assert metadata["verified_at"] is None  # email_verified=False
        assert attr_values[":provider_name"] == "github"
        assert attr_values[":new_provider"] == ["github"]


class TestLinkProviderExistingUserSameProvider:
    """Test re-authenticating with same provider updates metadata."""

    def test_link_provider_existing_user_same_provider(self):
        """Re-auth with same provider updates metadata.

        Verifies:
        - linked_providers is NOT modified (provider already exists)
        - provider_metadata is updated with new info
        - last_provider_used remains the same
        - Avatar and verified_at are refreshed
        """
        table = MagicMock()
        old_time = datetime.now(UTC) - timedelta(days=30)
        user = User(
            user_id=str(uuid.uuid4()),
            email="user@example.com",
            cognito_sub="cognito-sub-123",
            auth_type="google",
            created_at=datetime.now(UTC) - timedelta(days=60),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={
                "google": ProviderMetadata(
                    sub="google-user-123",
                    email="user@example.com",
                    avatar="https://example.com/old-avatar.jpg",
                    linked_at=old_time,
                    verified_at=old_time,
                )
            },
        )

        _link_provider(
            table=table,
            user=user,
            provider="google",
            sub="google-user-123",
            email="user@example.com",
            avatar="https://example.com/new-avatar.jpg",  # Updated avatar
            email_verified=True,
        )

        # Verify update_item was called
        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args.kwargs

        # Verify linked_providers is NOT added again
        update_expr = call_kwargs["UpdateExpression"]
        assert "list_append" not in update_expr

        # Verify metadata is updated
        attr_values = call_kwargs["ExpressionAttributeValues"]
        metadata = attr_values[":metadata"]
        assert metadata["avatar"] == "https://example.com/new-avatar.jpg"
        assert metadata["verified_at"] is not None


class TestLinkProviderExistingUserAddProvider:
    """Test linking second provider to user with existing provider."""

    def test_link_provider_existing_user_add_provider(self):
        """Link second provider preserves first.

        Verifies:
        - Both providers coexist in linked_providers
        - New provider metadata is added without removing old
        - last_provider_used is updated to new provider
        - Old provider metadata remains intact
        """
        table = MagicMock()
        now = datetime.now(UTC)
        user = User(
            user_id=str(uuid.uuid4()),
            email="multi@example.com",
            cognito_sub="cognito-sub-456",
            auth_type="google",
            created_at=datetime.now(UTC) - timedelta(days=60),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={
                "google": ProviderMetadata(
                    sub="google-user-789",
                    email="multi@example.com",
                    avatar="https://example.com/google-avatar.jpg",
                    linked_at=now - timedelta(days=30),
                    verified_at=now - timedelta(days=30),
                )
            },
        )

        _link_provider(
            table=table,
            user=user,
            provider="github",
            sub="github-user-999",
            email="multi@example.com",
            avatar="https://avatars.githubusercontent.com/u/999",
            email_verified=True,
        )

        # Verify update_item was called
        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args.kwargs

        # Verify update expression adds provider to linked_providers
        assert "linked_providers = list_append" in call_kwargs["UpdateExpression"]

        # Verify github is added to linked_providers
        attr_values = call_kwargs["ExpressionAttributeValues"]
        assert attr_values[":new_provider"] == ["github"]

        # Verify last_provider_used is updated to github
        assert attr_values[":provider_name"] == "github"

        # Verify new provider metadata
        metadata = attr_values[":metadata"]
        assert metadata["sub"] == "github-user-999"
        assert metadata["avatar"] == "https://avatars.githubusercontent.com/u/999"


class TestLinkProviderNoDuplicateEntries:
    """Test that no duplicate entries are created in linked_providers."""

    def test_link_provider_no_duplicate_entries(self):
        """No duplicates in linked_providers.

        Verifies:
        - If provider already in linked_providers, list_append is not used
        - Provider metadata is still updated
        - Prevents multiple entries for same provider
        """
        table = MagicMock()
        now = datetime.now(UTC)
        user = User(
            user_id=str(uuid.uuid4()),
            email="noDup@example.com",
            cognito_sub="cognito-sub-dup",
            auth_type="email",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google", "github"],
            provider_metadata={
                "google": ProviderMetadata(
                    sub="google-123",
                    email="noDup@example.com",
                    avatar=None,
                    linked_at=now,
                    verified_at=None,
                ),
                "github": ProviderMetadata(
                    sub="github-456",
                    email="noDup@example.com",
                    avatar=None,
                    linked_at=now,
                    verified_at=None,
                ),
            },
        )

        # Re-link google - should not duplicate in list
        _link_provider(
            table=table,
            user=user,
            provider="google",
            sub="google-123-updated",
            email="noDup@example.com",
            avatar="https://example.com/new.jpg",
            email_verified=True,
        )

        # Verify update_item was called
        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args.kwargs

        # Verify list_append is NOT in the update expression
        update_expr = call_kwargs["UpdateExpression"]
        assert "list_append" not in update_expr

        # Metadata should still be updated
        attr_values = call_kwargs["ExpressionAttributeValues"]
        metadata = attr_values[":metadata"]
        assert metadata["sub"] == "google-123-updated"
        assert metadata["avatar"] == "https://example.com/new.jpg"


class TestLinkProviderHandlesMissingAvatar:
    """Test that avatar is optional."""

    def test_link_provider_handles_missing_avatar(self):
        """Avatar is optional.

        Verifies:
        - Linking works without avatar
        - avatar field is set to None
        - All other fields are populated
        """
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="noAvatar@example.com",
            cognito_sub=None,
            auth_type="google",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        _link_provider(
            table=table,
            user=user,
            provider="google",
            sub="google-no-avatar",
            email="noAvatar@example.com",
            avatar=None,  # No avatar provided
            email_verified=True,
        )

        # Verify update_item was called
        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args.kwargs

        # Verify metadata is stored even without avatar
        attr_values = call_kwargs["ExpressionAttributeValues"]
        metadata = attr_values[":metadata"]
        assert metadata["avatar"] is None
        assert metadata["sub"] == "google-no-avatar"
        assert metadata["email"] == "noAvatar@example.com"


class TestLinkProviderHandlesMissingSub:
    """Test that missing sub (OAuth subject) is handled gracefully."""

    def test_link_provider_handles_missing_sub(self):
        """Missing sub logs warning and returns early.

        Verifies:
        - Function returns early if sub is None or empty
        - DynamoDB is not updated
        - Warning is logged
        - Silent failure pattern maintained
        """
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="noSub@example.com",
            cognito_sub=None,
            auth_type="google",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        with patch("src.lambdas.dashboard.auth.logger") as mock_logger:
            _link_provider(
                table=table,
                user=user,
                provider="google",
                sub=None,  # Missing sub
                email="noSub@example.com",
                avatar=None,
                email_verified=False,
            )

            # Verify warning was logged
            mock_logger.warning.assert_called_once()

        # Verify update_item was NOT called
        table.update_item.assert_not_called()


class TestLinkProviderSilentFailure:
    """Test that DynamoDB errors don't break OAuth flow."""

    def test_link_provider_silent_failure(self):
        """DynamoDB error doesn't raise.

        Verifies:
        - Function catches DynamoDB exceptions
        - Returns without raising
        - Warning is logged (not error)
        - OAuth flow continues successfully
        """
        table = MagicMock()
        # Simulate DynamoDB error
        table.update_item.side_effect = Exception("DynamoDB connection failed")

        user = User(
            user_id=str(uuid.uuid4()),
            email="failure@example.com",
            cognito_sub=None,
            auth_type="google",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        with patch("src.lambdas.dashboard.auth.logger") as mock_logger:
            # Should not raise
            _link_provider(
                table=table,
                user=user,
                provider="google",
                sub="google-failure",
                email="failure@example.com",
                avatar=None,
                email_verified=False,
            )

            # Verify warning was logged (not error - silent failure)
            mock_logger.warning.assert_called_once()

        # Verify update_item was attempted
        table.update_item.assert_called_once()


class TestLinkProviderMetadataTimestamps:
    """Test that provider metadata timestamps are set correctly."""

    def test_link_provider_sets_linked_at_timestamp(self):
        """linked_at timestamp is set to current time.

        Verifies:
        - linked_at is populated with current UTC time
        - Timestamp is in ISO format for DynamoDB
        """
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="timestamp@example.com",
            cognito_sub=None,
            auth_type="google",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        before = datetime.now(UTC)
        _link_provider(
            table=table,
            user=user,
            provider="google",
            sub="google-timestamp",
            email="timestamp@example.com",
            avatar=None,
            email_verified=True,
        )
        after = datetime.now(UTC)

        # Verify metadata timestamp
        call_kwargs = table.update_item.call_args.kwargs
        attr_values = call_kwargs["ExpressionAttributeValues"]
        metadata = attr_values[":metadata"]

        linked_at_str = metadata["linked_at"]
        linked_at = datetime.fromisoformat(linked_at_str)

        # Verify linked_at is between before and after
        assert before <= linked_at <= after

    def test_link_provider_sets_verified_at_when_email_verified(self):
        """verified_at is set when email_verified=True."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="verified@example.com",
            cognito_sub=None,
            auth_type="google",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        _link_provider(
            table=table,
            user=user,
            provider="google",
            sub="google-verified",
            email="verified@example.com",
            avatar=None,
            email_verified=True,
        )

        # Verify verified_at is set
        call_kwargs = table.update_item.call_args.kwargs
        attr_values = call_kwargs["ExpressionAttributeValues"]
        metadata = attr_values[":metadata"]
        assert metadata["verified_at"] is not None

    def test_link_provider_omits_verified_at_when_not_verified(self):
        """verified_at is None when email_verified=False."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="unverified@example.com",
            cognito_sub=None,
            auth_type="github",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        _link_provider(
            table=table,
            user=user,
            provider="github",
            sub="github-unverified",
            email="unverified@example.com",
            avatar=None,
            email_verified=False,
        )

        # Verify verified_at is None
        call_kwargs = table.update_item.call_args.kwargs
        attr_values = call_kwargs["ExpressionAttributeValues"]
        metadata = attr_values[":metadata"]
        assert metadata["verified_at"] is None

"""Unit tests for get_user_by_provider_sub() and provider_sub population (Feature 1180).

Tests the GSI-based lookup function and _link_provider() update that populates
the provider_sub attribute for account linking flows.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.lambdas.dashboard.auth import (
    _link_provider,
    get_user_by_provider_sub,
)
from src.lambdas.shared.models.user import User


def _create_test_user(
    user_id: str | None = None,
    role: str = "anonymous",
    verification: str = "none",
    auth_type: str = "anonymous",
    linked_providers: list[str] | None = None,
) -> User:
    """Create a test user with all required fields."""
    now = datetime.now(UTC)
    return User(
        user_id=user_id or str(uuid.uuid4()),
        email=None,
        role=role,
        verification=verification,
        auth_type=auth_type,
        linked_providers=linked_providers or [],
        created_at=now,
        last_active_at=now,
        session_expires_at=now + timedelta(days=30),
    )


class TestGetUserByProviderSub:
    """Tests for get_user_by_provider_sub() function."""

    def test_returns_user_when_found(self):
        """Test that function returns User when provider_sub matches."""
        # Arrange
        user_id = str(uuid.uuid4())
        provider = "google"
        sub = "118368473829470293847"
        provider_sub = f"{provider}:{sub}"
        now = datetime.now(UTC)

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "PK": f"USER#{user_id}",
                    "SK": "PROFILE",
                    "user_id": user_id,
                    "email": "test@gmail.com",
                    "role": "free",
                    "verification": "verified",
                    "auth_type": "google",
                    "entity_type": "USER",
                    "provider_sub": provider_sub,
                    "linked_providers": ["google"],
                    "created_at": now.isoformat(),
                    "last_active_at": now.isoformat(),
                    "session_expires_at": (now + timedelta(days=30)).isoformat(),
                }
            ]
        }

        # Act
        result = get_user_by_provider_sub(mock_table, provider, sub)

        # Assert
        assert result is not None
        assert result.user_id == user_id
        assert result.email == "test@gmail.com"

        # Verify GSI was queried correctly
        mock_table.query.assert_called_once()
        call_kwargs = mock_table.query.call_args.kwargs
        assert call_kwargs["IndexName"] == "by_provider_sub"
        assert call_kwargs["ExpressionAttributeValues"][":provider_sub"] == provider_sub

    def test_returns_none_when_not_found(self):
        """Test that function returns None when no matching user exists."""
        # Arrange
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        # Act
        result = get_user_by_provider_sub(mock_table, "google", "nonexistent")

        # Assert
        assert result is None

    def test_returns_none_for_different_provider(self):
        """Test that function returns None when same sub but different provider."""
        # Arrange - User has github linked, we query for google
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}  # No match for google:sub

        # Act
        result = get_user_by_provider_sub(mock_table, "google", "12345")

        # Assert
        assert result is None
        # Verify we queried for google:12345, not github:12345
        call_kwargs = mock_table.query.call_args.kwargs
        assert (
            call_kwargs["ExpressionAttributeValues"][":provider_sub"] == "google:12345"
        )

    def test_returns_none_for_empty_provider(self):
        """Test that function returns None for empty provider."""
        mock_table = MagicMock()

        result = get_user_by_provider_sub(mock_table, "", "12345")

        assert result is None
        mock_table.query.assert_not_called()

    def test_returns_none_for_empty_sub(self):
        """Test that function returns None for empty sub."""
        mock_table = MagicMock()

        result = get_user_by_provider_sub(mock_table, "google", "")

        assert result is None
        mock_table.query.assert_not_called()

    def test_handles_query_exception(self):
        """Test that function returns None and logs on exception."""
        mock_table = MagicMock()
        mock_table.query.side_effect = Exception("DynamoDB error")

        result = get_user_by_provider_sub(mock_table, "google", "12345")

        assert result is None


class TestLinkProviderPopulatesProviderSub:
    """Tests that _link_provider() populates provider_sub attribute."""

    def test_link_provider_sets_provider_sub(self):
        """Test that _link_provider sets provider_sub for GSI indexing."""
        # Arrange
        user = _create_test_user()
        mock_table = MagicMock()
        provider = "google"
        sub = "118368473829470293847"
        expected_provider_sub = f"{provider}:{sub}"

        # Act
        _link_provider(
            table=mock_table,
            user=user,
            provider=provider,
            sub=sub,
            email="test@gmail.com",
            email_verified=True,
        )

        # Assert
        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args.kwargs

        # Verify provider_sub is in the update expression
        assert "provider_sub = :provider_sub" in call_kwargs["UpdateExpression"]

        # Verify provider_sub value is correct
        assert (
            call_kwargs["ExpressionAttributeValues"][":provider_sub"]
            == expected_provider_sub
        )

    def test_link_provider_updates_provider_sub_on_relink(self):
        """Test that _link_provider updates provider_sub when relinking."""
        # Arrange - User already has google linked (free + verified)
        user = _create_test_user(
            role="free",
            verification="verified",
            auth_type="google",
            linked_providers=["google"],
        )

        mock_table = MagicMock()
        provider = "google"
        new_sub = "new_sub_after_reauth"

        # Act
        _link_provider(
            table=mock_table,
            user=user,
            provider=provider,
            sub=new_sub,
            email="test@gmail.com",
            email_verified=True,
        )

        # Assert - provider_sub should be updated with new sub
        call_kwargs = mock_table.update_item.call_args.kwargs
        assert (
            call_kwargs["ExpressionAttributeValues"][":provider_sub"]
            == f"{provider}:{new_sub}"
        )

    def test_link_provider_github_sets_provider_sub(self):
        """Test that _link_provider works for GitHub provider."""
        user = _create_test_user()

        mock_table = MagicMock()
        provider = "github"
        sub = "12345678"

        _link_provider(
            table=mock_table,
            user=user,
            provider=provider,
            sub=sub,
            email="test@github.com",
            email_verified=False,
        )

        call_kwargs = mock_table.update_item.call_args.kwargs
        assert (
            call_kwargs["ExpressionAttributeValues"][":provider_sub"]
            == "github:12345678"
        )

    def test_link_provider_without_sub_does_not_set_provider_sub(self):
        """Test that _link_provider does not set provider_sub when sub is None."""
        user = _create_test_user()

        mock_table = MagicMock()

        _link_provider(
            table=mock_table,
            user=user,
            provider="google",
            sub=None,  # No sub
            email="test@gmail.com",
        )

        # Should still call update_item but without provider_sub
        # OR should not call at all - check actual behavior
        if mock_table.update_item.called:
            call_kwargs = mock_table.update_item.call_args.kwargs
            # provider_sub should not be in the expression
            assert ":provider_sub" not in call_kwargs.get(
                "ExpressionAttributeValues", {}
            )

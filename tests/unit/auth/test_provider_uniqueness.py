"""Tests for provider sub uniqueness enforcement (Feature 1222, US1)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.shared.models.user import User

_NOW = datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)
_EXPIRES = _NOW + timedelta(days=30)


@pytest.fixture
def mock_table():
    return MagicMock()


@pytest.fixture
def user_a():
    return User(
        user_id="aaaa1111-0000-0000-0000-000000000001",
        role="free",
        verification="verified",
        linked_providers=["google"],
        provider_metadata={},
        created_at=_NOW,
        last_active_at=_NOW,
        session_expires_at=_EXPIRES,
    )


@pytest.fixture
def user_b():
    return User(
        user_id="bbbb2222-0000-0000-0000-000000000002",
        role="free",
        verification="verified",
        linked_providers=["google"],
        provider_metadata={},
        created_at=_NOW,
        last_active_at=_NOW,
        session_expires_at=_EXPIRES,
    )


class TestProviderUniqueness:
    """FR-001, FR-002: Provider sub uniqueness enforcement."""

    @patch("src.lambdas.dashboard.auth.get_user_by_provider_sub")
    def test_link_succeeds_when_sub_unlinked(self, mock_get_user, mock_table, user_a):
        """Linking succeeds when no other user owns the provider sub."""
        mock_get_user.return_value = None  # No existing owner

        from src.lambdas.dashboard.auth import _link_provider

        _link_provider(
            table=mock_table,
            user=user_a,
            provider="google",
            sub="new-sub-123",
            email="a@example.com",
        )

        # Should proceed to update_item (not return early)
        mock_table.update_item.assert_called_once()

    @patch("src.lambdas.dashboard.auth.get_user_by_provider_sub")
    def test_link_rejected_when_sub_owned_by_different_user(
        self, mock_get_user, mock_table, user_a, user_b
    ):
        """Linking fails when provider sub is already owned by another user."""
        mock_get_user.return_value = user_b  # User B owns this sub

        from src.lambdas.dashboard.auth import _link_provider

        _link_provider(
            table=mock_table,
            user=user_a,
            provider="google",
            sub="existing-sub-456",
            email="a@example.com",
        )

        # Should NOT call update_item (returned early)
        mock_table.update_item.assert_not_called()

    @patch("src.lambdas.dashboard.auth.get_user_by_provider_sub")
    def test_idempotent_relink_by_same_user(self, mock_get_user, mock_table, user_a):
        """Relinking by the same user is allowed (idempotent)."""
        mock_get_user.return_value = user_a  # Same user owns it

        from src.lambdas.dashboard.auth import _link_provider

        _link_provider(
            table=mock_table,
            user=user_a,
            provider="google",
            sub="my-existing-sub",
            email="a@example.com",
        )

        # Should proceed to update_item (idempotent re-link)
        mock_table.update_item.assert_called_once()

    @patch("src.lambdas.dashboard.auth.get_user_by_provider_sub")
    def test_error_message_is_generic(
        self, mock_get_user, mock_table, user_a, user_b, caplog
    ):
        """FR-010: Error must not reveal which user owns the provider sub."""
        mock_get_user.return_value = user_b

        from src.lambdas.dashboard.auth import _link_provider

        _link_provider(
            table=mock_table,
            user=user_a,
            provider="google",
            sub="stolen-sub",
            email="a@example.com",
        )

        # Verify log doesn't contain user_b's full user_id
        for record in caplog.records:
            assert user_b.user_id not in record.getMessage()

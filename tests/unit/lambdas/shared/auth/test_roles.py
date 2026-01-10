"""Unit tests for get_roles_for_user function (Feature 1150).

Tests role assignment logic based on user state.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.auth.enums import Role
from src.lambdas.shared.auth.roles import get_roles_for_user


class TestGetRolesForUser:
    """Test get_roles_for_user function."""

    @pytest.fixture
    def mock_user(self) -> MagicMock:
        """Create a mock User object for testing.

        Returns a MagicMock that simulates a User without RBAC fields,
        allowing getattr() to return AttributeError for missing attributes.
        """
        user = MagicMock()
        # Configure to raise AttributeError for RBAC fields (simulating pre-1151 User)
        del user.subscription_active
        del user.subscription_expires_at
        del user.is_operator
        return user

    @pytest.fixture
    def mock_user_with_rbac(self) -> MagicMock:
        """Create a mock User with all RBAC fields."""
        user = MagicMock()
        user.subscription_active = False
        user.subscription_expires_at = None
        user.is_operator = False
        return user

    def test_anonymous_user_gets_anonymous_role(self, mock_user: MagicMock) -> None:
        """Anonymous users should only get the anonymous role."""
        mock_user.auth_type = "anonymous"

        roles = get_roles_for_user(mock_user)

        assert roles == [Role.ANONYMOUS.value]
        assert roles == ["anonymous"]

    def test_email_authenticated_user_gets_free_role(
        self, mock_user: MagicMock
    ) -> None:
        """Email-authenticated users should get the free role."""
        mock_user.auth_type = "email"

        roles = get_roles_for_user(mock_user)

        assert roles == [Role.FREE.value]
        assert roles == ["free"]

    def test_google_authenticated_user_gets_free_role(
        self, mock_user: MagicMock
    ) -> None:
        """Google-authenticated users should get the free role."""
        mock_user.auth_type = "google"

        roles = get_roles_for_user(mock_user)

        assert roles == ["free"]

    def test_github_authenticated_user_gets_free_role(
        self, mock_user: MagicMock
    ) -> None:
        """GitHub-authenticated users should get the free role."""
        mock_user.auth_type = "github"

        roles = get_roles_for_user(mock_user)

        assert roles == ["free"]

    def test_paid_user_gets_free_and_paid_roles(
        self, mock_user_with_rbac: MagicMock
    ) -> None:
        """Users with active subscription should get free and paid roles."""
        mock_user_with_rbac.auth_type = "email"
        mock_user_with_rbac.subscription_active = True

        roles = get_roles_for_user(mock_user_with_rbac)

        assert roles == ["free", "paid"]

    def test_paid_user_with_future_expiry_gets_paid_role(
        self, mock_user_with_rbac: MagicMock
    ) -> None:
        """Users with future subscription expiry should get paid role."""
        mock_user_with_rbac.auth_type = "email"
        mock_user_with_rbac.subscription_active = True
        mock_user_with_rbac.subscription_expires_at = datetime.now(UTC) + timedelta(
            days=30
        )

        roles = get_roles_for_user(mock_user_with_rbac)

        assert roles == ["free", "paid"]

    def test_expired_subscription_gets_only_free_role(
        self, mock_user_with_rbac: MagicMock
    ) -> None:
        """Users with expired subscription should only get free role."""
        mock_user_with_rbac.auth_type = "email"
        mock_user_with_rbac.subscription_active = True
        mock_user_with_rbac.subscription_expires_at = datetime.now(UTC) - timedelta(
            days=1
        )

        roles = get_roles_for_user(mock_user_with_rbac)

        assert roles == ["free"]

    def test_operator_gets_all_roles(self, mock_user_with_rbac: MagicMock) -> None:
        """Operators should get free, paid, and operator roles."""
        mock_user_with_rbac.auth_type = "email"
        mock_user_with_rbac.is_operator = True

        roles = get_roles_for_user(mock_user_with_rbac)

        assert roles == ["free", "paid", "operator"]

    def test_operator_with_active_subscription(
        self, mock_user_with_rbac: MagicMock
    ) -> None:
        """Operators with subscription should still get all three roles (no duplicates)."""
        mock_user_with_rbac.auth_type = "email"
        mock_user_with_rbac.subscription_active = True
        mock_user_with_rbac.is_operator = True

        roles = get_roles_for_user(mock_user_with_rbac)

        assert roles == ["free", "paid", "operator"]
        # Verify no duplicates
        assert len(roles) == len(set(roles))

    def test_anonymous_cannot_be_operator(self, mock_user_with_rbac: MagicMock) -> None:
        """Anonymous users cannot have operator role, even if flag is set."""
        mock_user_with_rbac.auth_type = "anonymous"
        mock_user_with_rbac.is_operator = True  # This should be ignored

        roles = get_roles_for_user(mock_user_with_rbac)

        assert roles == ["anonymous"]
        assert "operator" not in roles

    def test_anonymous_cannot_be_paid(self, mock_user_with_rbac: MagicMock) -> None:
        """Anonymous users cannot have paid role, even if subscription is active."""
        mock_user_with_rbac.auth_type = "anonymous"
        mock_user_with_rbac.subscription_active = True  # This should be ignored

        roles = get_roles_for_user(mock_user_with_rbac)

        assert roles == ["anonymous"]
        assert "paid" not in roles

    def test_user_without_rbac_fields_defaults_to_free(
        self, mock_user: MagicMock
    ) -> None:
        """Users without RBAC fields (pre-1151) should default to free role."""
        mock_user.auth_type = "email"

        roles = get_roles_for_user(mock_user)

        assert roles == ["free"]

    def test_naive_datetime_expiry_comparison(
        self, mock_user_with_rbac: MagicMock
    ) -> None:
        """Handle naive datetime for subscription_expires_at."""
        mock_user_with_rbac.auth_type = "email"
        mock_user_with_rbac.subscription_active = True
        # Naive datetime (no timezone) - should be treated as UTC
        mock_user_with_rbac.subscription_expires_at = datetime.now(UTC).replace(
            tzinfo=None
        ) + timedelta(days=30)

        roles = get_roles_for_user(mock_user_with_rbac)

        assert "paid" in roles

    def test_roles_use_canonical_enum_values(
        self, mock_user_with_rbac: MagicMock
    ) -> None:
        """Verify returned roles use the canonical Role enum values."""
        mock_user_with_rbac.auth_type = "email"
        mock_user_with_rbac.subscription_active = True
        mock_user_with_rbac.is_operator = True

        roles = get_roles_for_user(mock_user_with_rbac)

        # All roles should be valid Role enum values
        from src.lambdas.shared.auth.enums import VALID_ROLES

        for role in roles:
            assert role in VALID_ROLES, f"Role '{role}' not in VALID_ROLES"


class TestGetRolesForUserEdgeCases:
    """Edge case tests for get_roles_for_user."""

    def test_subscription_active_false_with_future_expiry(self) -> None:
        """subscription_active=False should mean no paid role even with future expiry."""
        user = MagicMock()
        user.auth_type = "email"
        user.subscription_active = False
        user.subscription_expires_at = datetime.now(UTC) + timedelta(days=30)
        user.is_operator = False

        roles = get_roles_for_user(user)

        assert roles == ["free"]
        assert "paid" not in roles

    def test_none_subscription_expires_at_with_active(self) -> None:
        """subscription_expires_at=None with subscription_active=True means no expiry."""
        user = MagicMock()
        user.auth_type = "email"
        user.subscription_active = True
        user.subscription_expires_at = None  # Lifetime subscription
        user.is_operator = False

        roles = get_roles_for_user(user)

        assert roles == ["free", "paid"]

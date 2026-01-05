"""Unit tests for RBAC constants (Feature 1130).

Tests:
- Role enum values
- VALID_ROLES frozenset
- Role validation behavior
"""

from __future__ import annotations

import pytest

from src.lambdas.shared.auth.constants import VALID_ROLES, Role


class TestRoleEnum:
    """Tests for the Role enum."""

    def test_role_has_four_values(self) -> None:
        """Role enum should have exactly 4 canonical roles."""
        assert len(Role) == 4

    def test_anonymous_value(self) -> None:
        """Role.ANONYMOUS should have value 'anonymous'."""
        assert Role.ANONYMOUS == "anonymous"
        assert Role.ANONYMOUS.value == "anonymous"

    def test_free_value(self) -> None:
        """Role.FREE should have value 'free'."""
        assert Role.FREE == "free"
        assert Role.FREE.value == "free"

    def test_paid_value(self) -> None:
        """Role.PAID should have value 'paid'."""
        assert Role.PAID == "paid"
        assert Role.PAID.value == "paid"

    def test_operator_value(self) -> None:
        """Role.OPERATOR should have value 'operator'."""
        assert Role.OPERATOR == "operator"
        assert Role.OPERATOR.value == "operator"

    def test_role_is_str_enum(self) -> None:
        """Role should be a StrEnum for string comparisons."""
        # Can compare directly with strings
        assert Role.OPERATOR == "operator"
        assert "operator" == Role.OPERATOR

    def test_role_can_be_used_in_string_operations(self) -> None:
        """Role values should work in string operations."""
        role = Role.OPERATOR
        assert f"User has {role} role" == "User has operator role"


class TestValidRoles:
    """Tests for the VALID_ROLES constant."""

    def test_valid_roles_is_frozenset(self) -> None:
        """VALID_ROLES should be immutable (frozenset)."""
        assert isinstance(VALID_ROLES, frozenset)

    def test_valid_roles_contains_all_role_values(self) -> None:
        """VALID_ROLES should contain all Role enum values."""
        expected = {"anonymous", "free", "paid", "operator"}
        assert VALID_ROLES == expected

    def test_valid_roles_membership_check_is_o1(self) -> None:
        """VALID_ROLES should support O(1) membership check."""
        # This test documents the performance expectation
        # frozenset provides O(1) average case for 'in' operator
        assert "operator" in VALID_ROLES
        assert "admin" not in VALID_ROLES

    def test_valid_roles_cannot_be_modified(self) -> None:
        """VALID_ROLES should be immutable."""
        with pytest.raises(AttributeError):
            VALID_ROLES.add("admin")  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "role",
        ["anonymous", "free", "paid", "operator"],
    )
    def test_all_canonical_roles_are_valid(self, role: str) -> None:
        """All canonical role strings should be in VALID_ROLES."""
        assert role in VALID_ROLES

    @pytest.mark.parametrize(
        "invalid_role",
        ["admin", "superuser", "root", "OPERATOR", "Operator", "", "admn"],
    )
    def test_invalid_roles_not_in_valid_roles(self, invalid_role: str) -> None:
        """Non-canonical role strings should not be in VALID_ROLES."""
        assert invalid_role not in VALID_ROLES

"""Tests for User model role-verification state machine invariants.

Feature 1163: Tests the @model_validator that enforces the role-verification
state matrix from spec-v2.md.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.lambdas.shared.models.user import User


class TestRoleVerificationInvariant:
    """Test suite for role-verification state machine validation."""

    # Shared test fixtures
    @pytest.fixture
    def base_user_kwargs(self) -> dict:
        """Common user attributes for all tests."""
        now = datetime.now(UTC)
        return {
            "user_id": "test-user-123",
            "created_at": now,
            "last_active_at": now,
            "session_expires_at": now + timedelta(days=30),
        }

    # =========================================================================
    # Valid State Combinations
    # =========================================================================

    def test_anonymous_none_valid(self, base_user_kwargs: dict) -> None:
        """anonymous:none is a valid state (default for new users)."""
        user = User(**base_user_kwargs, role="anonymous", verification="none")
        assert user.role == "anonymous"
        assert user.verification == "none"

    def test_anonymous_pending_valid(self, base_user_kwargs: dict) -> None:
        """anonymous:pending is a valid state (user started email verification)."""
        user = User(**base_user_kwargs, role="anonymous", verification="pending")
        assert user.role == "anonymous"
        assert user.verification == "pending"

    def test_free_verified_valid(self, base_user_kwargs: dict) -> None:
        """free:verified is a valid state (completed verification)."""
        user = User(**base_user_kwargs, role="free", verification="verified")
        assert user.role == "free"
        assert user.verification == "verified"

    def test_paid_verified_valid(self, base_user_kwargs: dict) -> None:
        """paid:verified is a valid state (subscribed user)."""
        user = User(**base_user_kwargs, role="paid", verification="verified")
        assert user.role == "paid"
        assert user.verification == "verified"

    def test_operator_verified_valid(self, base_user_kwargs: dict) -> None:
        """operator:verified is a valid state (admin user)."""
        user = User(**base_user_kwargs, role="operator", verification="verified")
        assert user.role == "operator"
        assert user.verification == "verified"

    # =========================================================================
    # Auto-upgrade: anonymous:verified → free:verified
    # =========================================================================

    def test_anonymous_verified_auto_upgrades_to_free(
        self, base_user_kwargs: dict
    ) -> None:
        """anonymous:verified auto-upgrades to free:verified.

        Per FR-002: System MUST automatically upgrade role from 'anonymous' to
        'free' when verification is set to 'verified' on an anonymous user.
        """
        user = User(**base_user_kwargs, role="anonymous", verification="verified")
        # Validator auto-upgrades the role
        assert user.role == "free"
        assert user.verification == "verified"

    # =========================================================================
    # Invalid State Rejection: Non-anonymous requires verified
    # =========================================================================

    def test_free_none_raises_valueerror(self, base_user_kwargs: dict) -> None:
        """free:none is invalid - free role requires verified status."""
        with pytest.raises(ValueError, match="free role requires verified status"):
            User(**base_user_kwargs, role="free", verification="none")

    def test_free_pending_raises_valueerror(self, base_user_kwargs: dict) -> None:
        """free:pending is invalid - free role requires verified status."""
        with pytest.raises(ValueError, match="free role requires verified status"):
            User(**base_user_kwargs, role="free", verification="pending")

    def test_paid_none_raises_valueerror(self, base_user_kwargs: dict) -> None:
        """paid:none is invalid - paid role requires verified status."""
        with pytest.raises(ValueError, match="paid role requires verified status"):
            User(**base_user_kwargs, role="paid", verification="none")

    def test_paid_pending_raises_valueerror(self, base_user_kwargs: dict) -> None:
        """paid:pending is invalid - paid role requires verified status."""
        with pytest.raises(ValueError, match="paid role requires verified status"):
            User(**base_user_kwargs, role="paid", verification="pending")

    def test_operator_none_raises_valueerror(self, base_user_kwargs: dict) -> None:
        """operator:none is invalid - operator role requires verified status."""
        with pytest.raises(ValueError, match="operator role requires verified status"):
            User(**base_user_kwargs, role="operator", verification="none")

    def test_operator_pending_raises_valueerror(self, base_user_kwargs: dict) -> None:
        """operator:pending is invalid - operator role requires verified status."""
        with pytest.raises(ValueError, match="operator role requires verified status"):
            User(**base_user_kwargs, role="operator", verification="pending")

    # =========================================================================
    # Backward Compatibility
    # =========================================================================

    def test_legacy_item_without_role_verification_valid(self) -> None:
        """Legacy DynamoDB items without role/verification fields load with valid defaults.

        Default is anonymous:none, which is a valid state.
        """
        now = datetime.now(UTC)
        legacy_item = {
            "PK": "USER#legacy-user-456",
            "SK": "PROFILE",
            "user_id": "legacy-user-456",
            "auth_type": "anonymous",
            "created_at": now.isoformat(),
            "last_active_at": now.isoformat(),
            "session_expires_at": (now + timedelta(days=30)).isoformat(),
            # Note: no role or verification fields
        }
        user = User.from_dynamodb_item(legacy_item)
        # Defaults should be applied
        assert user.role == "anonymous"
        assert user.verification == "none"

    def test_roundtrip_preserves_valid_state(self, base_user_kwargs: dict) -> None:
        """Valid state survives DynamoDB roundtrip."""
        original = User(**base_user_kwargs, role="free", verification="verified")

        # Convert to DynamoDB item and back
        item = original.to_dynamodb_item()
        restored = User.from_dynamodb_item(item)

        assert restored.role == original.role
        assert restored.verification == original.verification

    def test_default_user_is_valid(self, base_user_kwargs: dict) -> None:
        """User with all defaults passes validation."""
        user = User(**base_user_kwargs)
        # Defaults are anonymous:none, which is valid
        assert user.role == "anonymous"
        assert user.verification == "none"


class TestRoleVerificationEdgeCases:
    """Edge cases for role-verification validation."""

    @pytest.fixture
    def base_user_kwargs(self) -> dict:
        """Common user attributes for all tests."""
        now = datetime.now(UTC)
        return {
            "user_id": "edge-case-user",
            "created_at": now,
            "last_active_at": now,
            "session_expires_at": now + timedelta(days=30),
        }

    def test_error_message_includes_actual_verification_state(
        self, base_user_kwargs: dict
    ) -> None:
        """Error message shows the actual verification value for debugging."""
        with pytest.raises(ValueError) as exc_info:
            User(**base_user_kwargs, role="paid", verification="pending")
        assert "verification=pending" in str(exc_info.value)

    def test_error_message_includes_role(self, base_user_kwargs: dict) -> None:
        """Error message shows the role for debugging."""
        with pytest.raises(ValueError) as exc_info:
            User(**base_user_kwargs, role="operator", verification="none")
        assert "operator role" in str(exc_info.value)

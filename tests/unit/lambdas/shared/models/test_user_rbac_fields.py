"""Tests for User model RBAC fields (Feature 1151).

Tests the subscription_active, subscription_expires_at, and is_operator
fields added to support get_roles_for_user() function.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.lambdas.shared.models.user import User


class TestUserRBACFieldsDefaults:
    """Test default values for RBAC fields."""

    def test_subscription_active_defaults_to_false(self):
        """New users should not have active subscriptions by default."""
        user = User(
            user_id="test-123",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        assert user.subscription_active is False

    def test_subscription_expires_at_defaults_to_none(self):
        """New users should not have subscription expiry by default."""
        user = User(
            user_id="test-123",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        assert user.subscription_expires_at is None

    def test_is_operator_defaults_to_false(self):
        """New users should not be operators by default."""
        user = User(
            user_id="test-123",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        assert user.is_operator is False


class TestUserRBACFieldsSerialization:
    """Test to_dynamodb_item() serialization of RBAC fields."""

    @pytest.fixture
    def base_user(self):
        """Create a base user for testing."""
        return User(
            user_id="user-456",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )

    def test_serializes_subscription_active_true(self, base_user):
        """subscription_active=True should be in DynamoDB item."""
        base_user.subscription_active = True
        item = base_user.to_dynamodb_item()
        assert item["subscription_active"] is True

    def test_serializes_subscription_active_false(self, base_user):
        """subscription_active=False should be in DynamoDB item."""
        item = base_user.to_dynamodb_item()
        assert item["subscription_active"] is False

    def test_serializes_is_operator_true(self, base_user):
        """is_operator=True should be in DynamoDB item."""
        base_user.is_operator = True
        item = base_user.to_dynamodb_item()
        assert item["is_operator"] is True

    def test_serializes_is_operator_false(self, base_user):
        """is_operator=False should be in DynamoDB item."""
        item = base_user.to_dynamodb_item()
        assert item["is_operator"] is False

    def test_serializes_subscription_expires_at_when_set(self, base_user):
        """subscription_expires_at should be ISO8601 string when set."""
        expires = datetime(2027, 1, 1, 12, 0, 0, tzinfo=UTC)
        base_user.subscription_expires_at = expires
        item = base_user.to_dynamodb_item()
        assert item["subscription_expires_at"] == expires.isoformat()

    def test_excludes_subscription_expires_at_when_none(self, base_user):
        """subscription_expires_at should not be in item when None."""
        item = base_user.to_dynamodb_item()
        assert "subscription_expires_at" not in item


class TestUserRBACFieldsDeserialization:
    """Test from_dynamodb_item() deserialization of RBAC fields."""

    @pytest.fixture
    def base_item(self):
        """Create a base DynamoDB item for testing."""
        now = datetime.now(UTC)
        return {
            "PK": "USER#user-789",
            "SK": "PROFILE",
            "user_id": "user-789",
            "auth_type": "email",
            "created_at": now.isoformat(),
            "last_active_at": now.isoformat(),
            "session_expires_at": (now + timedelta(days=30)).isoformat(),
        }

    def test_deserializes_subscription_active_true(self, base_item):
        """subscription_active=True should be parsed from item."""
        base_item["subscription_active"] = True
        user = User.from_dynamodb_item(base_item)
        assert user.subscription_active is True

    def test_deserializes_subscription_active_false(self, base_item):
        """subscription_active=False should be parsed from item."""
        base_item["subscription_active"] = False
        user = User.from_dynamodb_item(base_item)
        assert user.subscription_active is False

    def test_deserializes_is_operator_true(self, base_item):
        """is_operator=True should be parsed from item."""
        base_item["is_operator"] = True
        user = User.from_dynamodb_item(base_item)
        assert user.is_operator is True

    def test_deserializes_is_operator_false(self, base_item):
        """is_operator=False should be parsed from item."""
        base_item["is_operator"] = False
        user = User.from_dynamodb_item(base_item)
        assert user.is_operator is False

    def test_deserializes_subscription_expires_at(self, base_item):
        """subscription_expires_at should be parsed as datetime."""
        expires = datetime(2027, 6, 15, 18, 30, 0, tzinfo=UTC)
        base_item["subscription_expires_at"] = expires.isoformat()
        user = User.from_dynamodb_item(base_item)
        assert user.subscription_expires_at == expires

    def test_handles_missing_subscription_expires_at(self, base_item):
        """Missing subscription_expires_at should default to None."""
        user = User.from_dynamodb_item(base_item)
        assert user.subscription_expires_at is None


class TestUserRBACFieldsBackwardCompatibility:
    """Test backward compatibility with legacy items missing RBAC fields."""

    @pytest.fixture
    def legacy_item(self):
        """Create a legacy DynamoDB item without RBAC fields."""
        now = datetime.now(UTC)
        return {
            "PK": "USER#legacy-user",
            "SK": "PROFILE",
            "user_id": "legacy-user",
            "auth_type": "anonymous",
            "created_at": now.isoformat(),
            "last_active_at": now.isoformat(),
            "session_expires_at": (now + timedelta(days=30)).isoformat(),
        }

    def test_legacy_item_gets_subscription_active_default(self, legacy_item):
        """Legacy items should get subscription_active=False."""
        user = User.from_dynamodb_item(legacy_item)
        assert user.subscription_active is False

    def test_legacy_item_gets_subscription_expires_at_default(self, legacy_item):
        """Legacy items should get subscription_expires_at=None."""
        user = User.from_dynamodb_item(legacy_item)
        assert user.subscription_expires_at is None

    def test_legacy_item_gets_is_operator_default(self, legacy_item):
        """Legacy items should get is_operator=False."""
        user = User.from_dynamodb_item(legacy_item)
        assert user.is_operator is False


class TestUserRBACFieldsRoundtrip:
    """Test roundtrip serialization/deserialization of RBAC fields."""

    def test_roundtrip_with_all_rbac_fields(self):
        """All RBAC fields should survive roundtrip."""
        expires = datetime(2028, 3, 15, 10, 0, 0, tzinfo=UTC)
        original = User(
            user_id="roundtrip-user",
            email="test@example.com",
            auth_type="email",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            subscription_active=True,
            subscription_expires_at=expires,
            is_operator=True,
        )

        # Serialize to DynamoDB format
        item = original.to_dynamodb_item()

        # Deserialize back to User
        restored = User.from_dynamodb_item(item)

        # Verify RBAC fields
        assert restored.subscription_active == original.subscription_active
        assert restored.subscription_expires_at == original.subscription_expires_at
        assert restored.is_operator == original.is_operator

    def test_roundtrip_with_default_rbac_fields(self):
        """Default RBAC fields should survive roundtrip."""
        original = User(
            user_id="default-rbac-user",
            auth_type="anonymous",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        # Serialize and deserialize
        item = original.to_dynamodb_item()
        restored = User.from_dynamodb_item(item)

        # Verify defaults preserved
        assert restored.subscription_active is False
        assert restored.subscription_expires_at is None
        assert restored.is_operator is False

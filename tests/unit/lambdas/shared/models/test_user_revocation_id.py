"""Tests for User model revocation_id field (Feature 1186, A14).

Tests the revocation_id field added to support atomic token rotation
and TOCTOU attack prevention per A14 JWT enhancement.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.lambdas.shared.models.user import User


class TestUserRevocationIdDefaults:
    """Test default values for revocation_id field."""

    def test_revocation_id_defaults_to_zero(self):
        """New users should have revocation_id=0 by default."""
        user = User(
            user_id="test-123",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        assert user.revocation_id == 0


class TestUserRevocationIdSerialization:
    """Test to_dynamodb_item() serialization of revocation_id field."""

    @pytest.fixture
    def base_user(self):
        """Create a base user for testing."""
        return User(
            user_id="user-456",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )

    def test_serializes_revocation_id_zero(self, base_user):
        """revocation_id=0 should be in DynamoDB item."""
        item = base_user.to_dynamodb_item()
        assert item["revocation_id"] == 0

    def test_serializes_revocation_id_nonzero(self, base_user):
        """revocation_id > 0 should be in DynamoDB item."""
        # Use object.__setattr__ since the model may be frozen
        object.__setattr__(base_user, "revocation_id", 5)
        item = base_user.to_dynamodb_item()
        assert item["revocation_id"] == 5


class TestUserRevocationIdDeserialization:
    """Test from_dynamodb_item() deserialization of revocation_id field."""

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

    def test_deserializes_revocation_id_zero(self, base_item):
        """revocation_id=0 should be parsed from item."""
        base_item["revocation_id"] = 0
        user = User.from_dynamodb_item(base_item)
        assert user.revocation_id == 0

    def test_deserializes_revocation_id_nonzero(self, base_item):
        """revocation_id > 0 should be parsed from item."""
        base_item["revocation_id"] = 7
        user = User.from_dynamodb_item(base_item)
        assert user.revocation_id == 7

    def test_handles_missing_revocation_id(self, base_item):
        """Missing revocation_id should default to 0 (backward compatibility)."""
        # Don't add revocation_id to simulate legacy item
        user = User.from_dynamodb_item(base_item)
        assert user.revocation_id == 0


class TestUserRevocationIdBackwardCompatibility:
    """Test backward compatibility with legacy items missing revocation_id."""

    @pytest.fixture
    def legacy_item(self):
        """Create a legacy DynamoDB item without revocation_id field."""
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

    def test_legacy_item_gets_revocation_id_default(self, legacy_item):
        """Legacy items should get revocation_id=0."""
        user = User.from_dynamodb_item(legacy_item)
        assert user.revocation_id == 0


class TestUserRevocationIdRoundtrip:
    """Test roundtrip serialization/deserialization of revocation_id field."""

    def test_roundtrip_with_revocation_id_zero(self):
        """revocation_id=0 should survive roundtrip."""
        original = User(
            user_id="roundtrip-user",
            auth_type="anonymous",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            revocation_id=0,
        )

        # Serialize to DynamoDB format
        item = original.to_dynamodb_item()

        # Deserialize back to User
        restored = User.from_dynamodb_item(item)

        # Verify revocation_id preserved
        assert restored.revocation_id == 0

    def test_roundtrip_with_revocation_id_incremented(self):
        """Incremented revocation_id should survive roundtrip."""
        original = User(
            user_id="roundtrip-user",
            email="test@example.com",
            auth_type="email",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            revocation_id=42,
        )

        # Serialize to DynamoDB format
        item = original.to_dynamodb_item()

        # Deserialize back to User
        restored = User.from_dynamodb_item(item)

        # Verify revocation_id preserved
        assert restored.revocation_id == 42

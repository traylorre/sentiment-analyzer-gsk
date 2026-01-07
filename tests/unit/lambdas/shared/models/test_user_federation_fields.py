"""Tests for User model federation fields (Feature 1162).

Tests cover:
- Default values for new federation fields
- Serialization to DynamoDB format
- Deserialization from DynamoDB format
- Backward compatibility with legacy items
- Roundtrip serialization/deserialization
- ProviderMetadata nested model
"""

from datetime import UTC, datetime

import pytest

from src.lambdas.shared.models.user import ProviderMetadata, User


class TestProviderMetadata:
    """Tests for ProviderMetadata model."""

    def test_provider_metadata_required_fields(self):
        """linked_at is required, others are optional."""
        linked_at = datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC)
        metadata = ProviderMetadata(linked_at=linked_at)

        assert metadata.linked_at == linked_at
        assert metadata.sub is None
        assert metadata.email is None
        assert metadata.avatar is None
        assert metadata.verified_at is None

    def test_provider_metadata_all_fields(self):
        """All fields can be set."""
        linked_at = datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC)
        verified_at = datetime(2026, 1, 7, 10, 5, 0, tzinfo=UTC)

        metadata = ProviderMetadata(
            sub="google-oauth-sub-123",
            email="user@gmail.com",
            avatar="https://lh3.googleusercontent.com/avatar",
            linked_at=linked_at,
            verified_at=verified_at,
        )

        assert metadata.sub == "google-oauth-sub-123"
        assert metadata.email == "user@gmail.com"
        assert metadata.avatar == "https://lh3.googleusercontent.com/avatar"
        assert metadata.linked_at == linked_at
        assert metadata.verified_at == verified_at

    def test_provider_metadata_serialization(self):
        """ProviderMetadata can be serialized to dict."""
        linked_at = datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC)
        metadata = ProviderMetadata(
            sub="sub-123",
            email="test@example.com",
            linked_at=linked_at,
        )

        data = metadata.model_dump()
        assert data["sub"] == "sub-123"
        assert data["email"] == "test@example.com"
        assert data["linked_at"] == linked_at


class TestUserFederationFieldsDefaults:
    """Tests for default values of federation fields."""

    @pytest.fixture
    def base_user(self):
        """Create a User with only required fields."""
        now = datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC)
        return User(
            user_id="usr_test123",
            created_at=now,
            last_active_at=now,
            session_expires_at=now,
        )

    def test_role_defaults_to_anonymous(self, base_user):
        """role field defaults to 'anonymous'."""
        assert base_user.role == "anonymous"

    def test_verification_defaults_to_none(self, base_user):
        """verification field defaults to 'none'."""
        assert base_user.verification == "none"

    def test_pending_email_defaults_to_none(self, base_user):
        """pending_email field defaults to None."""
        assert base_user.pending_email is None

    def test_primary_email_defaults_to_none(self, base_user):
        """primary_email field defaults to None."""
        assert base_user.primary_email is None

    def test_linked_providers_defaults_to_empty_list(self, base_user):
        """linked_providers field defaults to empty list."""
        assert base_user.linked_providers == []

    def test_provider_metadata_defaults_to_empty_dict(self, base_user):
        """provider_metadata field defaults to empty dict."""
        assert base_user.provider_metadata == {}

    def test_last_provider_used_defaults_to_none(self, base_user):
        """last_provider_used field defaults to None."""
        assert base_user.last_provider_used is None

    def test_role_assigned_at_defaults_to_none(self, base_user):
        """role_assigned_at field defaults to None."""
        assert base_user.role_assigned_at is None

    def test_role_assigned_by_defaults_to_none(self, base_user):
        """role_assigned_by field defaults to None."""
        assert base_user.role_assigned_by is None


class TestUserFederationFieldsSerialization:
    """Tests for serializing federation fields to DynamoDB."""

    @pytest.fixture
    def base_user(self):
        """Create a User with required fields and some federation data."""
        now = datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC)
        return User(
            user_id="usr_test123",
            created_at=now,
            last_active_at=now,
            session_expires_at=now,
        )

    def test_role_serializes_correctly(self, base_user):
        """role field is included in DynamoDB item."""
        base_user.role = "free"
        item = base_user.to_dynamodb_item()
        assert item["role"] == "free"

    def test_verification_serializes_correctly(self, base_user):
        """verification field is included in DynamoDB item."""
        base_user.verification = "verified"
        item = base_user.to_dynamodb_item()
        assert item["verification"] == "verified"

    def test_pending_email_excluded_when_none(self, base_user):
        """pending_email is excluded when None."""
        item = base_user.to_dynamodb_item()
        assert "pending_email" not in item

    def test_pending_email_included_when_set(self, base_user):
        """pending_email is included when set."""
        base_user.pending_email = "pending@example.com"
        item = base_user.to_dynamodb_item()
        assert item["pending_email"] == "pending@example.com"

    def test_primary_email_excluded_when_none(self, base_user):
        """primary_email is excluded when None."""
        item = base_user.to_dynamodb_item()
        assert "primary_email" not in item

    def test_primary_email_included_when_set(self, base_user):
        """primary_email is included when set."""
        base_user.primary_email = "verified@example.com"
        item = base_user.to_dynamodb_item()
        assert item["primary_email"] == "verified@example.com"

    def test_linked_providers_serializes_as_list(self, base_user):
        """linked_providers serializes as list."""
        base_user.linked_providers = ["email", "google"]
        item = base_user.to_dynamodb_item()
        assert item["linked_providers"] == ["email", "google"]

    def test_provider_metadata_serializes_as_dict(self, base_user):
        """provider_metadata serializes nested ProviderMetadata objects."""
        linked_at = datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC)
        base_user.provider_metadata = {
            "google": ProviderMetadata(
                sub="google-sub-123",
                email="user@gmail.com",
                linked_at=linked_at,
            )
        }
        item = base_user.to_dynamodb_item()
        assert "provider_metadata" in item
        assert "google" in item["provider_metadata"]
        assert item["provider_metadata"]["google"]["sub"] == "google-sub-123"

    def test_last_provider_used_excluded_when_none(self, base_user):
        """last_provider_used is excluded when None."""
        item = base_user.to_dynamodb_item()
        assert "last_provider_used" not in item

    def test_last_provider_used_included_when_set(self, base_user):
        """last_provider_used is included when set."""
        base_user.last_provider_used = "github"
        item = base_user.to_dynamodb_item()
        assert item["last_provider_used"] == "github"

    def test_role_assigned_at_excluded_when_none(self, base_user):
        """role_assigned_at is excluded when None."""
        item = base_user.to_dynamodb_item()
        assert "role_assigned_at" not in item

    def test_role_assigned_at_serializes_as_iso(self, base_user):
        """role_assigned_at serializes as ISO string."""
        assigned_at = datetime(2026, 1, 7, 11, 0, 0, tzinfo=UTC)
        base_user.role_assigned_at = assigned_at
        item = base_user.to_dynamodb_item()
        assert item["role_assigned_at"] == "2026-01-07T11:00:00+00:00"

    def test_role_assigned_by_excluded_when_none(self, base_user):
        """role_assigned_by is excluded when None."""
        item = base_user.to_dynamodb_item()
        assert "role_assigned_by" not in item

    def test_role_assigned_by_included_when_set(self, base_user):
        """role_assigned_by is included when set."""
        base_user.role_assigned_by = "stripe_webhook"
        item = base_user.to_dynamodb_item()
        assert item["role_assigned_by"] == "stripe_webhook"


class TestUserFederationFieldsDeserialization:
    """Tests for deserializing federation fields from DynamoDB."""

    @pytest.fixture
    def base_item(self):
        """Create a base DynamoDB item with required fields."""
        return {
            "PK": "USER#usr_test123",
            "SK": "PROFILE",
            "user_id": "usr_test123",
            "auth_type": "anonymous",
            "created_at": "2026-01-07T10:00:00+00:00",
            "last_active_at": "2026-01-07T10:00:00+00:00",
            "session_expires_at": "2026-01-07T10:00:00+00:00",
            "timezone": "America/New_York",
            "email_notifications_enabled": True,
            "daily_email_count": 0,
            "entity_type": "USER",
            "revoked": False,
            "subscription_active": False,
            "is_operator": False,
            # Feature 1162 fields
            "role": "free",
            "verification": "verified",
            "linked_providers": ["email", "google"],
            "provider_metadata": {},
        }

    def test_role_deserializes_correctly(self, base_item):
        """role field is parsed from DynamoDB item."""
        user = User.from_dynamodb_item(base_item)
        assert user.role == "free"

    def test_verification_deserializes_correctly(self, base_item):
        """verification field is parsed from DynamoDB item."""
        user = User.from_dynamodb_item(base_item)
        assert user.verification == "verified"

    def test_pending_email_deserializes_when_present(self, base_item):
        """pending_email is parsed when present."""
        base_item["pending_email"] = "pending@example.com"
        user = User.from_dynamodb_item(base_item)
        assert user.pending_email == "pending@example.com"

    def test_primary_email_deserializes_when_present(self, base_item):
        """primary_email is parsed when present."""
        base_item["primary_email"] = "verified@example.com"
        user = User.from_dynamodb_item(base_item)
        assert user.primary_email == "verified@example.com"

    def test_linked_providers_deserializes_as_list(self, base_item):
        """linked_providers is parsed as list."""
        user = User.from_dynamodb_item(base_item)
        assert user.linked_providers == ["email", "google"]

    def test_provider_metadata_deserializes_nested_objects(self, base_item):
        """provider_metadata deserializes to ProviderMetadata objects."""
        base_item["provider_metadata"] = {
            "google": {
                "sub": "google-sub-123",
                "email": "user@gmail.com",
                "avatar": None,
                "linked_at": "2026-01-07T10:00:00+00:00",
                "verified_at": None,
            }
        }
        user = User.from_dynamodb_item(base_item)
        assert "google" in user.provider_metadata
        assert isinstance(user.provider_metadata["google"], ProviderMetadata)
        assert user.provider_metadata["google"].sub == "google-sub-123"

    def test_last_provider_used_deserializes_when_present(self, base_item):
        """last_provider_used is parsed when present."""
        base_item["last_provider_used"] = "github"
        user = User.from_dynamodb_item(base_item)
        assert user.last_provider_used == "github"

    def test_role_assigned_at_deserializes_datetime(self, base_item):
        """role_assigned_at is parsed as datetime."""
        base_item["role_assigned_at"] = "2026-01-07T11:00:00+00:00"
        user = User.from_dynamodb_item(base_item)
        assert user.role_assigned_at is not None
        assert user.role_assigned_at.year == 2026

    def test_role_assigned_by_deserializes_when_present(self, base_item):
        """role_assigned_by is parsed when present."""
        base_item["role_assigned_by"] = "admin:usr_admin123"
        user = User.from_dynamodb_item(base_item)
        assert user.role_assigned_by == "admin:usr_admin123"


class TestUserFederationFieldsBackwardCompatibility:
    """Tests for backward compatibility with legacy items."""

    @pytest.fixture
    def legacy_item(self):
        """Create a legacy DynamoDB item without federation fields."""
        return {
            "PK": "USER#usr_legacy123",
            "SK": "PROFILE",
            "user_id": "usr_legacy123",
            "auth_type": "email",
            "created_at": "2025-06-01T10:00:00+00:00",
            "last_active_at": "2025-06-01T10:00:00+00:00",
            "session_expires_at": "2025-07-01T10:00:00+00:00",
            "timezone": "America/New_York",
            "email_notifications_enabled": True,
            "daily_email_count": 0,
            "entity_type": "USER",
            "revoked": False,
            # Note: No Feature 1162 fields
        }

    def test_legacy_item_loads_with_defaults(self, legacy_item):
        """Legacy items without federation fields load with defaults."""
        user = User.from_dynamodb_item(legacy_item)
        assert user.role == "anonymous"
        assert user.verification == "none"
        assert user.pending_email is None
        assert user.primary_email is None
        assert user.linked_providers == []
        assert user.provider_metadata == {}
        assert user.last_provider_used is None
        assert user.role_assigned_at is None
        assert user.role_assigned_by is None

    def test_legacy_item_preserves_auth_type(self, legacy_item):
        """Legacy auth_type field is preserved."""
        user = User.from_dynamodb_item(legacy_item)
        assert user.auth_type == "email"


class TestUserFederationFieldsRoundtrip:
    """Tests for roundtrip serialization/deserialization."""

    def test_roundtrip_with_all_federation_fields(self):
        """User with all federation fields survives roundtrip."""
        now = datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC)
        linked_at = datetime(2026, 1, 7, 9, 0, 0, tzinfo=UTC)
        role_assigned = datetime(2026, 1, 7, 9, 30, 0, tzinfo=UTC)

        original = User(
            user_id="usr_roundtrip123",
            created_at=now,
            last_active_at=now,
            session_expires_at=now,
            role="paid",
            verification="verified",
            pending_email=None,
            primary_email="user@example.com",
            linked_providers=["email", "google", "github"],
            provider_metadata={
                "google": ProviderMetadata(
                    sub="google-sub-456",
                    email="user@gmail.com",
                    avatar="https://avatar.url",
                    linked_at=linked_at,
                ),
                "github": ProviderMetadata(
                    sub="github-sub-789",
                    email="user@github.com",
                    linked_at=linked_at,
                ),
            },
            last_provider_used="google",
            role_assigned_at=role_assigned,
            role_assigned_by="stripe_webhook",
        )

        # Serialize to DynamoDB format
        item = original.to_dynamodb_item()

        # Deserialize back to User
        restored = User.from_dynamodb_item(item)

        # Verify all federation fields match
        assert restored.role == original.role
        assert restored.verification == original.verification
        assert restored.pending_email == original.pending_email
        assert restored.primary_email == original.primary_email
        assert restored.linked_providers == original.linked_providers
        assert restored.last_provider_used == original.last_provider_used
        assert restored.role_assigned_by == original.role_assigned_by

        # Verify provider_metadata roundtrip
        assert "google" in restored.provider_metadata
        assert restored.provider_metadata["google"].sub == "google-sub-456"
        assert "github" in restored.provider_metadata
        assert restored.provider_metadata["github"].sub == "github-sub-789"

    def test_roundtrip_with_empty_federation_fields(self):
        """User with default/empty federation fields survives roundtrip."""
        now = datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC)

        original = User(
            user_id="usr_empty123",
            created_at=now,
            last_active_at=now,
            session_expires_at=now,
        )

        item = original.to_dynamodb_item()
        restored = User.from_dynamodb_item(item)

        assert restored.role == "anonymous"
        assert restored.verification == "none"
        assert restored.linked_providers == []
        assert restored.provider_metadata == {}

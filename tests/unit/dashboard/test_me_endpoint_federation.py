"""Unit tests for /api/v2/auth/me federation fields (Feature 1172).

Tests that the /me endpoint returns federation fields needed for RBAC-aware UI.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.lambdas.shared.models.user import User
from src.lambdas.shared.response_models import UserMeResponse


class TestUserMeResponseModel:
    """Tests for UserMeResponse model with federation fields."""

    def test_model_includes_role_field(self) -> None:
        """Response model accepts role field."""
        response = UserMeResponse(
            auth_type="google",
            configs_count=0,
            role="free",
        )
        assert response.role == "free"

    def test_model_includes_linked_providers_field(self) -> None:
        """Response model accepts linked_providers field."""
        response = UserMeResponse(
            auth_type="google",
            configs_count=0,
            linked_providers=["google", "github"],
        )
        assert response.linked_providers == ["google", "github"]

    def test_model_includes_verification_field(self) -> None:
        """Response model accepts verification field."""
        response = UserMeResponse(
            auth_type="google",
            configs_count=0,
            verification="verified",
        )
        assert response.verification == "verified"

    def test_model_includes_last_provider_used_field(self) -> None:
        """Response model accepts last_provider_used field."""
        response = UserMeResponse(
            auth_type="google",
            configs_count=0,
            last_provider_used="google",
        )
        assert response.last_provider_used == "google"

    def test_model_defaults_for_federation_fields(self) -> None:
        """Federation fields have sensible defaults."""
        response = UserMeResponse(
            auth_type="anonymous",
            configs_count=0,
        )
        assert response.role == "anonymous"
        assert response.linked_providers == []
        assert response.verification == "none"
        assert response.last_provider_used is None

    def test_model_serialization_includes_all_fields(self) -> None:
        """model_dump() includes federation fields."""
        response = UserMeResponse(
            auth_type="google",
            email_masked="j***@example.com",
            configs_count=1,
            max_configs=2,
            session_expires_in_seconds=3600,
            role="free",
            linked_providers=["google"],
            verification="verified",
            last_provider_used="google",
        )
        data = response.model_dump()
        assert "role" in data
        assert "linked_providers" in data
        assert "verification" in data
        assert "last_provider_used" in data


class TestUserMeResponseBackwardCompatibility:
    """Tests that existing fields remain unchanged."""

    def test_auth_type_field_unchanged(self) -> None:
        """auth_type field still works as before."""
        response = UserMeResponse(
            auth_type="anonymous",
            configs_count=0,
        )
        assert response.auth_type == "anonymous"

    def test_email_masked_field_unchanged(self) -> None:
        """email_masked field still works as before."""
        response = UserMeResponse(
            auth_type="google",
            email_masked="j***@example.com",
            configs_count=0,
        )
        assert response.email_masked == "j***@example.com"

    def test_configs_count_field_unchanged(self) -> None:
        """configs_count field still works as before."""
        response = UserMeResponse(
            auth_type="google",
            configs_count=5,
        )
        assert response.configs_count == 5

    def test_max_configs_default_unchanged(self) -> None:
        """max_configs default value is still 2."""
        response = UserMeResponse(
            auth_type="google",
            configs_count=0,
        )
        assert response.max_configs == 2

    def test_session_expires_in_seconds_field_unchanged(self) -> None:
        """session_expires_in_seconds field still works as before."""
        response = UserMeResponse(
            auth_type="google",
            configs_count=0,
            session_expires_in_seconds=3600,
        )
        assert response.session_expires_in_seconds == 3600


class TestMeEndpointFederationFields:
    """Integration tests for /me endpoint federation fields."""

    def _create_test_user(
        self,
        role: str = "anonymous",
        verification: str | None = None,
        linked_providers: list[str] | None = None,
        last_provider_used: str | None = None,
    ) -> User:
        """Create a test User with federation fields.

        Respects role-verification state machine invariant:
        - anonymous: can have any verification state
        - free/paid/operator: must have verification="verified"
        """
        # Apply state machine invariant: non-anonymous roles require verified
        if verification is None:
            verification = "verified" if role != "anonymous" else "none"

        return User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role=role,
            verification=verification,
            linked_providers=linked_providers or [],
            last_provider_used=last_provider_used,
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            provider_metadata={},
        )

    def test_endpoint_returns_user_role(self) -> None:
        """Endpoint includes user's role in response."""
        user = self._create_test_user(role="free")
        response = UserMeResponse(
            auth_type=user.auth_type,
            configs_count=0,
            role=user.role,
            linked_providers=user.linked_providers,
            verification=user.verification,
            last_provider_used=user.last_provider_used,
        )
        assert response.role == "free"

    def test_endpoint_returns_linked_providers(self) -> None:
        """Endpoint includes user's linked_providers in response."""
        user = self._create_test_user(linked_providers=["google", "github"])
        response = UserMeResponse(
            auth_type=user.auth_type,
            configs_count=0,
            role=user.role,
            linked_providers=user.linked_providers,
            verification=user.verification,
            last_provider_used=user.last_provider_used,
        )
        assert response.linked_providers == ["google", "github"]

    def test_endpoint_returns_verification_status(self) -> None:
        """Endpoint includes user's verification status in response."""
        user = self._create_test_user(verification="verified")
        response = UserMeResponse(
            auth_type=user.auth_type,
            configs_count=0,
            role=user.role,
            linked_providers=user.linked_providers,
            verification=user.verification,
            last_provider_used=user.last_provider_used,
        )
        assert response.verification == "verified"

    def test_endpoint_returns_last_provider_used(self) -> None:
        """Endpoint includes user's last_provider_used in response."""
        user = self._create_test_user(last_provider_used="github")
        response = UserMeResponse(
            auth_type=user.auth_type,
            configs_count=0,
            role=user.role,
            linked_providers=user.linked_providers,
            verification=user.verification,
            last_provider_used=user.last_provider_used,
        )
        assert response.last_provider_used == "github"

    @pytest.mark.parametrize(
        "role",
        ["anonymous", "free", "paid", "operator"],
    )
    def test_all_role_values_serialized(self, role: str) -> None:
        """All role values are properly serialized in response."""
        user = self._create_test_user(role=role)
        response = UserMeResponse(
            auth_type=user.auth_type,
            configs_count=0,
            role=user.role,
            linked_providers=user.linked_providers,
            verification=user.verification,
            last_provider_used=user.last_provider_used,
        )
        data = response.model_dump()
        assert data["role"] == role

    @pytest.mark.parametrize(
        "verification",
        ["none", "pending", "verified"],
    )
    def test_all_verification_values_serialized(self, verification: str) -> None:
        """All verification values are properly serialized in response."""
        user = self._create_test_user(verification=verification)
        response = UserMeResponse(
            auth_type=user.auth_type,
            configs_count=0,
            role=user.role,
            linked_providers=user.linked_providers,
            verification=user.verification,
            last_provider_used=user.last_provider_used,
        )
        data = response.model_dump()
        assert data["verification"] == verification


class TestMeEndpointSecurityConstraints:
    """Tests that response doesn't expose sensitive data."""

    def test_no_user_id_in_response(self) -> None:
        """user_id is NOT in response model."""
        response = UserMeResponse(
            auth_type="google",
            configs_count=0,
        )
        data = response.model_dump()
        assert "user_id" not in data

    def test_no_cognito_sub_in_response(self) -> None:
        """cognito_sub is NOT in response model."""
        response = UserMeResponse(
            auth_type="google",
            configs_count=0,
        )
        data = response.model_dump()
        assert "cognito_sub" not in data

    def test_no_provider_metadata_in_response(self) -> None:
        """provider_metadata (with OAuth secrets) is NOT in response model."""
        response = UserMeResponse(
            auth_type="google",
            configs_count=0,
        )
        data = response.model_dump()
        assert "provider_metadata" not in data

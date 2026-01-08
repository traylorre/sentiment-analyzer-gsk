"""Unit tests for _mark_email_verified() (Feature 1171).

Tests email verification marking from OAuth provider JWT claims.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.auth import _mark_email_verified
from src.lambdas.shared.models.user import User


class TestMarkEmailVerifiedHappyPath:
    """Tests for successful email verification marking."""

    def test_marks_verified_when_provider_verified(self) -> None:
        """Email marked verified when provider says email_verified=True."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            verification="none",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        _mark_email_verified(
            table=table,
            user=user,
            provider="google",
            email="test@example.com",
            email_verified=True,
        )

        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args.kwargs
        assert call_kwargs["ExpressionAttributeValues"][":verified"] == "verified"

    def test_sets_primary_email(self) -> None:
        """primary_email is set to the OAuth email."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            verification="none",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        _mark_email_verified(
            table=table,
            user=user,
            provider="google",
            email="verified@gmail.com",
            email_verified=True,
        )

        call_kwargs = table.update_item.call_args.kwargs
        assert (
            call_kwargs["ExpressionAttributeValues"][":email"] == "verified@gmail.com"
        )

    def test_sets_audit_fields(self) -> None:
        """Audit fields verification_marked_at and verification_marked_by are set."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="github",
            role="anonymous",
            verification="none",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["github"],
            provider_metadata={},
        )

        with patch("src.lambdas.dashboard.auth.datetime") as mock_dt:
            mock_now = datetime(2026, 1, 7, 12, 0, 0, tzinfo=UTC)
            mock_dt.now.return_value = mock_now

            _mark_email_verified(
                table=table,
                user=user,
                provider="github",
                email="test@github.com",
                email_verified=True,
            )

        call_kwargs = table.update_item.call_args.kwargs
        assert (
            call_kwargs["ExpressionAttributeValues"][":marked_at"]
            == mock_now.isoformat()
        )
        assert call_kwargs["ExpressionAttributeValues"][":marked_by"] == "oauth:github"


class TestMarkEmailVerifiedSkipPaths:
    """Tests for cases where verification marking is skipped."""

    def test_skip_when_provider_not_verified(self) -> None:
        """Skip when email_verified=False from provider."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            verification="none",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        _mark_email_verified(
            table=table,
            user=user,
            provider="google",
            email="test@example.com",
            email_verified=False,
        )

        table.update_item.assert_not_called()

    def test_skip_when_already_verified(self) -> None:
        """Skip when user.verification is already 'verified'."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="free",
            verification="verified",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        _mark_email_verified(
            table=table,
            user=user,
            provider="google",
            email="test@example.com",
            email_verified=True,
        )

        table.update_item.assert_not_called()

    def test_marks_when_pending(self) -> None:
        """Mark verified when current status is 'pending'."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            verification="pending",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        _mark_email_verified(
            table=table,
            user=user,
            provider="google",
            email="test@example.com",
            email_verified=True,
        )

        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args.kwargs
        assert call_kwargs["ExpressionAttributeValues"][":verified"] == "verified"


class TestMarkEmailVerifiedErrorHandling:
    """Tests for error resilience."""

    def test_silent_failure_on_dynamodb_error(self) -> None:
        """OAuth flow continues even if DynamoDB update fails."""
        table = MagicMock()
        table.update_item.side_effect = Exception("DynamoDB error")
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            verification="none",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        # Should NOT raise
        _mark_email_verified(
            table=table,
            user=user,
            provider="google",
            email="test@example.com",
            email_verified=True,
        )

        table.update_item.assert_called_once()


class TestMarkEmailVerifiedDynamoDBStructure:
    """Tests for DynamoDB update expression structure."""

    def test_correct_key_structure(self) -> None:
        """DynamoDB key uses correct PK/SK format."""
        table = MagicMock()
        user_id = str(uuid.uuid4())
        user = User(
            user_id=user_id,
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            verification="none",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        _mark_email_verified(
            table=table,
            user=user,
            provider="google",
            email="test@example.com",
            email_verified=True,
        )

        call_kwargs = table.update_item.call_args.kwargs
        assert call_kwargs["Key"]["PK"] == f"USER#{user_id}"
        assert call_kwargs["Key"]["SK"] == "PROFILE"

    def test_update_expression_includes_all_fields(self) -> None:
        """UpdateExpression sets all required fields."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            verification="none",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        _mark_email_verified(
            table=table,
            user=user,
            provider="google",
            email="test@example.com",
            email_verified=True,
        )

        call_kwargs = table.update_item.call_args.kwargs
        update_expr = call_kwargs["UpdateExpression"]
        assert "verification = :verified" in update_expr
        assert "primary_email = :email" in update_expr
        assert "verification_marked_at = :marked_at" in update_expr
        assert "verification_marked_by = :marked_by" in update_expr


class TestMarkEmailVerifiedProviders:
    """Tests for different OAuth providers."""

    @pytest.mark.parametrize("provider", ["google", "github"])
    def test_works_with_all_providers(self, provider: str) -> None:
        """Verification marking works for all supported providers."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type=provider,
            role="anonymous",
            verification="none",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[provider],
            provider_metadata={},
        )

        _mark_email_verified(
            table=table,
            user=user,
            provider=provider,
            email=f"test@{provider}.com",
            email_verified=True,
        )

        call_kwargs = table.update_item.call_args.kwargs
        assert (
            call_kwargs["ExpressionAttributeValues"][":marked_by"]
            == f"oauth:{provider}"
        )

"""Unit tests for _advance_role() function (Feature 1170).

Tests role advancement from anonymous to free during OAuth authentication,
and preservation of higher roles (free/paid/operator).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.lambdas.dashboard.auth import _advance_role
from src.lambdas.shared.models.user import User


class TestAdvanceRoleAnonymousToFree:
    """Test role advancement from anonymous to free."""

    def test_advances_anonymous_to_free(self) -> None:
        """Anonymous user role is advanced to free."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        # Mimic the callback sequence: _mark_email_verified has already
        # synced the in-memory object before _advance_role runs (1163 FR-003).
        user.verification = "verified"
        _advance_role(table=table, user=user, provider="google")

        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args.kwargs
        assert call_kwargs["Key"]["PK"] == f"USER#{user.user_id}"
        assert call_kwargs["Key"]["SK"] == "PROFILE"
        assert call_kwargs["ExpressionAttributeValues"][":new_role"] == "free"

    def test_sets_role_assigned_at(self) -> None:
        """role_assigned_at is set to current timestamp."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        # Mimic the callback sequence: _mark_email_verified has already
        # synced the in-memory object before _advance_role runs (1163 FR-003).
        user.verification = "verified"
        with patch("src.lambdas.dashboard.auth.datetime") as mock_dt:
            mock_now = datetime(2026, 1, 7, 12, 0, 0, tzinfo=UTC)
            mock_dt.now.return_value = mock_now

            _advance_role(table=table, user=user, provider="google")

        call_kwargs = table.update_item.call_args.kwargs
        assert (
            call_kwargs["ExpressionAttributeValues"][":assigned_at"]
            == mock_now.isoformat()
        )

    def test_sets_role_assigned_by_google(self) -> None:
        """role_assigned_by is set to oauth:google for Google provider."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        # Mimic the callback sequence: _mark_email_verified has already
        # synced the in-memory object before _advance_role runs (1163 FR-003).
        user.verification = "verified"
        _advance_role(table=table, user=user, provider="google")

        call_kwargs = table.update_item.call_args.kwargs
        assert (
            call_kwargs["ExpressionAttributeValues"][":assigned_by"] == "oauth:google"
        )

    def test_sets_role_assigned_by_github(self) -> None:
        """role_assigned_by is set to oauth:github for GitHub provider."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="github",
            role="anonymous",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        # Mimic the callback sequence: _mark_email_verified has already
        # synced the in-memory object before _advance_role runs (1163 FR-003).
        user.verification = "verified"
        _advance_role(table=table, user=user, provider="github")

        call_kwargs = table.update_item.call_args.kwargs
        assert (
            call_kwargs["ExpressionAttributeValues"][":assigned_by"] == "oauth:github"
        )


class TestAdvanceRolePreservesHigherRoles:
    """Test that higher roles are preserved without modification."""

    def test_free_role_unchanged(self) -> None:
        """Free role is not modified."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="free",
            verification="verified",  # Required for free role
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        # Mimic the callback sequence: _mark_email_verified has already
        # synced the in-memory object before _advance_role runs (1163 FR-003).
        user.verification = "verified"
        _advance_role(table=table, user=user, provider="google")

        table.update_item.assert_not_called()

    def test_paid_role_unchanged(self) -> None:
        """Paid role is not modified."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="paid",
            verification="verified",  # Required for paid role
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        # Mimic the callback sequence: _mark_email_verified has already
        # synced the in-memory object before _advance_role runs (1163 FR-003).
        user.verification = "verified"
        _advance_role(table=table, user=user, provider="google")

        table.update_item.assert_not_called()

    def test_operator_role_unchanged(self) -> None:
        """Operator role is not modified."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="operator",
            verification="verified",  # Required for operator role
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

        # Mimic the callback sequence: _mark_email_verified has already
        # synced the in-memory object before _advance_role runs (1163 FR-003).
        user.verification = "verified"
        _advance_role(table=table, user=user, provider="google")

        table.update_item.assert_not_called()


class TestAdvanceRoleErrorHandling:
    """Test error handling - OAuth must not fail due to role advancement errors."""

    def test_dynamo_error_does_not_raise(self) -> None:
        """DynamoDB errors are logged but do not raise exceptions."""
        table = MagicMock()
        table.update_item.side_effect = Exception("DynamoDB error")
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        # Should not raise
        # Mimic the callback sequence: _mark_email_verified has already
        # synced the in-memory object before _advance_role runs (1163 FR-003).
        user.verification = "verified"
        _advance_role(table=table, user=user, provider="google")

        table.update_item.assert_called_once()


class TestAdvanceRoleUpdateExpression:
    """Test DynamoDB UpdateExpression structure."""

    def test_update_expression_sets_all_fields(self) -> None:
        """UpdateExpression includes role, role_assigned_at, and role_assigned_by."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        # Mimic the callback sequence: _mark_email_verified has already
        # synced the in-memory object before _advance_role runs (1163 FR-003).
        user.verification = "verified"
        _advance_role(table=table, user=user, provider="google")

        call_kwargs = table.update_item.call_args.kwargs
        update_expr = call_kwargs["UpdateExpression"]
        assert "#role" in update_expr
        assert "role_assigned_at" in update_expr
        assert "role_assigned_by" in update_expr

    def test_uses_expression_attribute_name_for_role(self) -> None:
        """Uses ExpressionAttributeNames for 'role' (reserved word handling)."""
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=[],
            provider_metadata={},
        )

        # Mimic the callback sequence: _mark_email_verified has already
        # synced the in-memory object before _advance_role runs (1163 FR-003).
        user.verification = "verified"
        _advance_role(table=table, user=user, provider="google")

        call_kwargs = table.update_item.call_args.kwargs
        assert call_kwargs["ExpressionAttributeNames"]["#role"] == "role"


class TestAdvanceRole1163Guard:
    """Feature 1163 FR-003: free requires verified — enforced at write time.

    Regression tests for the preprod 2026-07-25 incident: _advance_role used
    to promote anonymous:none to free:none, a state the model rejects, which
    made identity lookups skip the row and mint a duplicate per OAuth login.
    """

    @staticmethod
    def _make_user() -> User:
        return User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub="cognito-123",
            auth_type="google",
            role="anonymous",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
            linked_providers=["google"],
            provider_metadata={},
        )

    def test_unverified_user_is_not_advanced(self) -> None:
        """anonymous:none stays anonymous — no DB write, no in-memory change."""
        table = MagicMock()
        user = self._make_user()
        assert user.verification == "none"

        _advance_role(table=table, user=user, provider="google")

        table.update_item.assert_not_called()
        assert user.role == "anonymous"

    def test_pending_verification_is_not_advanced(self) -> None:
        table = MagicMock()
        user = self._make_user()
        user.verification = "pending"

        _advance_role(table=table, user=user, provider="google")

        table.update_item.assert_not_called()
        assert user.role == "anonymous"

    def test_verified_user_advances_and_syncs_in_memory(self) -> None:
        """The in-memory object reflects the new role: the callback mints the
        app JWT from this instance after the helpers run."""
        table = MagicMock()
        user = self._make_user()
        user.verification = "verified"

        _advance_role(table=table, user=user, provider="google")

        table.update_item.assert_called_once()
        assert user.role == "free"

    def test_failed_update_does_not_sync_in_memory(self) -> None:
        """If the DB write fails, the in-memory role must not lie."""
        table = MagicMock()
        table.update_item.side_effect = RuntimeError("boom")
        user = self._make_user()
        user.verification = "verified"

        _advance_role(table=table, user=user, provider="google")

        assert user.role == "anonymous"

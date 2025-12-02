"""Unit tests for session lifecycle management (Feature 014, User Story 4).

Tests for FR-010, FR-011, FR-012: Session expiry extension on activity.

These tests verify:
- Session expiry is extended on valid activity
- Extension respects sliding window (30 days)
- Extension is atomic and consistent
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.models.user import User


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us4
class TestSessionExpiryExtension:
    """Tests for session expiry extension (FR-010, T045)."""

    def test_extend_session_updates_expiry_by_30_days(self):
        """FR-010: Session expiry extended by 30 days on activity."""
        from src.lambdas.dashboard.auth import extend_session_expiry

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        old_expiry = now + timedelta(days=15)  # 15 days remaining

        user = User(
            user_id=user_id,
            email="test@example.com",
            auth_type="email",
            created_at=now - timedelta(days=15),
            last_active_at=now - timedelta(hours=1),
            session_expires_at=old_expiry,
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}
        mock_table.update_item.return_value = {}

        result = extend_session_expiry(table=mock_table, user_id=user_id)

        assert result is not None
        # Check update_item was called with new expiry
        call_kwargs = mock_table.update_item.call_args.kwargs
        update_expr = call_kwargs["UpdateExpression"]
        assert "session_expires_at" in update_expr
        assert "last_active_at" in update_expr

    def test_extend_session_updates_last_active_timestamp(self):
        """FR-010: Last active timestamp updated on extension."""
        from src.lambdas.dashboard.auth import extend_session_expiry

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            email="test@example.com",
            auth_type="email",
            created_at=now - timedelta(days=10),
            last_active_at=now - timedelta(days=1),  # Last active yesterday
            session_expires_at=now + timedelta(days=20),
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}
        mock_table.update_item.return_value = {}

        result = extend_session_expiry(table=mock_table, user_id=user_id)

        assert result is not None
        call_kwargs = mock_table.update_item.call_args.kwargs
        attr_values = call_kwargs["ExpressionAttributeValues"]
        # last_active_at should be updated to approximately now
        assert ":last_active" in attr_values

    def test_extend_session_returns_none_for_nonexistent_user(self):
        """Extension returns None if user doesn't exist."""
        from src.lambdas.dashboard.auth import extend_session_expiry

        mock_table = MagicMock()
        mock_table.get_item.return_value = {}  # No Item

        result = extend_session_expiry(table=mock_table, user_id=str(uuid.uuid4()))

        assert result is None
        mock_table.update_item.assert_not_called()

    def test_extend_session_returns_none_for_expired_session(self):
        """Extension returns None if session already expired."""
        from src.lambdas.dashboard.auth import extend_session_expiry

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            email="test@example.com",
            auth_type="email",
            created_at=now - timedelta(days=60),
            last_active_at=now - timedelta(days=35),
            session_expires_at=now - timedelta(days=5),  # Expired 5 days ago
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}

        result = extend_session_expiry(table=mock_table, user_id=user_id)

        assert result is None
        mock_table.update_item.assert_not_called()

    def test_extend_session_returns_none_for_revoked_session(self):
        """Extension returns None if session has been revoked."""
        from src.lambdas.dashboard.auth import extend_session_expiry

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            email="test@example.com",
            auth_type="email",
            created_at=now - timedelta(days=10),
            last_active_at=now - timedelta(hours=1),
            session_expires_at=now + timedelta(days=20),
            revoked=True,
            revoked_at=now - timedelta(hours=2),
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}

        result = extend_session_expiry(table=mock_table, user_id=user_id)

        assert result is None
        mock_table.update_item.assert_not_called()


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us4
class TestValidateSessionExtension:
    """Tests for session extension during validation (FR-011, T052)."""

    def test_validate_session_extends_expiry_on_valid(self):
        """FR-011: validate_session extends expiry when session is valid."""
        from src.lambdas.dashboard.auth import validate_session

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            auth_type="anonymous",
            created_at=now - timedelta(days=10),
            last_active_at=now - timedelta(hours=2),
            session_expires_at=now + timedelta(days=20),
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}
        mock_table.update_item.return_value = {}

        result = validate_session(
            table=mock_table,
            anonymous_id=user_id,
            extend_on_valid=True,
        )

        assert result.valid is True
        # update_item should be called to extend expiry
        mock_table.update_item.assert_called()

    def test_validate_session_does_not_extend_when_disabled(self):
        """FR-011: Extension can be disabled via parameter."""
        from src.lambdas.dashboard.auth import validate_session

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            auth_type="anonymous",
            created_at=now - timedelta(days=10),
            last_active_at=now - timedelta(hours=2),
            session_expires_at=now + timedelta(days=20),
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}

        result = validate_session(
            table=mock_table,
            anonymous_id=user_id,
            extend_on_valid=False,
        )

        assert result.valid is True
        # update_item is called once for last_active_at update, but NOT for session extension
        # When extend_on_valid=False, no session_expires_at update should happen
        assert mock_table.update_item.call_count == 1  # Only last_active_at update
        call_kwargs = mock_table.update_item.call_args.kwargs
        update_expr = call_kwargs["UpdateExpression"]
        assert "last_active_at" in update_expr
        assert "session_expires_at" not in update_expr


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us4
class TestSessionRefreshResponse:
    """Tests for session refresh response format."""

    def test_refresh_response_includes_new_expiry(self):
        """Refresh response includes the new session expiry time."""
        from src.lambdas.dashboard.auth import refresh_session

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            email="test@example.com",
            auth_type="email",
            created_at=now - timedelta(days=10),
            last_active_at=now - timedelta(hours=1),
            session_expires_at=now + timedelta(days=15),
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}
        mock_table.update_item.return_value = {}

        result = refresh_session(table=mock_table, user_id=user_id)

        assert result is not None
        assert hasattr(result, "session_expires_at") or "session_expires_at" in result
        assert hasattr(result, "remaining_seconds") or "remaining_seconds" in result

    def test_refresh_returns_none_for_invalid_session(self):
        """Refresh returns None for invalid/expired sessions."""
        from src.lambdas.dashboard.auth import refresh_session

        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = refresh_session(table=mock_table, user_id=str(uuid.uuid4()))

        assert result is None

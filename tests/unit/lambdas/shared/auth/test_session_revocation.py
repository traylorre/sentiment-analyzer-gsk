"""Unit tests for session revocation (Feature 014, User Story 4).

Tests for FR-016, FR-017: Session revocation for single user and bulk (andon cord).

These tests verify:
- Single session can be revoked
- Bulk sessions can be revoked (andon cord pattern)
- Revoked sessions are detected during validation
- Revocation includes audit trail
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.errors.session_errors import SessionRevokedException
from src.lambdas.shared.models.user import User


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us4
class TestSessionRevocationCheck:
    """Tests for session revocation detection (FR-016, T046)."""

    def test_validate_session_detects_revoked_session(self):
        """FR-016: validate_session raises SessionRevokedException for revoked session."""
        from src.lambdas.dashboard.auth import validate_session

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            auth_type="anonymous",
            created_at=now - timedelta(days=10),
            last_active_at=now - timedelta(hours=1),
            session_expires_at=now + timedelta(days=20),
            revoked=True,
            revoked_at=now - timedelta(hours=2),
            revoked_reason="Security incident",
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}

        with pytest.raises(SessionRevokedException) as exc_info:
            validate_session(table=mock_table, anonymous_id=user_id)

        # SessionRevokedException stores reason and revoked_at, not user_id
        assert exc_info.value.reason == "Security incident"
        assert exc_info.value.revoked_at is not None

    def test_validate_session_passes_for_non_revoked_session(self):
        """Non-revoked session passes validation."""
        from src.lambdas.dashboard.auth import validate_session

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            auth_type="anonymous",
            created_at=now - timedelta(days=10),
            last_active_at=now - timedelta(hours=1),
            session_expires_at=now + timedelta(days=20),
            revoked=False,  # Not revoked
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}

        result = validate_session(table=mock_table, anonymous_id=user_id)

        assert result.valid is True

    def test_revoked_exception_includes_timestamp(self):
        """SessionRevokedException includes revocation timestamp."""
        revoked_at = datetime.now(UTC) - timedelta(hours=1)
        exc = SessionRevokedException(
            reason="Test reason",
            revoked_at=revoked_at,
        )

        assert exc.revoked_at == revoked_at
        assert exc.reason == "Test reason"


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us4
class TestSingleSessionRevocation:
    """Tests for revoking single session (FR-016, T053)."""

    def test_revoke_session_marks_user_as_revoked(self):
        """FR-016: revoke_user_session marks session as revoked."""
        from src.lambdas.dashboard.auth import revoke_user_session

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            email="test@example.com",
            auth_type="email",
            created_at=now - timedelta(days=10),
            last_active_at=now - timedelta(hours=1),
            session_expires_at=now + timedelta(days=20),
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}
        mock_table.update_item.return_value = {}

        result = revoke_user_session(
            table=mock_table,
            user_id=user_id,
            reason="User requested logout",
        )

        assert result is True
        # Verify update_item was called with revocation fields
        call_kwargs = mock_table.update_item.call_args.kwargs
        update_expr = call_kwargs["UpdateExpression"]
        assert "revoked" in update_expr
        assert "revoked_at" in update_expr
        assert "revoked_reason" in update_expr

    def test_revoke_session_includes_reason(self):
        """Revocation includes the reason for audit."""
        from src.lambdas.dashboard.auth import revoke_user_session

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            auth_type="email",
            created_at=now,
            last_active_at=now,
            session_expires_at=now + timedelta(days=30),
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}
        mock_table.update_item.return_value = {}

        revoke_user_session(
            table=mock_table,
            user_id=user_id,
            reason="Security policy violation",
        )

        call_kwargs = mock_table.update_item.call_args.kwargs
        attr_values = call_kwargs["ExpressionAttributeValues"]
        assert attr_values[":reason"] == "Security policy violation"

    def test_revoke_nonexistent_session_returns_false(self):
        """Revoking nonexistent user returns False."""
        from src.lambdas.dashboard.auth import revoke_user_session

        mock_table = MagicMock()
        mock_table.get_item.return_value = {}  # No Item

        result = revoke_user_session(
            table=mock_table,
            user_id=str(uuid.uuid4()),
            reason="Test",
        )

        assert result is False
        mock_table.update_item.assert_not_called()

    def test_revoke_already_revoked_session_is_idempotent(self):
        """Revoking already revoked session is idempotent."""
        from src.lambdas.dashboard.auth import revoke_user_session

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            auth_type="email",
            created_at=now - timedelta(days=10),
            last_active_at=now - timedelta(hours=5),
            session_expires_at=now + timedelta(days=20),
            revoked=True,  # Already revoked
            revoked_at=now - timedelta(hours=3),
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}

        result = revoke_user_session(
            table=mock_table,
            user_id=user_id,
            reason="Second revocation",
        )

        # Should return True but not update (idempotent)
        assert result is True
        mock_table.update_item.assert_not_called()


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us4
class TestBulkSessionRevocation:
    """Tests for bulk session revocation / andon cord (FR-017, T047)."""

    def test_revoke_sessions_bulk_revokes_multiple_users(self):
        """FR-017: revoke_sessions_bulk revokes all specified users."""
        from src.lambdas.dashboard.auth import revoke_sessions_bulk

        user_ids = [str(uuid.uuid4()) for _ in range(5)]
        now = datetime.now(UTC)

        mock_table = MagicMock()

        # Mock each user lookup
        def mock_get_item(Key):
            user_id = Key["PK"].replace("USER#", "")
            if user_id in user_ids:
                user = User(
                    user_id=user_id,
                    auth_type="email",
                    created_at=now,
                    last_active_at=now,
                    session_expires_at=now + timedelta(days=30),
                )
                return {"Item": user.to_dynamodb_item()}
            return {}

        mock_table.get_item.side_effect = mock_get_item
        mock_table.update_item.return_value = {}

        result = revoke_sessions_bulk(
            table=mock_table,
            user_ids=user_ids,
            reason="Security incident - andon cord",
        )

        assert result.revoked_count == 5
        assert result.failed_count == 0
        assert mock_table.update_item.call_count == 5

    def test_revoke_sessions_bulk_handles_partial_failure(self):
        """Bulk revocation continues despite partial failures."""
        from src.lambdas.dashboard.auth import revoke_sessions_bulk

        user_ids = [str(uuid.uuid4()) for _ in range(3)]
        now = datetime.now(UTC)

        mock_table = MagicMock()

        # First user exists, second doesn't, third exists
        def mock_get_item(Key):
            user_id = Key["PK"].replace("USER#", "")
            idx = user_ids.index(user_id) if user_id in user_ids else -1
            if idx == 0 or idx == 2:  # First and third exist
                user = User(
                    user_id=user_id,
                    auth_type="email",
                    created_at=now,
                    last_active_at=now,
                    session_expires_at=now + timedelta(days=30),
                )
                return {"Item": user.to_dynamodb_item()}
            return {}  # Second doesn't exist

        mock_table.get_item.side_effect = mock_get_item
        mock_table.update_item.return_value = {}

        result = revoke_sessions_bulk(
            table=mock_table,
            user_ids=user_ids,
            reason="Bulk revocation test",
        )

        assert result.revoked_count == 2
        assert result.failed_count == 1
        assert len(result.failed_user_ids) == 1
        assert user_ids[1] in result.failed_user_ids

    def test_revoke_sessions_bulk_returns_empty_for_empty_list(self):
        """Bulk revocation with empty list returns zero counts."""
        from src.lambdas.dashboard.auth import revoke_sessions_bulk

        mock_table = MagicMock()

        result = revoke_sessions_bulk(
            table=mock_table,
            user_ids=[],
            reason="Empty test",
        )

        assert result.revoked_count == 0
        assert result.failed_count == 0
        mock_table.get_item.assert_not_called()

    def test_revoke_sessions_bulk_includes_reason_for_all(self):
        """All revoked sessions include the same reason."""
        from src.lambdas.dashboard.auth import revoke_sessions_bulk

        user_ids = [str(uuid.uuid4()) for _ in range(2)]
        now = datetime.now(UTC)
        reason = "Critical security patch deployment"

        mock_table = MagicMock()

        def mock_get_item(Key):
            user_id = Key["PK"].replace("USER#", "")
            user = User(
                user_id=user_id,
                auth_type="email",
                created_at=now,
                last_active_at=now,
                session_expires_at=now + timedelta(days=30),
            )
            return {"Item": user.to_dynamodb_item()}

        mock_table.get_item.side_effect = mock_get_item
        mock_table.update_item.return_value = {}

        revoke_sessions_bulk(
            table=mock_table,
            user_ids=user_ids,
            reason=reason,
        )

        # Verify all update calls include the reason
        for call in mock_table.update_item.call_args_list:
            attr_values = call.kwargs["ExpressionAttributeValues"]
            assert attr_values[":reason"] == reason


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us4
class TestSessionRevocationAudit:
    """Tests for revocation audit trail."""

    def test_revocation_timestamp_is_recorded(self):
        """Revocation timestamp is recorded for audit."""
        from src.lambdas.dashboard.auth import revoke_user_session

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        user = User(
            user_id=user_id,
            auth_type="email",
            created_at=now,
            last_active_at=now,
            session_expires_at=now + timedelta(days=30),
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": user.to_dynamodb_item()}
        mock_table.update_item.return_value = {}

        before_revoke = datetime.now(UTC)
        revoke_user_session(table=mock_table, user_id=user_id, reason="Test")
        after_revoke = datetime.now(UTC)

        call_kwargs = mock_table.update_item.call_args.kwargs
        attr_values = call_kwargs["ExpressionAttributeValues"]
        revoked_at = datetime.fromisoformat(attr_values[":revoked_at"])

        assert before_revoke <= revoked_at <= after_revoke

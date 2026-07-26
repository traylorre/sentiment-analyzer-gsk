"""Unit tests for _restart_session_expiry (sign-out -> sign-in 404 fix).

sign_out backdates session_expires_at; the OAuth callback's reuse branch must
restart the window on re-authentication, or /auth/me 404s forever on a valid
JWT (get_user returns None for expired sessions). Masked pre-1395 by the
duplicate-user-per-login bug.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.lambdas.dashboard.auth import SESSION_DURATION_DAYS, _restart_session_expiry
from src.lambdas.shared.models.user import User


def _expired_user() -> User:
    return User(
        user_id=str(uuid.uuid4()),
        email="test@example.com",
        auth_type="google",
        role="free",
        verification="verified",
        created_at=datetime.now(UTC) - timedelta(days=2),
        last_active_at=datetime.now(UTC) - timedelta(days=1),
        session_expires_at=datetime.now(UTC) - timedelta(days=1),
    )


class TestRestartSessionExpiry:
    def test_restarts_expired_session(self) -> None:
        """An expired window is restarted (unlike extend_session_expiry)."""
        table = MagicMock()
        user = _expired_user()

        _restart_session_expiry(table, user)

        table.update_item.assert_called_once()
        vals = table.update_item.call_args.kwargs["ExpressionAttributeValues"]
        new_expiry = datetime.fromisoformat(vals[":expires"])
        assert new_expiry > datetime.now(UTC) + timedelta(
            days=SESSION_DURATION_DAYS - 1
        )

    def test_syncs_in_memory_user(self) -> None:
        """Callback response reads session_expires_in_seconds from this object."""
        table = MagicMock()
        user = _expired_user()

        _restart_session_expiry(table, user)

        assert user.session_expires_at > datetime.now(UTC)

    def test_failed_write_does_not_sync_or_raise(self) -> None:
        table = MagicMock()
        table.update_item.side_effect = RuntimeError("boom")
        user = _expired_user()
        old_expiry = user.session_expires_at

        _restart_session_expiry(table, user)  # silent-failure pattern

        assert user.session_expires_at == old_expiry

    def test_does_not_touch_revoked_flag(self) -> None:
        """Administrative revocation must survive re-login."""
        table = MagicMock()
        user = _expired_user()
        user.revoked = True

        _restart_session_expiry(table, user)

        expr = table.update_item.call_args.kwargs["UpdateExpression"]
        assert "revoked" not in expr
        assert user.revoked is True

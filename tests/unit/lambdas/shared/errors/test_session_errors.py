"""Tests for session error types."""

from datetime import datetime

from src.lambdas.shared.errors.session_errors import (
    EmailAlreadyExistsError,
    InvalidMergeTargetError,
    MergeConflictError,
    SessionExpiredError,
    SessionLimitRaceError,
    SessionRevokedException,
    TokenAlreadyUsedError,
    TokenExpiredError,
)


class TestSessionRevokedException:
    def test_with_reason_and_timestamp(self):
        ts = datetime(2026, 1, 15, 10, 0)
        err = SessionRevokedException(reason="admin action", revoked_at=ts)
        assert "admin action" in str(err)
        assert "2026-01-15" in str(err)

    def test_without_optional_args(self):
        err = SessionRevokedException()
        assert "No reason provided" in str(err)


class TestSessionExpiredError:
    def test_with_timestamp(self):
        ts = datetime(2026, 1, 15, 10, 0)
        err = SessionExpiredError("u-001", expired_at=ts)
        assert err.user_id == "u-001"
        assert "2026-01-15" in str(err)

    def test_without_timestamp(self):
        err = SessionExpiredError("u-001")
        assert "u-001" in str(err)


class TestTokenAlreadyUsedError:
    def test_with_timestamp(self):
        ts = datetime(2026, 1, 15, 10, 0)
        err = TokenAlreadyUsedError("tok-123", used_at=ts)
        assert err.token_id == "tok-123"
        assert "2026-01-15" in str(err)

    def test_without_timestamp(self):
        err = TokenAlreadyUsedError("tok-123")
        assert "tok-123" in str(err)


class TestTokenExpiredError:
    def test_with_timestamp(self):
        ts = datetime(2026, 1, 15, 10, 0)
        err = TokenExpiredError("tok-456", expired_at=ts)
        assert err.token_id == "tok-456"
        assert "2026-01-15" in str(err)


class TestEmailAlreadyExistsError:
    def test_basic(self):
        err = EmailAlreadyExistsError("test@example.com", existing_user_id="u-002")
        assert err.email == "test@example.com"
        assert err.existing_user_id == "u-002"


class TestMergeConflictError:
    def test_with_existing_target(self):
        err = MergeConflictError("u-001", "u-002", "already merged", "u-003")
        assert "u-001" in str(err)
        assert "u-003" in str(err)

    def test_without_existing_target(self):
        err = MergeConflictError("u-001", "u-002", "conflict")
        assert err.existing_merge_target is None


class TestInvalidMergeTargetError:
    def test_with_reason(self):
        err = InvalidMergeTargetError("u-999", reason="user deleted")
        assert "u-999" in str(err)
        assert "user deleted" in str(err)

    def test_without_reason(self):
        err = InvalidMergeTargetError("u-999")
        assert err.reason is None


class TestSessionLimitRaceError:
    def test_attributes(self):
        err = SessionLimitRaceError(
            "u-001", cancellation_reasons=[{"Code": "ConditionalCheckFailed"}]
        )
        assert err.user_id == "u-001"
        assert err.retryable is True
        assert len(err.cancellation_reasons) == 1

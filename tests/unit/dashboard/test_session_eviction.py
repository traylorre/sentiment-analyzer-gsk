"""Unit tests for session eviction atomic transaction (Feature 1188).

Tests for A11: Session eviction must use TransactWriteItems for atomic deletion.
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.lambdas.dashboard.auth import (
    SESSION_DURATION_DAYS,
    SESSION_LIMIT,
    create_session_with_limit_enforcement,
    evict_oldest_session_atomic,
    get_user_sessions,
    hash_refresh_token,
    is_token_blocklisted,
)
from src.lambdas.shared.errors.session_errors import SessionLimitRaceError


class TestHashRefreshToken:
    """Tests for hash_refresh_token function."""

    def test_returns_hex_string(self):
        """Hash should return a hex-encoded SHA-256 hash."""
        result = hash_refresh_token("test_token")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        """Same input should produce same hash."""
        hash1 = hash_refresh_token("same_token")
        hash2 = hash_refresh_token("same_token")
        assert hash1 == hash2

    def test_different_tokens_different_hashes(self):
        """Different tokens should produce different hashes."""
        hash1 = hash_refresh_token("token_a")
        hash2 = hash_refresh_token("token_b")
        assert hash1 != hash2


class TestGetUserSessions:
    """Tests for get_user_sessions function."""

    def test_returns_sessions_sorted_by_created_at(self):
        """Sessions should be sorted by created_at ascending (oldest first)."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"PK": "USER#123", "SK": "SESSION#3", "created_at": "2026-01-03"},
                {"PK": "USER#123", "SK": "SESSION#1", "created_at": "2026-01-01"},
                {"PK": "USER#123", "SK": "SESSION#2", "created_at": "2026-01-02"},
            ]
        }

        sessions = get_user_sessions(mock_table, "123")

        assert len(sessions) == 3
        assert sessions[0]["created_at"] == "2026-01-01"
        assert sessions[1]["created_at"] == "2026-01-02"
        assert sessions[2]["created_at"] == "2026-01-03"

    def test_returns_empty_list_on_no_sessions(self):
        """Should return empty list when user has no sessions."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        sessions = get_user_sessions(mock_table, "123")

        assert sessions == []

    def test_returns_empty_list_on_error(self):
        """Should return empty list on query error (fail safe)."""
        mock_table = MagicMock()
        mock_table.query.side_effect = Exception("DynamoDB error")

        sessions = get_user_sessions(mock_table, "123")

        assert sessions == []


class TestIsTokenBlocklisted:
    """Tests for is_token_blocklisted function."""

    def test_returns_true_when_blocklisted(self):
        """Should return True when token is in blocklist."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"PK": "BLOCK#refresh#abc123", "SK": "BLOCK"}
        }

        result = is_token_blocklisted(mock_table, "abc123")

        assert result is True
        mock_table.get_item.assert_called_once()

    def test_returns_false_when_not_blocklisted(self):
        """Should return False when token is not in blocklist."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = is_token_blocklisted(mock_table, "abc123")

        assert result is False

    def test_returns_true_on_error_fail_closed(self):
        """Should return True on error (fail closed for security)."""
        mock_table = MagicMock()
        mock_table.get_item.side_effect = Exception("DynamoDB error")

        result = is_token_blocklisted(mock_table, "abc123")

        assert result is True  # Fail closed


class TestEvictOldestSessionAtomic:
    """Tests for evict_oldest_session_atomic function."""

    @patch("src.lambdas.dashboard.auth.boto3")
    def test_calls_transact_write_items(self, mock_boto3):
        """Should call DynamoDB transact_write_items."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_table = MagicMock()
        mock_table.name = "test-table"

        evict_oldest_session_atomic(
            table=mock_table,
            user_id="user123",
            oldest_session={"PK": "USER#user123", "SK": "SESSION#old"},
            new_session_item={"PK": "USER#user123", "SK": "SESSION#new"},
            refresh_token_hash="abc123",
        )

        mock_client.transact_write_items.assert_called_once()

    @patch("src.lambdas.dashboard.auth.boto3")
    def test_transaction_has_four_operations(self, mock_boto3):
        """Transaction should have exactly 4 operations."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_table = MagicMock()
        mock_table.name = "test-table"

        evict_oldest_session_atomic(
            table=mock_table,
            user_id="user123",
            oldest_session={"PK": "USER#user123", "SK": "SESSION#old"},
            new_session_item={"PK": "USER#user123", "SK": "SESSION#new"},
            refresh_token_hash="abc123",
        )

        call_args = mock_client.transact_write_items.call_args
        transact_items = call_args.kwargs["TransactItems"]
        assert len(transact_items) == 4

    @patch("src.lambdas.dashboard.auth.boto3")
    def test_raises_session_limit_race_error_on_transaction_canceled(self, mock_boto3):
        """Should raise SessionLimitRaceError on TransactionCanceledException."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_table = MagicMock()
        mock_table.name = "test-table"

        error_response = {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [{"Code": "ConditionalCheckFailed"}],
        }
        mock_client.transact_write_items.side_effect = ClientError(
            error_response, "TransactWriteItems"
        )

        with pytest.raises(SessionLimitRaceError) as exc_info:
            evict_oldest_session_atomic(
                table=mock_table,
                user_id="user123",
                oldest_session={"PK": "USER#user123", "SK": "SESSION#old"},
                new_session_item={"PK": "USER#user123", "SK": "SESSION#new"},
                refresh_token_hash="abc123",
            )

        assert exc_info.value.user_id == "user123"
        assert exc_info.value.retryable is True


class TestCreateSessionWithLimitEnforcement:
    """Tests for create_session_with_limit_enforcement function."""

    def test_creates_session_under_limit(self):
        """Should create session without eviction when under limit."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}  # No existing sessions

        result = create_session_with_limit_enforcement(
            table=mock_table,
            user_id="user123",
            session_item={"PK": "USER#user123", "SK": "SESSION#new"},
        )

        assert result is True
        mock_table.put_item.assert_called_once()

    @patch("src.lambdas.dashboard.auth.evict_oldest_session_atomic")
    def test_evicts_when_at_limit(self, mock_evict):
        """Should evict oldest session when at limit."""
        mock_table = MagicMock()
        # Create SESSION_LIMIT sessions
        sessions = [
            {
                "PK": "USER#user123",
                "SK": f"SESSION#{i}",
                "created_at": f"2026-01-{i:02d}",
            }
            for i in range(1, SESSION_LIMIT + 1)
        ]
        mock_table.query.return_value = {"Items": sessions}

        result = create_session_with_limit_enforcement(
            table=mock_table,
            user_id="user123",
            session_item={"PK": "USER#user123", "SK": "SESSION#new"},
        )

        assert result is True
        mock_evict.assert_called_once()

    @patch("src.lambdas.dashboard.auth.evict_oldest_session_atomic")
    def test_evicts_oldest_session(self, mock_evict):
        """Should evict the oldest session (first by created_at)."""
        mock_table = MagicMock()
        sessions = [
            {"PK": "USER#user123", "SK": "SESSION#oldest", "created_at": "2026-01-01"},
            {"PK": "USER#user123", "SK": "SESSION#newer", "created_at": "2026-01-05"},
            {"PK": "USER#user123", "SK": "SESSION#newest", "created_at": "2026-01-10"},
            {"PK": "USER#user123", "SK": "SESSION#4", "created_at": "2026-01-08"},
            {"PK": "USER#user123", "SK": "SESSION#5", "created_at": "2026-01-09"},
        ]
        mock_table.query.return_value = {"Items": sessions}

        create_session_with_limit_enforcement(
            table=mock_table,
            user_id="user123",
            session_item={"PK": "USER#user123", "SK": "SESSION#new"},
        )

        call_args = mock_evict.call_args
        evicted_session = call_args.kwargs["oldest_session"]
        assert evicted_session["SK"] == "SESSION#oldest"

    def test_handles_race_condition_on_create(self):
        """Should handle ConditionalCheckFailedException gracefully."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}  # Under limit
        error_response = {"Error": {"Code": "ConditionalCheckFailedException"}}
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        # Should not raise - treats existing session as success
        result = create_session_with_limit_enforcement(
            table=mock_table,
            user_id="user123",
            session_item={"PK": "USER#user123", "SK": "SESSION#new"},
        )

        assert result is True


class TestSessionLimitRaceError:
    """Tests for SessionLimitRaceError exception."""

    def test_has_retryable_flag(self):
        """Error should be marked as retryable."""
        error = SessionLimitRaceError("user123")
        assert error.retryable is True

    def test_stores_user_id(self):
        """Error should store user_id."""
        error = SessionLimitRaceError("user123")
        assert error.user_id == "user123"

    def test_stores_cancellation_reasons(self):
        """Error should store cancellation reasons."""
        reasons = [{"Code": "ConditionalCheckFailed"}]
        error = SessionLimitRaceError("user123", reasons)
        assert error.cancellation_reasons == reasons

    def test_message_includes_retry_guidance(self):
        """Error message should include retry guidance."""
        error = SessionLimitRaceError("user123")
        assert "retry" in str(error).lower()


class TestConstants:
    """Tests for session limit constants."""

    def test_session_limit_is_five(self):
        """Session limit should be 5 (per spec)."""
        assert SESSION_LIMIT == 5

    def test_session_duration_is_thirty_days(self):
        """Session duration should be 30 days."""
        assert SESSION_DURATION_DAYS == 30

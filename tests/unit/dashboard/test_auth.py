"""Unit tests for auth endpoints (T047-T048)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.lambdas.dashboard.auth import (
    AnonymousSessionRequest,
    AnonymousSessionResponse,
    InvalidSessionResponse,
    ValidateSessionResponse,
    create_anonymous_session,
    extend_session,
    get_user_by_id,
    validate_session,
)


class TestCreateAnonymousSession:
    """Tests for create_anonymous_session function."""

    def test_creates_session_with_valid_request(self):
        """Should create anonymous session with valid request."""
        mock_table = MagicMock()
        request = AnonymousSessionRequest(timezone="America/New_York")

        response = create_anonymous_session(mock_table, request)

        assert isinstance(response, AnonymousSessionResponse)
        assert response.auth_type == "anonymous"
        assert response.storage_hint == "localStorage"
        mock_table.put_item.assert_called_once()

    def test_creates_valid_uuid(self):
        """Should create valid UUID for user_id."""
        mock_table = MagicMock()
        request = AnonymousSessionRequest()

        response = create_anonymous_session(mock_table, request)

        # Should not raise
        uuid.UUID(response.user_id)

    def test_session_expires_in_30_days(self):
        """Should set session expiry to 30 days from now."""
        mock_table = MagicMock()
        request = AnonymousSessionRequest()

        response = create_anonymous_session(mock_table, request)

        created = datetime.fromisoformat(response.created_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(
            response.session_expires_at.replace("Z", "+00:00")
        )
        duration = expires - created

        assert 29 <= duration.days <= 31

    def test_stores_item_in_dynamodb(self):
        """Should store user item in DynamoDB."""
        mock_table = MagicMock()
        request = AnonymousSessionRequest(timezone="Europe/London")

        create_anonymous_session(mock_table, request)

        call_args = mock_table.put_item.call_args
        item = call_args.kwargs["Item"]

        assert item["PK"].startswith("USER#")
        assert item["SK"] == "PROFILE"
        assert item["auth_type"] == "anonymous"
        assert item["timezone"] == "Europe/London"
        assert "ttl" in item

    def test_handles_dynamodb_error(self):
        """Should raise on DynamoDB error."""
        mock_table = MagicMock()
        mock_table.put_item.side_effect = Exception("DynamoDB error")
        request = AnonymousSessionRequest()

        with pytest.raises(Exception, match="DynamoDB error"):
            create_anonymous_session(mock_table, request)


class TestValidateSession:
    """Tests for validate_session function."""

    def test_returns_invalid_for_missing_id(self):
        """Should return invalid for missing user ID."""
        mock_table = MagicMock()

        response = validate_session(mock_table, None)

        assert isinstance(response, InvalidSessionResponse)
        assert response.valid is False
        assert response.error == "missing_user_id"

    def test_returns_invalid_for_invalid_uuid(self):
        """Should return invalid for malformed UUID."""
        mock_table = MagicMock()

        response = validate_session(mock_table, "not-a-uuid")

        assert isinstance(response, InvalidSessionResponse)
        assert response.valid is False
        assert response.error == "invalid_user_id"

    def test_returns_invalid_for_nonexistent_user(self):
        """Should return invalid for nonexistent user."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        user_id = str(uuid.uuid4())

        response = validate_session(mock_table, user_id)

        assert isinstance(response, InvalidSessionResponse)
        assert response.valid is False
        assert response.error == "user_not_found"

    def test_returns_invalid_for_expired_session(self):
        """Should return invalid for expired session."""
        mock_table = MagicMock()
        user_id = str(uuid.uuid4())
        past = datetime.now(UTC) - timedelta(days=1)

        mock_table.get_item.return_value = {
            "Item": {
                "user_id": user_id,
                "auth_type": "anonymous",
                "created_at": past.isoformat(),
                "last_active_at": past.isoformat(),
                "session_expires_at": past.isoformat(),
                "timezone": "UTC",
            }
        }

        response = validate_session(mock_table, user_id)

        assert isinstance(response, InvalidSessionResponse)
        assert response.valid is False
        assert response.error == "session_expired"

    def test_returns_valid_for_active_session(self):
        """Should return valid for active session."""
        mock_table = MagicMock()
        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        future = now + timedelta(days=15)

        mock_table.get_item.return_value = {
            "Item": {
                "user_id": user_id,
                "auth_type": "anonymous",
                "created_at": now.isoformat(),
                "last_active_at": now.isoformat(),
                "session_expires_at": future.isoformat(),
                "timezone": "UTC",
            }
        }

        response = validate_session(mock_table, user_id)

        assert isinstance(response, ValidateSessionResponse)
        assert response.valid is True
        assert response.user_id == user_id
        assert response.auth_type == "anonymous"

    def test_updates_last_active_on_valid(self):
        """Should update last_active_at for valid session."""
        mock_table = MagicMock()
        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        future = now + timedelta(days=15)

        mock_table.get_item.return_value = {
            "Item": {
                "user_id": user_id,
                "auth_type": "anonymous",
                "created_at": now.isoformat(),
                "last_active_at": now.isoformat(),
                "session_expires_at": future.isoformat(),
                "timezone": "UTC",
            }
        }

        validate_session(mock_table, user_id)

        mock_table.update_item.assert_called_once()


class TestGetUserById:
    """Tests for get_user_by_id function."""

    def test_returns_none_for_nonexistent(self):
        """Should return None for nonexistent user."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = get_user_by_id(mock_table, str(uuid.uuid4()))

        assert result is None

    def test_returns_none_for_expired_session(self):
        """Should return None for expired session."""
        mock_table = MagicMock()
        user_id = str(uuid.uuid4())
        past = datetime.now(UTC) - timedelta(days=1)

        mock_table.get_item.return_value = {
            "Item": {
                "user_id": user_id,
                "auth_type": "anonymous",
                "created_at": past.isoformat(),
                "last_active_at": past.isoformat(),
                "session_expires_at": past.isoformat(),
                "timezone": "UTC",
            }
        }

        result = get_user_by_id(mock_table, user_id)

        assert result is None

    def test_returns_user_for_valid_session(self):
        """Should return User for valid session."""
        mock_table = MagicMock()
        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        future = now + timedelta(days=15)

        mock_table.get_item.return_value = {
            "Item": {
                "user_id": user_id,
                "auth_type": "anonymous",
                "created_at": now.isoformat(),
                "last_active_at": now.isoformat(),
                "session_expires_at": future.isoformat(),
                "timezone": "UTC",
            }
        }

        result = get_user_by_id(mock_table, user_id)

        assert result is not None
        assert result.user_id == user_id


class TestExtendSession:
    """Tests for extend_session function."""

    def test_returns_none_for_invalid_user(self):
        """Should return None for invalid user."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = extend_session(mock_table, str(uuid.uuid4()))

        assert result is None

    def test_extends_session_by_30_days(self):
        """Should extend session by 30 days."""
        mock_table = MagicMock()
        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        soon = now + timedelta(days=5)

        mock_table.get_item.return_value = {
            "Item": {
                "user_id": user_id,
                "auth_type": "anonymous",
                "created_at": now.isoformat(),
                "last_active_at": now.isoformat(),
                "session_expires_at": soon.isoformat(),
                "timezone": "UTC",
            }
        }

        result = extend_session(mock_table, user_id)

        assert result is not None
        mock_table.update_item.assert_called_once()

        # Check new expiry is ~30 days from now
        call_args = mock_table.update_item.call_args
        new_expiry = call_args.kwargs["ExpressionAttributeValues"][":expires"]
        new_expiry_dt = datetime.fromisoformat(new_expiry)
        days_extended = (new_expiry_dt - now).days

        assert 29 <= days_extended <= 31

"""Unit tests for auth endpoints (T047-T048, Feature 1048 bypass prevention)."""

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
from src.lambdas.shared.middleware.auth_middleware import (
    AuthType,
    extract_auth_context_typed,
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


class TestAuthContextTyped:
    """Tests for extract_auth_context_typed function (Feature 1048).

    These tests verify that auth_type is determined by TOKEN VALIDATION,
    not by request headers. This prevents the X-Auth-Type header bypass.
    """

    def test_uuid_bearer_returns_anonymous_auth_type(self):
        """UUID Bearer token should return AuthType.ANONYMOUS."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"Authorization": f"Bearer {user_id}"}}

        context = extract_auth_context_typed(event)

        assert context.user_id == user_id
        assert context.auth_type == AuthType.ANONYMOUS
        assert context.auth_method == "bearer"

    def test_x_user_id_header_returns_anonymous_auth_type(self):
        """X-User-ID header should return AuthType.ANONYMOUS."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"X-User-ID": user_id}}

        context = extract_auth_context_typed(event)

        assert context.user_id == user_id
        assert context.auth_type == AuthType.ANONYMOUS
        assert context.auth_method == "x-user-id"

    def test_no_auth_returns_anonymous_with_none_user_id(self):
        """No auth headers should return ANONYMOUS with user_id=None."""
        event = {"headers": {}}

        context = extract_auth_context_typed(event)

        assert context.user_id is None
        assert context.auth_type == AuthType.ANONYMOUS
        assert context.auth_method is None

    def test_x_auth_type_header_is_ignored(self):
        """X-Auth-Type header should NOT affect auth_type determination.

        Feature 1048: This is the key test that verifies the bypass fix.
        Anonymous users cannot claim to be authenticated via headers.
        """
        user_id = str(uuid.uuid4())
        event = {
            "headers": {
                "X-User-ID": user_id,
                "X-Auth-Type": "authenticated",  # Bypass attempt - should be IGNORED
            }
        }

        context = extract_auth_context_typed(event)

        # Auth type determined by token validation, not headers
        assert context.auth_type == AuthType.ANONYMOUS
        assert context.user_id == user_id

    def test_invalid_uuid_returns_none_user_id(self):
        """Invalid UUID in X-User-ID should return None user_id."""
        event = {"headers": {"X-User-ID": "not-a-valid-uuid"}}

        context = extract_auth_context_typed(event)

        assert context.user_id is None
        assert context.auth_type == AuthType.ANONYMOUS

    def test_bearer_prefers_over_x_user_id(self):
        """Bearer token should take precedence over X-User-ID header."""
        bearer_id = str(uuid.uuid4())
        header_id = str(uuid.uuid4())
        event = {
            "headers": {
                "Authorization": f"Bearer {bearer_id}",
                "X-User-ID": header_id,
            }
        }

        context = extract_auth_context_typed(event)

        assert context.user_id == bearer_id
        assert context.auth_method == "bearer"

    def test_case_insensitive_headers(self):
        """Headers should be matched case-insensitively."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"x-user-id": user_id}}  # lowercase

        context = extract_auth_context_typed(event)

        assert context.user_id == user_id
        assert context.auth_type == AuthType.ANONYMOUS

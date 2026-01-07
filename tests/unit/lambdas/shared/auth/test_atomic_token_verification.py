"""Unit tests for atomic token verification (Feature 014, User Story 2).

Tests for FR-004, FR-005, FR-006: Atomic magic link verification preventing race conditions.

These tests verify:
- Token can only be consumed exactly once via conditional update
- Second verification attempt returns TokenAlreadyUsedError
- Expired tokens return TokenExpiredError
- used_at and used_by_ip are recorded atomically
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.errors.session_errors import (
    TokenAlreadyUsedError,
    TokenExpiredError,
)
from src.lambdas.shared.models.magic_link_token import MagicLinkToken


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us2
class TestAtomicTokenVerification:
    """Tests for atomic token verification (FR-004, T026)."""

    def test_verify_and_consume_token_success(self):
        """FR-004: First verification succeeds and marks token as used."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        token = MagicLinkToken(
            token_id=token_id,
            email="test@example.com",
            # Feature 1166: signature removed
            created_at=now - timedelta(minutes=5),
            expires_at=now + timedelta(hours=1),
            used=False,
        )

        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": token.to_dynamodb_item()}
        mock_table.update_item.return_value = {}  # Success

        result = verify_and_consume_token(
            table=mock_table,
            token_id=token_id,
            client_ip="192.168.1.1",
        )

        assert result is not None
        assert result.token_id == token_id
        assert result.email == "test@example.com"

        # Verify conditional update was called
        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args
        assert "ConditionExpression" in call_args.kwargs
        assert "used = :false" in call_args.kwargs["ConditionExpression"]

    def test_verify_and_consume_token_records_audit_fields(self):
        """FR-004: Verification records used_at timestamp and client IP."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        token = MagicLinkToken(
            token_id=token_id,
            email="test@example.com",
            # Feature 1166: signature removed
            created_at=now - timedelta(minutes=5),
            expires_at=now + timedelta(hours=1),
            used=False,
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": token.to_dynamodb_item()}
        mock_table.update_item.return_value = {}

        verify_and_consume_token(
            table=mock_table,
            token_id=token_id,
            client_ip="10.0.0.1",
        )

        # Check update expression includes audit fields
        call_args = mock_table.update_item.call_args
        update_expr = call_args.kwargs["UpdateExpression"]
        assert "used_at" in update_expr
        assert "used_by_ip" in update_expr

        # Check values
        attr_values = call_args.kwargs["ExpressionAttributeValues"]
        assert ":ip" in attr_values
        assert attr_values[":ip"] == "10.0.0.1"

    def test_verify_and_consume_token_not_found(self):
        """Token not found returns None."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        mock_table = MagicMock()
        mock_table.get_item.return_value = {}  # No Item

        result = verify_and_consume_token(
            table=mock_table,
            token_id=str(uuid.uuid4()),
            client_ip="192.168.1.1",
        )

        assert result is None


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us2
class TestTokenAlreadyUsedError:
    """Tests for token already used error (FR-005, T027)."""

    def test_verify_already_used_token_raises_error(self):
        """FR-005: Second verification raises TokenAlreadyUsedError."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        used_at = now - timedelta(minutes=1)

        # Token already marked as used
        token = MagicLinkToken(
            token_id=token_id,
            email="test@example.com",
            # Feature 1166: signature removed
            created_at=now - timedelta(minutes=10),
            expires_at=now + timedelta(hours=1),
            used=True,
            used_at=used_at,
            used_by_ip="192.168.1.100",
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": token.to_dynamodb_item()}

        with pytest.raises(TokenAlreadyUsedError) as exc_info:
            verify_and_consume_token(
                table=mock_table,
                token_id=token_id,
                client_ip="192.168.1.200",
            )

        assert exc_info.value.token_id == token_id
        assert exc_info.value.used_at == used_at

    def test_conditional_update_fails_on_race_condition(self):
        """FR-005: Race condition triggers ConditionalCheckFailedException."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        token = MagicLinkToken(
            token_id=token_id,
            email="test@example.com",
            # Feature 1166: signature removed
            created_at=now - timedelta(minutes=5),
            expires_at=now + timedelta(hours=1),
            used=False,
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": token.to_dynamodb_item()}

        # Simulate race condition - conditional check fails
        # Create a mock exception class that matches boto3's structure
        class MockConditionalCheckFailedException(Exception):
            pass

        mock_table.meta.client.exceptions.ConditionalCheckFailedException = (
            MockConditionalCheckFailedException
        )
        mock_table.update_item.side_effect = MockConditionalCheckFailedException(
            "The conditional request failed"
        )

        with pytest.raises(TokenAlreadyUsedError) as exc_info:
            verify_and_consume_token(
                table=mock_table,
                token_id=token_id,
                client_ip="192.168.1.1",
            )

        assert exc_info.value.token_id == token_id

    def test_token_already_used_error_message(self):
        """TokenAlreadyUsedError has descriptive message."""
        used_at = datetime.now(UTC)
        error = TokenAlreadyUsedError(token_id="abc123", used_at=used_at)

        assert "abc123" in str(error)
        assert "already" in str(error).lower()


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us2
class TestTokenExpiredError:
    """Tests for token expired error (FR-006, T028)."""

    def test_verify_expired_token_raises_error(self):
        """FR-006: Expired token raises TokenExpiredError."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # Token expired 30 minutes ago
        token = MagicLinkToken(
            token_id=token_id,
            email="test@example.com",
            # Feature 1166: signature removed
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(minutes=30),
            used=False,
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": token.to_dynamodb_item()}

        with pytest.raises(TokenExpiredError) as exc_info:
            verify_and_consume_token(
                table=mock_table,
                token_id=token_id,
                client_ip="192.168.1.1",
            )

        assert exc_info.value.token_id == token_id

    def test_token_expiry_checked_before_consumption(self):
        """Expiry is checked before attempting conditional update."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # Expired token
        token = MagicLinkToken(
            token_id=token_id,
            email="test@example.com",
            # Feature 1166: signature removed
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(minutes=1),
            used=False,
        )

        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": token.to_dynamodb_item()}

        with pytest.raises(TokenExpiredError):
            verify_and_consume_token(
                table=mock_table,
                token_id=token_id,
                client_ip="192.168.1.1",
            )

        # update_item should NOT be called for expired tokens
        mock_table.update_item.assert_not_called()

    def test_token_expired_error_includes_expiry_time(self):
        """TokenExpiredError includes expiration timestamp."""
        expired_at = datetime.now(UTC) - timedelta(hours=1)
        error = TokenExpiredError(token_id="xyz789", expired_at=expired_at)

        assert "xyz789" in str(error)
        assert error.expired_at == expired_at


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us2
class TestMagicLinkTokenModel:
    """Tests for MagicLinkToken model Feature 014 fields."""

    def test_token_to_dynamodb_includes_audit_fields(self):
        """to_dynamodb_item includes used_at and used_by_ip when set."""
        now = datetime.now(UTC)
        token = MagicLinkToken(
            token_id=str(uuid.uuid4()),
            email="test@example.com",
            # Feature 1166: signature removed
            created_at=now,
            expires_at=now + timedelta(hours=1),
            used=True,
            used_at=now,
            used_by_ip="10.0.0.1",
        )

        item = token.to_dynamodb_item()

        assert "used_at" in item
        assert "used_by_ip" in item
        assert item["used_by_ip"] == "10.0.0.1"

    def test_token_from_dynamodb_parses_audit_fields(self):
        """from_dynamodb_item correctly parses used_at and used_by_ip."""
        now = datetime.now(UTC)
        item = {
            "PK": "TOKEN#abc123",
            "SK": "MAGIC_LINK",
            "token_id": "abc123",
            "email": "test@example.com",
            # Feature 1166: signature optional - testing backwards compat with old tokens
            "signature": "legacy-sig",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "used": True,
            "used_at": now.isoformat(),
            "used_by_ip": "192.168.1.50",
        }

        token = MagicLinkToken.from_dynamodb_item(item)

        assert token.used is True
        assert token.used_at is not None
        assert token.used_by_ip == "192.168.1.50"

    def test_token_without_audit_fields_defaults_to_none(self):
        """Tokens without audit fields default to None."""
        now = datetime.now(UTC)
        # Feature 1166: Test new tokens without signature field
        item = {
            "token_id": "abc123",
            "email": "test@example.com",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "used": False,
        }

        token = MagicLinkToken.from_dynamodb_item(item)

        assert token.used_at is None
        assert token.used_by_ip is None

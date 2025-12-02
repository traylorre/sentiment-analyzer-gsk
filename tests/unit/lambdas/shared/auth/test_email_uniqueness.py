"""Unit tests for email uniqueness enforcement (Feature 014, User Story 3).

Tests for FR-007, FR-008, FR-009: Email uniqueness via GSI + conditional writes.

These tests verify:
- Email GSI lookup returns correct user (FR-009)
- Conditional write rejects duplicate email (FR-007)
- Existing email returns existing user without creating duplicate (FR-008)
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.errors.session_errors import EmailAlreadyExistsError
from src.lambdas.shared.models.user import User


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us3
class TestEmailGSILookup:
    """Tests for email GSI lookup (FR-009, T035)."""

    def test_get_user_by_email_gsi_returns_user(self):
        """FR-009: GSI lookup returns user when email exists."""
        from src.lambdas.dashboard.auth import get_user_by_email_gsi

        now = datetime.now(UTC)
        existing_user = User(
            user_id=str(uuid.uuid4()),
            email="existing@example.com",
            auth_type="email",
            created_at=now,
            last_active_at=now,
            session_expires_at=now + timedelta(days=30),
        )

        mock_table = MagicMock()
        # GSI query returns the user
        mock_table.query.return_value = {
            "Items": [existing_user.to_dynamodb_item()],
            "Count": 1,
        }

        result = get_user_by_email_gsi(table=mock_table, email="existing@example.com")

        assert result is not None
        assert result.email == "existing@example.com"

        # Verify GSI query was used
        mock_table.query.assert_called_once()
        call_kwargs = mock_table.query.call_args.kwargs
        assert call_kwargs["IndexName"] == "by_email"

    def test_get_user_by_email_gsi_returns_none_when_not_found(self):
        """GSI lookup returns None when email doesn't exist."""
        from src.lambdas.dashboard.auth import get_user_by_email_gsi

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [], "Count": 0}

        result = get_user_by_email_gsi(
            table=mock_table, email="nonexistent@example.com"
        )

        assert result is None

    def test_get_user_by_email_gsi_case_insensitive(self):
        """FR-009: Email lookup is case-insensitive."""
        from src.lambdas.dashboard.auth import get_user_by_email_gsi

        now = datetime.now(UTC)
        existing_user = User(
            user_id=str(uuid.uuid4()),
            email="user@example.com",
            auth_type="email",
            created_at=now,
            last_active_at=now,
            session_expires_at=now + timedelta(days=30),
        )

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [existing_user.to_dynamodb_item()],
            "Count": 1,
        }

        # Query with uppercase email
        result = get_user_by_email_gsi(table=mock_table, email="USER@EXAMPLE.COM")

        assert result is not None
        # Verify lowercase was used in query
        call_kwargs = mock_table.query.call_args.kwargs
        assert call_kwargs["ExpressionAttributeValues"][":email"] == "user@example.com"

    def test_get_user_by_email_gsi_filters_by_entity_type(self):
        """GSI lookup filters by entity_type='USER' to exclude other entities."""
        from src.lambdas.dashboard.auth import get_user_by_email_gsi

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [], "Count": 0}

        get_user_by_email_gsi(table=mock_table, email="test@example.com")

        call_kwargs = mock_table.query.call_args.kwargs
        # Should filter by entity_type in the FilterExpression
        assert "entity_type" in call_kwargs.get("FilterExpression", "")


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us3
class TestConditionalWriteRejection:
    """Tests for conditional write rejection (FR-007, T036)."""

    def test_create_user_with_email_succeeds_new_email(self):
        """FR-007: User creation succeeds when email is new."""
        from src.lambdas.dashboard.auth import create_user_with_email

        mock_table = MagicMock()
        # GSI query returns no existing user
        mock_table.query.return_value = {"Items": [], "Count": 0}
        # put_item succeeds
        mock_table.put_item.return_value = {}

        user = create_user_with_email(
            table=mock_table,
            email="newuser@example.com",
            auth_type="email",
        )

        assert user is not None
        assert user.email == "newuser@example.com"
        assert user.auth_type == "email"
        mock_table.put_item.assert_called_once()

    def test_create_user_with_email_raises_on_duplicate(self):
        """FR-007: Conditional write raises EmailAlreadyExistsError on duplicate."""
        from src.lambdas.dashboard.auth import create_user_with_email

        existing_user_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        existing_user = User(
            user_id=existing_user_id,
            email="duplicate@example.com",
            auth_type="google",
            created_at=now,
            last_active_at=now,
            session_expires_at=now + timedelta(days=30),
        )

        mock_table = MagicMock()
        # GSI query returns existing user
        mock_table.query.return_value = {
            "Items": [existing_user.to_dynamodb_item()],
            "Count": 1,
        }

        with pytest.raises(EmailAlreadyExistsError) as exc_info:
            create_user_with_email(
                table=mock_table,
                email="duplicate@example.com",
                auth_type="email",
            )

        assert exc_info.value.email == "duplicate@example.com"
        assert exc_info.value.existing_user_id == existing_user_id
        # put_item should NOT be called
        mock_table.put_item.assert_not_called()

    def test_create_user_with_email_handles_race_condition(self):
        """FR-007: Race condition triggers EmailAlreadyExistsError."""
        from src.lambdas.dashboard.auth import create_user_with_email

        mock_table = MagicMock()
        # GSI query shows no user (yet)
        mock_table.query.return_value = {"Items": [], "Count": 0}

        # But put_item fails with ConditionalCheckFailedException (another request created user)
        class MockConditionalCheckFailedException(Exception):
            pass

        mock_table.meta.client.exceptions.ConditionalCheckFailedException = (
            MockConditionalCheckFailedException
        )
        mock_table.put_item.side_effect = MockConditionalCheckFailedException(
            "The conditional request failed"
        )

        with pytest.raises(EmailAlreadyExistsError) as exc_info:
            create_user_with_email(
                table=mock_table,
                email="race@example.com",
                auth_type="email",
            )

        assert exc_info.value.email == "race@example.com"


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us3
class TestExistingEmailReturnsUser:
    """Tests for existing email returning user (FR-008, T037)."""

    def test_get_or_create_user_returns_existing_user(self):
        """FR-008: Existing email returns the existing user without creating new."""
        from src.lambdas.dashboard.auth import get_or_create_user_by_email

        existing_user_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        existing_user = User(
            user_id=existing_user_id,
            email="existing@example.com",
            auth_type="google",
            created_at=now,
            last_active_at=now,
            session_expires_at=now + timedelta(days=30),
        )

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [existing_user.to_dynamodb_item()],
            "Count": 1,
        }

        user, is_new = get_or_create_user_by_email(
            table=mock_table,
            email="existing@example.com",
            auth_type="email",
        )

        assert user.user_id == existing_user_id
        assert is_new is False
        # put_item should NOT be called
        mock_table.put_item.assert_not_called()

    def test_get_or_create_user_creates_new_when_not_exists(self):
        """FR-008: New email creates new user."""
        from src.lambdas.dashboard.auth import get_or_create_user_by_email

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [], "Count": 0}
        mock_table.put_item.return_value = {}

        user, is_new = get_or_create_user_by_email(
            table=mock_table,
            email="newuser@example.com",
            auth_type="email",
        )

        assert user is not None
        assert user.email == "newuser@example.com"
        assert is_new is True
        mock_table.put_item.assert_called_once()

    def test_get_or_create_user_preserves_original_auth_type(self):
        """FR-008: Existing user's auth_type is preserved."""
        from src.lambdas.dashboard.auth import get_or_create_user_by_email

        now = datetime.now(UTC)
        existing_user = User(
            user_id=str(uuid.uuid4()),
            email="provider@example.com",
            auth_type="google",  # Original auth type
            created_at=now,
            last_active_at=now,
            session_expires_at=now + timedelta(days=30),
        )

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [existing_user.to_dynamodb_item()],
            "Count": 1,
        }

        # Try to create with different auth type
        user, is_new = get_or_create_user_by_email(
            table=mock_table,
            email="provider@example.com",
            auth_type="email",  # Different auth type
        )

        # Should return existing user with original auth type
        assert user.auth_type == "google"
        assert is_new is False


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us3
class TestEmailAlreadyExistsError:
    """Tests for EmailAlreadyExistsError exception."""

    def test_error_message_includes_email(self):
        """Error message includes the email address."""
        error = EmailAlreadyExistsError(email="test@example.com")

        assert "test@example.com" in str(error)

    def test_error_includes_existing_user_id(self):
        """Error includes existing_user_id when provided."""
        existing_id = str(uuid.uuid4())
        error = EmailAlreadyExistsError(
            email="test@example.com", existing_user_id=existing_id
        )

        assert error.existing_user_id == existing_id

    def test_error_without_existing_user_id(self):
        """Error works without existing_user_id (race condition case)."""
        error = EmailAlreadyExistsError(email="race@example.com")

        assert error.existing_user_id is None
        assert "race@example.com" in str(error)


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us6
class TestEmailGSIPerformance:
    """Tests for GSI query performance optimization (T071)."""

    def test_gsi_query_uses_limit_one(self):
        """GSI query uses Limit=1 for performance (only need one result)."""
        from src.lambdas.dashboard.auth import get_user_by_email_gsi

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        get_user_by_email_gsi(table=mock_table, email="test@example.com")

        # Verify Limit=1 is used
        call_kwargs = mock_table.query.call_args.kwargs
        assert call_kwargs.get("Limit") == 1

    def test_gsi_query_uses_index_name(self):
        """GSI query specifies correct index name."""
        from src.lambdas.dashboard.auth import get_user_by_email_gsi

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        get_user_by_email_gsi(table=mock_table, email="test@example.com")

        call_kwargs = mock_table.query.call_args.kwargs
        assert call_kwargs.get("IndexName") == "by_email"

    def test_gsi_query_normalizes_email_to_lowercase(self):
        """GSI query normalizes email to lowercase for consistent lookups."""
        from src.lambdas.dashboard.auth import get_user_by_email_gsi

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        get_user_by_email_gsi(table=mock_table, email="TeSt@EXAMPLE.COM")

        call_kwargs = mock_table.query.call_args.kwargs
        # Email in ExpressionAttributeValues should be lowercase
        assert call_kwargs["ExpressionAttributeValues"][":email"] == "test@example.com"

    def test_gsi_query_filters_by_entity_type(self):
        """GSI query filters by entity_type=USER."""
        from src.lambdas.dashboard.auth import get_user_by_email_gsi

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        get_user_by_email_gsi(table=mock_table, email="test@example.com")

        call_kwargs = mock_table.query.call_args.kwargs
        # Should have FilterExpression for entity_type
        assert "entity_type" in call_kwargs.get("FilterExpression", "")
        assert call_kwargs["ExpressionAttributeValues"][":type"] == "USER"

    def test_gsi_lookup_handles_no_results(self):
        """GSI lookup returns None when no user found."""
        from src.lambdas.dashboard.auth import get_user_by_email_gsi

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [], "Count": 0}

        result = get_user_by_email_gsi(table=mock_table, email="notfound@example.com")

        assert result is None

    def test_gsi_lookup_returns_first_result(self):
        """GSI lookup returns first result (there should only be one)."""
        from src.lambdas.dashboard.auth import get_user_by_email_gsi

        now = datetime.now(UTC)
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            auth_type="email",
            created_at=now,
            last_active_at=now,
            session_expires_at=now + timedelta(days=30),
        )

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [user.to_dynamodb_item()]}

        result = get_user_by_email_gsi(table=mock_table, email="test@example.com")

        assert result is not None
        assert result.email == "test@example.com"

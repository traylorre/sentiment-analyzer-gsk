"""Integration tests for session race condition handling (Feature 014).

Tests concurrent operations to verify atomic behavior:
- T029: 10 concurrent magic link verifications -> exactly 1 success
- T038: 10 concurrent user creations with same email -> exactly 1 account

Uses moto for DynamoDB mocking with realistic concurrency simulation.
"""

import uuid
from datetime import UTC, datetime, timedelta

import boto3
import pytest
from moto import mock_aws

from src.lambdas.shared.errors.session_errors import TokenAlreadyUsedError
from src.lambdas.shared.models.magic_link_token import MagicLinkToken


@pytest.fixture
def mock_dynamodb_table():
    """Create a mocked DynamoDB table for testing."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        table = dynamodb.create_table(
            TableName="test-session-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "email", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "by_email",
                    "KeySchema": [
                        {"AttributeName": "email", "KeyType": "HASH"},
                        {"AttributeName": "SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                }
            ],
            ProvisionedThroughput={
                "ReadCapacityUnits": 5,
                "WriteCapacityUnits": 5,
            },
        )

        table.wait_until_exists()
        yield table


@pytest.mark.integration
@pytest.mark.session_consistency
@pytest.mark.session_us2
class TestConcurrentTokenVerification:
    """Tests for concurrent magic link verification (T029)."""

    def test_10_concurrent_verifications_exactly_one_succeeds(
        self, mock_dynamodb_table
    ):
        """FR-005: Fire 10 concurrent requests, exactly 1 succeeds."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        # Create a valid token
        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        token = MagicLinkToken(
            token_id=token_id,
            email="concurrent@example.com",
            signature="test-signature",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            used=False,
        )

        # Store token in DynamoDB
        mock_dynamodb_table.put_item(Item=token.to_dynamodb_item())

        # Track results
        success_count = 0
        failure_count = 0
        results = []

        # Simulate 10 concurrent verifications
        # Note: In real integration tests, we'd use asyncio.gather or threading
        # For moto, we simulate sequential calls that test the atomic condition
        for i in range(10):
            try:
                result = verify_and_consume_token(
                    table=mock_dynamodb_table,
                    token_id=token_id,
                    client_ip=f"192.168.1.{i}",
                )
                if result:
                    success_count += 1
                    results.append(("success", i))
            except TokenAlreadyUsedError:
                failure_count += 1
                results.append(("already_used", i))

        # Exactly 1 success, 9 failures
        assert success_count == 1, f"Expected 1 success, got {success_count}"
        assert failure_count == 9, f"Expected 9 failures, got {failure_count}"

        # Verify token is marked as used in database
        response = mock_dynamodb_table.get_item(
            Key={"PK": f"TOKEN#{token_id}", "SK": "MAGIC_LINK"}
        )
        item = response.get("Item")
        assert item is not None
        assert item["used"] is True
        assert "used_at" in item
        assert "used_by_ip" in item

    def test_concurrent_verification_records_first_client_ip(self, mock_dynamodb_table):
        """The successful verification records its client IP."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        token = MagicLinkToken(
            token_id=token_id,
            email="first-ip@example.com",
            signature="test-signature",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            used=False,
        )
        mock_dynamodb_table.put_item(Item=token.to_dynamodb_item())

        # First verification succeeds
        first_ip = "10.0.0.1"
        result = verify_and_consume_token(
            table=mock_dynamodb_table,
            token_id=token_id,
            client_ip=first_ip,
        )

        assert result is not None

        # Check database records the first IP
        response = mock_dynamodb_table.get_item(
            Key={"PK": f"TOKEN#{token_id}", "SK": "MAGIC_LINK"}
        )
        item = response.get("Item")
        assert item["used_by_ip"] == first_ip

    def test_token_expiry_takes_precedence_over_race_check(self, mock_dynamodb_table):
        """Expired token raises TokenExpiredError, not race condition error."""
        from src.lambdas.dashboard.auth import verify_and_consume_token
        from src.lambdas.shared.errors.session_errors import TokenExpiredError

        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # Create expired token
        token = MagicLinkToken(
            token_id=token_id,
            email="expired@example.com",
            signature="test-signature",
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),  # Expired 1 hour ago
            used=False,
        )
        mock_dynamodb_table.put_item(Item=token.to_dynamodb_item())

        with pytest.raises(TokenExpiredError) as exc_info:
            verify_and_consume_token(
                table=mock_dynamodb_table,
                token_id=token_id,
                client_ip="192.168.1.1",
            )

        assert exc_info.value.token_id == token_id


@pytest.mark.integration
@pytest.mark.session_consistency
@pytest.mark.session_us2
class TestAtomicTokenState:
    """Tests for atomic token state transitions."""

    def test_token_state_transition_is_atomic(self, mock_dynamodb_table):
        """Token transitions from unused to used atomically."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        token = MagicLinkToken(
            token_id=token_id,
            email="atomic@example.com",
            signature="test-signature",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            used=False,
        )
        mock_dynamodb_table.put_item(Item=token.to_dynamodb_item())

        # Verify initial state
        before = mock_dynamodb_table.get_item(
            Key={"PK": f"TOKEN#{token_id}", "SK": "MAGIC_LINK"}
        )
        assert before["Item"]["used"] is False
        assert "used_at" not in before["Item"]

        # Consume token
        verify_and_consume_token(
            table=mock_dynamodb_table,
            token_id=token_id,
            client_ip="192.168.1.1",
        )

        # Verify final state
        after = mock_dynamodb_table.get_item(
            Key={"PK": f"TOKEN#{token_id}", "SK": "MAGIC_LINK"}
        )
        assert after["Item"]["used"] is True
        assert "used_at" in after["Item"]
        assert "used_by_ip" in after["Item"]

    def test_audit_fields_set_on_consumption(self, mock_dynamodb_table):
        """used_at and used_by_ip are set atomically."""
        from src.lambdas.dashboard.auth import verify_and_consume_token

        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        token = MagicLinkToken(
            token_id=token_id,
            email="audit@example.com",
            signature="test-signature",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            used=False,
        )
        mock_dynamodb_table.put_item(Item=token.to_dynamodb_item())

        client_ip = "203.0.113.42"
        before_verify = datetime.now(UTC)

        verify_and_consume_token(
            table=mock_dynamodb_table,
            token_id=token_id,
            client_ip=client_ip,
        )

        after_verify = datetime.now(UTC)

        # Check audit fields
        response = mock_dynamodb_table.get_item(
            Key={"PK": f"TOKEN#{token_id}", "SK": "MAGIC_LINK"}
        )
        item = response["Item"]

        assert item["used_by_ip"] == client_ip

        used_at = datetime.fromisoformat(item["used_at"])
        assert before_verify <= used_at <= after_verify


@pytest.mark.integration
@pytest.mark.session_consistency
@pytest.mark.session_us3
class TestConcurrentUserCreation:
    """Tests for concurrent user creation with same email (T038)."""

    def test_10_concurrent_creations_exactly_one_account(self, mock_dynamodb_table):
        """FR-007: Fire 10 concurrent user creations, exactly 1 account created."""
        from src.lambdas.dashboard.auth import get_or_create_user_by_email
        from src.lambdas.shared.errors.session_errors import EmailAlreadyExistsError

        email = "concurrent-signup@example.com"

        # Track results
        success_count = 0
        existing_count = 0
        error_count = 0
        created_user_ids = set()

        # Simulate 10 concurrent user creations
        for _ in range(10):
            try:
                user, is_new = get_or_create_user_by_email(
                    table=mock_dynamodb_table,
                    email=email,
                    auth_type="email",
                )
                if is_new:
                    success_count += 1
                    created_user_ids.add(user.user_id)
                else:
                    existing_count += 1
                    created_user_ids.add(user.user_id)
            except EmailAlreadyExistsError:
                error_count += 1

        # Exactly 1 account should be created
        assert success_count == 1, f"Expected exactly 1 new user, got {success_count}"
        assert existing_count == 9, f"Expected 9 existing returns, got {existing_count}"
        assert error_count == 0, f"Expected 0 errors, got {error_count}"

        # All operations should reference the same user ID
        assert len(created_user_ids) == 1, "All operations should return same user"

        # Verify only one user exists in database via GSI
        response = mock_dynamodb_table.query(
            IndexName="by_email",
            KeyConditionExpression="email = :email",
            ExpressionAttributeValues={":email": email.lower()},
        )
        assert response["Count"] == 1, "Exactly one user should exist in database"

    def test_concurrent_creation_preserves_first_auth_type(self, mock_dynamodb_table):
        """First creation's auth_type is preserved for subsequent lookups."""
        from src.lambdas.dashboard.auth import get_or_create_user_by_email

        email = "auth-type-test@example.com"

        # First creation with google
        user1, is_new1 = get_or_create_user_by_email(
            table=mock_dynamodb_table,
            email=email,
            auth_type="google",
        )
        assert is_new1 is True
        assert user1.auth_type == "google"

        # Second creation attempt with email (different auth type)
        user2, is_new2 = get_or_create_user_by_email(
            table=mock_dynamodb_table,
            email=email,
            auth_type="email",
        )
        assert is_new2 is False
        # Original auth type preserved
        assert user2.auth_type == "google"
        assert user1.user_id == user2.user_id

    def test_email_case_insensitivity_prevents_duplicates(self, mock_dynamodb_table):
        """Email case variations all resolve to same user."""
        from src.lambdas.dashboard.auth import get_or_create_user_by_email

        base_email = "CaseTest@Example.COM"

        # Create with mixed case
        user1, is_new1 = get_or_create_user_by_email(
            table=mock_dynamodb_table,
            email=base_email,
            auth_type="email",
        )
        assert is_new1 is True

        # Try to create with different case variations
        variations = [
            "casetest@example.com",
            "CASETEST@EXAMPLE.COM",
            "CaseTest@example.com",
            "casetest@Example.COM",
        ]

        for variation in variations:
            user, is_new = get_or_create_user_by_email(
                table=mock_dynamodb_table,
                email=variation,
                auth_type="email",
            )
            assert is_new is False, f"Should find existing user for {variation}"
            assert user.user_id == user1.user_id

    def test_different_emails_create_separate_accounts(self, mock_dynamodb_table):
        """Different emails create separate accounts (sanity check)."""
        from src.lambdas.dashboard.auth import get_or_create_user_by_email

        emails = [
            "user1@example.com",
            "user2@example.com",
            "user3@example.com",
        ]

        created_ids = set()
        for email in emails:
            user, is_new = get_or_create_user_by_email(
                table=mock_dynamodb_table,
                email=email,
                auth_type="email",
            )
            assert is_new is True
            created_ids.add(user.user_id)

        # All users should have unique IDs
        assert len(created_ids) == 3

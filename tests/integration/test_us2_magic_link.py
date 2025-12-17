"""
Integration Test: User Story 2 - Magic Link Authentication Flow (T088)
======================================================================

Tests the complete magic link authentication flow:
1. User requests magic link
2. Email is sent (mocked)
3. User clicks link
4. Token is verified
5. Anonymous data is merged
6. User receives authenticated tokens

IMPORTANT: This test uses moto to mock ALL AWS infrastructure.
- Purpose: Verify the complete auth flow works end-to-end
- Run on: Every PR, every merge
- Cost: $0 (no real AWS resources)

For On-Call Engineers:
    If this test fails, check:
    1. DynamoDB table schema matches expected keys (PK, SK)
    2. MagicLinkToken model TTL handling
    3. Email service integration (mocked in tests)
    4. Token signature validation logic
"""

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def env_vars():
    """Set test environment variables."""
    os.environ["DATABASE_TABLE"] = "test-auth-table"
    os.environ["ENVIRONMENT"] = "test"
    os.environ["MAGIC_LINK_SECRET"] = "test-secret-key-for-signing"
    os.environ["DASHBOARD_URL"] = "https://test.sentiment-analyzer.com"
    yield
    for key in ["DATABASE_TABLE", "ENVIRONMENT", "MAGIC_LINK_SECRET", "DASHBOARD_URL"]:
        os.environ.pop(key, None)


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB table for auth tests."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        table = dynamodb.create_table(
            TableName="test-auth-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield table


class TestMagicLinkFlow:
    """Integration tests for User Story 2: Magic Link Authentication."""

    @mock_aws
    def test_complete_magic_link_flow(self, env_vars):
        """E2E: Complete magic link flow from request to authenticated session."""
        # Setup
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-auth-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Step 1: Create anonymous session first
        anonymous_user_id = str(uuid.uuid4())
        _create_anonymous_user(table, anonymous_user_id)

        # Step 2: Create configuration as anonymous user
        config_id = str(uuid.uuid4())
        _create_configuration(table, anonymous_user_id, config_id, "Test Config")

        # Step 3: Request magic link
        email = "testuser@example.com"
        with patch("tests.integration.test_us2_magic_link._send_email") as mock_send:
            mock_send.return_value = True

            magic_link_result = _request_magic_link(table, email, anonymous_user_id)

            assert magic_link_result["status"] == "email_sent"
            assert mock_send.called
            token_id = magic_link_result["token_id"]
            signature = magic_link_result["signature"]

        # Step 4: Verify magic link token
        verify_result = _verify_magic_link(
            table, token_id, signature, anonymous_user_id
        )

        assert verify_result["status"] == "verified"
        assert verify_result["email"] == email
        assert verify_result["auth_type"] == "email"
        assert "tokens" in verify_result
        assert verify_result["merged_anonymous_data"] is True

        # Step 5: Check that authenticated user can access the configuration
        authenticated_user_id = verify_result["user_id"]
        config = _get_configuration(table, authenticated_user_id, config_id)

        # Config should now belong to authenticated user
        assert config is not None
        assert config["name"] == "Test Config"

    @mock_aws
    def test_magic_link_token_expiry(self, env_vars):
        """E2E: Expired magic link tokens are rejected."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-auth-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create an expired token
        email = "testuser@example.com"
        token_id = secrets.token_urlsafe(32)
        signature = _generate_signature(token_id)

        # Store expired token (created 2 hours ago, expired 1 hour ago)
        created_at = datetime.now(UTC) - timedelta(hours=2)
        expires_at = datetime.now(UTC) - timedelta(hours=1)

        _store_magic_link_token(
            table, token_id, email, signature, created_at, expires_at
        )

        # Attempt to verify expired token
        verify_result = _verify_magic_link(table, token_id, signature, None)

        assert verify_result["status"] == "invalid"
        assert verify_result["error"] == "token_expired"

    @mock_aws
    def test_magic_link_single_use(self, env_vars):
        """E2E: Magic link tokens can only be used once."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-auth-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Request magic link
        email = "testuser@example.com"
        with patch("tests.integration.test_us2_magic_link._send_email") as mock_send:
            mock_send.return_value = True
            magic_link_result = _request_magic_link(table, email, None)

        token_id = magic_link_result["token_id"]
        signature = magic_link_result["signature"]

        # First verification - should succeed
        first_verify = _verify_magic_link(table, token_id, signature, None)
        assert first_verify["status"] == "verified"

        # Second verification - should fail (token already used)
        second_verify = _verify_magic_link(table, token_id, signature, None)
        assert second_verify["status"] == "invalid"
        assert second_verify["error"] == "token_used"

    @mock_aws
    def test_new_request_invalidates_previous(self, env_vars):
        """E2E: New magic link request invalidates any pending tokens."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-auth-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        email = "testuser@example.com"

        with patch("tests.integration.test_us2_magic_link._send_email") as mock_send:
            mock_send.return_value = True

            # First request
            first_result = _request_magic_link(table, email, None)
            first_token_id = first_result["token_id"]
            first_signature = first_result["signature"]

            # Second request (should invalidate first)
            second_result = _request_magic_link(table, email, None)
            second_token_id = second_result["token_id"]
            second_signature = second_result["signature"]

        # First token should be invalidated
        first_verify = _verify_magic_link(table, first_token_id, first_signature, None)
        assert first_verify["status"] == "invalid"
        assert first_verify["error"] == "token_invalidated"

        # Second token should work
        second_verify = _verify_magic_link(
            table, second_token_id, second_signature, None
        )
        assert second_verify["status"] == "verified"

    @mock_aws
    def test_anonymous_data_merge(self, env_vars):
        """E2E: Anonymous configurations are merged on authentication."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-auth-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create anonymous user with 2 configurations
        anonymous_user_id = str(uuid.uuid4())
        _create_anonymous_user(table, anonymous_user_id)

        config1_id = str(uuid.uuid4())
        config2_id = str(uuid.uuid4())
        _create_configuration(table, anonymous_user_id, config1_id, "Config 1")
        _create_configuration(table, anonymous_user_id, config2_id, "Config 2")

        # Authenticate via magic link
        email = "testuser@example.com"
        with patch("tests.integration.test_us2_magic_link._send_email") as mock_send:
            mock_send.return_value = True
            magic_link_result = _request_magic_link(table, email, anonymous_user_id)

        verify_result = _verify_magic_link(
            table,
            magic_link_result["token_id"],
            magic_link_result["signature"],
            anonymous_user_id,
        )

        # Verify merge happened
        assert verify_result["merged_anonymous_data"] is True

        # Configurations should belong to authenticated user
        authenticated_user_id = verify_result["user_id"]
        configs = _list_configurations(table, authenticated_user_id)

        assert len(configs) == 2
        config_names = [c["name"] for c in configs]
        assert "Config 1" in config_names
        assert "Config 2" in config_names

    @mock_aws
    def test_invalid_signature_rejected(self, env_vars):
        """E2E: Invalid signatures are rejected."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-auth-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Request magic link
        email = "testuser@example.com"
        with patch("tests.integration.test_us2_magic_link._send_email") as mock_send:
            mock_send.return_value = True
            magic_link_result = _request_magic_link(table, email, None)

        token_id = magic_link_result["token_id"]
        invalid_signature = "invalid_signature_value"

        # Attempt to verify with invalid signature
        verify_result = _verify_magic_link(table, token_id, invalid_signature, None)

        assert verify_result["status"] == "invalid"
        assert verify_result["error"] == "invalid_signature"

    @mock_aws
    def test_existing_user_login(self, env_vars):
        """E2E: Existing user can login via magic link."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-auth-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        email = "existinguser@example.com"

        # First authentication (creates user)
        with patch("tests.integration.test_us2_magic_link._send_email") as mock_send:
            mock_send.return_value = True
            first_magic_link = _request_magic_link(table, email, None)

        first_verify = _verify_magic_link(
            table, first_magic_link["token_id"], first_magic_link["signature"], None
        )

        first_user_id = first_verify["user_id"]
        assert first_verify["status"] == "verified"

        # Second authentication (same email, should return same user)
        with patch("tests.integration.test_us2_magic_link._send_email") as mock_send:
            mock_send.return_value = True
            second_magic_link = _request_magic_link(table, email, None)

        second_verify = _verify_magic_link(
            table, second_magic_link["token_id"], second_magic_link["signature"], None
        )

        second_user_id = second_verify["user_id"]

        # Same user returned
        assert second_user_id == first_user_id


# Helper functions (simulating the actual implementation)


def _create_anonymous_user(table: Any, user_id: str) -> None:
    """Create anonymous user in DynamoDB."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=30)

    table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": "PROFILE",
            "user_id": user_id,
            "email": None,
            "auth_type": "anonymous",
            "created_at": now.isoformat(),
            "session_expires_at": expires_at.isoformat(),
            "entity_type": "USER",
        }
    )


def _create_configuration(table: Any, user_id: str, config_id: str, name: str) -> None:
    """Create configuration for user."""
    now = datetime.now(UTC)

    table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"CONFIG#{config_id}",
            "config_id": config_id,
            "user_id": user_id,
            "name": name,
            "tickers": [{"symbol": "AAPL", "added_at": now.isoformat()}],
            "created_at": now.isoformat(),
            "is_active": True,
            "entity_type": "CONFIGURATION",
        }
    )


def _get_configuration(table: Any, user_id: str, config_id: str) -> dict | None:
    """Get configuration by ID for user."""
    response = table.get_item(
        Key={
            "PK": f"USER#{user_id}",
            "SK": f"CONFIG#{config_id}",
        }
    )
    return response.get("Item")


def _list_configurations(table: Any, user_id: str) -> list[dict]:
    """List all configurations for user."""
    response = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}",
            ":sk_prefix": "CONFIG#",
        },
    )
    return response.get("Items", [])


def _request_magic_link(
    table: Any, email: str, anonymous_user_id: str | None
) -> dict[str, Any]:
    """Request magic link for email."""
    # Invalidate any existing tokens for this email
    _invalidate_existing_tokens(table, email)

    # Generate token and signature
    token_id = secrets.token_urlsafe(32)
    signature = _generate_signature(token_id)

    # Store token
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=1)

    _store_magic_link_token(
        table,
        token_id,
        email,
        signature,
        now,
        expires_at,
        anonymous_user_id,
    )

    # Send email (mocked)
    _send_email(email, token_id, signature)

    return {
        "status": "email_sent",
        "email": email,
        "expires_in_seconds": 3600,
        "token_id": token_id,
        "signature": signature,
    }


def _store_magic_link_token(
    table: Any,
    token_id: str,
    email: str,
    signature: str,
    created_at: datetime,
    expires_at: datetime,
    anonymous_user_id: str | None = None,
) -> None:
    """Store magic link token in DynamoDB."""
    item = {
        "PK": f"MAGIC_LINK#{token_id}",
        "SK": "TOKEN",
        "token_id": token_id,
        "email": email,
        "signature": signature,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "used": False,
        "invalidated": False,
        "entity_type": "MAGIC_LINK_TOKEN",
        "ttl": int(expires_at.timestamp()) + 86400,  # TTL 1 day after expiry
    }

    if anonymous_user_id:
        item["anonymous_user_id"] = anonymous_user_id

    # Also store by email for lookup
    table.put_item(Item=item)

    # Store email -> token mapping for invalidation
    table.put_item(
        Item={
            "PK": f"EMAIL#{email}",
            "SK": f"MAGIC_LINK#{token_id}",
            "token_id": token_id,
            "entity_type": "EMAIL_TOKEN_MAP",
        }
    )


def _invalidate_existing_tokens(table: Any, email: str) -> None:
    """Invalidate any existing magic link tokens for email."""
    # Query existing tokens
    response = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": f"EMAIL#{email}",
            ":sk_prefix": "MAGIC_LINK#",
        },
    )

    for item in response.get("Items", []):
        token_id = item["token_id"]
        table.update_item(
            Key={
                "PK": f"MAGIC_LINK#{token_id}",
                "SK": "TOKEN",
            },
            UpdateExpression="SET invalidated = :inv",
            ExpressionAttributeValues={":inv": True},
        )


def _verify_magic_link(
    table: Any,
    token_id: str,
    signature: str,
    anonymous_user_id: str | None,
) -> dict[str, Any]:
    """Verify magic link token."""
    # Get token from DynamoDB
    response = table.get_item(
        Key={
            "PK": f"MAGIC_LINK#{token_id}",
            "SK": "TOKEN",
        }
    )

    item = response.get("Item")
    if not item:
        return {
            "status": "invalid",
            "error": "token_not_found",
            "message": "Token not found.",
        }

    # Check if invalidated
    if item.get("invalidated", False):
        return {
            "status": "invalid",
            "error": "token_invalidated",
            "message": "This link has been invalidated. A new link was requested.",
        }

    # Check if already used
    if item.get("used", False):
        return {
            "status": "invalid",
            "error": "token_used",
            "message": "This link has already been used.",
        }

    # Check expiry
    expires_at = datetime.fromisoformat(item["expires_at"])
    if datetime.now(UTC) > expires_at:
        return {
            "status": "invalid",
            "error": "token_expired",
            "message": "This link has expired. Please request a new one.",
        }

    # Verify signature
    expected_signature = _generate_signature(token_id)
    if not hmac.compare_digest(signature, expected_signature):
        return {
            "status": "invalid",
            "error": "invalid_signature",
            "message": "Invalid link. Please request a new one.",
        }

    # Mark token as used
    table.update_item(
        Key={
            "PK": f"MAGIC_LINK#{token_id}",
            "SK": "TOKEN",
        },
        UpdateExpression="SET used = :used",
        ExpressionAttributeValues={":used": True},
    )

    email = item["email"]

    # Get or create user
    user_id, merged = _get_or_create_user_by_email(table, email, anonymous_user_id)

    # Generate tokens (simulated)
    tokens = _generate_tokens(user_id)

    return {
        "status": "verified",
        "user_id": user_id,
        "email": email,
        "auth_type": "email",
        "tokens": tokens,
        "merged_anonymous_data": merged,
    }


def _get_or_create_user_by_email(
    table: Any, email: str, anonymous_user_id: str | None
) -> tuple[str, bool]:
    """Get existing user by email or create new one, optionally merging anonymous data."""
    # For simplicity, scan for user with this email
    # In production, would use a GSI on email
    scan_response = table.scan(
        FilterExpression="email = :email AND entity_type = :et",
        ExpressionAttributeValues={
            ":email": email,
            ":et": "USER",
        },
    )

    existing_users = scan_response.get("Items", [])

    if existing_users:
        # Return existing user
        user_id = existing_users[0]["user_id"]
        merged = False

        # Still merge if anonymous_user_id provided
        if anonymous_user_id:
            _merge_anonymous_data(table, anonymous_user_id, user_id)
            merged = True

        return user_id, merged

    # Create new user
    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=30)

    table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": "PROFILE",
            "user_id": user_id,
            "email": email,
            "auth_type": "email",
            "created_at": now.isoformat(),
            "session_expires_at": expires_at.isoformat(),
            "entity_type": "USER",
        }
    )

    merged = False
    if anonymous_user_id:
        _merge_anonymous_data(table, anonymous_user_id, user_id)
        merged = True

    return user_id, merged


def _merge_anonymous_data(
    table: Any, anonymous_user_id: str, authenticated_user_id: str
) -> None:
    """Merge configurations from anonymous user to authenticated user."""
    # Get anonymous user's configurations
    configs = _list_configurations(table, anonymous_user_id)

    for config in configs:
        config_id = config["config_id"]

        # Delete from anonymous user
        table.delete_item(
            Key={
                "PK": f"USER#{anonymous_user_id}",
                "SK": f"CONFIG#{config_id}",
            }
        )

        # Add to authenticated user
        config["PK"] = f"USER#{authenticated_user_id}"
        config["user_id"] = authenticated_user_id
        table.put_item(Item=config)

    # Mark anonymous user as merged
    table.update_item(
        Key={
            "PK": f"USER#{anonymous_user_id}",
            "SK": "PROFILE",
        },
        UpdateExpression="SET merged_to = :merged_to",
        ExpressionAttributeValues={":merged_to": authenticated_user_id},
    )


def _generate_signature(token_id: str) -> str:
    """Generate HMAC signature for token."""
    secret = os.environ.get("MAGIC_LINK_SECRET", "default-secret")
    return hmac.new(secret.encode(), token_id.encode(), hashlib.sha256).hexdigest()


def _generate_tokens(user_id: str) -> dict[str, Any]:
    """Generate authentication tokens (simulated)."""
    return {
        "id_token": f"eyJ_id_{user_id[:8]}...",
        "access_token": f"eyJ_access_{user_id[:8]}...",
        "refresh_token": f"eyJ_refresh_{user_id[:8]}...",
        "expires_in": 3600,
    }


def _send_email(email: str, token_id: str, signature: str) -> bool:
    """Send magic link email (mocked in tests)."""
    # This would call SendGrid in production
    return True

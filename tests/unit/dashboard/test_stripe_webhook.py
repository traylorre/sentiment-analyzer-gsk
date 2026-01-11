"""Unit tests for Stripe webhook handler.

Feature: 1191 - Mid-Session Tier Upgrade
"""

import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

# Set STRIPE_WEBHOOK_SECRET before importing modules that need it
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_for_unit_tests")

from src.lambdas.shared.models.webhook_event import WebhookEvent


class TestWebhookEvent:
    """Tests for WebhookEvent model."""

    def test_pk_sk_format(self):
        """Test PK/SK format follows single-table design."""
        event = WebhookEvent(
            event_id="evt_123",
            event_type="customer.subscription.created",
            user_id="user_456",
        )

        assert event.pk == "WEBHOOK#evt_123"
        assert event.sk == "WEBHOOK#evt_123"

    def test_to_dynamodb_item(self):
        """Test conversion to DynamoDB item format."""
        now = datetime.now(UTC)
        event = WebhookEvent(
            event_id="evt_123",
            event_type="customer.subscription.created",
            user_id="user_456",
            subscription_id="sub_789",
            processed_at=now,
            ttl=1234567890,
        )

        item = event.to_dynamodb_item()

        assert item["PK"] == "WEBHOOK#evt_123"
        assert item["SK"] == "WEBHOOK#evt_123"
        assert item["event_id"] == "evt_123"
        assert item["event_type"] == "customer.subscription.created"
        assert item["user_id"] == "user_456"
        assert item["subscription_id"] == "sub_789"
        assert item["ttl"] == 1234567890
        assert item["entity_type"] == "webhook_event"

    def test_to_dynamodb_item_without_optional_fields(self):
        """Test conversion when optional fields are None."""
        event = WebhookEvent(
            event_id="evt_123",
            event_type="customer.subscription.created",
            user_id="user_456",
        )

        item = event.to_dynamodb_item()

        assert "subscription_id" not in item
        assert "ttl" not in item

    def test_from_dynamodb_item(self):
        """Test parsing DynamoDB item to model."""
        now = datetime.now(UTC)
        item = {
            "PK": "WEBHOOK#evt_123",
            "SK": "WEBHOOK#evt_123",
            "event_id": "evt_123",
            "event_type": "customer.subscription.created",
            "user_id": "user_456",
            "subscription_id": "sub_789",
            "processed_at": now.isoformat(),
            "ttl": 1234567890,
        }

        event = WebhookEvent.from_dynamodb_item(item)

        assert event.event_id == "evt_123"
        assert event.event_type == "customer.subscription.created"
        assert event.user_id == "user_456"
        assert event.subscription_id == "sub_789"
        assert event.ttl == 1234567890


class TestMapStripePlanToRole:
    """Tests for map_stripe_plan_to_role function."""

    def test_known_price_id(self):
        """Test mapping known price IDs."""
        from src.lambdas.shared.auth.roles import map_stripe_plan_to_role

        assert map_stripe_plan_to_role("price_paid_monthly") == "paid"
        assert map_stripe_plan_to_role("price_paid_yearly") == "paid"
        assert map_stripe_plan_to_role("price_test_paid_monthly") == "paid"

    def test_unknown_price_id_defaults_to_paid(self):
        """Test unknown price IDs default to paid (conservative)."""
        from src.lambdas.shared.auth.roles import map_stripe_plan_to_role

        assert map_stripe_plan_to_role("unknown_price_xyz") == "paid"

    def test_none_price_id_defaults_to_paid(self):
        """Test None price ID defaults to paid."""
        from src.lambdas.shared.auth.roles import map_stripe_plan_to_role

        assert map_stripe_plan_to_role(None) == "paid"


class TestStripeUtils:
    """Tests for Stripe utility functions."""

    def test_extract_user_id_from_subscription(self):
        """Test extracting user_id from subscription metadata."""
        from src.lambdas.shared.auth.stripe_utils import (
            extract_user_id_from_subscription,
        )

        subscription = {
            "id": "sub_123",
            "metadata": {"user_id": "user_456"},
        }

        user_id = extract_user_id_from_subscription(subscription)
        assert user_id == "user_456"

    def test_extract_user_id_missing_metadata(self):
        """Test handling missing metadata."""
        from src.lambdas.shared.auth.stripe_utils import (
            extract_user_id_from_subscription,
        )

        subscription = {"id": "sub_123"}

        user_id = extract_user_id_from_subscription(subscription)
        assert user_id is None

    def test_extract_user_id_empty_metadata(self):
        """Test handling empty metadata."""
        from src.lambdas.shared.auth.stripe_utils import (
            extract_user_id_from_subscription,
        )

        subscription = {"id": "sub_123", "metadata": {}}

        user_id = extract_user_id_from_subscription(subscription)
        assert user_id is None

    def test_extract_price_id_from_subscription(self):
        """Test extracting price_id from subscription items."""
        from src.lambdas.shared.auth.stripe_utils import (
            extract_price_id_from_subscription,
        )

        subscription = {
            "id": "sub_123",
            "items": {
                "data": [
                    {"price": {"id": "price_paid_monthly"}},
                ]
            },
        }

        price_id = extract_price_id_from_subscription(subscription)
        assert price_id == "price_paid_monthly"

    def test_extract_price_id_no_items(self):
        """Test handling subscription with no items."""
        from src.lambdas.shared.auth.stripe_utils import (
            extract_price_id_from_subscription,
        )

        subscription = {"id": "sub_123", "items": {"data": []}}

        price_id = extract_price_id_from_subscription(subscription)
        assert price_id is None


class TestHandleStripeWebhook:
    """Tests for handle_stripe_webhook function."""

    @pytest.fixture
    def mock_table(self):
        """Create mock DynamoDB table."""
        table = MagicMock()
        table.table_name = "test-users"
        return table

    @pytest.fixture
    def mock_dynamodb(self):
        """Create mock DynamoDB client."""
        return MagicMock()

    def test_idempotency_already_processed(self, mock_table, mock_dynamodb):
        """Test idempotent handling of already processed events."""
        # Mock existing webhook event
        mock_table.get_item.return_value = {
            "Item": {"PK": "WEBHOOK#evt_123", "SK": "WEBHOOK#evt_123"}
        }

        # Mock signature verification
        with patch("src.lambdas.dashboard.auth.verify_stripe_signature") as mock_verify:
            mock_event = MagicMock()
            mock_event.id = "evt_123"
            mock_event.type = "customer.subscription.created"
            mock_verify.return_value = mock_event

            from src.lambdas.dashboard.auth import handle_stripe_webhook

            response = handle_stripe_webhook(
                table=mock_table,
                dynamodb=mock_dynamodb,
                payload=b"{}",
                signature="test_sig",
            )

            assert response.status == "already_processed"
            assert response.event_id == "evt_123"
            # Should not attempt transaction
            mock_dynamodb.transact_write_items.assert_not_called()

    def test_unhandled_event_type(self, mock_table, mock_dynamodb):
        """Test handling of unhandled event types."""
        mock_table.get_item.return_value = {}  # No existing event

        with patch("src.lambdas.dashboard.auth.verify_stripe_signature") as mock_verify:
            mock_event = MagicMock()
            mock_event.id = "evt_123"
            mock_event.type = "payment_intent.succeeded"  # Unhandled type
            mock_verify.return_value = mock_event

            from src.lambdas.dashboard.auth import handle_stripe_webhook

            response = handle_stripe_webhook(
                table=mock_table,
                dynamodb=mock_dynamodb,
                payload=b"{}",
                signature="test_sig",
            )

            assert response.status == "ignored"
            assert "not handled" in response.message

    def test_subscription_created_user_not_found(self, mock_table, mock_dynamodb):
        """Test handling when user is not found."""
        # No existing webhook event
        mock_table.get_item.side_effect = [
            {},  # First call: check webhook
            {},  # Second call: get user
        ]

        with patch("src.lambdas.dashboard.auth.verify_stripe_signature") as mock_verify:
            mock_event = MagicMock()
            mock_event.id = "evt_123"
            mock_event.type = "customer.subscription.created"
            mock_event.data.object = {
                "id": "sub_123",
                "metadata": {"user_id": "user_456"},
                "items": {"data": [{"price": {"id": "price_paid_monthly"}}]},
            }
            mock_verify.return_value = mock_event

            from src.lambdas.dashboard.auth import handle_stripe_webhook

            response = handle_stripe_webhook(
                table=mock_table,
                dynamodb=mock_dynamodb,
                payload=b"{}",
                signature="test_sig",
            )

            assert response.status == "skipped"
            assert "not found" in response.message.lower()

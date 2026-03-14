"""Tests for Notification and DigestSettings models."""

from datetime import datetime

from src.lambdas.shared.models.notification import DigestSettings, Notification


class TestNotification:
    """Tests for Notification model."""

    def _make_notification(self, **overrides):
        defaults = {
            "notification_id": "n-001",
            "user_id": "u-001",
            "alert_id": "a-001",
            "email": "test@example.com",
            "subject": "Alert triggered",
            "sent_at": datetime(2026, 1, 15, 10, 0),
            "status": "sent",
            "ticker": "AAPL",
            "alert_type": "threshold",
            "triggered_value": 150.5,
            "deep_link": "https://app.example.com/config/a-001",
        }
        defaults.update(overrides)
        return Notification(**defaults)

    def test_pk_sk(self):
        n = self._make_notification()
        assert n.pk == "USER#u-001"
        assert n.sk == "2026-01-15T10:00:00"

    def test_to_dynamodb_item_basic(self):
        n = self._make_notification()
        item = n.to_dynamodb_item()
        assert item["PK"] == "USER#u-001"
        assert item["entity_type"] == "NOTIFICATION"
        assert item["triggered_value"] == "150.5"
        assert "sendgrid_message_id" not in item

    def test_to_dynamodb_item_with_optional_fields(self):
        n = self._make_notification(
            sendgrid_message_id="sg-123",
            opened_at=datetime(2026, 1, 15, 11, 0),
            clicked_at=datetime(2026, 1, 15, 11, 5),
        )
        item = n.to_dynamodb_item()
        assert item["sendgrid_message_id"] == "sg-123"
        assert item["opened_at"] == "2026-01-15T11:00:00"
        assert item["clicked_at"] == "2026-01-15T11:05:00"

    def test_from_dynamodb_item_roundtrip(self):
        n = self._make_notification(
            sendgrid_message_id="sg-123",
            opened_at=datetime(2026, 1, 15, 11, 0),
            clicked_at=datetime(2026, 1, 15, 11, 5),
        )
        item = n.to_dynamodb_item()
        restored = Notification.from_dynamodb_item(item)
        assert restored.notification_id == "n-001"
        assert restored.opened_at == datetime(2026, 1, 15, 11, 0)
        assert restored.clicked_at == datetime(2026, 1, 15, 11, 5)

    def test_from_dynamodb_item_without_optional(self):
        n = self._make_notification()
        item = n.to_dynamodb_item()
        restored = Notification.from_dynamodb_item(item)
        assert restored.sendgrid_message_id is None
        assert restored.opened_at is None
        assert restored.clicked_at is None


class TestDigestSettings:
    """Tests for DigestSettings model."""

    def test_pk_sk(self):
        ds = DigestSettings(user_id="u-001")
        assert ds.pk == "USER#u-001"
        assert ds.sk == "DIGEST_SETTINGS"

    def test_to_dynamodb_item_basic(self):
        ds = DigestSettings(user_id="u-001")
        item = ds.to_dynamodb_item()
        assert item["entity_type"] == "DIGEST_SETTINGS"
        assert item["status"] == "disabled"
        assert "next_scheduled" not in item

    def test_to_dynamodb_item_with_schedule(self):
        ds = DigestSettings(
            user_id="u-001",
            status="enabled",
            next_scheduled=datetime(2026, 1, 16, 9, 0),
            last_sent=datetime(2026, 1, 15, 9, 0),
        )
        item = ds.to_dynamodb_item()
        assert item["next_scheduled"] == "2026-01-16T09:00:00"
        assert item["last_sent"] == "2026-01-15T09:00:00"

    def test_from_dynamodb_item_roundtrip(self):
        ds = DigestSettings(
            user_id="u-001",
            status="enabled",
            next_scheduled=datetime(2026, 1, 16, 9, 0),
            last_sent=datetime(2026, 1, 15, 9, 0),
        )
        item = ds.to_dynamodb_item()
        restored = DigestSettings.from_dynamodb_item(item)
        assert restored.user_id == "u-001"
        assert restored.status == "enabled"
        assert restored.next_scheduled == datetime(2026, 1, 16, 9, 0)

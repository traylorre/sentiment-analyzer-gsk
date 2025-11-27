"""Unit tests for notification endpoints (T137-T144)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.notifications import (
    DigestSettingsResponse,
    DisableAllResponse,
    ErrorResponse,
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationResponse,
    ResubscribeResponse,
    TriggerTestDigestResponse,
    UnsubscribeResponse,
    _calculate_next_scheduled,
    _generate_unsubscribe_signature,
    _validate_time_format,
    disable_all_notifications,
    generate_unsubscribe_token,
    get_digest_settings,
    get_notification,
    get_notification_preferences,
    list_notifications,
    resubscribe,
    trigger_test_digest,
    unsubscribe_via_token,
    update_digest_settings,
    update_notification_preferences,
)


@pytest.fixture
def mock_table():
    """Create a mock DynamoDB table."""
    return MagicMock()


@pytest.fixture
def user_id():
    """Generate a user ID."""
    return str(uuid.uuid4())


@pytest.fixture
def notification_id():
    """Generate a notification ID."""
    return str(uuid.uuid4())


@pytest.fixture
def alert_id():
    """Generate an alert ID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_notification_item(user_id, notification_id, alert_id):
    """Create a sample notification DynamoDB item."""
    return {
        "PK": f"USER#{user_id}",
        "SK": "2025-11-25T10:00:00+00:00",
        "notification_id": notification_id,
        "user_id": user_id,
        "alert_id": alert_id,
        "email": "test@example.com",
        "subject": "Alert: AAPL sentiment dropped below -0.3",
        "sent_at": "2025-11-25T10:00:00+00:00",
        "status": "sent",
        "ticker": "AAPL",
        "alert_type": "sentiment_threshold",
        "triggered_value": "-0.42",
        "deep_link": "https://app.example.com/dashboard/config/123?highlight=AAPL",
        "entity_type": "NOTIFICATION",
    }


class TestListNotifications:
    """Tests for list_notifications function."""

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_lists_notifications(
        self, mock_xray, mock_table, user_id, sample_notification_item
    ):
        """Lists user's notifications."""
        mock_table.query.return_value = {"Items": [sample_notification_item]}

        result = list_notifications(mock_table, user_id)

        assert isinstance(result, NotificationListResponse)
        assert len(result.notifications) == 1
        assert result.total == 1
        assert result.notifications[0].ticker == "AAPL"

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_filters_by_status(
        self, mock_xray, mock_table, user_id, sample_notification_item
    ):
        """Filters notifications by status."""
        failed_item = {**sample_notification_item, "status": "failed"}
        mock_table.query.return_value = {
            "Items": [sample_notification_item, failed_item]
        }

        result = list_notifications(mock_table, user_id, status="sent")

        assert len(result.notifications) == 1
        assert result.notifications[0].status == "sent"

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_filters_by_alert_id(
        self, mock_xray, mock_table, user_id, sample_notification_item, alert_id
    ):
        """Filters notifications by alert_id."""
        other_alert = {**sample_notification_item, "alert_id": str(uuid.uuid4())}
        mock_table.query.return_value = {
            "Items": [sample_notification_item, other_alert]
        }

        result = list_notifications(mock_table, user_id, alert_id=alert_id)

        assert len(result.notifications) == 1
        assert result.notifications[0].alert_id == alert_id

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_paginates_results(
        self, mock_xray, mock_table, user_id, sample_notification_item
    ):
        """Paginates notification list."""
        items = [sample_notification_item.copy() for _ in range(5)]
        for item in items:
            item["notification_id"] = str(uuid.uuid4())
        mock_table.query.return_value = {"Items": items}

        result = list_notifications(mock_table, user_id, limit=2, offset=1)

        assert len(result.notifications) == 2
        assert result.total == 5
        assert result.limit == 2
        assert result.offset == 1

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_enforces_max_limit(
        self, mock_xray, mock_table, user_id, sample_notification_item
    ):
        """Enforces max limit of 100."""
        mock_table.query.return_value = {"Items": [sample_notification_item]}

        result = list_notifications(mock_table, user_id, limit=200)

        assert result.limit == 100

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_returns_empty_list(self, mock_xray, mock_table, user_id):
        """Returns empty list when no notifications."""
        mock_table.query.return_value = {"Items": []}

        result = list_notifications(mock_table, user_id)

        assert len(result.notifications) == 0
        assert result.total == 0


class TestGetNotification:
    """Tests for get_notification function."""

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_gets_notification(
        self, mock_xray, mock_table, user_id, sample_notification_item, notification_id
    ):
        """Gets notification by ID."""
        mock_table.query.return_value = {"Items": [sample_notification_item]}

        result = get_notification(mock_table, user_id, notification_id)

        assert isinstance(result, NotificationResponse)
        assert result.notification_id == notification_id

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_includes_email_in_detail(
        self, mock_xray, mock_table, user_id, sample_notification_item, notification_id
    ):
        """Includes email in detail response."""
        mock_table.query.return_value = {"Items": [sample_notification_item]}

        result = get_notification(mock_table, user_id, notification_id)

        assert result.email == "test@example.com"

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_includes_tracking_info(
        self, mock_xray, mock_table, user_id, sample_notification_item, notification_id
    ):
        """Includes tracking info when available."""
        sample_notification_item["opened_at"] = "2025-11-25T10:30:00+00:00"
        sample_notification_item["clicked_at"] = "2025-11-25T10:31:00+00:00"
        mock_table.query.return_value = {"Items": [sample_notification_item]}

        result = get_notification(mock_table, user_id, notification_id)

        assert result.tracking is not None
        assert result.tracking.opened_at is not None

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_returns_none_for_not_found(self, mock_xray, mock_table, user_id):
        """Returns None when notification not found."""
        mock_table.query.return_value = {"Items": []}

        result = get_notification(mock_table, user_id, str(uuid.uuid4()))

        assert result is None


class TestGetNotificationPreferences:
    """Tests for get_notification_preferences function."""

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_gets_existing_preferences(self, mock_xray, mock_table, user_id):
        """Gets existing preferences."""
        mock_table.get_item.return_value = {
            "Item": {
                "email_notifications_enabled": True,
                "daily_digest_enabled": True,
                "digest_time": "08:00",
                "timezone": "America/Los_Angeles",
                "email_verified": True,
            }
        }

        result = get_notification_preferences(mock_table, user_id)

        assert isinstance(result, NotificationPreferencesResponse)
        assert result.email_notifications_enabled is True
        assert result.daily_digest_enabled is True
        assert result.digest_time == "08:00"

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_returns_defaults_for_new_user(self, mock_xray, mock_table, user_id):
        """Returns default preferences for new user."""
        mock_table.get_item.return_value = {}

        result = get_notification_preferences(mock_table, user_id)

        assert result.email_notifications_enabled is True
        assert result.daily_digest_enabled is False
        assert result.digest_time == "09:00"
        assert result.timezone == "America/New_York"


class TestUpdateNotificationPreferences:
    """Tests for update_notification_preferences function."""

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_updates_email_enabled(self, mock_xray, mock_table, user_id):
        """Updates email notifications enabled."""
        mock_table.get_item.return_value = {}

        result = update_notification_preferences(
            mock_table, user_id, email_notifications_enabled=False
        )

        assert isinstance(result, NotificationPreferencesResponse)
        mock_table.update_item.assert_called_once()

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_updates_digest_time(self, mock_xray, mock_table, user_id):
        """Updates digest time."""
        mock_table.get_item.return_value = {}

        result = update_notification_preferences(
            mock_table, user_id, digest_time="08:00"
        )

        assert isinstance(result, NotificationPreferencesResponse)

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_rejects_invalid_time_format(self, mock_xray, mock_table, user_id):
        """Rejects invalid time format."""
        result = update_notification_preferences(mock_table, user_id, digest_time="9am")

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_TIME"

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_rejects_invalid_timezone(self, mock_xray, mock_table, user_id):
        """Rejects invalid timezone."""
        result = update_notification_preferences(
            mock_table, user_id, timezone="Invalid/Zone"
        )

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_TIMEZONE"


class TestDisableAllNotifications:
    """Tests for disable_all_notifications function."""

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_disables_preferences_and_alerts(self, mock_xray, mock_table, user_id):
        """Disables preferences and all alerts."""
        mock_table.query.return_value = {
            "Items": [
                {"SK": "ALERT#123", "is_enabled": True},
                {"SK": "ALERT#456", "is_enabled": True},
            ]
        }

        result = disable_all_notifications(mock_table, user_id)

        assert isinstance(result, DisableAllResponse)
        assert result.status == "disabled"
        assert result.alerts_disabled == 2
        assert "disabled" in result.message.lower()


class TestUnsubscribeViaToken:
    """Tests for unsubscribe_via_token function."""

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_unsubscribes_with_valid_token(self, mock_xray, mock_table, user_id):
        """Unsubscribes with valid token."""
        secret_key = "test_secret_key"
        token = generate_unsubscribe_token(user_id, secret_key)

        result = unsubscribe_via_token(mock_table, token, secret_key)

        assert isinstance(result, UnsubscribeResponse)
        assert result.status == "unsubscribed"
        assert result.user_id == user_id

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_rejects_invalid_token_format(self, mock_xray, mock_table):
        """Rejects invalid token format."""
        result = unsubscribe_via_token(mock_table, "invalid_token", "secret")

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_TOKEN"

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_rejects_invalid_signature(self, mock_xray, mock_table, user_id):
        """Rejects token with invalid signature."""
        timestamp = datetime.now(UTC).isoformat()
        invalid_token = f"{user_id}|{timestamp}|wrong_signature"

        result = unsubscribe_via_token(mock_table, invalid_token, "secret")

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_TOKEN"

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_rejects_expired_token(self, mock_xray, mock_table, user_id):
        """Rejects expired token (older than 24 hours)."""
        secret_key = "test_secret"
        old_timestamp = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
        signature = _generate_unsubscribe_signature(user_id, old_timestamp, secret_key)
        expired_token = f"{user_id}|{old_timestamp}|{signature}"

        result = unsubscribe_via_token(mock_table, expired_token, secret_key)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_TOKEN"


class TestResubscribe:
    """Tests for resubscribe function."""

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_resubscribes_user(self, mock_xray, mock_table, user_id):
        """Resubscribes user."""
        result = resubscribe(mock_table, user_id)

        assert isinstance(result, ResubscribeResponse)
        assert result.status == "resubscribed"
        mock_table.update_item.assert_called_once()


class TestGetDigestSettings:
    """Tests for get_digest_settings function."""

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_gets_existing_settings(self, mock_xray, mock_table, user_id):
        """Gets existing digest settings."""
        mock_table.get_item.return_value = {
            "Item": {
                "user_id": user_id,
                "enabled": True,
                "time": "08:00",
                "timezone": "America/Los_Angeles",
                "include_all_configs": False,
                "config_ids": ["config-1", "config-2"],
                "next_scheduled": "2025-11-27T16:00:00+00:00",
            }
        }

        result = get_digest_settings(mock_table, user_id)

        assert isinstance(result, DigestSettingsResponse)
        assert result.enabled is True
        assert result.time == "08:00"
        assert result.include_all_configs is False

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_returns_defaults_for_new_user(self, mock_xray, mock_table, user_id):
        """Returns default settings for new user."""
        mock_table.get_item.return_value = {}

        result = get_digest_settings(mock_table, user_id)

        assert result.enabled is False
        assert result.time == "09:00"
        assert result.timezone == "America/New_York"
        assert result.include_all_configs is True


class TestUpdateDigestSettings:
    """Tests for update_digest_settings function."""

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_updates_enabled(self, mock_xray, mock_table, user_id):
        """Updates enabled status."""
        mock_table.get_item.return_value = {}

        result = update_digest_settings(mock_table, user_id, enabled=True)

        assert isinstance(result, DigestSettingsResponse)
        mock_table.update_item.assert_called_once()

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_updates_time(self, mock_xray, mock_table, user_id):
        """Updates digest time."""
        mock_table.get_item.return_value = {}

        result = update_digest_settings(mock_table, user_id, time="08:00")

        assert isinstance(result, DigestSettingsResponse)

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_rejects_invalid_time(self, mock_xray, mock_table, user_id):
        """Rejects invalid time format."""
        result = update_digest_settings(mock_table, user_id, time="9:00")

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_TIME"

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_rejects_invalid_timezone(self, mock_xray, mock_table, user_id):
        """Rejects invalid timezone."""
        result = update_digest_settings(mock_table, user_id, timezone="PST")

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_TIMEZONE"

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_requires_config_ids_when_not_all(self, mock_xray, mock_table, user_id):
        """Requires config_ids when include_all_configs is false."""
        result = update_digest_settings(mock_table, user_id, include_all_configs=False)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "CONFIG_IDS_REQUIRED"

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_accepts_config_ids_with_not_all(self, mock_xray, mock_table, user_id):
        """Accepts config_ids with include_all_configs=false."""
        mock_table.get_item.return_value = {}

        result = update_digest_settings(
            mock_table,
            user_id,
            include_all_configs=False,
            config_ids=["config-1"],
        )

        assert isinstance(result, DigestSettingsResponse)


class TestTriggerTestDigest:
    """Tests for trigger_test_digest function."""

    @patch("src.lambdas.dashboard.notifications.xray_recorder")
    def test_queues_test_digest(self, mock_xray, mock_table, user_id):
        """Queues test digest."""
        result = trigger_test_digest(mock_table, user_id)

        assert isinstance(result, TriggerTestDigestResponse)
        assert result.status == "test_queued"
        assert "1 minute" in result.message


class TestValidateTimeFormat:
    """Tests for _validate_time_format helper."""

    def test_accepts_valid_times(self):
        """Accepts valid HH:MM times."""
        assert _validate_time_format("00:00") is True
        assert _validate_time_format("09:00") is True
        assert _validate_time_format("12:30") is True
        assert _validate_time_format("23:59") is True

    def test_rejects_invalid_times(self):
        """Rejects invalid time formats."""
        assert _validate_time_format("9:00") is False  # Missing leading zero
        assert _validate_time_format("9am") is False
        assert _validate_time_format("25:00") is False
        assert _validate_time_format("12:60") is False
        assert _validate_time_format("invalid") is False
        assert _validate_time_format("") is False


class TestCalculateNextScheduled:
    """Tests for _calculate_next_scheduled helper."""

    def test_returns_future_time(self):
        """Returns a future timestamp."""
        result = _calculate_next_scheduled("09:00", "America/New_York")

        assert result.endswith("Z")
        # Parse and verify it's in the future
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert parsed > datetime.now(UTC) - timedelta(seconds=10)


class TestGenerateUnsubscribeSignature:
    """Tests for _generate_unsubscribe_signature helper."""

    def test_generates_consistent_signature(self):
        """Generates consistent signature for same inputs."""
        user_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()
        secret = "test_secret"

        sig1 = _generate_unsubscribe_signature(user_id, timestamp, secret)
        sig2 = _generate_unsubscribe_signature(user_id, timestamp, secret)

        assert sig1 == sig2

    def test_different_inputs_different_signature(self):
        """Different inputs produce different signatures."""
        timestamp = datetime.now(UTC).isoformat()
        secret = "test_secret"

        sig1 = _generate_unsubscribe_signature("user1", timestamp, secret)
        sig2 = _generate_unsubscribe_signature("user2", timestamp, secret)

        assert sig1 != sig2


class TestGenerateUnsubscribeToken:
    """Tests for generate_unsubscribe_token function."""

    def test_generates_valid_token(self):
        """Generates a valid token."""
        user_id = str(uuid.uuid4())
        secret = "test_secret"

        token = generate_unsubscribe_token(user_id, secret)

        parts = token.split("|")
        assert len(parts) == 3
        assert parts[0] == user_id

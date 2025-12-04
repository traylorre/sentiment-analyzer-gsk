"""Contract tests for notification endpoints (T128 - User Story 4).

Validates notification history endpoints per notification-api.md:
- GET /api/v2/notifications - List notifications with filtering
- GET /api/v2/notifications/{id} - Get notification detail
- GET /api/v2/notifications/preferences - Get preferences
- PATCH /api/v2/notifications/preferences - Update preferences
- POST /api/v2/notifications/disable-all - Disable all notifications
- GET /api/v2/notifications/unsubscribe - Unsubscribe via token
- POST /api/v2/notifications/resubscribe - Re-enable notifications
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel, Field

# --- Response Schema Definitions ---


class NotificationTracking(BaseModel):
    """Email tracking info."""

    opened_at: str | None = None
    clicked_at: str | None = None


class NotificationResponse(BaseModel):
    """Response schema for a single notification."""

    notification_id: str
    alert_id: str
    ticker: str
    alert_type: str
    triggered_value: float
    threshold_value: float
    subject: str
    sent_at: str
    status: str
    deep_link: str


class NotificationDetailResponse(NotificationResponse):
    """Detailed notification response."""

    threshold_direction: str
    body_preview: str
    email: str
    tracking: NotificationTracking | None = None


class NotificationListResponse(BaseModel):
    """Response for GET /api/v2/notifications."""

    notifications: list[NotificationResponse]
    total: int = Field(..., ge=0)
    limit: int
    offset: int


class NotificationPreferencesResponse(BaseModel):
    """User notification preferences."""

    email_notifications_enabled: bool
    daily_digest_enabled: bool
    digest_time: str
    timezone: str
    email: str
    email_verified: bool


class DisableAllResponse(BaseModel):
    """Response for POST /api/v2/notifications/disable-all."""

    status: str
    alerts_disabled: int
    message: str


class UnsubscribeResponse(BaseModel):
    """Response for unsubscribe endpoint."""

    status: str
    user_id: str | None = None
    message: str


class ResubscribeResponse(BaseModel):
    """Response for resubscribe endpoint."""

    status: str
    message: str


# --- Mock Notification API ---


class MockNotificationAPI:
    """Mock API for notification endpoints."""

    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100

    def __init__(self):
        self.notifications: dict[str, dict[str, Any]] = {}
        self.user_notifications: dict[
            str, list[str]
        ] = {}  # user_id -> notification_ids
        self.preferences: dict[str, dict[str, Any]] = {}  # user_id -> prefs
        self.unsubscribe_tokens: dict[str, str] = {}  # token -> user_id

    def _create_notification(
        self,
        user_id: str,
        alert_id: str,
        ticker: str,
        alert_type: str,
        triggered_value: float,
        threshold_value: float,
        status: str = "sent",
    ) -> dict[str, Any]:
        """Helper to create a notification (for testing)."""
        notification_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat() + "Z"

        notification = {
            "notification_id": notification_id,
            "alert_id": alert_id,
            "ticker": ticker,
            "alert_type": alert_type,
            "triggered_value": triggered_value,
            "threshold_value": threshold_value,
            "threshold_direction": (
                "below" if triggered_value < threshold_value else "above"
            ),
            "subject": f"Alert: {ticker} {alert_type.replace('_', ' ')} threshold crossed",
            "body_preview": f"The {alert_type.replace('_', ' ')} for {ticker} has changed...",
            "sent_at": now,
            "status": status,
            "email": "user@example.com",
            "deep_link": f"https://app.domain/dashboard?highlight={ticker}",
            "tracking": None,
        }

        self.notifications[notification_id] = notification
        self.user_notifications.setdefault(user_id, []).append(notification_id)
        return notification

    def list_notifications(
        self,
        user_id: str,
        status_filter: str | None = None,
        alert_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, dict[str, Any]]:
        """List notifications with optional filters."""
        # Clamp limit
        limit = min(limit, self.MAX_LIMIT)

        user_notif_ids = self.user_notifications.get(user_id, [])
        notifications = [
            self.notifications[nid]
            for nid in user_notif_ids
            if nid in self.notifications
        ]

        # Apply filters
        if status_filter:
            notifications = [n for n in notifications if n["status"] == status_filter]
        if alert_id:
            notifications = [n for n in notifications if n["alert_id"] == alert_id]

        total = len(notifications)

        # Apply pagination
        notifications = notifications[offset : offset + limit]

        # Convert to list response format (without detail fields)
        response_notifications = [
            {
                k: v
                for k, v in n.items()
                if k not in ("threshold_direction", "body_preview", "email", "tracking")
            }
            for n in notifications
        ]

        return 200, {
            "notifications": response_notifications,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_notification(
        self, user_id: str, notification_id: str
    ) -> tuple[int, dict[str, Any]]:
        """Get notification detail."""
        if notification_id not in self.notifications:
            return 404, {"error": "not_found", "message": "Notification not found"}

        if notification_id not in self.user_notifications.get(user_id, []):
            return 403, {"error": "forbidden", "message": "Access denied"}

        return 200, self.notifications[notification_id]

    def get_preferences(self, user_id: str) -> tuple[int, dict[str, Any]]:
        """Get user notification preferences."""
        if user_id not in self.preferences:
            # Return defaults
            return 200, {
                "email_notifications_enabled": True,
                "daily_digest_enabled": False,
                "digest_time": "09:00",
                "timezone": "America/New_York",
                "email": "user@example.com",
                "email_verified": True,
            }
        return 200, self.preferences[user_id]

    def update_preferences(
        self,
        user_id: str,
        email_notifications_enabled: bool | None = None,
        daily_digest_enabled: bool | None = None,
        digest_time: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Update notification preferences."""
        # Validate digest time format
        if digest_time:
            try:
                hours, minutes = digest_time.split(":")
                if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                    return 400, {
                        "error": "invalid_time",
                        "message": "Time must be in HH:MM format (24-hour)",
                    }
            except ValueError:
                return 400, {
                    "error": "invalid_time",
                    "message": "Time must be in HH:MM format (24-hour)",
                }

        # Get existing or defaults
        _, current = self.get_preferences(user_id)

        # Update fields
        if email_notifications_enabled is not None:
            current["email_notifications_enabled"] = email_notifications_enabled
        if daily_digest_enabled is not None:
            current["daily_digest_enabled"] = daily_digest_enabled
        if digest_time is not None:
            current["digest_time"] = digest_time

        self.preferences[user_id] = current
        return 200, current

    def disable_all(self, user_id: str) -> tuple[int, dict[str, Any]]:
        """Disable all notifications for user."""
        # Get or create preferences
        _, prefs = self.get_preferences(user_id)
        prefs["email_notifications_enabled"] = False
        prefs["daily_digest_enabled"] = False
        self.preferences[user_id] = prefs

        # Count alerts that would be disabled (mock)
        alerts_disabled = 5  # Simulated

        return 200, {
            "status": "disabled",
            "alerts_disabled": alerts_disabled,
            "message": "All notifications disabled",
        }

    def unsubscribe(self, token: str) -> tuple[int, dict[str, Any]]:
        """Unsubscribe via token from email."""
        if token not in self.unsubscribe_tokens:
            return 400, {
                "error": "invalid_token",
                "message": "Unsubscribe link is invalid or expired",
            }

        user_id = self.unsubscribe_tokens[token]

        # Disable notifications
        _, prefs = self.get_preferences(user_id)
        prefs["email_notifications_enabled"] = False
        self.preferences[user_id] = prefs

        return 200, {
            "status": "unsubscribed",
            "user_id": user_id,
            "message": "You have been unsubscribed from notification emails",
        }

    def resubscribe(self, user_id: str) -> tuple[int, dict[str, Any]]:
        """Re-enable email notifications."""
        _, prefs = self.get_preferences(user_id)
        prefs["email_notifications_enabled"] = True
        self.preferences[user_id] = prefs

        return 200, {
            "status": "resubscribed",
            "message": "Email notifications re-enabled",
        }


@pytest.fixture
def mock_api():
    """Create fresh mock API for each test."""
    return MockNotificationAPI()


@pytest.fixture
def user_id():
    """Generate a user ID for testing."""
    return str(uuid.uuid4())


# --- Contract Tests ---


class TestListNotifications:
    """Tests for GET /api/v2/notifications."""

    def test_lists_empty_notifications(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Empty list for user with no notifications."""
        status, response = mock_api.list_notifications(user_id)

        assert status == 200
        list_response = NotificationListResponse(**response)
        assert list_response.notifications == []
        assert list_response.total == 0

    def test_lists_user_notifications(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Lists all notifications for a user."""
        alert_id = str(uuid.uuid4())
        mock_api._create_notification(
            user_id, alert_id, "AAPL", "sentiment_threshold", -0.42, -0.3
        )
        mock_api._create_notification(
            user_id, alert_id, "TSLA", "volatility_threshold", 6.0, 5.0
        )

        status, response = mock_api.list_notifications(user_id)

        assert status == 200
        assert response["total"] == 2

    def test_filters_by_status(self, mock_api: MockNotificationAPI, user_id: str):
        """Filters notifications by status."""
        alert_id = str(uuid.uuid4())
        mock_api._create_notification(
            user_id, alert_id, "AAPL", "sentiment_threshold", -0.42, -0.3, status="sent"
        )
        mock_api._create_notification(
            user_id, alert_id, "TSLA", "volatility_threshold", 6.0, 5.0, status="failed"
        )

        status, response = mock_api.list_notifications(user_id, status_filter="sent")

        assert status == 200
        assert response["total"] == 1
        assert response["notifications"][0]["ticker"] == "AAPL"

    def test_filters_by_alert_id(self, mock_api: MockNotificationAPI, user_id: str):
        """Filters notifications by alert_id."""
        alert_a = str(uuid.uuid4())
        alert_b = str(uuid.uuid4())

        mock_api._create_notification(
            user_id, alert_a, "AAPL", "sentiment_threshold", -0.42, -0.3
        )
        mock_api._create_notification(
            user_id, alert_b, "TSLA", "volatility_threshold", 6.0, 5.0
        )

        status, response = mock_api.list_notifications(user_id, alert_id=alert_a)

        assert status == 200
        assert response["total"] == 1
        assert response["notifications"][0]["ticker"] == "AAPL"

    def test_respects_limit_parameter(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Respects limit parameter."""
        alert_id = str(uuid.uuid4())
        for i in range(10):
            mock_api._create_notification(
                user_id, alert_id, f"T{i:02d}", "sentiment_threshold", -0.42, -0.3
            )

        status, response = mock_api.list_notifications(user_id, limit=5)

        assert status == 200
        assert response["total"] == 10
        assert len(response["notifications"]) == 5
        assert response["limit"] == 5

    def test_respects_offset_parameter(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Respects offset for pagination."""
        alert_id = str(uuid.uuid4())
        for i in range(10):
            mock_api._create_notification(
                user_id, alert_id, f"T{i:02d}", "sentiment_threshold", -0.42, -0.3
            )

        status, response = mock_api.list_notifications(user_id, limit=5, offset=5)

        assert status == 200
        assert response["offset"] == 5
        assert len(response["notifications"]) == 5

    def test_caps_limit_at_max(self, mock_api: MockNotificationAPI, user_id: str):
        """Caps limit at maximum allowed value."""
        status, response = mock_api.list_notifications(user_id, limit=500)

        assert status == 200
        assert response["limit"] == 100  # MAX_LIMIT


class TestGetNotification:
    """Tests for GET /api/v2/notifications/{id}."""

    def test_gets_notification_detail(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Returns detailed notification info."""
        alert_id = str(uuid.uuid4())
        notification = mock_api._create_notification(
            user_id, alert_id, "AAPL", "sentiment_threshold", -0.42, -0.3
        )

        status, response = mock_api.get_notification(
            user_id, notification["notification_id"]
        )

        assert status == 200
        detail = NotificationDetailResponse(**response)
        assert detail.notification_id == notification["notification_id"]
        assert detail.ticker == "AAPL"
        assert detail.threshold_direction == "below"
        assert detail.body_preview is not None
        assert detail.email is not None
        assert detail.deep_link is not None

    def test_returns_404_for_nonexistent(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Returns 404 for nonexistent notification."""
        status, response = mock_api.get_notification(user_id, str(uuid.uuid4()))

        assert status == 404
        assert response["error"] == "not_found"

    def test_returns_403_for_other_user(self, mock_api: MockNotificationAPI):
        """Returns 403 when accessing another user's notification."""
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())
        alert_id = str(uuid.uuid4())

        notification = mock_api._create_notification(
            user_a, alert_id, "AAPL", "sentiment_threshold", -0.42, -0.3
        )

        status, response = mock_api.get_notification(
            user_b, notification["notification_id"]
        )

        assert status == 403
        assert response["error"] == "forbidden"


class TestPreferences:
    """Tests for notification preferences endpoints."""

    def test_gets_default_preferences(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Returns default preferences for new user."""
        status, response = mock_api.get_preferences(user_id)

        assert status == 200
        prefs = NotificationPreferencesResponse(**response)
        assert prefs.email_notifications_enabled is True
        assert prefs.daily_digest_enabled is False
        assert prefs.digest_time == "09:00"
        assert prefs.timezone == "America/New_York"

    def test_updates_email_notifications_enabled(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Updates email_notifications_enabled."""
        status, response = mock_api.update_preferences(
            user_id, email_notifications_enabled=False
        )

        assert status == 200
        assert response["email_notifications_enabled"] is False

    def test_updates_daily_digest_enabled(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Updates daily_digest_enabled."""
        status, response = mock_api.update_preferences(
            user_id, daily_digest_enabled=True
        )

        assert status == 200
        assert response["daily_digest_enabled"] is True

    def test_updates_digest_time(self, mock_api: MockNotificationAPI, user_id: str):
        """Updates digest_time."""
        status, response = mock_api.update_preferences(user_id, digest_time="08:00")

        assert status == 200
        assert response["digest_time"] == "08:00"

    def test_rejects_invalid_time_format(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Rejects invalid time format."""
        status, response = mock_api.update_preferences(user_id, digest_time="8am")

        assert status == 400
        assert response["error"] == "invalid_time"

    def test_rejects_out_of_range_time(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Rejects out of range time."""
        status, response = mock_api.update_preferences(user_id, digest_time="25:00")

        assert status == 400
        assert response["error"] == "invalid_time"


class TestDisableAll:
    """Tests for POST /api/v2/notifications/disable-all."""

    def test_disables_all_notifications(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Disables all notifications for user."""
        status, response = mock_api.disable_all(user_id)

        assert status == 200
        disable_response = DisableAllResponse(**response)
        assert disable_response.status == "disabled"
        assert disable_response.alerts_disabled >= 0
        assert "disabled" in disable_response.message.lower()

        # Verify preferences updated
        _, prefs = mock_api.get_preferences(user_id)
        assert prefs["email_notifications_enabled"] is False
        assert prefs["daily_digest_enabled"] is False


class TestUnsubscribe:
    """Tests for GET /api/v2/notifications/unsubscribe."""

    def test_unsubscribes_with_valid_token(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Unsubscribes with valid token."""
        token = str(uuid.uuid4())
        mock_api.unsubscribe_tokens[token] = user_id

        status, response = mock_api.unsubscribe(token)

        assert status == 200
        unsub_response = UnsubscribeResponse(**response)
        assert unsub_response.status == "unsubscribed"
        assert unsub_response.user_id == user_id

        # Verify preferences updated
        _, prefs = mock_api.get_preferences(user_id)
        assert prefs["email_notifications_enabled"] is False

    def test_rejects_invalid_token(self, mock_api: MockNotificationAPI):
        """Rejects invalid unsubscribe token."""
        status, response = mock_api.unsubscribe("invalid-token")

        assert status == 400
        assert response["error"] == "invalid_token"
        assert "invalid or expired" in response["message"].lower()


class TestResubscribe:
    """Tests for POST /api/v2/notifications/resubscribe."""

    def test_resubscribes_after_unsubscribe(
        self, mock_api: MockNotificationAPI, user_id: str
    ):
        """Re-enables notifications after unsubscribe."""
        # Disable first
        mock_api.update_preferences(user_id, email_notifications_enabled=False)

        status, response = mock_api.resubscribe(user_id)

        assert status == 200
        resub_response = ResubscribeResponse(**response)
        assert resub_response.status == "resubscribed"
        assert "re-enabled" in resub_response.message.lower()

        # Verify preferences updated
        _, prefs = mock_api.get_preferences(user_id)
        assert prefs["email_notifications_enabled"] is True


class TestUserIsolation:
    """Tests for user data isolation."""

    def test_users_only_see_own_notifications(self, mock_api: MockNotificationAPI):
        """Users can only see their own notifications."""
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())
        alert_id = str(uuid.uuid4())

        mock_api._create_notification(
            user_a, alert_id, "AAPL", "sentiment_threshold", -0.42, -0.3
        )
        mock_api._create_notification(
            user_b, alert_id, "TSLA", "volatility_threshold", 6.0, 5.0
        )

        _, list_a = mock_api.list_notifications(user_a)
        _, list_b = mock_api.list_notifications(user_b)

        assert list_a["total"] == 1
        assert list_a["notifications"][0]["ticker"] == "AAPL"

        assert list_b["total"] == 1
        assert list_b["notifications"][0]["ticker"] == "TSLA"

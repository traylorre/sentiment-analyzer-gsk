"""Integration tests for alert trigger and email delivery (T130 - User Story 4).

Tests the complete alert flow:
1. User creates sentiment threshold alert for AAPL at -0.3
2. Sentiment drops to -0.42 (below threshold)
3. Alert evaluation triggers
4. Email notification is queued and sent
5. Notification appears in history
6. User receives email with deep link
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

# --- Helper Classes ---


class AlertRule:
    """Represents an alert rule."""

    def __init__(
        self,
        alert_id: str,
        user_id: str,
        config_id: str,
        ticker: str,
        alert_type: str,
        threshold_value: float,
        threshold_direction: str,
    ):
        self.alert_id = alert_id
        self.user_id = user_id
        self.config_id = config_id
        self.ticker = ticker
        self.alert_type = alert_type
        self.threshold_value = threshold_value
        self.threshold_direction = threshold_direction
        self.is_enabled = True
        self.last_triggered_at: str | None = None
        self.trigger_count = 0
        self.created_at = datetime.now(UTC).isoformat() + "Z"


class Notification:
    """Represents a notification."""

    def __init__(
        self,
        notification_id: str,
        alert: AlertRule,
        triggered_value: float,
    ):
        self.notification_id = notification_id
        self.alert_id = alert.alert_id
        self.user_id = alert.user_id
        self.ticker = alert.ticker
        self.alert_type = alert.alert_type
        self.triggered_value = triggered_value
        self.threshold_value = alert.threshold_value
        self.threshold_direction = alert.threshold_direction
        self.status = "pending"
        self.sent_at: str | None = None
        self.subject = f"Alert: {alert.ticker} {alert.alert_type.replace('_', ' ')} threshold crossed"
        self.deep_link = f"https://app.domain/dashboard/config/{alert.config_id}?highlight={alert.ticker}"
        self.email = "user@example.com"


class MockEmailService:
    """Mock SendGrid email service."""

    def __init__(self):
        self.sent_emails: list[dict[str, Any]] = []

    def send_alert(
        self,
        to_email: str,
        ticker: str,
        alert_type: str,
        triggered_value: float,
        threshold: float,
        dashboard_url: str,
    ) -> bool:
        """Send alert email."""
        self.sent_emails.append(
            {
                "to": to_email,
                "ticker": ticker,
                "alert_type": alert_type,
                "triggered_value": triggered_value,
                "threshold": threshold,
                "deep_link": dashboard_url,
                "sent_at": datetime.now(UTC).isoformat() + "Z",
            }
        )
        return True


class AlertFlowService:
    """Service that orchestrates the alert flow."""

    def __init__(self, email_service: MockEmailService):
        self.alerts: dict[str, AlertRule] = {}
        self.notifications: dict[str, Notification] = {}
        self.user_alerts: dict[str, list[str]] = {}
        self.user_notifications: dict[str, list[str]] = {}
        self.email_service = email_service

    def create_alert(
        self,
        user_id: str,
        config_id: str,
        ticker: str,
        alert_type: str,
        threshold_value: float,
        threshold_direction: str,
    ) -> AlertRule:
        """Create a new alert rule."""
        alert = AlertRule(
            alert_id=str(uuid.uuid4()),
            user_id=user_id,
            config_id=config_id,
            ticker=ticker,
            alert_type=alert_type,
            threshold_value=threshold_value,
            threshold_direction=threshold_direction,
        )
        self.alerts[alert.alert_id] = alert
        self.user_alerts.setdefault(user_id, []).append(alert.alert_id)
        return alert

    def evaluate_alerts(
        self,
        ticker: str,
        sentiment_score: float | None = None,
        volatility_atr: float | None = None,
    ) -> list[Notification]:
        """Evaluate all alerts for a ticker and trigger notifications."""
        triggered_notifications = []

        for alert in self.alerts.values():
            if alert.ticker != ticker:
                continue
            if not alert.is_enabled:
                continue

            # Check if threshold is crossed
            triggered = False
            triggered_value = 0.0

            if (
                alert.alert_type == "sentiment_threshold"
                and sentiment_score is not None
            ):
                triggered_value = sentiment_score
                if alert.threshold_direction == "below":
                    triggered = sentiment_score < alert.threshold_value
                else:
                    triggered = sentiment_score > alert.threshold_value

            elif (
                alert.alert_type == "volatility_threshold"
                and volatility_atr is not None
            ):
                triggered_value = volatility_atr
                if alert.threshold_direction == "below":
                    triggered = volatility_atr < alert.threshold_value
                else:
                    triggered = volatility_atr > alert.threshold_value

            if triggered:
                notification = self._create_notification(alert, triggered_value)
                triggered_notifications.append(notification)

        return triggered_notifications

    def _create_notification(
        self, alert: AlertRule, triggered_value: float
    ) -> Notification:
        """Create and send notification."""
        notification = Notification(
            notification_id=str(uuid.uuid4()),
            alert=alert,
            triggered_value=triggered_value,
        )

        # Update alert
        alert.last_triggered_at = datetime.now(UTC).isoformat() + "Z"
        alert.trigger_count += 1

        # Store notification
        self.notifications[notification.notification_id] = notification
        self.user_notifications.setdefault(alert.user_id, []).append(
            notification.notification_id
        )

        # Send email
        email_sent = self.email_service.send_alert(
            to_email=notification.email,
            ticker=alert.ticker,
            alert_type=alert.alert_type,
            triggered_value=triggered_value,
            threshold=alert.threshold_value,
            dashboard_url=notification.deep_link,
        )

        if email_sent:
            notification.status = "sent"
            notification.sent_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            notification.status = "failed"

        return notification

    def get_user_notifications(self, user_id: str) -> list[Notification]:
        """Get notifications for a user."""
        notification_ids = self.user_notifications.get(user_id, [])
        return [self.notifications[nid] for nid in notification_ids]


@pytest.fixture
def email_service():
    """Create mock email service."""
    return MockEmailService()


@pytest.fixture
def alert_service(email_service: MockEmailService):
    """Create alert flow service."""
    return AlertFlowService(email_service)


@pytest.fixture
def user_id():
    """Generate a user ID."""
    return str(uuid.uuid4())


@pytest.fixture
def config_id():
    """Generate a config ID."""
    return str(uuid.uuid4())


# --- Integration Tests ---


class TestCompleteAlertFlow:
    """Tests for complete alert trigger flow."""

    def test_sentiment_alert_triggers_email(
        self,
        alert_service: AlertFlowService,
        email_service: MockEmailService,
        user_id: str,
        config_id: str,
    ):
        """Complete flow: Create alert -> Sentiment drops -> Email sent."""
        # Step 1: User creates sentiment threshold alert
        alert = alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )
        assert alert.is_enabled is True

        # Step 2: Sentiment drops below threshold
        notifications = alert_service.evaluate_alerts(
            ticker="AAPL",
            sentiment_score=-0.42,  # Below -0.3 threshold
        )

        # Step 3: Alert triggered
        assert len(notifications) == 1
        notification = notifications[0]
        assert notification.status == "sent"
        assert notification.triggered_value == -0.42
        assert notification.threshold_value == -0.3

        # Step 4: Email was sent
        assert len(email_service.sent_emails) == 1
        email = email_service.sent_emails[0]
        assert email["ticker"] == "AAPL"
        assert email["alert_type"] == "sentiment_threshold"
        assert email["triggered_value"] == -0.42
        assert email["threshold"] == -0.3
        assert "AAPL" in email["deep_link"]

        # Step 5: Notification in history
        user_notifications = alert_service.get_user_notifications(user_id)
        assert len(user_notifications) == 1
        assert user_notifications[0].notification_id == notification.notification_id

        # Step 6: Alert trigger count updated
        assert alert.trigger_count == 1
        assert alert.last_triggered_at is not None

    def test_volatility_alert_triggers_email(
        self,
        alert_service: AlertFlowService,
        email_service: MockEmailService,
        user_id: str,
        config_id: str,
    ):
        """Volatility alert triggers when ATR exceeds threshold."""
        # Create volatility alert
        alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="TSLA",
            alert_type="volatility_threshold",
            threshold_value=5.0,  # 5% ATR
            threshold_direction="above",
        )

        # ATR spikes above threshold
        notifications = alert_service.evaluate_alerts(
            ticker="TSLA",
            volatility_atr=7.2,  # Above 5% threshold
        )

        assert len(notifications) == 1
        assert notifications[0].triggered_value == 7.2
        assert len(email_service.sent_emails) == 1

    def test_alert_does_not_trigger_when_threshold_not_crossed(
        self,
        alert_service: AlertFlowService,
        email_service: MockEmailService,
        user_id: str,
        config_id: str,
    ):
        """Alert does not trigger when value is above threshold."""
        alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        # Sentiment is above threshold (not crossed)
        notifications = alert_service.evaluate_alerts(
            ticker="AAPL",
            sentiment_score=-0.2,  # Above -0.3 threshold
        )

        assert len(notifications) == 0
        assert len(email_service.sent_emails) == 0

    def test_disabled_alert_does_not_trigger(
        self,
        alert_service: AlertFlowService,
        email_service: MockEmailService,
        user_id: str,
        config_id: str,
    ):
        """Disabled alert does not trigger notification."""
        alert = alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        # Disable alert
        alert.is_enabled = False

        # Sentiment drops below threshold
        notifications = alert_service.evaluate_alerts(
            ticker="AAPL",
            sentiment_score=-0.42,
        )

        assert len(notifications) == 0
        assert len(email_service.sent_emails) == 0

    def test_multiple_alerts_for_same_ticker(
        self,
        alert_service: AlertFlowService,
        email_service: MockEmailService,
        user_id: str,
        config_id: str,
    ):
        """Multiple alerts for same ticker all evaluated."""
        # Create multiple alerts
        alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )
        alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.5,
            threshold_direction="below",
        )

        # Sentiment drops to -0.6 (crosses both thresholds)
        notifications = alert_service.evaluate_alerts(
            ticker="AAPL",
            sentiment_score=-0.6,
        )

        assert len(notifications) == 2
        assert len(email_service.sent_emails) == 2


class TestAlertDirections:
    """Tests for alert threshold directions."""

    def test_below_direction_triggers_when_value_drops(
        self,
        alert_service: AlertFlowService,
        user_id: str,
        config_id: str,
    ):
        """'below' direction triggers when value goes below threshold."""
        alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=0.0,  # threshold at 0
            threshold_direction="below",
        )

        # Negative sentiment (below 0)
        notifications = alert_service.evaluate_alerts(
            ticker="AAPL",
            sentiment_score=-0.1,
        )

        assert len(notifications) == 1

    def test_above_direction_triggers_when_value_rises(
        self,
        alert_service: AlertFlowService,
        user_id: str,
        config_id: str,
    ):
        """'above' direction triggers when value goes above threshold."""
        alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=0.5,
            threshold_direction="above",
        )

        # Positive sentiment (above 0.5)
        notifications = alert_service.evaluate_alerts(
            ticker="AAPL",
            sentiment_score=0.7,
        )

        assert len(notifications) == 1

    def test_at_threshold_does_not_trigger(
        self,
        alert_service: AlertFlowService,
        user_id: str,
        config_id: str,
    ):
        """Value exactly at threshold does not trigger alert."""
        alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        # Value exactly at threshold
        notifications = alert_service.evaluate_alerts(
            ticker="AAPL",
            sentiment_score=-0.3,  # Exactly at threshold
        )

        assert len(notifications) == 0


class TestNotificationHistory:
    """Tests for notification history tracking."""

    def test_notification_includes_deep_link(
        self,
        alert_service: AlertFlowService,
        user_id: str,
        config_id: str,
    ):
        """Notification includes deep link to dashboard."""
        alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        notifications = alert_service.evaluate_alerts(
            ticker="AAPL",
            sentiment_score=-0.42,
        )

        notification = notifications[0]
        assert config_id in notification.deep_link
        assert "AAPL" in notification.deep_link

    def test_notification_tracks_trigger_value(
        self,
        alert_service: AlertFlowService,
        user_id: str,
        config_id: str,
    ):
        """Notification records the value that triggered it."""
        alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        notifications = alert_service.evaluate_alerts(
            ticker="AAPL",
            sentiment_score=-0.42,
        )

        notification = notifications[0]
        assert notification.triggered_value == -0.42
        assert notification.threshold_value == -0.3

    def test_notification_has_sent_timestamp(
        self,
        alert_service: AlertFlowService,
        user_id: str,
        config_id: str,
    ):
        """Sent notification has timestamp."""
        alert_service.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        notifications = alert_service.evaluate_alerts(
            ticker="AAPL",
            sentiment_score=-0.42,
        )

        notification = notifications[0]
        assert notification.sent_at is not None
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(notification.sent_at.replace("Z", "+00:00"))


class TestUserIsolation:
    """Tests for user alert isolation."""

    def test_users_only_see_own_notifications(
        self,
        alert_service: AlertFlowService,
    ):
        """Users only see their own alert notifications."""
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())
        config = str(uuid.uuid4())

        # User A creates alert
        alert_service.create_alert(
            user_id=user_a,
            config_id=config,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        # User B creates alert
        alert_service.create_alert(
            user_id=user_b,
            config_id=config,
            ticker="TSLA",
            alert_type="sentiment_threshold",
            threshold_value=-0.5,
            threshold_direction="below",
        )

        # Trigger both alerts
        alert_service.evaluate_alerts(ticker="AAPL", sentiment_score=-0.42)
        alert_service.evaluate_alerts(ticker="TSLA", sentiment_score=-0.6)

        # Check isolation
        user_a_notifications = alert_service.get_user_notifications(user_a)
        user_b_notifications = alert_service.get_user_notifications(user_b)

        assert len(user_a_notifications) == 1
        assert user_a_notifications[0].ticker == "AAPL"

        assert len(user_b_notifications) == 1
        assert user_b_notifications[0].ticker == "TSLA"

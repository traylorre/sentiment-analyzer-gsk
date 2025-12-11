"""Unit tests for consecutive failure alerting (T045).

Tests the alerting system per US4 requirements:
- Alert after 3 consecutive failures within 15 minutes
- SNS notification delivery
- Alert suppression during non-market hours
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from src.lambdas.ingestion.alerting import (
    AlertPublisher,
    AlertType,
    ConsecutiveFailureAlert,
    create_alert_publisher,
)


class TestConsecutiveFailureAlert:
    """Tests for ConsecutiveFailureAlert data structure."""

    def test_alert_creation_with_required_fields(self) -> None:
        """Alert can be created with required fields."""
        alert = ConsecutiveFailureAlert(
            failure_count=3,
            window_minutes=15,
            first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
            sources_affected=["tiingo", "finnhub"],
            error_summary="Connection timeout",
        )

        assert alert.failure_count == 3
        assert alert.window_minutes == 15
        assert len(alert.sources_affected) == 2

    def test_alert_message_format(self) -> None:
        """Alert message should be formatted for SNS."""
        alert = ConsecutiveFailureAlert(
            failure_count=3,
            window_minutes=15,
            first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
            sources_affected=["tiingo"],
            error_summary="HTTP 503 Service Unavailable",
        )

        message = alert.to_sns_message()

        assert "3 consecutive failures" in message
        assert "15 minutes" in message
        assert "tiingo" in message
        assert "HTTP 503" in message

    def test_alert_subject_for_sns(self) -> None:
        """Alert subject should indicate severity."""
        alert = ConsecutiveFailureAlert(
            failure_count=3,
            window_minutes=15,
            first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
            sources_affected=["tiingo", "finnhub"],
            error_summary="All sources down",
        )

        subject = alert.to_sns_subject()

        assert "ALERT" in subject.upper()
        assert "Ingestion" in subject or "Collection" in subject


class TestAlertPublisher:
    """Tests for AlertPublisher SNS integration."""

    def test_publish_failure_alert_to_sns(self) -> None:
        """Should publish failure alert to SNS topic."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        alert = ConsecutiveFailureAlert(
            failure_count=3,
            window_minutes=15,
            first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
            sources_affected=["tiingo"],
            error_summary="Timeout",
        )

        publisher.publish_failure_alert(alert)

        mock_sns.publish.assert_called_once()
        call_kwargs = mock_sns.publish.call_args[1]
        assert call_kwargs["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:alerts"
        assert "Message" in call_kwargs
        assert "Subject" in call_kwargs

    def test_publish_handles_sns_error_gracefully(self, caplog) -> None:
        """Should log error but not raise on SNS failure."""
        mock_sns = MagicMock()
        mock_sns.publish.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameter", "Message": "Bad topic"}},
            "Publish",
        )
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        alert = ConsecutiveFailureAlert(
            failure_count=3,
            window_minutes=15,
            first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
            sources_affected=["tiingo"],
            error_summary="Timeout",
        )

        # Should not raise
        publisher.publish_failure_alert(alert)

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Failed to publish failure alert")

    def test_alert_includes_alert_type(self) -> None:
        """Alert should include type for routing."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        alert = ConsecutiveFailureAlert(
            failure_count=3,
            window_minutes=15,
            first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
            sources_affected=["tiingo"],
            error_summary="Timeout",
        )

        publisher.publish_failure_alert(alert)

        call_kwargs = mock_sns.publish.call_args[1]
        # Should have message attributes for filtering
        assert "MessageAttributes" in call_kwargs
        attrs = call_kwargs["MessageAttributes"]
        assert attrs["AlertType"]["StringValue"] == AlertType.CONSECUTIVE_FAILURE.value


class TestAlertThresholds:
    """Tests for alert threshold logic."""

    def test_alert_triggered_at_exactly_3_failures(self) -> None:
        """Alert should trigger at exactly 3 failures."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        # Exactly 3 failures should trigger
        result = publisher.should_alert(failure_count=3, window_minutes=15)
        assert result is True

    def test_no_alert_at_2_failures(self) -> None:
        """Alert should not trigger at 2 failures."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        result = publisher.should_alert(failure_count=2, window_minutes=15)
        assert result is False

    def test_alert_triggered_above_3_failures(self) -> None:
        """Alert should trigger for any count >= 3."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        result = publisher.should_alert(failure_count=5, window_minutes=15)
        assert result is True

    def test_no_alert_outside_15_minute_window(self) -> None:
        """Failures outside 15-minute window should not trigger alert."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        # 3 failures but over 20 minutes - outside window
        result = publisher.should_alert(failure_count=3, window_minutes=20)
        assert result is False


class TestAlertDeduplication:
    """Tests for alert deduplication."""

    def test_no_duplicate_alerts_within_cooldown(self) -> None:
        """Should not send duplicate alerts within cooldown period."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
            alert_cooldown_minutes=5,
        )

        alert = ConsecutiveFailureAlert(
            failure_count=3,
            window_minutes=15,
            first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
            sources_affected=["tiingo"],
            error_summary="Timeout",
        )

        # First alert should publish
        publisher.publish_failure_alert(alert)
        assert mock_sns.publish.call_count == 1

        # Second alert within cooldown should not publish
        publisher.publish_failure_alert(alert)
        assert mock_sns.publish.call_count == 1

    def test_alert_sent_after_cooldown_expires(self) -> None:
        """Should send alert after cooldown expires."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
            alert_cooldown_minutes=5,
        )

        alert = ConsecutiveFailureAlert(
            failure_count=3,
            window_minutes=15,
            first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
            sources_affected=["tiingo"],
            error_summary="Timeout",
        )

        # First alert
        publisher.publish_failure_alert(alert)
        assert mock_sns.publish.call_count == 1

        # Simulate cooldown expiry by resetting internal state
        publisher._last_alert_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        # Alert after cooldown should publish
        with patch("src.lambdas.ingestion.alerting.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 12, 9, 14, 20, 0, tzinfo=UTC)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            publisher.publish_failure_alert(alert)

        assert mock_sns.publish.call_count == 2


class TestCreateAlertPublisher:
    """Tests for alert publisher factory function."""

    def test_create_with_topic_arn(self) -> None:
        """Should create publisher with topic ARN."""
        mock_sns = MagicMock()
        publisher = create_alert_publisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        assert publisher is not None
        assert publisher._topic_arn == "arn:aws:sns:us-east-1:123456789012:alerts"

    def test_create_with_custom_sns_client(self) -> None:
        """Should accept custom SNS client for testing."""
        mock_sns = MagicMock()
        publisher = create_alert_publisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        assert publisher._sns == mock_sns

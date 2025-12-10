"""Unit tests for NewDataNotification payload generation (T056).

Tests the downstream notification system per FR-004 and SC-005:
- Notify dependent systems within 30 seconds of new data storage
- Notification payload includes item count, source, and timestamp
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.lambdas.ingestion.notification import (
    NewDataNotification,
    NotificationPublisher,
    create_notification_publisher,
)


class TestNewDataNotificationPayload:
    """Tests for NewDataNotification data class."""

    def test_notification_includes_item_count(self) -> None:
        """Should include number of items stored."""
        notification = NewDataNotification(
            items_stored=25,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        assert notification.items_stored == 25

    def test_notification_includes_source(self) -> None:
        """Should include data source identifier."""
        notification = NewDataNotification(
            items_stored=10,
            source="finnhub",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        assert notification.source == "finnhub"

    def test_notification_includes_timestamp(self) -> None:
        """Should include collection timestamp."""
        ts = datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC)
        notification = NewDataNotification(
            items_stored=10,
            source="tiingo",
            collection_timestamp=ts,
        )

        assert notification.collection_timestamp == ts

    def test_notification_includes_is_failover_flag(self) -> None:
        """Should include failover indicator."""
        notification = NewDataNotification(
            items_stored=10,
            source="finnhub",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            is_failover=True,
        )

        assert notification.is_failover is True

    def test_notification_includes_duplicate_count(self) -> None:
        """Should include number of duplicates skipped."""
        notification = NewDataNotification(
            items_stored=20,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            items_duplicate=5,
        )

        assert notification.items_duplicate == 5


class TestNewDataNotificationSnsFormat:
    """Tests for SNS message formatting."""

    def test_to_sns_message_includes_item_count(self) -> None:
        """SNS message should include item count."""
        notification = NewDataNotification(
            items_stored=25,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        message = notification.to_sns_message()

        assert "25" in message
        assert "items" in message.lower()

    def test_to_sns_message_includes_source(self) -> None:
        """SNS message should include source name."""
        notification = NewDataNotification(
            items_stored=10,
            source="finnhub",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        message = notification.to_sns_message()

        assert "finnhub" in message.lower()

    def test_to_sns_message_includes_timestamp(self) -> None:
        """SNS message should include timestamp in ISO format."""
        notification = NewDataNotification(
            items_stored=10,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
        )

        message = notification.to_sns_message()

        assert "2025-12-09" in message

    def test_to_sns_message_indicates_failover(self) -> None:
        """SNS message should indicate if failover was used."""
        notification = NewDataNotification(
            items_stored=10,
            source="finnhub",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            is_failover=True,
        )

        message = notification.to_sns_message()

        assert "failover" in message.lower()

    def test_to_sns_subject(self) -> None:
        """Should generate appropriate subject line."""
        notification = NewDataNotification(
            items_stored=25,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        subject = notification.to_sns_subject()

        assert "new data" in subject.lower() or "ingestion" in subject.lower()
        assert "25" in subject


class TestNotificationPublisher:
    """Tests for NotificationPublisher."""

    def test_publish_calls_sns(self) -> None:
        """Should call SNS publish."""
        mock_sns = MagicMock()
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        notification = NewDataNotification(
            items_stored=25,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        publisher.publish(notification)

        mock_sns.publish.assert_called_once()

    def test_publish_uses_correct_topic_arn(self) -> None:
        """Should publish to configured topic ARN."""
        mock_sns = MagicMock()
        topic_arn = "arn:aws:sns:us-east-1:123456789012:downstream-notifications"
        publisher = NotificationPublisher(
            topic_arn=topic_arn,
            sns_client=mock_sns,
        )

        notification = NewDataNotification(
            items_stored=10,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        publisher.publish(notification)

        call_kwargs = mock_sns.publish.call_args[1]
        assert call_kwargs["TopicArn"] == topic_arn

    def test_publish_includes_message_attributes(self) -> None:
        """Should include message attributes for filtering."""
        mock_sns = MagicMock()
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        notification = NewDataNotification(
            items_stored=25,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        publisher.publish(notification)

        call_kwargs = mock_sns.publish.call_args[1]
        assert "MessageAttributes" in call_kwargs
        attrs = call_kwargs["MessageAttributes"]
        assert "Source" in attrs
        assert attrs["Source"]["StringValue"] == "tiingo"

    def test_publish_returns_message_id(self) -> None:
        """Should return SNS message ID on success."""
        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "msg-12345"}
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        notification = NewDataNotification(
            items_stored=25,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        result = publisher.publish(notification)

        assert result == "msg-12345"

    def test_publish_returns_none_on_error(self) -> None:
        """Should return None on SNS error."""
        from botocore.exceptions import ClientError

        mock_sns = MagicMock()
        mock_sns.publish.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameter", "Message": "Bad topic"}},
            "Publish",
        )
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:bad-topic",
            sns_client=mock_sns,
        )

        notification = NewDataNotification(
            items_stored=25,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        result = publisher.publish(notification)

        assert result is None

    def test_skip_notification_when_zero_items(self) -> None:
        """Should not publish when zero items stored."""
        mock_sns = MagicMock()
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        notification = NewDataNotification(
            items_stored=0,
            source="tiingo",
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        result = publisher.publish(notification)

        mock_sns.publish.assert_not_called()
        assert result is None


class TestNotificationPublisherFactory:
    """Tests for factory function."""

    def test_create_notification_publisher(self) -> None:
        """Factory should create publisher."""
        mock_sns = MagicMock()

        publisher = create_notification_publisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        assert isinstance(publisher, NotificationPublisher)

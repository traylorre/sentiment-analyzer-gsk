"""Unit tests for notification integration with storage (T059).

Tests that notifications are sent after successful storage operations
per FR-004 and SC-005 requirements.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.lambdas.ingestion.notification import (
    NotificationPublisher,
)
from src.lambdas.ingestion.storage import (
    StorageResult,
    store_news_items_with_notification,
)
from src.lambdas.shared.adapters.base import NewsArticle


def _make_article(i: int = 1, source: str = "tiingo") -> NewsArticle:
    """Helper to create NewsArticle with correct fields."""
    return NewsArticle(
        article_id=f"art-{i}",
        source=source,
        title=f"Test Article {i}",
        description=f"Description {i}",
        url=f"https://example.com/{i}",
        published_at=datetime(2025, 12, 9, 14, i, 0, tzinfo=UTC),
        source_name="Test Source",
        tickers=["AAPL"],
    )


class TestStorageWithNotification:
    """Tests for store_news_items_with_notification."""

    def test_sends_notification_after_storage(self) -> None:
        """Should send notification after storing items."""
        mock_table = MagicMock()
        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "msg-123"}
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        articles = [_make_article(1, "tiingo")]

        result, notification_id = store_news_items_with_notification(
            table=mock_table,
            articles=articles,
            source="tiingo",
            notification_publisher=publisher,
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        mock_sns.publish.assert_called_once()
        assert notification_id == "msg-123"

    def test_notification_includes_correct_item_count(self) -> None:
        """Notification should include number of items stored."""
        mock_table = MagicMock()
        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "msg-123"}
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        articles = [_make_article(i, "tiingo") for i in range(5)]

        store_news_items_with_notification(
            table=mock_table,
            articles=articles,
            source="tiingo",
            notification_publisher=publisher,
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        call_kwargs = mock_sns.publish.call_args[1]
        # Check message attributes for item count
        attrs = call_kwargs["MessageAttributes"]
        assert attrs["ItemCount"]["StringValue"] == "5"

    def test_notification_includes_source(self) -> None:
        """Notification should include data source."""
        mock_table = MagicMock()
        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "msg-123"}
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        articles = [_make_article(1, "finnhub")]

        store_news_items_with_notification(
            table=mock_table,
            articles=articles,
            source="finnhub",
            notification_publisher=publisher,
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        call_kwargs = mock_sns.publish.call_args[1]
        attrs = call_kwargs["MessageAttributes"]
        assert attrs["Source"]["StringValue"] == "finnhub"

    def test_no_notification_when_zero_items_stored(self) -> None:
        """Should not send notification when all items are duplicates."""
        mock_table = MagicMock()
        # Simulate all items being duplicates
        mock_table.put_item.side_effect = (
            mock_table.meta.client.exceptions.ConditionalCheckFailedException(
                {}, "test"
            )
        )
        mock_sns = MagicMock()
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        # Create an empty list of articles to get zero stored
        articles: list[NewsArticle] = []

        result, notification_id = store_news_items_with_notification(
            table=mock_table,
            articles=articles,
            source="tiingo",
            notification_publisher=publisher,
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        mock_sns.publish.assert_not_called()
        assert notification_id is None

    def test_notification_includes_failover_flag(self) -> None:
        """Notification should include is_failover when set."""
        mock_table = MagicMock()
        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "msg-123"}
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        articles = [_make_article(1, "finnhub")]

        store_news_items_with_notification(
            table=mock_table,
            articles=articles,
            source="finnhub",
            notification_publisher=publisher,
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            is_failover=True,
        )

        call_kwargs = mock_sns.publish.call_args[1]
        attrs = call_kwargs["MessageAttributes"]
        assert attrs["IsFailover"]["StringValue"] == "true"

    def test_returns_storage_result(self) -> None:
        """Should return StorageResult with counts."""
        mock_table = MagicMock()
        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "msg-123"}
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        articles = [_make_article(1, "tiingo")]

        result, notification_id = store_news_items_with_notification(
            table=mock_table,
            articles=articles,
            source="tiingo",
            notification_publisher=publisher,
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        assert isinstance(result, StorageResult)
        assert result.items_stored == 1

    def test_notification_sent_even_if_some_duplicates(self) -> None:
        """Should send notification if at least one item stored."""
        mock_table = MagicMock()
        # First call succeeds (new item), second raises duplicate exception
        duplicate_exception = Exception("ConditionalCheckFailed")
        mock_table.put_item.side_effect = [None, duplicate_exception]
        mock_table.meta.client.exceptions.ConditionalCheckFailedException = type(
            duplicate_exception
        )
        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "msg-123"}
        publisher = NotificationPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:new-data",
            sns_client=mock_sns,
        )

        articles = [_make_article(i, "tiingo") for i in range(2)]

        result, notification_id = store_news_items_with_notification(
            table=mock_table,
            articles=articles,
            source="tiingo",
            notification_publisher=publisher,
            collection_timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        # Should have stored 1, skipped 1 duplicate
        # Notification should still be sent
        assert result.items_stored == 1
        assert result.items_duplicate == 1
        mock_sns.publish.assert_called_once()


class TestStorageWithoutNotification:
    """Tests for backwards compatibility without notification."""

    def test_store_news_items_works_without_notification(self) -> None:
        """Original function should work without notification."""
        from src.lambdas.ingestion.storage import store_news_items

        mock_table = MagicMock()

        articles = [_make_article(1, "tiingo")]

        result = store_news_items(
            table=mock_table,
            articles=articles,
            source="tiingo",
        )

        assert isinstance(result, StorageResult)
        assert result.items_stored == 1

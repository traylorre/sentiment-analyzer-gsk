"""Unit tests for CollectionEventRepository (T052).

Tests the audit trail persistence per US4 requirements:
- Save collection events to DynamoDB
- Query events by date
- Query failed events
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from src.lambdas.ingestion.audit import (
    CollectionEventRepository,
    create_collection_event_repository,
)
from src.lambdas.shared.models.collection_event import CollectionEvent


class TestCollectionEventSave:
    """Tests for saving collection events."""

    def test_save_success(self) -> None:
        """Should save event to DynamoDB."""
        mock_table = MagicMock()
        repo = CollectionEventRepository(mock_table)

        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
            items_collected=100,
            items_stored=95,
        )

        result = repo.save(event)

        assert result is True
        mock_table.put_item.assert_called_once()

    def test_save_includes_all_fields(self) -> None:
        """Saved item should include all event fields."""
        mock_table = MagicMock()
        repo = CollectionEventRepository(mock_table)

        event = CollectionEvent(
            event_id="test-event-123",
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
            is_failover=True,
            items_collected=100,
            items_stored=95,
            items_duplicates=5,
        )

        repo.save(event)

        call_kwargs = mock_table.put_item.call_args[1]
        item = call_kwargs["Item"]
        assert item["PK"] == "COLLECTION#2025-12-09"
        assert item["event_id"] == "test-event-123"
        assert item["status"] == "success"
        assert item["source_used"] == "tiingo"
        assert item["is_failover"] is True

    def test_save_handles_dynamodb_error(self) -> None:
        """Should return False on DynamoDB error."""
        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Bad item"}},
            "PutItem",
        )
        repo = CollectionEventRepository(mock_table)

        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
        )

        result = repo.save(event)

        assert result is False


class TestCollectionEventQueryByDate:
    """Tests for querying events by date."""

    def test_get_by_date_returns_events(self) -> None:
        """Should return list of events for date."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "PK": "COLLECTION#2025-12-09",
                    "SK": "2025-12-09T14:00:00#abc12345",
                    "event_id": "abc12345-1234-5678-1234-567812345678",
                    "triggered_at": "2025-12-09T14:00:00+00:00",
                    "status": "success",
                    "source_used": "tiingo",
                    "is_failover": False,
                    "items_collected": 100,
                    "items_stored": 95,
                    "items_duplicates": 5,
                    "trigger_type": "scheduled",
                    "entity_type": "COLLECTION_EVENT",
                }
            ]
        }
        repo = CollectionEventRepository(mock_table)

        events = repo.get_by_date("2025-12-09")

        assert len(events) == 1
        assert events[0].status == "success"
        assert events[0].source_used == "tiingo"

    def test_get_by_date_empty_result(self) -> None:
        """Should return empty list when no events found."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        repo = CollectionEventRepository(mock_table)

        events = repo.get_by_date("2025-12-09")

        assert events == []

    def test_get_by_date_handles_error(self) -> None:
        """Should return empty list on DynamoDB error."""
        mock_table = MagicMock()
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Bad query"}},
            "Query",
        )
        repo = CollectionEventRepository(mock_table)

        events = repo.get_by_date("2025-12-09")

        assert events == []


class TestCollectionEventQueryFailures:
    """Tests for querying failed events."""

    def test_get_recent_failures(self) -> None:
        """Should return only failed events."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "PK": "COLLECTION#2025-12-09",
                    "SK": "2025-12-09T14:00:00#abc12345",
                    "event_id": "abc12345-1234-5678-1234-567812345678",
                    "triggered_at": "2025-12-09T14:00:00+00:00",
                    "status": "failed",
                    "source_used": "tiingo",
                    "is_failover": False,
                    "items_collected": 0,
                    "items_stored": 0,
                    "items_duplicates": 0,
                    "trigger_type": "scheduled",
                    "error_message": "Connection timeout",
                    "entity_type": "COLLECTION_EVENT",
                }
            ]
        }
        repo = CollectionEventRepository(mock_table)

        events = repo.get_recent_failures("2025-12-09")

        assert len(events) == 1
        assert events[0].status == "failed"
        assert events[0].error_message == "Connection timeout"

    def test_get_recent_failures_uses_filter(self) -> None:
        """Should filter by failed status."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        repo = CollectionEventRepository(mock_table)

        repo.get_recent_failures("2025-12-09")

        call_kwargs = mock_table.query.call_args[1]
        assert "FilterExpression" in call_kwargs
        assert call_kwargs["FilterExpression"] == "status = :failed"


class TestCollectionEventRepositoryFactory:
    """Tests for factory function."""

    def test_create_repository(self) -> None:
        """Factory should create repository."""
        mock_table = MagicMock()

        repo = create_collection_event_repository(mock_table)

        assert isinstance(repo, CollectionEventRepository)

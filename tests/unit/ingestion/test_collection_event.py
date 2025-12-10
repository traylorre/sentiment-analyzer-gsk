"""Unit tests for CollectionEvent logging (T046).

Tests the collection event audit trail per US4 requirements:
- Event creation and completion
- DynamoDB persistence format
- Duration calculation
- Status tracking
"""

from datetime import UTC, datetime

from src.lambdas.shared.models.collection_event import CollectionEvent


class TestCollectionEventCreation:
    """Tests for CollectionEvent creation and field validation."""

    def test_create_event_with_required_fields(self) -> None:
        """Event can be created with minimal required fields."""
        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
        )

        assert event.status == "success"
        assert event.source_used == "tiingo"
        assert event.triggered_at.year == 2025
        assert event.event_id  # Auto-generated UUID

    def test_create_event_with_all_fields(self) -> None:
        """Event can be created with all optional fields."""
        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 12, 9, 14, 0, 5, tzinfo=UTC),
            status="success",
            source_used="finnhub",
            is_failover=True,
            items_collected=50,
            items_stored=45,
            items_duplicates=5,
            duration_ms=5000,
            error_message=None,
            trigger_type="scheduled",
        )

        assert event.is_failover is True
        assert event.items_collected == 50
        assert event.items_stored == 45
        assert event.items_duplicates == 5
        assert event.duration_ms == 5000

    def test_event_id_is_unique(self) -> None:
        """Each event should have a unique ID."""
        event1 = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
        )
        event2 = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
        )

        assert event1.event_id != event2.event_id


class TestCollectionEventStatus:
    """Tests for collection event status tracking."""

    def test_success_status(self) -> None:
        """Success status indicates full collection completion."""
        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
            items_collected=100,
            items_stored=95,
        )

        assert event.status == "success"

    def test_partial_status(self) -> None:
        """Partial status indicates some items collected."""
        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="partial",
            source_used="tiingo",
            items_collected=50,
            items_stored=50,
            error_message="Timeout after 50 items",
        )

        assert event.status == "partial"
        assert event.error_message is not None

    def test_failed_status(self) -> None:
        """Failed status indicates complete collection failure."""
        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="failed",
            source_used="tiingo",
            items_collected=0,
            error_message="Connection refused",
        )

        assert event.status == "failed"
        assert event.items_collected == 0


class TestCollectionEventMarkCompleted:
    """Tests for mark_completed helper method."""

    def test_mark_completed_success(self) -> None:
        """mark_completed sets completion fields for success."""
        initial_event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",  # Initial placeholder
            source_used="tiingo",
            items_collected=100,
        )

        completed = initial_event.mark_completed(
            status="success",
            items_stored=95,
            items_duplicates=5,
        )

        assert completed.status == "success"
        assert completed.items_stored == 95
        assert completed.items_duplicates == 5
        assert completed.completed_at is not None
        assert completed.duration_ms is not None
        assert completed.duration_ms >= 0

    def test_mark_completed_failed_with_error(self) -> None:
        """mark_completed captures error message for failures."""
        initial_event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",  # Will be updated
            source_used="finnhub",
            items_collected=0,
        )

        completed = initial_event.mark_completed(
            status="failed",
            items_stored=0,
            items_duplicates=0,
            error_message="HTTP 503 Service Unavailable",
        )

        assert completed.status == "failed"
        assert completed.error_message == "HTTP 503 Service Unavailable"

    def test_mark_completed_preserves_original_fields(self) -> None:
        """mark_completed preserves event_id and triggered_at."""
        initial_event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
            items_collected=50,
            is_failover=True,
        )

        original_event_id = initial_event.event_id
        original_triggered_at = initial_event.triggered_at

        completed = initial_event.mark_completed(status="success", items_stored=50)

        assert completed.event_id == original_event_id
        assert completed.triggered_at == original_triggered_at
        assert completed.is_failover is True


class TestCollectionEventDynamoDB:
    """Tests for DynamoDB serialization."""

    def test_partition_key_format(self) -> None:
        """PK should be COLLECTION#{date}."""
        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
        )

        assert event.pk == "COLLECTION#2025-12-09"

    def test_sort_key_format(self) -> None:
        """SK should be {timestamp}#{event_id_prefix}."""
        event = CollectionEvent(
            event_id="12345678-1234-5678-1234-567812345678",
            triggered_at=datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
        )

        sk = event.sk
        assert sk.startswith("2025-12-09T14:30:00")
        assert "#12345678" in sk

    def test_to_dynamodb_item_all_fields(self) -> None:
        """to_dynamodb_item includes all fields."""
        event = CollectionEvent(
            event_id="test-event-123",
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 12, 9, 14, 0, 5, tzinfo=UTC),
            status="success",
            source_used="tiingo",
            is_failover=False,
            items_collected=100,
            items_stored=95,
            items_duplicates=5,
            duration_ms=5000,
            trigger_type="scheduled",
        )

        item = event.to_dynamodb_item()

        assert item["PK"] == "COLLECTION#2025-12-09"
        assert item["event_id"] == "test-event-123"
        assert item["status"] == "success"
        assert item["source_used"] == "tiingo"
        assert item["items_collected"] == 100
        assert item["items_stored"] == 95
        assert item["duration_ms"] == 5000
        assert item["entity_type"] == "COLLECTION_EVENT"

    def test_to_dynamodb_item_optional_fields_omitted_when_none(self) -> None:
        """Optional fields should not appear when None."""
        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="failed",
            source_used="tiingo",
            # completed_at, duration_ms, error_message all None
        )

        item = event.to_dynamodb_item()

        assert "completed_at" not in item
        assert "duration_ms" not in item
        assert "error_message" not in item

    def test_from_dynamodb_item_roundtrip(self) -> None:
        """from_dynamodb_item should reconstruct event."""
        original = CollectionEvent(
            event_id="roundtrip-test",
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 12, 9, 14, 0, 5, tzinfo=UTC),
            status="partial",
            source_used="finnhub",
            is_failover=True,
            items_collected=75,
            items_stored=70,
            items_duplicates=5,
            duration_ms=5000,
            error_message="Timeout after partial fetch",
            trigger_type="retry",
        )

        item = original.to_dynamodb_item()
        restored = CollectionEvent.from_dynamodb_item(item)

        assert restored.event_id == original.event_id
        assert restored.status == original.status
        assert restored.source_used == original.source_used
        assert restored.is_failover == original.is_failover
        assert restored.items_collected == original.items_collected
        assert restored.items_stored == original.items_stored
        assert restored.items_duplicates == original.items_duplicates
        assert restored.error_message == original.error_message
        assert restored.trigger_type == original.trigger_type


class TestCollectionEventTriggerTypes:
    """Tests for trigger type classification."""

    def test_scheduled_trigger_type(self) -> None:
        """Scheduled is the default trigger type."""
        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
        )

        assert event.trigger_type == "scheduled"

    def test_manual_trigger_type(self) -> None:
        """Manual trigger type for ad-hoc invocations."""
        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
            trigger_type="manual",
        )

        assert event.trigger_type == "manual"

    def test_retry_trigger_type(self) -> None:
        """Retry trigger type for automatic retries."""
        event = CollectionEvent(
            triggered_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            status="success",
            source_used="tiingo",
            trigger_type="retry",
        )

        assert event.trigger_type == "retry"

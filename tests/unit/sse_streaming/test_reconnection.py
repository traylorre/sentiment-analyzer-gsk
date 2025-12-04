"""Unit tests for Last-Event-ID reconnection handling.

Tests the EventBuffer and stream generator's support for
reconnection resumption per FR-007.
"""

from src.lambdas.sse_streaming.models import HeartbeatData, MetricsEventData, SSEEvent
from src.lambdas.sse_streaming.stream import EventBuffer


def make_heartbeat() -> HeartbeatData:
    """Create a valid HeartbeatData for testing."""
    return HeartbeatData(connections=5, uptime_seconds=120)


class TestEventBuffer:
    """Tests for EventBuffer class."""

    def test_add_event(self):
        """Test adding events to buffer."""
        buffer = EventBuffer(max_size=10)
        event = SSEEvent(event="heartbeat", data=make_heartbeat())

        buffer.add(event)

        assert len(buffer._buffer) == 1
        assert buffer._buffer[0] == event

    def test_buffer_size_limit(self):
        """Test buffer respects max size limit."""
        buffer = EventBuffer(max_size=5)

        # Add 10 events
        events = []
        for i in range(10):
            event = SSEEvent(id=f"event-{i}", event="heartbeat", data=make_heartbeat())
            events.append(event)
            buffer.add(event)

        # Should only keep last 5
        assert len(buffer._buffer) == 5
        assert buffer._buffer[0].id == "event-5"
        assert buffer._buffer[-1].id == "event-9"

    def test_get_events_after_valid_id(self):
        """Test getting events after a valid event ID."""
        buffer = EventBuffer(max_size=100)

        # Add 5 events
        for i in range(5):
            event = SSEEvent(id=f"event-{i}", event="heartbeat", data=make_heartbeat())
            buffer.add(event)

        # Get events after event-2
        events = buffer.get_events_after("event-2")

        assert len(events) == 2
        assert events[0].id == "event-3"
        assert events[1].id == "event-4"

    def test_get_events_after_last_id(self):
        """Test getting events after the last event ID returns empty."""
        buffer = EventBuffer(max_size=100)

        for i in range(5):
            event = SSEEvent(id=f"event-{i}", event="heartbeat", data=make_heartbeat())
            buffer.add(event)

        # Get events after the last event
        events = buffer.get_events_after("event-4")

        assert len(events) == 0

    def test_get_events_after_invalid_id(self):
        """Test getting events after an invalid event ID returns empty."""
        buffer = EventBuffer(max_size=100)

        for i in range(5):
            event = SSEEvent(id=f"event-{i}", event="heartbeat", data=make_heartbeat())
            buffer.add(event)

        # Get events after non-existent ID
        events = buffer.get_events_after("invalid-id")

        assert len(events) == 0

    def test_get_events_after_first_id(self):
        """Test getting events after the first event ID."""
        buffer = EventBuffer(max_size=100)

        for i in range(5):
            event = SSEEvent(id=f"event-{i}", event="heartbeat", data=make_heartbeat())
            buffer.add(event)

        # Get events after first event
        events = buffer.get_events_after("event-0")

        assert len(events) == 4

    def test_clear_buffer(self):
        """Test clearing the event buffer."""
        buffer = EventBuffer(max_size=100)

        for i in range(5):
            event = SSEEvent(id=f"event-{i}", event="heartbeat", data=make_heartbeat())
            buffer.add(event)

        buffer.clear()

        assert len(buffer._buffer) == 0

    def test_buffer_preserves_event_order(self):
        """Test buffer preserves insertion order."""
        buffer = EventBuffer(max_size=100)

        for i in range(10):
            event = SSEEvent(id=f"event-{i}", event="heartbeat", data=make_heartbeat())
            buffer.add(event)

        # Verify order
        for i, event in enumerate(buffer._buffer):
            assert event.id == f"event-{i}"

    def test_buffer_with_different_event_types(self):
        """Test buffer handles different event types."""
        buffer = EventBuffer(max_size=100)

        heartbeat = SSEEvent(id="hb-1", event="heartbeat", data=make_heartbeat())
        metrics = SSEEvent(
            id="metrics-1",
            event="metrics",
            data=MetricsEventData(
                total=10, positive=5, negative=3, neutral=2, by_tag={}
            ),
        )

        buffer.add(heartbeat)
        buffer.add(metrics)

        assert len(buffer._buffer) == 2
        assert buffer._buffer[0].event == "heartbeat"
        assert buffer._buffer[1].event == "metrics"


class TestReconnectionReplay:
    """Tests for reconnection replay logic."""

    def test_replay_returns_events_in_order(self):
        """Test that replay returns events in correct order."""
        buffer = EventBuffer(max_size=100)

        events = []
        for i in range(5):
            event = SSEEvent(id=f"event-{i}", event="heartbeat", data=make_heartbeat())
            events.append(event)
            buffer.add(event)

        # Simulate reconnection after event-1
        replayed = buffer.get_events_after("event-1")

        assert len(replayed) == 3
        assert replayed[0].id == "event-2"
        assert replayed[1].id == "event-3"
        assert replayed[2].id == "event-4"

    def test_replay_empty_on_no_new_events(self):
        """Test that replay is empty when client is up-to-date."""
        buffer = EventBuffer(max_size=100)

        for i in range(3):
            event = SSEEvent(id=f"event-{i}", event="heartbeat", data=make_heartbeat())
            buffer.add(event)

        # Reconnect with latest event ID
        replayed = buffer.get_events_after("event-2")

        assert len(replayed) == 0

    def test_replay_all_events_on_expired_id(self):
        """Test that replay returns empty when event ID expired from buffer."""
        buffer = EventBuffer(max_size=5)

        # Add events that overflow buffer
        for i in range(10):
            event = SSEEvent(id=f"event-{i}", event="heartbeat", data=make_heartbeat())
            buffer.add(event)

        # Try to replay from event-0 which is no longer in buffer
        replayed = buffer.get_events_after("event-0")

        # Event-0 is not in buffer, so returns empty
        assert len(replayed) == 0


class TestEventIdGeneration:
    """Tests for event ID generation."""

    def test_event_auto_generates_id(self):
        """Test that SSEEvent auto-generates ID if not provided."""
        event1 = SSEEvent(event="heartbeat", data=make_heartbeat())
        event2 = SSEEvent(event="heartbeat", data=make_heartbeat())

        assert event1.id is not None
        assert event2.id is not None
        assert event1.id != event2.id

    def test_event_uses_provided_id(self):
        """Test that SSEEvent uses provided ID."""
        event = SSEEvent(id="custom-id-123", event="heartbeat", data=make_heartbeat())

        assert event.id == "custom-id-123"

    def test_event_id_format(self):
        """Test event ID has expected format."""
        event = SSEEvent(event="heartbeat", data=make_heartbeat())

        # Auto-generated ID should start with "evt_"
        assert event.id.startswith("evt_")

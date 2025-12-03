"""Unit tests for SSE stream generator.

Tests SSEStreamGenerator for generating heartbeats, metrics, and sentiment events.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.lambdas.sse_streaming.connection import SSEConnection
from src.lambdas.sse_streaming.models import MetricsEventData, SSEEvent
from src.lambdas.sse_streaming.stream import EventBuffer, SSEStreamGenerator


class TestEventBuffer:
    """Tests for EventBuffer class."""

    def _create_metrics_event(self, total: int) -> SSEEvent:
        """Helper to create valid metrics event."""
        return SSEEvent(
            event="metrics",
            data=MetricsEventData(
                total=total,
                positive=total // 2,
                neutral=total // 3,
                negative=total // 6,
                timestamp=datetime.now(UTC),
            ),
        )

    def test_add_event(self):
        """Test adding events to buffer."""
        buffer = EventBuffer(max_size=10)
        event = self._create_metrics_event(10)

        buffer.add(event)

        assert len(buffer._buffer) == 1

    def test_buffer_respects_max_size(self):
        """Test buffer trims to max size."""
        buffer = EventBuffer(max_size=3)

        for i in range(5):
            event = self._create_metrics_event(i * 10)
            buffer.add(event)

        assert len(buffer._buffer) == 3
        # Should keep last 3 events
        assert buffer._buffer[0].data.total == 20
        assert buffer._buffer[1].data.total == 30
        assert buffer._buffer[2].data.total == 40

    def test_get_events_after_found(self):
        """Test getting events after a specific ID."""
        buffer = EventBuffer()
        events = []
        for i in range(5):
            event = self._create_metrics_event(i * 10)
            events.append(event)
            buffer.add(event)

        # Get events after the second one
        result = buffer.get_events_after(events[1].id)

        assert len(result) == 3
        assert result[0].data.total == 20
        assert result[1].data.total == 30
        assert result[2].data.total == 40

    def test_get_events_after_not_found(self):
        """Test getting events when ID not found returns empty."""
        buffer = EventBuffer()
        event = self._create_metrics_event(10)
        buffer.add(event)

        result = buffer.get_events_after("nonexistent-id")

        assert result == []

    def test_clear_buffer(self):
        """Test clearing the buffer."""
        buffer = EventBuffer()
        for i in range(5):
            buffer.add(self._create_metrics_event(i * 10))

        buffer.clear()

        assert len(buffer._buffer) == 0


class TestSSEStreamGenerator:
    """Tests for SSEStreamGenerator class."""

    @pytest.fixture
    def mock_conn_manager(self):
        """Create mock connection manager."""
        manager = MagicMock()
        manager.count = 5
        manager.update_last_event_id = MagicMock()
        return manager

    @pytest.fixture
    def mock_poll_service(self):
        """Create mock polling service."""
        service = MagicMock()
        return service

    @pytest.fixture
    def generator(self, mock_conn_manager, mock_poll_service):
        """Create SSEStreamGenerator with mocks."""
        return SSEStreamGenerator(
            conn_manager=mock_conn_manager,
            poll_service=mock_poll_service,
            heartbeat_interval=30,
        )

    def test_heartbeat_interval_property(self, generator):
        """Test heartbeat interval property."""
        assert generator.heartbeat_interval == 30

    def test_create_heartbeat(self, generator):
        """Test creating heartbeat event."""
        heartbeat = generator._create_heartbeat()

        assert heartbeat.event == "heartbeat"
        assert heartbeat.data.connections == 5
        assert heartbeat.retry == 3000
        assert heartbeat.id is not None

    def test_create_metrics_event(self, generator):
        """Test creating metrics event."""
        metrics = MetricsEventData(
            total=100,
            positive=60,
            neutral=30,
            negative=10,
            timestamp=datetime.now(UTC),
        )

        event = generator._create_metrics_event(metrics)

        assert event.event == "metrics"
        assert event.data.total == 100
        assert event.id is not None

    def test_create_sentiment_event(self, generator):
        """Test creating sentiment_update event."""
        event = generator._create_sentiment_event(
            ticker="AAPL",
            score=0.8,
            label="positive",
            confidence=0.95,
            source="tiingo",
        )

        assert event.event == "sentiment_update"
        assert event.data.ticker == "AAPL"
        assert event.data.score == 0.8
        assert event.data.label == "positive"
        assert event.data.confidence == 0.95
        assert event.data.source == "tiingo"


class TestGlobalStreamGeneration:
    """Tests for global stream generation."""

    @pytest.fixture
    def connection(self):
        """Create a mock SSE connection."""
        return SSEConnection(connection_id="test-conn-123")

    @pytest.mark.asyncio
    async def test_global_stream_yields_initial_heartbeat(self, connection):
        """Test that global stream yields initial heartbeat."""
        mock_conn_manager = MagicMock()
        mock_conn_manager.count = 1
        mock_conn_manager.update_last_event_id = MagicMock()

        # Create async generator that yields once then stops
        async def mock_poll_loop():
            # Yield one metrics update then break
            yield (
                MetricsEventData(
                    total=10,
                    positive=5,
                    neutral=3,
                    negative=2,
                    timestamp=datetime.now(UTC),
                ),
                True,
            )
            # Cancel after one iteration
            raise asyncio.CancelledError()

        mock_poll_service = MagicMock()
        mock_poll_service.poll_loop = mock_poll_loop

        generator = SSEStreamGenerator(
            conn_manager=mock_conn_manager,
            poll_service=mock_poll_service,
            heartbeat_interval=30,
        )

        events = []
        try:
            async for event in generator.generate_global_stream(connection):
                events.append(event)
                if len(events) >= 2:
                    break
        except asyncio.CancelledError:
            pass

        # Should have initial heartbeat and metrics event
        assert len(events) >= 1
        assert "heartbeat" in events[0]

    @pytest.mark.asyncio
    async def test_global_stream_replays_events_on_reconnect(self, connection):
        """Test that global stream replays buffered events on reconnect."""
        mock_conn_manager = MagicMock()
        mock_conn_manager.count = 1
        mock_conn_manager.update_last_event_id = MagicMock()

        async def mock_poll_loop():
            raise asyncio.CancelledError()
            yield  # Make it a generator

        mock_poll_service = MagicMock()
        mock_poll_service.poll_loop = mock_poll_loop

        generator = SSEStreamGenerator(
            conn_manager=mock_conn_manager,
            poll_service=mock_poll_service,
            heartbeat_interval=30,
        )

        # Add some events to buffer with valid data models
        event1 = SSEEvent(
            event="metrics",
            data=MetricsEventData(
                total=10, positive=5, neutral=3, negative=2, timestamp=datetime.now(UTC)
            ),
        )
        event2 = SSEEvent(
            event="metrics",
            data=MetricsEventData(
                total=20,
                positive=10,
                neutral=6,
                negative=4,
                timestamp=datetime.now(UTC),
            ),
        )
        generator._event_buffer.add(event1)
        generator._event_buffer.add(event2)

        events = []
        try:
            async for event in generator.generate_global_stream(
                connection, last_event_id=event1.id
            ):
                events.append(event)
        except asyncio.CancelledError:
            pass

        # Should replay event2 (after event1), then send heartbeat
        assert len(events) >= 2


class TestConfigStreamGeneration:
    """Tests for config-specific stream generation."""

    @pytest.fixture
    def connection_with_filters(self):
        """Create SSE connection with ticker filters."""
        return SSEConnection(
            connection_id="test-conn-456",
            user_id="user-123",
            config_id="config-789",
            ticker_filters=["AAPL", "MSFT"],
        )

    @pytest.mark.asyncio
    async def test_config_stream_yields_initial_heartbeat(
        self, connection_with_filters
    ):
        """Test that config stream yields initial heartbeat."""
        mock_conn_manager = MagicMock()
        mock_conn_manager.count = 1
        mock_conn_manager.update_last_event_id = MagicMock()

        mock_poll_service = MagicMock()

        generator = SSEStreamGenerator(
            conn_manager=mock_conn_manager,
            poll_service=mock_poll_service,
            heartbeat_interval=1,  # Short interval for testing
        )

        events = []
        try:
            async for event in generator.generate_config_stream(
                connection_with_filters
            ):
                events.append(event)
                if len(events) >= 1:
                    raise asyncio.CancelledError()
        except asyncio.CancelledError:
            pass

        # Should have initial heartbeat
        assert len(events) >= 1
        assert "heartbeat" in events[0]

    @pytest.mark.asyncio
    async def test_config_stream_filters_sentiment_replay(
        self, connection_with_filters
    ):
        """Test that config stream filters sentiment events on replay."""
        mock_conn_manager = MagicMock()
        mock_conn_manager.count = 1
        mock_conn_manager.update_last_event_id = MagicMock()

        mock_poll_service = MagicMock()

        generator = SSEStreamGenerator(
            conn_manager=mock_conn_manager,
            poll_service=mock_poll_service,
            heartbeat_interval=30,
        )

        # Add sentiment events to buffer - one matching, one not
        from src.lambdas.sse_streaming.models import SentimentUpdateData

        matching_data = SentimentUpdateData(
            ticker="AAPL",
            score=0.8,
            label="positive",
            confidence=0.9,
            source="tiingo",
            timestamp=datetime.now(UTC),
        )
        non_matching_data = SentimentUpdateData(
            ticker="GOOGL",
            score=0.6,
            label="neutral",
            confidence=0.85,
            source="tiingo",
            timestamp=datetime.now(UTC),
        )

        event1 = SSEEvent(event="sentiment_update", data=matching_data)
        event2 = SSEEvent(event="sentiment_update", data=non_matching_data)
        generator._event_buffer.add(event1)
        generator._event_buffer.add(event2)

        # Reconnect after event1
        events = []
        try:
            async for event in generator.generate_config_stream(
                connection_with_filters, last_event_id=event1.id
            ):
                events.append(event)
                if len(events) >= 2:
                    raise asyncio.CancelledError()
        except asyncio.CancelledError:
            pass

        # Should NOT include GOOGL event (filtered out)
        # Should include heartbeat
        for event in events:
            assert "GOOGL" not in event

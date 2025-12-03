"""Unit tests for SSE event models.

Tests event payloads and SSE format generation per contracts/sse-events.md.
"""

import json
from datetime import UTC, datetime

import pytest

from src.lambdas.sse_streaming.models import (
    HeartbeatData,
    MetricsEventData,
    SentimentUpdateData,
    SSEEvent,
    StreamStatus,
    generate_event_id,
)


class TestGenerateEventId:
    """Tests for event ID generation."""

    def test_generates_unique_ids(self):
        """Should generate unique event IDs."""
        ids = [generate_event_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_id_format(self):
        """Event IDs should start with 'evt_'."""
        event_id = generate_event_id()
        assert event_id.startswith("evt_")


class TestHeartbeatData:
    """Tests for HeartbeatData model."""

    def test_default_timestamp(self):
        """Should set default timestamp to now."""
        data = HeartbeatData(connections=5, uptime_seconds=100)
        assert data.timestamp is not None
        assert data.timestamp.tzinfo == UTC

    def test_serialization(self):
        """Should serialize to JSON correctly."""
        data = HeartbeatData(
            timestamp=datetime(2025, 12, 2, 10, 30, 0, tzinfo=UTC),
            connections=15,
            uptime_seconds=3600,
        )
        json_str = data.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["connections"] == 15
        assert parsed["uptime_seconds"] == 3600
        assert "2025-12-02" in parsed["timestamp"]


class TestMetricsEventData:
    """Tests for MetricsEventData model."""

    def test_all_fields(self):
        """Should accept all metric fields."""
        data = MetricsEventData(
            total=150,
            positive=80,
            neutral=45,
            negative=25,
            by_tag={"AAPL": 50, "MSFT": 40},
            rate_last_hour=12,
            rate_last_24h=150,
        )

        assert data.total == 150
        assert data.positive == 80
        assert data.by_tag["AAPL"] == 50

    def test_default_values(self):
        """Should have sensible defaults."""
        data = MetricsEventData(
            total=100,
            positive=50,
            neutral=30,
            negative=20,
        )

        assert data.by_tag == {}
        assert data.rate_last_hour == 0
        assert data.rate_last_24h == 0

    def test_serialization(self):
        """Should serialize to JSON correctly."""
        data = MetricsEventData(
            total=150,
            positive=80,
            neutral=45,
            negative=25,
            by_tag={"AAPL": 50},
        )
        json_str = data.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["total"] == 150
        assert parsed["by_tag"]["AAPL"] == 50


class TestSentimentUpdateData:
    """Tests for SentimentUpdateData model."""

    def test_all_fields(self):
        """Should accept all sentiment fields."""
        data = SentimentUpdateData(
            ticker="AAPL",
            score=0.85,
            label="positive",
            confidence=0.92,
            source="tiingo",
        )

        assert data.ticker == "AAPL"
        assert data.score == 0.85
        assert data.label == "positive"

    def test_score_validation(self):
        """Score should be between -1.0 and 1.0."""
        # Valid scores
        data = SentimentUpdateData(
            ticker="AAPL", score=-1.0, label="negative", confidence=0.9, source="tiingo"
        )
        assert data.score == -1.0

        data = SentimentUpdateData(
            ticker="AAPL", score=1.0, label="positive", confidence=0.9, source="tiingo"
        )
        assert data.score == 1.0

        # Invalid scores should raise error
        with pytest.raises(ValueError):
            SentimentUpdateData(
                ticker="AAPL",
                score=1.5,
                label="positive",
                confidence=0.9,
                source="tiingo",
            )

    def test_confidence_validation(self):
        """Confidence should be between 0.0 and 1.0."""
        with pytest.raises(ValueError):
            SentimentUpdateData(
                ticker="AAPL",
                score=0.5,
                label="positive",
                confidence=1.5,
                source="tiingo",
            )

    def test_serialization(self):
        """Should serialize to JSON correctly."""
        data = SentimentUpdateData(
            ticker="AAPL",
            score=0.85,
            label="positive",
            confidence=0.92,
            source="tiingo",
        )
        json_str = data.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["ticker"] == "AAPL"
        assert parsed["score"] == 0.85
        assert parsed["source"] == "tiingo"


class TestSSEEvent:
    """Tests for SSEEvent wrapper model."""

    def test_auto_generates_id(self):
        """Should auto-generate event ID."""
        event = SSEEvent(
            event="heartbeat",
            data=HeartbeatData(connections=5, uptime_seconds=100),
        )

        assert event.id.startswith("evt_")

    def test_custom_id(self):
        """Should accept custom event ID."""
        event = SSEEvent(
            event="heartbeat",
            id="evt_custom123",
            data=HeartbeatData(connections=5, uptime_seconds=100),
        )

        assert event.id == "evt_custom123"

    def test_retry_optional(self):
        """Retry should be optional."""
        event = SSEEvent(
            event="heartbeat",
            data=HeartbeatData(connections=5, uptime_seconds=100),
        )
        assert event.retry is None

        event_with_retry = SSEEvent(
            event="heartbeat",
            data=HeartbeatData(connections=5, uptime_seconds=100),
            retry=3000,
        )
        assert event_with_retry.retry == 3000

    def test_to_sse_format_heartbeat(self):
        """Should format heartbeat as SSE string."""
        event = SSEEvent(
            event="heartbeat",
            id="evt_test123",
            data=HeartbeatData(
                timestamp=datetime(2025, 12, 2, 10, 30, 0, tzinfo=UTC),
                connections=15,
                uptime_seconds=3600,
            ),
        )

        sse_str = event.to_sse_format()

        assert "event: heartbeat" in sse_str
        assert "id: evt_test123" in sse_str
        assert "data:" in sse_str
        assert '"connections":15' in sse_str or '"connections": 15' in sse_str

    def test_to_sse_format_with_retry(self):
        """Should include retry in SSE format when set."""
        event = SSEEvent(
            event="heartbeat",
            id="evt_test123",
            data=HeartbeatData(connections=5, uptime_seconds=100),
            retry=3000,
        )

        sse_str = event.to_sse_format()

        assert "retry: 3000" in sse_str

    def test_to_sse_format_metrics(self):
        """Should format metrics event correctly."""
        event = SSEEvent(
            event="metrics",
            id="evt_metrics123",
            data=MetricsEventData(
                total=150,
                positive=80,
                neutral=45,
                negative=25,
                by_tag={"AAPL": 50},
            ),
        )

        sse_str = event.to_sse_format()

        assert "event: metrics" in sse_str
        assert "id: evt_metrics123" in sse_str
        assert '"total":150' in sse_str or '"total": 150' in sse_str

    def test_to_sse_format_sentiment_update(self):
        """Should format sentiment_update event correctly."""
        event = SSEEvent(
            event="sentiment_update",
            id="evt_sentiment123",
            data=SentimentUpdateData(
                ticker="AAPL",
                score=0.85,
                label="positive",
                confidence=0.92,
                source="tiingo",
            ),
        )

        sse_str = event.to_sse_format()

        assert "event: sentiment_update" in sse_str
        assert '"ticker":"AAPL"' in sse_str or '"ticker": "AAPL"' in sse_str

    def test_sse_format_ends_with_newline(self):
        """SSE format should end with empty line."""
        event = SSEEvent(
            event="heartbeat",
            data=HeartbeatData(connections=5, uptime_seconds=100),
        )

        sse_str = event.to_sse_format()

        # SSE protocol requires empty line after data
        assert sse_str.endswith("\n")


class TestStreamStatus:
    """Tests for StreamStatus response model."""

    def test_all_fields(self):
        """Should accept all status fields."""
        status = StreamStatus(
            connections=15,
            max_connections=100,
            available=85,
            uptime_seconds=3600,
        )

        assert status.connections == 15
        assert status.max_connections == 100
        assert status.available == 85
        assert status.uptime_seconds == 3600

    def test_serialization(self):
        """Should serialize to JSON correctly."""
        status = StreamStatus(
            connections=15,
            max_connections=100,
            available=85,
            uptime_seconds=3600,
        )
        json_str = status.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["connections"] == 15
        assert parsed["available"] == 85

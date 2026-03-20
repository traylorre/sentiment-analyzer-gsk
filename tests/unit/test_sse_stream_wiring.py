"""Unit tests for SSE stream wiring — sentiment_update and partial_bucket events.

Feature 1228: Tests for event emission in generate_global_stream() and
generate_config_stream().
"""

import asyncio
import json
from contextlib import suppress
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.lambdas.sse_streaming.connection import SSEConnection
from src.lambdas.sse_streaming.models import MetricsEventData
from src.lambdas.sse_streaming.polling import PollResult, TickerAggregate
from src.lambdas.sse_streaming.stream import SSEStreamGenerator


def _make_poll_result(
    per_ticker: dict[str, TickerAggregate] | None = None,
    timeseries_buckets: dict[str, dict] | None = None,
    metrics_changed: bool = True,
) -> PollResult:
    """Create a PollResult with sensible defaults."""
    return PollResult(
        metrics=MetricsEventData(
            total=10,
            positive=5,
            neutral=3,
            negative=2,
            timestamp=datetime(2026, 3, 20, 15, 0, 0, tzinfo=UTC),
        ),
        metrics_changed=metrics_changed,
        per_ticker=per_ticker or {},
        timeseries_buckets=timeseries_buckets or {},
    )


def _make_connection(ticker_filters: list[str] | None = None) -> SSEConnection:
    """Create a mock SSE connection."""
    conn = MagicMock(spec=SSEConnection)
    conn.connection_id = "test-conn-001"
    conn.config_id = "test-config" if ticker_filters is not None else None
    conn.ticker_filters = ticker_filters or []

    def matches_ticker(ticker: str) -> bool:
        if not conn.ticker_filters:
            return True
        return ticker in conn.ticker_filters

    conn.matches_ticker = matches_ticker
    return conn


def _make_generator(poll_results: list[PollResult]) -> SSEStreamGenerator:
    """Create SSEStreamGenerator with mock polling that yields given results."""
    mock_conn_manager = MagicMock()
    mock_conn_manager.count = 1
    mock_conn_manager.update_last_event_id = MagicMock()

    async def mock_poll_loop():
        for result in poll_results:
            yield result
        raise asyncio.CancelledError()

    mock_poll_service = MagicMock()
    mock_poll_service.poll_loop = mock_poll_loop

    return SSEStreamGenerator(
        conn_manager=mock_conn_manager,
        poll_service=mock_poll_service,
        heartbeat_interval=300,  # Very long to avoid heartbeat interference
    )


class TestSentimentUpdateEmission:
    """T010: Test sentiment_update event emission in generate_global_stream()."""

    @pytest.mark.asyncio
    async def test_baseline_poll_emits_no_sentiment_events(self):
        """First poll establishes baseline — no sentiment_update emitted (FR-011)."""
        per_ticker = {
            "AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5),
            "MSFT": TickerAggregate("MSFT", 0.45, "neutral", 0.45, 3),
        }
        gen = _make_generator([_make_poll_result(per_ticker=per_ticker)])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        sentiment_events = [e for e in events if e.get("event") == "sentiment_update"]
        assert len(sentiment_events) == 0

    @pytest.mark.asyncio
    async def test_second_poll_emits_sentiment_update_for_changed_ticker(self):
        """Changed ticker aggregate triggers sentiment_update on second poll."""
        poll1 = _make_poll_result(
            per_ticker={
                "AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5),
            }
        )
        poll2 = _make_poll_result(
            per_ticker={
                "AAPL": TickerAggregate("AAPL", 0.90, "positive", 0.90, 6),
            },
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        sentiment_events = [e for e in events if e.get("event") == "sentiment_update"]
        assert len(sentiment_events) == 1

        data = json.loads(sentiment_events[0]["data"])
        assert data["ticker"] == "AAPL"
        assert data["source"] == "aggregate"

    @pytest.mark.asyncio
    async def test_unchanged_ticker_emits_nothing(self):
        """Unchanged aggregates between polls produce no sentiment_update."""
        agg = {"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)}
        poll1 = _make_poll_result(per_ticker=agg)
        poll2 = _make_poll_result(per_ticker=agg, metrics_changed=False)
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        sentiment_events = [e for e in events if e.get("event") == "sentiment_update"]
        assert len(sentiment_events) == 0

    @pytest.mark.asyncio
    async def test_new_ticker_emits_sentiment_update(self):
        """A ticker appearing for the first time after baseline emits sentiment_update."""
        poll1 = _make_poll_result(
            per_ticker={"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)}
        )
        poll2 = _make_poll_result(
            per_ticker={
                "AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5),
                "TSLA": TickerAggregate("TSLA", 0.30, "negative", 0.30, 2),
            },
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        sentiment_events = [e for e in events if e.get("event") == "sentiment_update"]
        assert len(sentiment_events) == 1
        data = json.loads(sentiment_events[0]["data"])
        assert data["ticker"] == "TSLA"

    @pytest.mark.asyncio
    async def test_payload_contains_fr012_fields(self):
        """sentiment_update payload must have score, label, confidence, source (FR-012)."""
        poll1 = _make_poll_result(
            per_ticker={"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)}
        )
        poll2 = _make_poll_result(
            per_ticker={"AAPL": TickerAggregate("AAPL", 0.92, "positive", 0.92, 7)},
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        sentiment_events = [e for e in events if e.get("event") == "sentiment_update"]
        assert len(sentiment_events) == 1
        data = json.loads(sentiment_events[0]["data"])
        assert "ticker" in data
        assert "score" in data
        assert "label" in data
        assert "confidence" in data
        assert data["source"] == "aggregate"


class TestEventBufferReplay:
    """T011: Test event buffer replay for sentiment_update events."""

    @pytest.mark.asyncio
    async def test_sentiment_events_added_to_buffer(self):
        """sentiment_update events should be added to EventBuffer (FR-007)."""
        poll1 = _make_poll_result(
            per_ticker={"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)}
        )
        poll2 = _make_poll_result(
            per_ticker={"AAPL": TickerAggregate("AAPL", 0.92, "positive", 0.92, 7)},
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        with suppress(asyncio.CancelledError):
            async for _ in gen.generate_global_stream(conn):
                pass

        # Check buffer contains sentiment_update events
        buffer_events = gen._event_buffer._buffer
        sentiment_in_buffer = [
            e for e in buffer_events if e.event == "sentiment_update"
        ]
        assert len(sentiment_in_buffer) == 1
        assert sentiment_in_buffer[0].data.ticker == "AAPL"


class TestConfigStreamTickerFiltering:
    """T026, T027: Test ticker-filtered event delivery in generate_config_stream()."""

    @pytest.mark.asyncio
    async def test_config_stream_filters_sentiment_by_ticker(self):
        """Only matching tickers pass through config stream filter (FR-006)."""
        poll1 = _make_poll_result(
            per_ticker={
                "AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5),
                "TSLA": TickerAggregate("TSLA", 0.30, "negative", 0.30, 2),
            }
        )
        poll2 = _make_poll_result(
            per_ticker={
                "AAPL": TickerAggregate("AAPL", 0.90, "positive", 0.90, 6),
                "TSLA": TickerAggregate("TSLA", 0.35, "negative", 0.35, 3),
            },
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection(ticker_filters=["AAPL"])

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_config_stream(conn):
                events.append(event)

        sentiment_events = [e for e in events if e.get("event") == "sentiment_update"]
        assert len(sentiment_events) == 1
        data = json.loads(sentiment_events[0]["data"])
        assert data["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_config_stream_empty_filter_delivers_all(self):
        """Empty ticker_filters delivers all events (FR-006)."""
        poll1 = _make_poll_result(
            per_ticker={
                "AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5),
            }
        )
        poll2 = _make_poll_result(
            per_ticker={
                "AAPL": TickerAggregate("AAPL", 0.90, "positive", 0.90, 6),
                "TSLA": TickerAggregate("TSLA", 0.30, "negative", 0.30, 2),
            },
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection(ticker_filters=[])  # Empty = all

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_config_stream(conn):
                events.append(event)

        sentiment_events = [e for e in events if e.get("event") == "sentiment_update"]
        # Should get both AAPL (changed) and TSLA (new)
        assert len(sentiment_events) == 2

    @pytest.mark.asyncio
    async def test_config_stream_filters_partial_bucket_by_ticker(self):
        """partial_bucket events filtered by ticker in config stream (FR-005, FR-006)."""
        poll1 = _make_poll_result(
            timeseries_buckets={
                "AAPL#5m": {
                    "open": 0.7,
                    "close": 0.8,
                    "high": 0.9,
                    "low": 0.6,
                    "count": 3,
                    "sum": 2.1,
                },
                "TSLA#5m": {
                    "open": 0.3,
                    "close": 0.4,
                    "high": 0.5,
                    "low": 0.2,
                    "count": 2,
                    "sum": 0.7,
                },
            }
        )
        poll2 = _make_poll_result(
            timeseries_buckets={
                "AAPL#5m": {
                    "open": 0.7,
                    "close": 0.85,
                    "high": 0.9,
                    "low": 0.6,
                    "count": 4,
                    "sum": 2.95,
                },
                "TSLA#5m": {
                    "open": 0.3,
                    "close": 0.45,
                    "high": 0.5,
                    "low": 0.2,
                    "count": 3,
                    "sum": 1.15,
                },
            },
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection(ticker_filters=["AAPL"])

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_config_stream(conn):
                events.append(event)

        bucket_events = [e for e in events if e.get("event") == "partial_bucket"]
        # Only AAPL bucket should pass filter
        assert len(bucket_events) == 1


class TestConfigStreamBaseline:
    """T028: Test config stream baseline establishment."""

    @pytest.mark.asyncio
    async def test_config_stream_baseline_no_events(self):
        """First poll in config stream emits no sentiment_update or partial_bucket (FR-011)."""
        poll1 = _make_poll_result(
            per_ticker={
                "AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5),
            },
            timeseries_buckets={
                "AAPL#5m": {
                    "open": 0.7,
                    "close": 0.8,
                    "high": 0.9,
                    "low": 0.6,
                    "count": 3,
                    "sum": 2.1,
                },
            },
        )
        gen = _make_generator([poll1])
        conn = _make_connection(ticker_filters=["AAPL"])

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_config_stream(conn):
                events.append(event)

        # Should only have heartbeat, no sentiment_update or partial_bucket
        sentiment_events = [e for e in events if e.get("event") == "sentiment_update"]
        bucket_events = [e for e in events if e.get("event") == "partial_bucket"]
        heartbeat_events = [e for e in events if e.get("event") == "heartbeat"]

        assert len(sentiment_events) == 0
        assert len(bucket_events) == 0
        assert len(heartbeat_events) >= 1  # Initial heartbeat

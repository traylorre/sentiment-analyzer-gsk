"""Unit tests for SSE timeseries polling — T017-T020.

Tests _fetch_timeseries_buckets (T017), bucket change detection (T018),
partial_bucket event emission (T019), and graceful degradation (T020).
"""

import asyncio
import json
from contextlib import suppress
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from src.lambdas.sse_streaming.connection import SSEConnection
from src.lambdas.sse_streaming.models import MetricsEventData
from src.lambdas.sse_streaming.polling import (
    PollingService,
    PollResult,
    TickerAggregate,
)
from src.lambdas.sse_streaming.stream import SSEStreamGenerator
from src.lib.timeseries import Resolution, floor_to_bucket

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_connection() -> SSEConnection:
    """Create a mock SSE connection."""
    conn = MagicMock(spec=SSEConnection)
    conn.connection_id = "test-conn-ts-001"
    conn.config_id = None
    conn.ticker_filters = []
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


def _dynamo_item(pk: str, sk: str, bucket: dict) -> dict:
    """Build a DynamoDB wire-format item for BatchGetItem response."""
    item = {
        "PK": {"S": pk},
        "SK": {"S": sk},
    }
    for field in ("open", "close", "high", "low", "sum"):
        if field in bucket:
            item[field] = {"N": str(bucket[field])}
    if "count" in bucket:
        item["count"] = {"N": str(bucket["count"])}
    return item


# ---------------------------------------------------------------------------
# T017: Test _fetch_timeseries_buckets
# ---------------------------------------------------------------------------


class TestFetchTimeseriesBuckets:
    """T017: Test _fetch_timeseries_buckets key construction and response parsing."""

    @freeze_time("2026-03-20T15:32:00Z")
    def test_correct_pk_sk_for_all_resolutions(self):
        """Should build correct PK/SK keys for all 8 resolutions."""
        table_name = "test-timeseries"

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {"TIMESERIES_TABLE": table_name}):
                service = PollingService(table_name="test-sentiments")

        mock_client = MagicMock()
        mock_client.batch_get_item.return_value = {"Responses": {table_name: []}}

        with patch("boto3.client", return_value=mock_client):
            service._fetch_timeseries_buckets(["AAPL"])

        # Verify batch_get_item was called
        assert mock_client.batch_get_item.called
        call_args = mock_client.batch_get_item.call_args
        request_items = (
            call_args[1]["RequestItems"]
            if "RequestItems" in call_args[1]
            else call_args[0][0]
        )

        # Should be called with keys for 1 ticker x 8 resolutions = 8 keys
        keys = request_items[table_name]["Keys"]
        assert len(keys) == 8

        # Verify specific PK values
        pk_values = {k["PK"]["S"] for k in keys}
        expected_pks = {f"AAPL#{r.value}" for r in Resolution}
        assert pk_values == expected_pks

        # Verify SK values are bucket-aligned timestamps
        now = datetime(2026, 3, 20, 15, 32, 0, tzinfo=UTC)
        for key in keys:
            pk = key["PK"]["S"]
            sk = key["SK"]["S"]
            res_str = pk.split("#")[1]
            resolution = Resolution(res_str)
            expected_sk = floor_to_bucket(now, resolution).isoformat()
            assert sk == expected_sk, f"SK mismatch for {pk}: {sk} != {expected_sk}"

    @freeze_time("2026-03-20T15:32:00Z")
    def test_parses_response_items_correctly(self):
        """Should parse DynamoDB wire-format response into plain dicts."""
        table_name = "test-timeseries"

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {"TIMESERIES_TABLE": table_name}):
                service = PollingService(table_name="test-sentiments")

        bucket = {
            "open": 0.5,
            "close": 0.7,
            "high": 0.9,
            "low": 0.3,
            "count": 12,
            "sum": 7.2,
        }
        now = datetime(2026, 3, 20, 15, 32, 0, tzinfo=UTC)
        sk = floor_to_bucket(now, Resolution.FIVE_MINUTES).isoformat()
        response_item = _dynamo_item("AAPL#5m", sk, bucket)

        mock_client = MagicMock()
        mock_client.batch_get_item.return_value = {
            "Responses": {table_name: [response_item]}
        }

        with patch("boto3.client", return_value=mock_client):
            result = service._fetch_timeseries_buckets(["AAPL"])

        assert "AAPL#5m" in result
        data = result["AAPL#5m"]
        assert data["open"] == 0.5
        assert data["close"] == 0.7
        assert data["high"] == 0.9
        assert data["low"] == 0.3
        assert data["count"] == 12
        assert data["sum"] == 7.2

    def test_empty_tickers_returns_empty_dict(self):
        """Empty tickers list should return empty dict without calling DynamoDB."""
        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {"TIMESERIES_TABLE": "test-timeseries"}):
                service = PollingService(table_name="test-sentiments")

        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            result = service._fetch_timeseries_buckets([])

        assert result == {}
        mock_client.batch_get_item.assert_not_called()

    def test_timeseries_table_not_set_returns_empty_dict(self):
        """When TIMESERIES_TABLE env var is not set, should return empty dict."""
        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {}, clear=False):
                # Ensure TIMESERIES_TABLE is not set
                import os

                os.environ.pop("TIMESERIES_TABLE", None)
                service = PollingService(table_name="test-sentiments")

        # _timeseries_table_name should be None
        assert service._timeseries_table_name is None

        result = service._fetch_timeseries_buckets(["AAPL"])
        assert result == {}

    @freeze_time("2026-03-20T15:32:00Z")
    def test_multiple_tickers_creates_correct_key_count(self):
        """Two tickers should produce 2 x 8 = 16 keys."""
        table_name = "test-timeseries"

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {"TIMESERIES_TABLE": table_name}):
                service = PollingService(table_name="test-sentiments")

        mock_client = MagicMock()
        mock_client.batch_get_item.return_value = {"Responses": {table_name: []}}

        with patch("boto3.client", return_value=mock_client):
            service._fetch_timeseries_buckets(["AAPL", "MSFT"])

        call_args = mock_client.batch_get_item.call_args
        request_items = (
            call_args[1]["RequestItems"]
            if "RequestItems" in call_args[1]
            else call_args[0][0]
        )
        keys = request_items[table_name]["Keys"]
        assert len(keys) == 16

    @freeze_time("2026-03-20T15:32:00Z")
    def test_batching_over_100_keys(self):
        """More than 100 keys should split into multiple BatchGetItem calls."""
        table_name = "test-timeseries"

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {"TIMESERIES_TABLE": table_name}):
                service = PollingService(table_name="test-sentiments")

        mock_client = MagicMock()
        mock_client.batch_get_item.return_value = {"Responses": {table_name: []}}

        # 13 tickers x 8 resolutions = 104 keys -> 2 batches
        tickers = [f"T{i:03d}" for i in range(13)]
        with patch("boto3.client", return_value=mock_client):
            service._fetch_timeseries_buckets(tickers)

        assert mock_client.batch_get_item.call_count == 2


# ---------------------------------------------------------------------------
# T018: Test bucket change detection logic
# ---------------------------------------------------------------------------


class TestBucketChangeDetection:
    """T018: Test that bucket changes are correctly detected between snapshots."""

    @pytest.mark.asyncio
    async def test_identical_buckets_no_partial_bucket_events(self):
        """Two identical bucket snapshots produce no partial_bucket events."""
        buckets = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.7,
                "high": 0.9,
                "low": 0.3,
                "count": 10,
                "sum": 5.0,
            },
        }
        per_ticker = {"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)}
        poll1 = _make_poll_result(per_ticker=per_ticker, timeseries_buckets=buckets)
        poll2 = _make_poll_result(
            per_ticker=per_ticker,
            timeseries_buckets=buckets,
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        partial_events = [e for e in events if e.get("event") == "partial_bucket"]
        assert len(partial_events) == 0

    @pytest.mark.asyncio
    async def test_bucket_count_increased_triggers_change(self):
        """Bucket with increased count should emit partial_bucket event."""
        per_ticker = {"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)}
        buckets1 = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.7,
                "high": 0.9,
                "low": 0.3,
                "count": 10,
                "sum": 5.0,
            },
        }
        buckets2 = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.7,
                "high": 0.9,
                "low": 0.3,
                "count": 12,
                "sum": 6.2,
            },
        }
        poll1 = _make_poll_result(per_ticker=per_ticker, timeseries_buckets=buckets1)
        poll2 = _make_poll_result(
            per_ticker=per_ticker,
            timeseries_buckets=buckets2,
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        partial_events = [e for e in events if e.get("event") == "partial_bucket"]
        assert len(partial_events) == 1

    @pytest.mark.asyncio
    async def test_new_bucket_key_triggers_change(self):
        """A new bucket key appearing should emit partial_bucket event."""
        per_ticker = {"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)}
        buckets1 = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.7,
                "high": 0.9,
                "low": 0.3,
                "count": 10,
                "sum": 5.0,
            },
        }
        buckets2 = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.7,
                "high": 0.9,
                "low": 0.3,
                "count": 10,
                "sum": 5.0,
            },
            "AAPL#1h": {
                "open": 0.4,
                "close": 0.6,
                "high": 0.8,
                "low": 0.2,
                "count": 50,
                "sum": 25.0,
            },
        }
        poll1 = _make_poll_result(per_ticker=per_ticker, timeseries_buckets=buckets1)
        poll2 = _make_poll_result(
            per_ticker=per_ticker,
            timeseries_buckets=buckets2,
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        partial_events = [e for e in events if e.get("event") == "partial_bucket"]
        assert len(partial_events) == 1

    @pytest.mark.asyncio
    async def test_unchanged_bucket_data_no_event(self):
        """Bucket data unchanged between polls should not emit events."""
        per_ticker = {"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)}
        buckets = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.7,
                "high": 0.9,
                "low": 0.3,
                "count": 10,
                "sum": 5.0,
            },
            "AAPL#1h": {
                "open": 0.4,
                "close": 0.6,
                "high": 0.8,
                "low": 0.2,
                "count": 50,
                "sum": 25.0,
            },
        }
        poll1 = _make_poll_result(per_ticker=per_ticker, timeseries_buckets=buckets)
        poll2 = _make_poll_result(
            per_ticker=per_ticker,
            timeseries_buckets=buckets,
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        partial_events = [e for e in events if e.get("event") == "partial_bucket"]
        assert len(partial_events) == 0


# ---------------------------------------------------------------------------
# T019: Test partial_bucket event emission in global stream
# ---------------------------------------------------------------------------


class TestPartialBucketEventEmission:
    """T019: Test partial_bucket event emission with correct payload fields."""

    @pytest.mark.asyncio
    async def test_baseline_poll_no_partial_bucket_events(self):
        """First poll (baseline) should not emit partial_bucket events (FR-011)."""
        per_ticker = {"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)}
        buckets = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.7,
                "high": 0.9,
                "low": 0.3,
                "count": 10,
                "sum": 5.0,
            },
        }
        gen = _make_generator(
            [_make_poll_result(per_ticker=per_ticker, timeseries_buckets=buckets)]
        )
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        partial_events = [e for e in events if e.get("event") == "partial_bucket"]
        assert len(partial_events) == 0

    @freeze_time("2026-03-20T15:32:00Z")
    @pytest.mark.asyncio
    async def test_changed_bucket_emits_partial_bucket_with_payload(self):
        """Changed bucket on second poll emits partial_bucket with ticker, resolution, bucket, progress_pct."""
        per_ticker = {"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)}
        buckets1 = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.6,
                "high": 0.8,
                "low": 0.3,
                "count": 8,
                "sum": 4.0,
            },
        }
        buckets2 = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.7,
                "high": 0.9,
                "low": 0.3,
                "count": 12,
                "sum": 6.0,
            },
        }
        poll1 = _make_poll_result(per_ticker=per_ticker, timeseries_buckets=buckets1)
        poll2 = _make_poll_result(
            per_ticker=per_ticker,
            timeseries_buckets=buckets2,
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        partial_events = [e for e in events if e.get("event") == "partial_bucket"]
        assert len(partial_events) == 1

        data = json.loads(partial_events[0]["data"])
        assert data["ticker"] == "AAPL"
        assert data["resolution"] == "5m"
        assert data["is_partial"] is True
        assert "progress_pct" in data
        assert 0.0 <= data["progress_pct"] <= 100.0
        # Verify bucket OHLC data is present
        assert data["bucket"]["open"] == 0.5
        assert data["bucket"]["close"] == 0.7
        assert data["bucket"]["high"] == 0.9
        assert data["bucket"]["count"] == 12

    @pytest.mark.asyncio
    async def test_multiple_changed_buckets_emit_multiple_events(self):
        """Multiple changed buckets should emit one partial_bucket per change."""
        per_ticker = {
            "AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5),
            "MSFT": TickerAggregate("MSFT", 0.60, "neutral", 0.60, 3),
        }
        buckets1 = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.6,
                "high": 0.8,
                "low": 0.3,
                "count": 8,
                "sum": 4.0,
            },
            "MSFT#1h": {
                "open": 0.3,
                "close": 0.5,
                "high": 0.6,
                "low": 0.2,
                "count": 20,
                "sum": 10.0,
            },
        }
        buckets2 = {
            "AAPL#5m": {
                "open": 0.5,
                "close": 0.7,
                "high": 0.9,
                "low": 0.3,
                "count": 10,
                "sum": 5.0,
            },
            "MSFT#1h": {
                "open": 0.3,
                "close": 0.6,
                "high": 0.7,
                "low": 0.2,
                "count": 25,
                "sum": 12.5,
            },
        }
        poll1 = _make_poll_result(per_ticker=per_ticker, timeseries_buckets=buckets1)
        poll2 = _make_poll_result(
            per_ticker=per_ticker,
            timeseries_buckets=buckets2,
            metrics_changed=False,
        )
        gen = _make_generator([poll1, poll2])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        partial_events = [e for e in events if e.get("event") == "partial_bucket"]
        assert len(partial_events) == 2

        # Check that both tickers are represented
        tickers_in_events = set()
        for pe in partial_events:
            data = json.loads(pe["data"])
            tickers_in_events.add(data["ticker"])
        assert "AAPL" in tickers_in_events
        assert "MSFT" in tickers_in_events


# ---------------------------------------------------------------------------
# T020: Test graceful degradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """T020: Test graceful degradation when timeseries fetch fails."""

    @freeze_time("2026-03-20T15:32:00Z")
    def test_client_error_returns_empty_dict(self):
        """When batch_get_item raises ClientError, should return empty dict."""
        from botocore.exceptions import ClientError

        table_name = "test-timeseries"

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {"TIMESERIES_TABLE": table_name}):
                service = PollingService(table_name="test-sentiments")

        mock_client = MagicMock()
        mock_client.batch_get_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "Rate exceeded",
                }
            },
            "BatchGetItem",
        )

        with patch("boto3.client", return_value=mock_client):
            result = service._fetch_timeseries_buckets(["AAPL"])

        assert result == {}

    @freeze_time("2026-03-20T15:32:00Z")
    def test_client_error_logs_warning(self):
        """ClientError should be logged as warning with error details (FR-009)."""
        from botocore.exceptions import ClientError

        table_name = "test-timeseries"

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {"TIMESERIES_TABLE": table_name}):
                service = PollingService(table_name="test-sentiments")

        mock_client = MagicMock()
        mock_client.batch_get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}},
            "BatchGetItem",
        )

        with (
            patch("boto3.client", return_value=mock_client),
            patch("src.lambdas.sse_streaming.polling.logger") as mock_logger,
        ):
            service._fetch_timeseries_buckets(["AAPL"])

        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args
        assert "Timeseries poll failed" in call_kwargs[0][0]

    @pytest.mark.asyncio
    async def test_poll_returns_empty_timeseries_on_fetch_failure(self):
        """poll() should still return valid PollResult with empty timeseries on failure."""
        from botocore.exceptions import ClientError

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {"TIMESERIES_TABLE": "test-timeseries"}):
                service = PollingService(table_name="test-sentiments")

        # Mock _query_all_sentiments to return some items
        items = [
            {
                "pk": "SENTIMENT#1",
                "matched_tickers": ["AAPL"],
                "sentiment": "positive",
                "score": 0.85,
            },
        ]
        service._query_all_sentiments = MagicMock(return_value={"Items": items})

        # Mock _fetch_timeseries_buckets to fail via ClientError internally
        mock_client = MagicMock()
        mock_client.batch_get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "fail"}},
            "BatchGetItem",
        )

        with patch("boto3.client", return_value=mock_client):
            result = await service.poll()

        # Should still get valid metrics and per_ticker
        assert result.metrics.total == 1
        assert "AAPL" in result.per_ticker
        # Timeseries should be empty due to failure
        assert result.timeseries_buckets == {}

    @pytest.mark.asyncio
    async def test_stream_unaffected_by_empty_timeseries(self):
        """Heartbeats and metrics should still emit when timeseries_buckets is empty."""
        poll1 = _make_poll_result(
            per_ticker={"AAPL": TickerAggregate("AAPL", 0.85, "positive", 0.85, 5)},
            timeseries_buckets={},
            metrics_changed=True,
        )
        gen = _make_generator([poll1])
        conn = _make_connection()

        events = []
        with suppress(asyncio.CancelledError):
            async for event in gen.generate_global_stream(conn):
                events.append(event)

        # Should have heartbeat and metrics events
        event_types = [e.get("event") for e in events]
        assert "heartbeat" in event_types
        assert "metrics" in event_types
        # No partial_bucket events
        assert "partial_bucket" not in event_types

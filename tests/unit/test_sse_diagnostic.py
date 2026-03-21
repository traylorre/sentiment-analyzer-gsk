"""Unit tests for SSE Diagnostic Tool (Feature 1230).

Tests the SSE protocol parser, event formatters, filtering,
session statistics, and connection error handling.
"""

# Import from scripts directory
import sys
import urllib.error
from argparse import Namespace
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from freezegun import freeze_time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from sse_diagnostic import (
    SessionStats,
    connect,
    format_event,
    format_heartbeat,
    format_metrics,
    format_partial_bucket,
    format_sentiment_update,
    parse_sse_stream,
    should_display,
)

# ─── SSE Parser Tests ─────────────────────────────────────────────────


class TestParseSSEStream:
    """Tests for parse_sse_stream()."""

    def test_parses_heartbeat_event(self):
        """Should parse a standard heartbeat SSE event."""
        raw = (
            b"event: heartbeat\n"
            b"id: evt_001\n"
            b'data: {"connections": 42, "uptime_seconds": 3600}\n'
            b"\n"
        )
        response = BytesIO(raw)
        events = list(parse_sse_stream(response))

        assert len(events) == 1
        event_type, data, event_id = events[0]
        assert event_type == "heartbeat"
        assert data["connections"] == 42
        assert data["uptime_seconds"] == 3600
        assert event_id == "evt_001"

    def test_parses_sentiment_update(self):
        """Should parse sentiment_update with all fields."""
        raw = (
            b"event: sentiment_update\n"
            b"id: evt_002\n"
            b'data: {"ticker": "AAPL", "score": 0.65, "label": "positive", "source": "tiingo", "confidence": 0.85}\n'
            b"\n"
        )
        events = list(parse_sse_stream(BytesIO(raw)))

        assert len(events) == 1
        _, data, _ = events[0]
        assert data["ticker"] == "AAPL"
        assert data["score"] == 0.65
        assert data["label"] == "positive"

    def test_handles_multiple_events(self):
        """Should parse multiple sequential events."""
        raw = (
            b"event: heartbeat\n"
            b'data: {"connections": 1}\n'
            b"\n"
            b"event: metrics\n"
            b'data: {"total": 100}\n'
            b"\n"
        )
        events = list(parse_sse_stream(BytesIO(raw)))
        assert len(events) == 2
        assert events[0][0] == "heartbeat"
        assert events[1][0] == "metrics"

    def test_skips_comment_lines(self):
        """Should ignore SSE comment lines (: prefix)."""
        raw = b': keepalive\nevent: heartbeat\ndata: {"ok": true}\n\n'
        events = list(parse_sse_stream(BytesIO(raw)))
        assert len(events) == 1

    def test_handles_multiline_data(self):
        """Should concatenate multiple data: lines."""
        raw = b'event: metrics\ndata: {"total":\ndata: 100}\n\n'
        events = list(parse_sse_stream(BytesIO(raw)))
        assert len(events) == 1
        _, data, _ = events[0]
        assert data["total"] == 100

    def test_handles_invalid_json(self):
        """Should wrap invalid JSON in raw field."""
        raw = b"event: test\ndata: not-json\n\n"
        events = list(parse_sse_stream(BytesIO(raw)))
        assert len(events) == 1
        _, data, _ = events[0]
        assert data["raw"] == "not-json"


# ─── Event Formatter Tests ────────────────────────────────────────────


class TestFormatters:
    """Tests for event formatter functions."""

    def test_format_heartbeat(self):
        """Should show connections and uptime."""
        result = format_heartbeat({"connections": 42, "uptime_seconds": 3600})
        assert "connections=42" in result
        assert "uptime=3600s" in result

    def test_format_metrics(self):
        """Should show totals and rates."""
        result = format_metrics(
            {
                "total": 1234,
                "positive": 678,
                "neutral": 345,
                "negative": 211,
                "rate_last_hour": 12,
            }
        )
        assert "total=1234" in result
        assert "positive=678" in result
        assert "+12/h" in result

    def test_format_sentiment_update(self):
        """Should show ticker, score, label, source."""
        result = format_sentiment_update(
            {
                "ticker": "AAPL",
                "score": 0.65,
                "label": "positive",
                "source": "tiingo",
                "confidence": 0.85,
            }
        )
        assert "AAPL" in result
        assert "+0.6500" in result
        assert "positive" in result
        assert "tiingo" in result

    def test_format_sentiment_negative_score(self):
        """Should show negative sign for negative scores."""
        result = format_sentiment_update(
            {"ticker": "TSLA", "score": -0.3, "label": "negative", "source": "finnhub"}
        )
        assert "-0.3000" in result

    def test_format_partial_bucket(self):
        """Should show ticker, resolution, progress, OHLC."""
        result = format_partial_bucket(
            {
                "ticker": "AAPL",
                "resolution": "5m",
                "progress_pct": 45.2,
                "bucket": {
                    "open": 0.55,
                    "high": 0.72,
                    "low": 0.41,
                    "close": 0.65,
                    "count": 8,
                },
            }
        )
        assert "AAPL#5m" in result
        assert "45.2%" in result
        assert "count=8" in result

    @freeze_time("2024-01-02T10:35:00Z")
    def test_format_event_includes_timestamp(self):
        """Should prefix with [HH:MM:SS] timestamp."""
        result = format_event("heartbeat", {"connections": 1, "uptime_seconds": 0})
        assert "[10:35:00]" in result

    def test_format_event_unknown_type(self):
        """Should render unknown event types as JSON."""
        result = format_event("custom_event", {"key": "value"})
        assert "custom_event" in result


# ─── Filter Tests ─────────────────────────────────────────────────────


class TestFiltering:
    """Tests for should_display() filter function."""

    def _args(self, event_type=None, ticker=None):
        return Namespace(event_type=event_type, ticker=ticker, json=False)

    def test_no_filter_passes_all(self):
        """With no filters, all events pass."""
        assert should_display("heartbeat", {}, self._args())
        assert should_display("sentiment_update", {"ticker": "AAPL"}, self._args())

    def test_event_type_filter_passes_matching(self):
        """Should pass events matching the event type filter."""
        assert should_display(
            "sentiment_update", {}, self._args(event_type="sentiment_update")
        )

    def test_event_type_filter_blocks_non_matching(self):
        """Should block events not matching the event type filter."""
        assert not should_display(
            "heartbeat", {}, self._args(event_type="sentiment_update")
        )

    def test_ticker_filter_passes_matching(self):
        """Should pass events with matching ticker."""
        assert should_display(
            "sentiment_update", {"ticker": "AAPL"}, self._args(ticker="AAPL")
        )

    def test_ticker_filter_blocks_non_matching(self):
        """Should block events with different ticker."""
        assert not should_display(
            "sentiment_update", {"ticker": "MSFT"}, self._args(ticker="AAPL")
        )

    def test_ticker_filter_passes_tickerless_events(self):
        """Should pass events without ticker field (heartbeat, deadline)."""
        assert should_display(
            "heartbeat", {"connections": 1}, self._args(ticker="AAPL")
        )

    def test_combined_filter_requires_both(self):
        """Should require both event type and ticker to match."""
        args = self._args(event_type="sentiment_update", ticker="AAPL")
        assert should_display("sentiment_update", {"ticker": "AAPL"}, args)
        assert not should_display("sentiment_update", {"ticker": "MSFT"}, args)
        assert not should_display("heartbeat", {}, args)

    def test_ticker_filter_case_insensitive(self):
        """Should match ticker case-insensitively."""
        assert should_display(
            "sentiment_update", {"ticker": "aapl"}, self._args(ticker="AAPL")
        )


# ─── Session Stats Tests ─────────────────────────────────────────────


class TestSessionStats:
    """Tests for SessionStats tracking and summary."""

    def test_counts_events_by_type(self):
        """Should accurately count events per type."""
        stats = SessionStats()
        stats.record_event("heartbeat")
        stats.record_event("heartbeat")
        stats.record_event("sentiment_update")

        assert stats.event_counts["heartbeat"] == 2
        assert stats.event_counts["sentiment_update"] == 1
        assert stats.total_events == 3

    def test_summary_includes_duration(self):
        """Should include session duration in summary."""
        stats = SessionStats()
        stats.record_event("heartbeat")
        summary = stats.summary()
        assert "Duration:" in summary
        assert "Total events:" in summary

    def test_summary_includes_per_type_breakdown(self):
        """Should list event counts by type."""
        stats = SessionStats()
        stats.record_event("heartbeat")
        stats.record_event("metrics")
        summary = stats.summary()
        assert "heartbeat: 1" in summary
        assert "metrics: 1" in summary

    def test_heartbeat_gap_warning(self):
        """Should warn when heartbeat gap exceeds 60 seconds."""
        stats = SessionStats()
        stats.last_heartbeat_time = 0.0
        stats.record_event("heartbeat")
        # Simulate large gap by manipulating internal state
        stats.max_heartbeat_gap = 90.0
        summary = stats.summary()
        assert "WARNING" in summary
        assert "Heartbeat gap" in summary

    def test_no_warning_for_normal_heartbeats(self):
        """Should not warn when heartbeats are regular."""
        stats = SessionStats()
        stats.max_heartbeat_gap = 35.0
        summary = stats.summary()
        assert "WARNING" not in summary

    def test_reconnect_count_in_summary(self):
        """Should show reconnection count if > 0."""
        stats = SessionStats()
        stats.reconnect_count = 2
        summary = stats.summary()
        assert "Reconnections: 2" in summary


# ─── Connection Tests ─────────────────────────────────────────────────


class TestConnect:
    """Tests for connect() HTTP error handling."""

    @patch("sse_diagnostic.urllib.request.urlopen")
    def test_sets_accept_header(self, mock_urlopen):
        """Should set Accept: text/event-stream header."""
        mock_urlopen.return_value = MagicMock()
        connect("http://localhost:8000/api/v2/stream")
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Accept") == "text/event-stream"

    @patch("sse_diagnostic.urllib.request.urlopen")
    def test_sets_bearer_token(self, mock_urlopen):
        """Should set Authorization header when token provided."""
        mock_urlopen.return_value = MagicMock()
        connect("http://localhost:8000/api/v2/stream", token="my-token")
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer my-token"

    @patch("sse_diagnostic.urllib.request.urlopen")
    def test_sets_user_id_header(self, mock_urlopen):
        """Should set X-User-ID header when user_id provided."""
        mock_urlopen.return_value = MagicMock()
        connect("http://localhost:8000/api/v2/stream", user_id="user-123")
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-user-id") == "user-123"

    @patch("sse_diagnostic.urllib.request.urlopen")
    def test_sets_last_event_id(self, mock_urlopen):
        """Should set Last-Event-ID header for resumption."""
        mock_urlopen.return_value = MagicMock()
        connect("http://localhost:8000/api/v2/stream", last_event_id="evt_42")
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Last-event-id") == "evt_42"

    @patch("sse_diagnostic.urllib.request.urlopen")
    def test_401_raises_auth_error(self, mock_urlopen):
        """Should raise clear auth error on 401."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "url", 401, "Unauthorized", {}, None
        )
        import pytest

        with pytest.raises(ConnectionError, match="Authentication required"):
            connect("http://localhost:8000/api/v2/stream")

    @patch("sse_diagnostic.urllib.request.urlopen")
    def test_503_raises_limit_error(self, mock_urlopen):
        """Should raise connection limit error with retry info on 503."""
        headers = MagicMock()
        headers.get.return_value = "30"
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "url", 503, "Service Unavailable", headers, None
        )
        import pytest

        with pytest.raises(ConnectionError, match="Connection limit.*30"):
            connect("http://localhost:8000/api/v2/stream")

    @patch("sse_diagnostic.urllib.request.urlopen")
    def test_network_error_raises_connection_error(self, mock_urlopen):
        """Should raise clear error on network failure."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        import pytest

        with pytest.raises(ConnectionError, match="Cannot connect"):
            connect("http://localhost:9999/api/v2/stream")

"""
Tests for SSE resolution-based event filtering.

Canonical References:
- [CS-007] MDN Server-Sent Events: "Filter events at server to reduce bandwidth"

TDD-SSE-001: Events matching subscribed resolutions pass filter
TDD-SSE-002: Events NOT matching subscribed resolutions are blocked
TDD-SSE-003: Heartbeat events always pass
TDD-SSE-004: Ticker and resolution filters combined
TDD-SSE-005: Empty ticker filter allows all tickers
"""

from datetime import UTC, datetime

from src.lambdas.sse_streaming.resolution_filter import should_send_event
from src.lambdas.sse_streaming.timeseries_models import (
    BucketUpdateEvent,
    HeartbeatEvent,
    PartialBucketEvent,
    SSEConnectionConfig,
)
from src.lib.timeseries import Resolution


class TestSSEResolutionFilter:
    """
    Canonical: [CS-007] "Filter events at server to reduce bandwidth"
    """

    def test_filter_passes_subscribed_resolutions(self):
        """Events matching subscribed resolutions MUST pass filter."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution.ONE_MINUTE, Resolution.FIVE_MINUTES],
        )

        event_1m = BucketUpdateEvent(
            ticker="AAPL",
            resolution=Resolution.ONE_MINUTE,
            bucket={},
        )
        event_5m = BucketUpdateEvent(
            ticker="AAPL",
            resolution=Resolution.FIVE_MINUTES,
            bucket={},
        )

        assert should_send_event(connection, event_1m) is True
        assert should_send_event(connection, event_5m) is True

    def test_filter_blocks_unsubscribed_resolutions(self):
        """Events NOT matching subscribed resolutions MUST be blocked."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution.ONE_MINUTE],
        )

        event_1h = BucketUpdateEvent(
            ticker="AAPL",
            resolution=Resolution.ONE_HOUR,
            bucket={},
        )

        assert should_send_event(connection, event_1h) is False

    def test_heartbeat_always_passes(self):
        """Heartbeat events MUST always pass regardless of resolution filter."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution.ONE_MINUTE],
        )

        heartbeat = HeartbeatEvent(
            timestamp=datetime.now(UTC),
            connections=10,
        )

        assert should_send_event(connection, heartbeat) is True

    def test_ticker_filter_combined_with_resolution(self):
        """Both ticker AND resolution filters MUST be applied."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution.ONE_MINUTE],
            subscribed_tickers=["AAPL", "TSLA"],
        )

        event_aapl = BucketUpdateEvent(
            ticker="AAPL",
            resolution=Resolution.ONE_MINUTE,
            bucket={},
        )
        event_msft = BucketUpdateEvent(
            ticker="MSFT",
            resolution=Resolution.ONE_MINUTE,
            bucket={},
        )

        assert should_send_event(connection, event_aapl) is True
        assert should_send_event(connection, event_msft) is False

    def test_empty_ticker_filter_allows_all(self):
        """Empty ticker filter MUST allow all tickers."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution.ONE_MINUTE],
            subscribed_tickers=[],  # Empty = all
        )

        event = BucketUpdateEvent(
            ticker="GOOGL",
            resolution=Resolution.ONE_MINUTE,
            bucket={},
        )

        assert should_send_event(connection, event) is True

    def test_empty_resolution_filter_allows_all(self):
        """Empty resolution filter MUST allow all resolutions."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[],  # Empty = all
        )

        for resolution in Resolution:
            event = BucketUpdateEvent(
                ticker="AAPL",
                resolution=resolution,
                bucket={},
            )
            assert should_send_event(connection, event) is True

    def test_partial_bucket_event_filtered_same_as_bucket(self):
        """PartialBucketEvent MUST use same filtering as BucketUpdateEvent."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution.ONE_MINUTE],
        )

        # Matching resolution - should pass
        partial_1m = PartialBucketEvent(
            ticker="AAPL",
            resolution=Resolution.ONE_MINUTE,
            bucket={},
            progress_pct=50.0,
        )
        assert should_send_event(connection, partial_1m) is True

        # Non-matching resolution - should block
        partial_1h = PartialBucketEvent(
            ticker="AAPL",
            resolution=Resolution.ONE_HOUR,
            bucket={},
            progress_pct=25.0,
        )
        assert should_send_event(connection, partial_1h) is False

    def test_multiple_resolutions_subscribed(self):
        """Connection with multiple resolutions MUST filter correctly."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[
                Resolution.ONE_MINUTE,
                Resolution.FIVE_MINUTES,
                Resolution.ONE_HOUR,
            ],
        )

        # These should pass
        for res in [
            Resolution.ONE_MINUTE,
            Resolution.FIVE_MINUTES,
            Resolution.ONE_HOUR,
        ]:
            event = BucketUpdateEvent(ticker="AAPL", resolution=res, bucket={})
            assert should_send_event(connection, event) is True

        # These should be blocked
        for res in [
            Resolution.TEN_MINUTES,
            Resolution.THREE_HOURS,
            Resolution.SIX_HOURS,
            Resolution.TWELVE_HOURS,
            Resolution.TWENTY_FOUR_HOURS,
        ]:
            event = BucketUpdateEvent(ticker="AAPL", resolution=res, bucket={})
            assert should_send_event(connection, event) is False

    def test_combined_ticker_and_resolution_rejection(self):
        """Event matching resolution but wrong ticker MUST be rejected."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution.ONE_MINUTE],
            subscribed_tickers=["AAPL"],
        )

        # Wrong ticker, right resolution
        event = BucketUpdateEvent(
            ticker="MSFT",
            resolution=Resolution.ONE_MINUTE,
            bucket={},
        )
        assert should_send_event(connection, event) is False

    def test_combined_resolution_and_ticker_rejection(self):
        """Event matching ticker but wrong resolution MUST be rejected."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution.ONE_MINUTE],
            subscribed_tickers=["AAPL"],
        )

        # Right ticker, wrong resolution
        event = BucketUpdateEvent(
            ticker="AAPL",
            resolution=Resolution.ONE_HOUR,
            bucket={},
        )
        assert should_send_event(connection, event) is False

    def test_case_sensitivity_ticker(self):
        """Ticker filter SHOULD be case-sensitive."""
        connection = SSEConnectionConfig(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution.ONE_MINUTE],
            subscribed_tickers=["AAPL"],
        )

        event_lower = BucketUpdateEvent(
            ticker="aapl",
            resolution=Resolution.ONE_MINUTE,
            bucket={},
        )
        # Ticker comparison should be case-sensitive
        assert should_send_event(connection, event_lower) is False

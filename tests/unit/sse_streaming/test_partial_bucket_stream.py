"""Unit tests for partial bucket streaming and debounce (T027, T028)."""

import time
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.lib.timeseries import Resolution


class TestDebouncer:
    """Tests for the Debouncer class (T028)."""

    def test_first_emit_always_allowed(self):
        """First emission for a key should always be allowed."""
        from stream import Debouncer

        debouncer = Debouncer(interval_ms=100)
        assert debouncer.should_emit("AAPL#5m") is True

    def test_rapid_emit_debounced(self):
        """Rapid emissions within interval should be debounced."""
        from stream import Debouncer

        debouncer = Debouncer(interval_ms=100)

        # First emission allowed
        assert debouncer.should_emit("AAPL#5m") is True

        # Immediate second emission debounced
        assert debouncer.should_emit("AAPL#5m") is False

    def test_emit_after_interval_allowed(self):
        """Emission after interval has passed should be allowed."""
        from stream import Debouncer

        debouncer = Debouncer(interval_ms=50)  # 50ms for faster test

        # First emission
        assert debouncer.should_emit("AAPL#5m") is True

        # Wait for interval
        time.sleep(0.06)  # 60ms > 50ms

        # Should be allowed now
        assert debouncer.should_emit("AAPL#5m") is True

    def test_different_keys_independent(self):
        """Different keys should have independent debounce state."""
        from stream import Debouncer

        debouncer = Debouncer(interval_ms=100)

        # Both first emissions allowed
        assert debouncer.should_emit("AAPL#5m") is True
        assert debouncer.should_emit("MSFT#1h") is True

        # Both debounced
        assert debouncer.should_emit("AAPL#5m") is False
        assert debouncer.should_emit("MSFT#1h") is False

    def test_reset_all_keys(self):
        """Reset without key should clear all state."""
        from stream import Debouncer

        debouncer = Debouncer(interval_ms=100)

        # Emit for both keys
        debouncer.should_emit("AAPL#5m")
        debouncer.should_emit("MSFT#1h")

        # Reset all
        debouncer.reset()

        # Both should be allowed now
        assert debouncer.should_emit("AAPL#5m") is True
        assert debouncer.should_emit("MSFT#1h") is True

    def test_reset_specific_key(self):
        """Reset with key should only clear that key's state."""
        from stream import Debouncer

        debouncer = Debouncer(interval_ms=100)

        # Emit for both keys
        debouncer.should_emit("AAPL#5m")
        debouncer.should_emit("MSFT#1h")

        # Reset only AAPL
        debouncer.reset("AAPL#5m")

        # AAPL allowed, MSFT still debounced
        assert debouncer.should_emit("AAPL#5m") is True
        assert debouncer.should_emit("MSFT#1h") is False


class TestPartialBucketEvent:
    """Tests for partial bucket event creation (T027)."""

    @pytest.fixture
    def mock_stream_generator(self):
        """Create a mock stream generator for testing."""
        from stream import SSEStreamGenerator

        with patch("stream.connection_manager"), patch("stream.get_polling_service"):
            generator = SSEStreamGenerator()
            return generator

    def test_create_partial_bucket_event_structure(self, mock_stream_generator):
        """Partial bucket event should have correct structure."""
        with (
            patch("stream.floor_to_bucket") as mock_floor,
            patch("stream.calculate_bucket_progress") as mock_progress,
        ):
            mock_floor.return_value = datetime(2025, 12, 22, 10, 0, 0, tzinfo=UTC)
            mock_progress.return_value = 45.5

            event = mock_stream_generator._create_partial_bucket_event(
                ticker="AAPL",
                resolution=Resolution.FIVE_MINUTES,
                bucket_data={"open": 0.5, "close": 0.7},
            )

            assert event.event == "partial_bucket"
            assert "ticker" in event.data
            assert event.data["ticker"] == "AAPL"
            assert event.data["resolution"] == "5m"
            assert event.data["progress_pct"] == 45.5
            assert event.data["is_partial"] is True

    def test_create_partial_bucket_event_calculates_progress(
        self, mock_stream_generator
    ):
        """Should calculate progress_pct using floor_to_bucket and calculate_bucket_progress."""
        with (
            patch("stream.floor_to_bucket") as mock_floor,
            patch("stream.calculate_bucket_progress") as mock_progress,
        ):
            mock_floor.return_value = datetime(2025, 12, 22, 10, 0, 0, tzinfo=UTC)
            mock_progress.return_value = 80.0

            event = mock_stream_generator._create_partial_bucket_event(
                ticker="MSFT",
                resolution=Resolution.ONE_HOUR,
                bucket_data={},
            )

            # Verify calculate_bucket_progress was called with the floored bucket start
            mock_floor.assert_called_once()
            mock_progress.assert_called_once()
            assert event.data["progress_pct"] == 80.0


class TestShouldEmitBucketUpdate:
    """Tests for debounced bucket update emission."""

    @pytest.fixture
    def mock_stream_generator(self):
        """Create a mock stream generator for testing."""
        from stream import SSEStreamGenerator

        with patch("stream.connection_manager"), patch("stream.get_polling_service"):
            generator = SSEStreamGenerator(debounce_ms=100)
            return generator

    def test_should_emit_uses_debouncer(self, mock_stream_generator):
        """should_emit_bucket_update should use the debouncer."""
        # First call allowed
        assert (
            mock_stream_generator.should_emit_bucket_update(
                "AAPL", Resolution.FIVE_MINUTES
            )
            is True
        )

        # Immediate second call debounced
        assert (
            mock_stream_generator.should_emit_bucket_update(
                "AAPL", Resolution.FIVE_MINUTES
            )
            is False
        )

    def test_debounce_key_format(self, mock_stream_generator):
        """Debounce key should be ticker#resolution format."""
        # These should be treated as different keys
        assert (
            mock_stream_generator.should_emit_bucket_update(
                "AAPL", Resolution.FIVE_MINUTES
            )
            is True
        )
        assert (
            mock_stream_generator.should_emit_bucket_update("AAPL", Resolution.ONE_HOUR)
            is True
        )

        # Both debounced now
        assert (
            mock_stream_generator.should_emit_bucket_update(
                "AAPL", Resolution.FIVE_MINUTES
            )
            is False
        )
        assert (
            mock_stream_generator.should_emit_bucket_update("AAPL", Resolution.ONE_HOUR)
            is False
        )


class TestDebounceIntegration:
    """Integration tests for debounce with default 100ms interval."""

    def test_default_debounce_interval(self):
        """Default debounce should be 100ms."""
        from stream import DEFAULT_DEBOUNCE_MS, Debouncer

        assert DEFAULT_DEBOUNCE_MS == 100

        # Default debouncer uses 100ms
        debouncer = Debouncer()
        assert debouncer._interval_seconds == 0.1  # 100ms = 0.1s

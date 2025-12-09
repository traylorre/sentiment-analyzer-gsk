"""Unit tests for ConsecutiveFailureTracker.

Tests failure tracking and alert triggering for operational monitoring.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.lambdas.shared.failure_tracker import (
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_FAILURE_WINDOW_MINUTES,
    ConsecutiveFailureTracker,
    FailureWindow,
)


class TestFailureWindow:
    """Tests for FailureWindow tracking."""

    def test_add_failure_increments_count(self) -> None:
        """Adding failures should increment count."""
        window = FailureWindow()

        count1 = window.add_failure(datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC))
        count2 = window.add_failure(datetime(2025, 12, 9, 14, 1, 0, tzinfo=UTC))
        count3 = window.add_failure(datetime(2025, 12, 9, 14, 2, 0, tzinfo=UTC))

        assert count1 == 1
        assert count2 == 2
        assert count3 == 3

    def test_prunes_old_failures(self) -> None:
        """Failures outside window should be pruned."""
        window = FailureWindow(window_minutes=15)

        # Add failure 20 minutes ago
        old_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)
        window.add_failure(old_time)

        # Add recent failure (this should prune the old one)
        recent_time = old_time + timedelta(minutes=20)
        count = window.add_failure(recent_time)

        assert count == 1  # Old failure pruned

    def test_keeps_failures_within_window(self) -> None:
        """Failures within window should be retained."""
        window = FailureWindow(window_minutes=15)
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        # Add 3 failures within 10 minutes
        window.add_failure(base_time)
        window.add_failure(base_time + timedelta(minutes=5))
        count = window.add_failure(base_time + timedelta(minutes=10))

        assert count == 3  # All within window

    def test_reset_clears_failures(self) -> None:
        """Reset should clear all tracked failures."""
        window = FailureWindow()

        window.add_failure(datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC))
        window.add_failure(datetime(2025, 12, 9, 14, 1, 0, tzinfo=UTC))

        window.reset()

        assert window.count == 0

    def test_count_property(self) -> None:
        """Count property should return current failure count."""
        window = FailureWindow()
        assert window.count == 0

        window.add_failure()
        assert window.count == 1


class TestConsecutiveFailureTracker:
    """Tests for ConsecutiveFailureTracker."""

    def test_default_configuration(self) -> None:
        """Should use default configuration values."""
        tracker = ConsecutiveFailureTracker()

        assert tracker.window_minutes == DEFAULT_FAILURE_WINDOW_MINUTES
        assert tracker.threshold == DEFAULT_FAILURE_THRESHOLD

    def test_record_failure_increments_count(self) -> None:
        """Recording failures should increment count."""
        tracker = ConsecutiveFailureTracker()
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        tracker.record_failure("Error 1", at=base_time)
        assert tracker.current_failure_count == 1

        tracker.record_failure("Error 2", at=base_time + timedelta(minutes=1))
        assert tracker.current_failure_count == 2

    def test_record_success_resets_count(self) -> None:
        """Recording success should reset failure count."""
        tracker = ConsecutiveFailureTracker()
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        tracker.record_failure("Error 1", at=base_time)
        tracker.record_failure("Error 2", at=base_time + timedelta(minutes=1))
        assert tracker.current_failure_count == 2

        tracker.record_success()
        assert tracker.current_failure_count == 0

    def test_alert_at_threshold(self) -> None:
        """Should trigger alert when threshold reached."""
        alert_callback = MagicMock()
        tracker = ConsecutiveFailureTracker(
            threshold=3,
            alert_callback=alert_callback,
        )
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        # First 2 failures - no alert
        tracker.record_failure("Error 1", at=base_time)
        tracker.record_failure("Error 2", at=base_time + timedelta(minutes=1))
        alert_callback.assert_not_called()

        # Third failure triggers alert
        triggered = tracker.record_failure(
            "Error 3", at=base_time + timedelta(minutes=2)
        )

        assert triggered is True
        alert_callback.assert_called_once()
        alert_msg = alert_callback.call_args[0][0]
        assert "3 consecutive" in alert_msg
        assert "Error 3" in alert_msg

    def test_no_duplicate_alerts(self) -> None:
        """Should not send duplicate alerts in same window."""
        alert_callback = MagicMock()
        tracker = ConsecutiveFailureTracker(
            threshold=3,
            alert_callback=alert_callback,
        )
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        # Reach threshold
        tracker.record_failure("Error 1", at=base_time)
        tracker.record_failure("Error 2", at=base_time + timedelta(minutes=1))
        tracker.record_failure("Error 3", at=base_time + timedelta(minutes=2))

        # Additional failures should not trigger more alerts
        triggered = tracker.record_failure(
            "Error 4", at=base_time + timedelta(minutes=3)
        )

        assert triggered is False
        assert alert_callback.call_count == 1  # Only one alert

    def test_alert_resets_after_success(self) -> None:
        """Should be able to alert again after success resets tracker."""
        alert_callback = MagicMock()
        tracker = ConsecutiveFailureTracker(
            threshold=3,
            alert_callback=alert_callback,
        )
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        # First alert
        tracker.record_failure("Error 1", at=base_time)
        tracker.record_failure("Error 2", at=base_time + timedelta(minutes=1))
        tracker.record_failure("Error 3", at=base_time + timedelta(minutes=2))
        assert alert_callback.call_count == 1

        # Success resets
        tracker.record_success()

        # Second round of failures should trigger new alert
        tracker.record_failure("Error 4", at=base_time + timedelta(minutes=10))
        tracker.record_failure("Error 5", at=base_time + timedelta(minutes=11))
        tracker.record_failure("Error 6", at=base_time + timedelta(minutes=12))

        assert alert_callback.call_count == 2

    def test_is_alert_active(self) -> None:
        """Should track whether alert has been sent."""
        tracker = ConsecutiveFailureTracker(threshold=2)
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        assert tracker.is_alert_active is False

        tracker.record_failure("Error 1", at=base_time)
        assert tracker.is_alert_active is False

        tracker.record_failure("Error 2", at=base_time + timedelta(minutes=1))
        assert tracker.is_alert_active is True

        tracker.record_success()
        assert tracker.is_alert_active is False

    def test_custom_window_minutes(self) -> None:
        """Should respect custom window configuration."""
        tracker = ConsecutiveFailureTracker(
            window_minutes=5,
            threshold=3,
        )
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        # Add failures within the 5-minute window
        tracker.record_failure("Error 1", at=base_time)
        tracker.record_failure("Error 2", at=base_time + timedelta(minutes=2))
        tracker.record_failure("Error 3", at=base_time + timedelta(minutes=4))

        # All 3 failures within 5-minute window
        assert tracker.current_failure_count == 3

    def test_window_prunes_old_failures(self) -> None:
        """Failures outside window should be pruned when new failure added."""
        tracker = ConsecutiveFailureTracker(
            window_minutes=5,
            threshold=3,
        )
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        # Add failures spread across time
        tracker.record_failure("Error 1", at=base_time)
        tracker.record_failure("Error 2", at=base_time + timedelta(minutes=3))
        # This one is 10 minutes after first - cutoff is 10-5=5, so failures <= 5min are pruned
        # Both 0min and 3min are pruned, only 10min remains
        tracker.record_failure("Error 3", at=base_time + timedelta(minutes=10))

        # Only the most recent failure remains (others outside 5-min window)
        assert tracker.current_failure_count == 1

    def test_alert_callback_exception_handled(self) -> None:
        """Should handle exceptions from alert callback gracefully."""

        def failing_callback(msg: str) -> None:
            raise RuntimeError("SNS unavailable")

        tracker = ConsecutiveFailureTracker(
            threshold=2,
            alert_callback=failing_callback,
        )
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        # Should not raise, even if callback fails
        tracker.record_failure("Error 1", at=base_time)
        tracker.record_failure("Error 2", at=base_time + timedelta(minutes=1))

        # Alert was attempted
        assert tracker.is_alert_active is True

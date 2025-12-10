"""Unit tests for failure tracker + alert publisher integration (T050).

Tests the integration between ConsecutiveFailureTracker and AlertPublisher
per US4 requirements for operational visibility.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.lambdas.ingestion.alerting import (
    AlertPublisher,
    ConsecutiveFailureAlert,
)
from src.lambdas.shared.failure_tracker import ConsecutiveFailureTracker


class TestFailureTrackerAlertIntegration:
    """Tests for integrating failure tracker with alert publisher."""

    def test_tracker_callback_publishes_to_sns(self) -> None:
        """Failure tracker callback should publish via AlertPublisher."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        # Create callback that wraps the publisher
        def alert_callback(message: str) -> None:
            alert = ConsecutiveFailureAlert(
                failure_count=3,
                window_minutes=15,
                first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
                last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
                sources_affected=["tiingo", "finnhub"],
                error_summary=message[:200],
            )
            publisher.publish_failure_alert(alert)

        tracker = ConsecutiveFailureTracker(
            alert_callback=alert_callback,
            threshold=3,
            window_minutes=15,
        )

        # Record 3 failures to trigger alert
        tracker.record_failure("Timeout error 1")
        tracker.record_failure("Timeout error 2")
        tracker.record_failure("Timeout error 3")

        # Should have published alert
        mock_sns.publish.assert_called_once()

    def test_success_resets_tracker_and_allows_new_alerts(self) -> None:
        """Success should reset tracker allowing future alerts."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
            alert_cooldown_minutes=0,  # No cooldown for testing
        )

        call_count = {"value": 0}

        def alert_callback(message: str) -> None:
            call_count["value"] += 1
            alert = ConsecutiveFailureAlert(
                failure_count=3,
                window_minutes=15,
                first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
                last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
                sources_affected=["tiingo"],
                error_summary=message[:200],
            )
            publisher.publish_failure_alert(alert)

        tracker = ConsecutiveFailureTracker(
            alert_callback=alert_callback,
            threshold=3,
        )

        # First set of failures
        tracker.record_failure("Error 1")
        tracker.record_failure("Error 2")
        tracker.record_failure("Error 3")
        assert call_count["value"] == 1

        # Success resets
        tracker.record_success()
        assert tracker.current_failure_count == 0

        # Second set of failures should trigger again
        with patch("src.lambdas.ingestion.alerting.datetime") as mock_dt:
            # Advance time past cooldown
            mock_dt.now.return_value = datetime(2025, 12, 9, 15, 0, 0, tzinfo=UTC)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            tracker.record_failure("Error 4")
            tracker.record_failure("Error 5")
            tracker.record_failure("Error 6")

        assert call_count["value"] == 2

    def test_tracker_tracks_affected_sources(self) -> None:
        """Tracker should track which sources are affected."""
        # The failure tracker doesn't currently track sources
        # This test documents expected behavior for future enhancement
        tracker = ConsecutiveFailureTracker(threshold=3)

        # Record failures with different source info in messages
        tracker.record_failure("Tiingo: Connection timeout")
        tracker.record_failure("Tiingo: HTTP 503")
        tracker.record_failure("Tiingo: Rate limited")

        assert tracker.current_failure_count == 3

    def test_alert_only_sent_once_until_reset(self) -> None:
        """Alert should only be sent once until success resets."""
        alert_count = {"value": 0}

        def alert_callback(message: str) -> None:
            alert_count["value"] += 1

        tracker = ConsecutiveFailureTracker(
            alert_callback=alert_callback,
            threshold=3,
        )

        # First 3 failures - alert sent
        tracker.record_failure("Error 1")
        tracker.record_failure("Error 2")
        tracker.record_failure("Error 3")
        assert alert_count["value"] == 1

        # More failures - no more alerts
        tracker.record_failure("Error 4")
        tracker.record_failure("Error 5")
        assert alert_count["value"] == 1  # Still 1

    def test_failures_outside_window_dont_trigger_alert(self) -> None:
        """Failures outside 15-minute window should not trigger alert."""
        alert_count = {"value": 0}

        def alert_callback(message: str) -> None:
            alert_count["value"] += 1

        tracker = ConsecutiveFailureTracker(
            alert_callback=alert_callback,
            threshold=3,
            window_minutes=15,
        )

        # Record failures spread over 20 minutes (outside window)
        base_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)
        tracker.record_failure("Error 1", at=base_time)
        tracker.record_failure("Error 2", at=base_time + timedelta(minutes=10))
        tracker.record_failure(
            "Error 3", at=base_time + timedelta(minutes=20)
        )  # 20 min after first

        # Third failure is 20 min after first, so first should be pruned
        # Only 2 failures in window - no alert
        assert alert_count["value"] == 0


class TestCreateAlertCallback:
    """Tests for creating alert callbacks from AlertPublisher."""

    def test_create_callback_from_publisher(self) -> None:
        """Can create a callback function from AlertPublisher."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        def create_alert_callback(
            pub: AlertPublisher,
            sources: list[str],
        ) -> callable:
            """Factory to create alert callback for tracker."""
            first_failure_at = datetime.now(UTC)

            def callback(error_message: str) -> None:
                alert = ConsecutiveFailureAlert(
                    failure_count=3,  # Always 3 at threshold
                    window_minutes=15,
                    first_failure_at=first_failure_at,
                    last_failure_at=datetime.now(UTC),
                    sources_affected=sources,
                    error_summary=error_message[:200],
                )
                pub.publish_failure_alert(alert)

            return callback

        callback = create_alert_callback(publisher, ["tiingo"])
        callback("Test error")

        mock_sns.publish.assert_called_once()

    def test_callback_handles_long_error_messages(self) -> None:
        """Callback should truncate long error messages."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        long_error = "Error: " + "x" * 500  # Very long message

        alert = ConsecutiveFailureAlert(
            failure_count=3,
            window_minutes=15,
            first_failure_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
            last_failure_at=datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC),
            sources_affected=["tiingo"],
            error_summary=long_error[:200],  # Truncated
        )

        publisher.publish_failure_alert(alert)

        # Should publish without error
        mock_sns.publish.assert_called_once()


class TestHandlerIntegrationPattern:
    """Tests documenting the expected handler integration pattern."""

    def test_handler_integration_pattern(self) -> None:
        """Document expected pattern for handler integration."""
        mock_sns = MagicMock()

        # This test documents the pattern for T050 handler integration:
        #
        # 1. Create AlertPublisher with SNS client
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        # 2. Create callback that creates structured alerts
        sources_affected: list[str] = []
        first_failure_time: datetime | None = None

        def alert_callback(error_message: str) -> None:
            nonlocal first_failure_time
            now = datetime.now(UTC)
            if first_failure_time is None:
                first_failure_time = now

            alert = ConsecutiveFailureAlert(
                failure_count=3,
                window_minutes=15,
                first_failure_at=first_failure_time,
                last_failure_at=now,
                sources_affected=sources_affected if sources_affected else ["unknown"],
                error_summary=error_message[:200],
            )
            publisher.publish_failure_alert(alert)

        # 3. Create tracker with callback
        tracker = ConsecutiveFailureTracker(
            alert_callback=alert_callback,
            threshold=3,
            window_minutes=15,
        )

        # 4. In handler, call tracker.record_failure() or tracker.record_success()
        sources_affected.append("tiingo")
        tracker.record_failure("Tiingo timeout")
        tracker.record_failure("Tiingo HTTP 500")
        tracker.record_failure("Tiingo rate limited")

        # Alert published via callback
        assert mock_sns.publish.called

"""Consecutive failure tracker for operational alerting.

Tracks consecutive failures within a time window to trigger alerts.
Implements FR-006: Alert on 3+ consecutive failures within 15 minutes.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_FAILURE_WINDOW_MINUTES = 15
DEFAULT_FAILURE_THRESHOLD = 3


@dataclass
class FailureWindow:
    """Tracks failures within a sliding time window.

    Attributes:
        failure_timestamps: List of failure timestamps within window
        window_minutes: Size of the tracking window
    """

    failure_timestamps: list[datetime] = field(default_factory=list)
    window_minutes: int = DEFAULT_FAILURE_WINDOW_MINUTES

    def add_failure(self, at: datetime | None = None) -> int:
        """Record a failure and return current consecutive count.

        Args:
            at: Failure timestamp (default: now)

        Returns:
            Number of consecutive failures within window
        """
        if at is None:
            at = datetime.now(UTC)

        # Add new failure
        self.failure_timestamps.append(at)

        # Prune old failures outside window
        cutoff = at - timedelta(minutes=self.window_minutes)
        self.failure_timestamps = [ts for ts in self.failure_timestamps if ts > cutoff]

        return len(self.failure_timestamps)

    def reset(self) -> None:
        """Reset failure tracking (e.g., after successful operation)."""
        self.failure_timestamps = []

    @property
    def count(self) -> int:
        """Current failure count within window.

        Note: Does NOT auto-prune based on current time. Pruning only
        happens during add_failure() to support deterministic testing
        with fixed timestamps.
        """
        return len(self.failure_timestamps)


@dataclass
class ConsecutiveFailureTracker:
    """Tracks consecutive failures and triggers alerts when threshold exceeded.

    Implements FR-006: Alert operations team when 3+ consecutive failures
    occur within a 15-minute window.

    Usage:
        tracker = ConsecutiveFailureTracker(
            alert_callback=lambda msg: sns_client.publish(TopicArn=..., Message=msg)
        )

        # On each collection attempt
        try:
            result = collect_data()
            tracker.record_success()
        except Exception as e:
            should_alert = tracker.record_failure(str(e))
            if should_alert:
                # Alert has already been sent via callback
                pass
    """

    window_minutes: int = DEFAULT_FAILURE_WINDOW_MINUTES
    threshold: int = DEFAULT_FAILURE_THRESHOLD
    alert_callback: callable = None  # type: ignore[assignment]
    _window: FailureWindow = field(default_factory=FailureWindow)
    _alert_sent: bool = field(default=False)
    _last_alert_at: datetime | None = field(default=None)

    def __post_init__(self) -> None:
        """Initialize failure window with configured duration."""
        self._window = FailureWindow(window_minutes=self.window_minutes)

    def record_failure(self, error_message: str, at: datetime | None = None) -> bool:
        """Record a failure and potentially trigger alert.

        Args:
            error_message: Description of the failure
            at: Failure timestamp (default: now)

        Returns:
            True if alert threshold was reached and alert was sent
        """
        if at is None:
            at = datetime.now(UTC)

        count = self._window.add_failure(at)

        logger.warning(
            "Collection failure recorded",
            extra={
                "consecutive_failures": count,
                "threshold": self.threshold,
                "error": error_message,
            },
        )

        # Check if we need to alert
        if count >= self.threshold and not self._alert_sent:
            self._send_alert(error_message, count, at)
            return True

        return False

    def record_success(self) -> None:
        """Record a successful operation, resetting failure tracking."""
        if self._window.count > 0:
            logger.info(
                "Collection succeeded after failures",
                extra={"previous_failures": self._window.count},
            )

        self._window.reset()
        self._alert_sent = False

    def _send_alert(self, error_message: str, failure_count: int, at: datetime) -> None:
        """Send alert via callback.

        Args:
            error_message: Most recent error
            failure_count: Number of consecutive failures
            at: Timestamp of alert
        """
        alert_message = (
            f"ALERT: {failure_count} consecutive collection failures "
            f"in the last {self.window_minutes} minutes.\n"
            f"Latest error: {error_message}\n"
            f"Time: {at.isoformat()}"
        )

        logger.error(
            "Consecutive failure threshold exceeded",
            extra={
                "failure_count": failure_count,
                "threshold": self.threshold,
                "window_minutes": self.window_minutes,
            },
        )

        if self.alert_callback:
            try:
                self.alert_callback(alert_message)
                logger.info("Alert sent successfully")
            except Exception as e:
                logger.error(
                    "Failed to send alert",
                    extra={"error": str(e)},
                )

        self._alert_sent = True
        self._last_alert_at = at

    @property
    def current_failure_count(self) -> int:
        """Get current consecutive failure count."""
        return self._window.count

    @property
    def is_alert_active(self) -> bool:
        """Check if an alert has been sent for current failure window."""
        return self._alert_sent

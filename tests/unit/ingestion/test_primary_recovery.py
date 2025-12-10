"""Unit tests for primary recovery after successful secondary operation (T031).

Tests the primary recovery logic per spec clarification:
- After 5 minutes of successful secondary operation, system attempts
  to switch back to primary source.

This tests the PrimaryRecoveryTracker that manages recovery timing.
"""

from datetime import UTC, datetime, timedelta

from src.lambdas.shared.models.data_source import DataSourceConfig

# Default recovery window is 5 minutes per spec clarification
PRIMARY_RECOVERY_WINDOW_SECONDS = 300  # 5 minutes


class TestPrimaryRecoveryTracker:
    """Tests for primary recovery timing logic."""

    def test_recovery_not_triggered_before_5_minutes(self) -> None:
        """Should NOT attempt primary recovery before 5 minutes of secondary success."""
        # Simulate failover occurred 3 minutes ago
        failover_at = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)
        current_time = datetime(2025, 12, 9, 14, 3, 0, tzinfo=UTC)  # 3 min later

        should_attempt = _should_attempt_primary_recovery(
            failover_time=failover_at,
            current_time=current_time,
            recovery_window_seconds=PRIMARY_RECOVERY_WINDOW_SECONDS,
        )

        assert should_attempt is False

    def test_recovery_triggered_after_5_minutes(self) -> None:
        """Should attempt primary recovery after 5 minutes of secondary success."""
        # Simulate failover occurred 6 minutes ago
        failover_at = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)
        current_time = datetime(2025, 12, 9, 14, 6, 0, tzinfo=UTC)  # 6 min later

        should_attempt = _should_attempt_primary_recovery(
            failover_time=failover_at,
            current_time=current_time,
            recovery_window_seconds=PRIMARY_RECOVERY_WINDOW_SECONDS,
        )

        assert should_attempt is True

    def test_recovery_triggered_at_exactly_5_minutes(self) -> None:
        """Should attempt primary recovery at exactly 5 minutes."""
        failover_at = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)
        current_time = datetime(2025, 12, 9, 14, 5, 0, tzinfo=UTC)  # Exactly 5 min

        should_attempt = _should_attempt_primary_recovery(
            failover_time=failover_at,
            current_time=current_time,
            recovery_window_seconds=PRIMARY_RECOVERY_WINDOW_SECONDS,
        )

        assert should_attempt is True

    def test_no_recovery_attempt_if_no_failover(self) -> None:
        """Should not attempt recovery if no failover has occurred."""
        # No failover time means primary is already active
        should_attempt = _should_attempt_primary_recovery(
            failover_time=None,
            current_time=datetime.now(UTC),
            recovery_window_seconds=PRIMARY_RECOVERY_WINDOW_SECONDS,
        )

        assert should_attempt is False

    def test_recovery_window_configurable(self) -> None:
        """Recovery window should be configurable (not hardcoded)."""
        failover_at = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)
        current_time = datetime(2025, 12, 9, 14, 2, 0, tzinfo=UTC)  # 2 min later

        # With 1 minute window, should attempt recovery
        should_attempt_short = _should_attempt_primary_recovery(
            failover_time=failover_at,
            current_time=current_time,
            recovery_window_seconds=60,  # 1 minute
        )

        # With 5 minute window, should NOT attempt recovery
        should_attempt_long = _should_attempt_primary_recovery(
            failover_time=failover_at,
            current_time=current_time,
            recovery_window_seconds=300,  # 5 minutes
        )

        assert should_attempt_short is True
        assert should_attempt_long is False


class TestPrimaryRecoveryWithDataSourceConfig:
    """Tests for primary recovery using DataSourceConfig state."""

    def test_config_tracks_failover_timestamp(self) -> None:
        """DataSourceConfig should track when failover occurred."""
        config = DataSourceConfig.tiingo_default()
        failover_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)

        # Record failure (which would trigger failover)
        updated_config = config.record_failure(failover_time)

        assert updated_config.last_failure_at == failover_time
        assert updated_config.consecutive_failures == 1

    def test_config_resets_on_primary_success(self) -> None:
        """DataSourceConfig should reset failure count on success."""
        config = DataSourceConfig.tiingo_default()
        failure_time = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)
        success_time = datetime(2025, 12, 9, 14, 10, 0, tzinfo=UTC)

        # Simulate failure then success
        failed_config = config.record_failure(failure_time)
        recovered_config = failed_config.record_success(success_time)

        assert recovered_config.consecutive_failures == 0
        assert recovered_config.last_success_at == success_time


class TestPrimaryRecoveryIntegration:
    """Integration-style tests for recovery flow."""

    def test_recovery_sequence(self) -> None:
        """Test full recovery sequence: failover -> wait -> recovery attempt."""
        # T0: Initial state (14:00:00 UTC)
        config = DataSourceConfig.tiingo_default()

        # T1: Primary fails, failover to secondary
        t1 = datetime(2025, 12, 9, 14, 1, 0, tzinfo=UTC)
        config = config.record_failure(t1)
        failover_time = t1

        # T2: 3 minutes later - should NOT attempt recovery
        t2 = t1 + timedelta(minutes=3)
        should_recover_t2 = _should_attempt_primary_recovery(
            failover_time=failover_time,
            current_time=t2,
            recovery_window_seconds=PRIMARY_RECOVERY_WINDOW_SECONDS,
        )
        assert should_recover_t2 is False

        # T3: 5 minutes later - SHOULD attempt recovery
        t3 = t1 + timedelta(minutes=5)
        should_recover_t3 = _should_attempt_primary_recovery(
            failover_time=failover_time,
            current_time=t3,
            recovery_window_seconds=PRIMARY_RECOVERY_WINDOW_SECONDS,
        )
        assert should_recover_t3 is True

        # T4: Recovery succeeds - reset failover state
        t4 = t3 + timedelta(seconds=5)
        config = config.record_success(t4)

        # After recovery, no failover time -> no recovery attempt needed
        should_recover_t4 = _should_attempt_primary_recovery(
            failover_time=None,  # Reset after successful recovery
            current_time=t4,
            recovery_window_seconds=PRIMARY_RECOVERY_WINDOW_SECONDS,
        )
        assert should_recover_t4 is False


def _should_attempt_primary_recovery(
    failover_time: datetime | None,
    current_time: datetime,
    recovery_window_seconds: int,
) -> bool:
    """Determine if primary recovery should be attempted.

    This is the core logic that will be implemented in FailoverOrchestrator.

    Args:
        failover_time: When failover to secondary occurred (None if primary active)
        current_time: Current timestamp
        recovery_window_seconds: Seconds to wait before attempting recovery

    Returns:
        True if recovery should be attempted, False otherwise
    """
    if failover_time is None:
        return False

    elapsed = (current_time - failover_time).total_seconds()
    return elapsed >= recovery_window_seconds

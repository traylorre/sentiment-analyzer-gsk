"""Unit tests for Feature 1233: Quota rate hysteresis.

Tests asymmetric thresholds that prevent oscillation between normal and
reduced-rate mode during DynamoDB flapping. Entry requires 3 consecutive
failures; exit requires 5 consecutive successes.
"""

from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.quota_tracker import (
    QuotaTracker,
    QuotaTrackerManager,
    _enter_reduced_rate_mode,
    _record_dynamo_failure,
    _record_dynamo_success,
    _set_cached_tracker,
    clear_quota_cache,
)


@pytest.fixture(autouse=True)
def _clean_quota_state():
    """Reset quota cache and hysteresis counters between tests."""
    clear_quota_cache()
    yield
    clear_quota_cache()


def _make_mock_table():
    """Create a mock DynamoDB table."""
    table = MagicMock()
    table.get_item.return_value = {}
    table.update_item.return_value = {}
    table.put_item.return_value = {}
    return table


def _preload_cache():
    """Pre-load cache with a default tracker so DynamoDB isn't hit."""
    tracker = QuotaTracker.create_default()
    _set_cached_tracker(tracker)
    return tracker


class TestHysteresisEntry:
    """Tests for entering reduced-rate mode with hysteresis."""

    def test_does_not_enter_reduced_on_single_failure(self):
        """A single DynamoDB failure should NOT trigger reduced-rate mode."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        _record_dynamo_failure()

        assert manager.is_reduced_rate() is False

    def test_does_not_enter_reduced_on_two_failures(self):
        """Two consecutive failures should NOT trigger reduced-rate mode."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        _record_dynamo_failure()
        _record_dynamo_failure()

        assert manager.is_reduced_rate() is False

    def test_enters_reduced_after_3_consecutive_failures(self):
        """Three consecutive failures should trigger reduced-rate mode."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        _record_dynamo_failure()
        _record_dynamo_failure()
        _record_dynamo_failure()

        assert manager.is_reduced_rate() is True


class TestHysteresisExit:
    """Tests for exiting reduced-rate mode with hysteresis."""

    def test_does_not_exit_on_single_success(self):
        """A single success while in reduced mode should NOT exit."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        # Enter reduced mode directly (bypass hysteresis for setup)
        _enter_reduced_rate_mode()
        assert manager.is_reduced_rate() is True

        _record_dynamo_success()

        assert manager.is_reduced_rate() is True

    def test_does_not_exit_on_four_successes(self):
        """Four consecutive successes should NOT exit reduced-rate mode."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        _enter_reduced_rate_mode()

        for _ in range(4):
            _record_dynamo_success()

        assert manager.is_reduced_rate() is True

    def test_exits_reduced_after_5_consecutive_successes(self):
        """Five consecutive successes should exit reduced-rate mode."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        _enter_reduced_rate_mode()
        assert manager.is_reduced_rate() is True

        for _ in range(5):
            _record_dynamo_success()

        assert manager.is_reduced_rate() is False


class TestCounterResets:
    """Tests for counter reset behavior on alternating outcomes."""

    def test_failure_resets_success_counter(self):
        """A failure after 4 successes should reset progress toward exit."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        _enter_reduced_rate_mode()

        # 4 successes (not enough to exit, need 5)
        for _ in range(4):
            _record_dynamo_success()
        assert manager.is_reduced_rate() is True

        # 1 failure resets success counter
        _record_dynamo_failure()

        # 4 more successes (would be 8 total without reset, but counter was reset)
        for _ in range(4):
            _record_dynamo_success()

        # Still in reduced mode because we only have 4 consecutive successes
        assert manager.is_reduced_rate() is True

        # 1 more success (5 consecutive) exits
        _record_dynamo_success()
        assert manager.is_reduced_rate() is False

    def test_success_resets_failure_counter(self):
        """A success after 2 failures should reset progress toward entry."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        # 2 failures (not enough to enter, need 3)
        _record_dynamo_failure()
        _record_dynamo_failure()
        assert manager.is_reduced_rate() is False

        # 1 success resets failure counter
        _record_dynamo_success()

        # 2 more failures (would be 4 total without reset, but counter was reset)
        _record_dynamo_failure()
        _record_dynamo_failure()

        # Still normal mode because we only have 2 consecutive failures
        assert manager.is_reduced_rate() is False

        # 1 more failure (3 consecutive) enters reduced
        _record_dynamo_failure()
        assert manager.is_reduced_rate() is True


class TestRapidFlapping:
    """Tests for stability under rapid alternation."""

    def test_rapid_flapping_stays_stable(self):
        """Alternating success/failure 20 times should never enter reduced mode.

        Because alternation resets the counter each time, we never reach
        3 consecutive failures.
        """
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        for _ in range(20):
            _record_dynamo_success()
            assert manager.is_reduced_rate() is False
            _record_dynamo_failure()
            assert manager.is_reduced_rate() is False

    def test_flapping_after_entering_reduced_stays_reduced(self):
        """Once in reduced mode, alternating should not exit (need 5 consecutive)."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        # Enter reduced mode
        for _ in range(3):
            _record_dynamo_failure()
        assert manager.is_reduced_rate() is True

        # Rapid flapping — should stay reduced
        for _ in range(20):
            _record_dynamo_success()
            assert manager.is_reduced_rate() is True
            _record_dynamo_failure()
            assert manager.is_reduced_rate() is True

"""Unit tests for Feature 1224: Quota tracker atomic DynamoDB counters.

Tests atomic increment, 25% fallback, disconnected alert, and threshold warning.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from freezegun import freeze_time

from src.lambdas.shared.quota_tracker import (
    QuotaTracker,
    QuotaTrackerManager,
    clear_quota_cache,
)


@pytest.fixture(autouse=True)
def _clean_quota_state():
    """Reset quota cache between tests."""
    clear_quota_cache()
    yield
    clear_quota_cache()


def _make_mock_table():
    """Create a mock DynamoDB table."""
    table = MagicMock()
    table.get_item.return_value = {}  # No existing item
    table.update_item.return_value = {}
    table.put_item.return_value = {}
    return table


class TestAtomicIncrement:
    """Tests for _atomic_increment_usage() via record_call()."""

    @freeze_time("2024-01-02 10:00:00")
    def test_record_call_calls_update_item_with_add(self):
        """record_call() uses update_item with ADD expression."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        manager.record_call("tiingo", count=1)

        # update_item should be called for atomic increment
        table.update_item.assert_called()
        call_kwargs = table.update_item.call_args
        update_expr = call_kwargs.kwargs.get(
            "UpdateExpression", call_kwargs[1].get("UpdateExpression", "")
        )
        assert "ADD" in update_expr
        assert "#used" in update_expr

    @freeze_time("2024-01-02 10:00:00")
    def test_record_call_increments_by_count(self):
        """record_call(count=5) increments by 5."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        manager.record_call("finnhub", count=5)

        call_kwargs = table.update_item.call_args
        expr_values = call_kwargs.kwargs.get(
            "ExpressionAttributeValues",
            call_kwargs[1].get("ExpressionAttributeValues", {}),
        )
        assert expr_values[":count"] == 5

    @freeze_time("2024-01-02 10:00:00")
    def test_record_call_uses_correct_service_field(self):
        """Atomic increment targets the correct service field."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        manager.record_call("tiingo")

        call_kwargs = table.update_item.call_args
        expr_names = call_kwargs.kwargs.get(
            "ExpressionAttributeNames",
            call_kwargs[1].get("ExpressionAttributeNames", {}),
        )
        assert expr_names["#used"] == "tiingo_used"

    @freeze_time("2024-01-02 10:00:00")
    def test_record_call_uses_daily_partition_key(self):
        """Atomic increment uses today's date as sort key."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        manager.record_call("tiingo")

        call_kwargs = table.update_item.call_args
        key = call_kwargs.kwargs.get("Key", call_kwargs[1].get("Key", {}))
        assert key == {"PK": "SYSTEM#QUOTA", "SK": "2024-01-02"}


class TestReducedRateFallback:
    """Tests for 25% rate reduction on DynamoDB failure."""

    @freeze_time("2024-01-02 10:00:00")
    def test_enters_reduced_rate_on_dynamodb_failure(self):
        """DynamoDB write failure triggers 25% rate mode."""
        table = _make_mock_table()
        dynamo_error = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "down"}},
            "UpdateItem",
        )
        # Both read and write fail (full DynamoDB outage)
        table.update_item.side_effect = dynamo_error
        table.get_item.side_effect = dynamo_error

        # Pre-load cache so get_tracker doesn't need DynamoDB
        from src.lambdas.shared.quota_tracker import _set_cached_tracker

        tracker = QuotaTracker.create_default()
        _set_cached_tracker(tracker)

        manager = QuotaTrackerManager(table)
        manager.record_call("tiingo")

        assert manager.is_reduced_rate() is True

    @freeze_time("2024-01-02 10:00:00")
    def test_reduced_rate_limits_to_25_percent(self):
        """In reduced-rate mode, can_call allows only 25% of quota."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        # Pre-load cache so get_tracker doesn't hit DynamoDB
        from src.lambdas.shared.quota_tracker import (
            _enter_reduced_rate_mode,
            _set_cached_tracker,
        )

        tracker = QuotaTracker.create_default()
        _set_cached_tracker(tracker)
        _enter_reduced_rate_mode()

        # Tiingo limit is 500, 25% = 125
        # Default tracker has 0 used, so should still allow
        assert manager.can_call("tiingo") is True

        # Simulate high usage
        tracker.tiingo.used = 126  # > 25% of 500 = 125
        tracker.tiingo.remaining = 374
        _set_cached_tracker(tracker)

        assert manager.can_call("tiingo") is False

    @freeze_time("2024-01-02 10:00:00")
    def test_exits_reduced_rate_on_successful_write(self):
        """Successful DynamoDB write exits reduced-rate mode."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        # Pre-load cache and enter reduced-rate mode
        from src.lambdas.shared.quota_tracker import (
            _enter_reduced_rate_mode,
            _set_cached_tracker,
        )

        tracker = QuotaTracker.create_default()
        _set_cached_tracker(tracker)
        _enter_reduced_rate_mode()
        assert manager.is_reduced_rate()

        # Successful record_call exits reduced-rate mode
        manager.record_call("tiingo")
        assert manager.is_reduced_rate() is False


class TestDisconnectedAlert:
    """Tests for QuotaTracker/Disconnected metric emission."""

    @freeze_time("2024-01-02 10:00:00")
    @patch("src.lib.metrics.emit_metric")
    def test_emits_disconnected_metric_on_failure(self, mock_emit):
        """QuotaTracker/Disconnected metric emitted on DynamoDB failure."""
        table = _make_mock_table()
        table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "down"}},
            "UpdateItem",
        )
        manager = QuotaTrackerManager(table)

        manager.record_call("tiingo")

        mock_emit.assert_called_with("QuotaTracker/Disconnected", 1.0)

    @freeze_time("2024-01-02 10:00:00")
    @patch("src.lib.metrics.emit_metric")
    def test_alert_spam_protection(self, mock_emit):
        """Disconnected alert emitted at most once per 5 minutes."""
        table = _make_mock_table()
        table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "down"}},
            "UpdateItem",
        )
        manager = QuotaTrackerManager(table)

        # First call emits alert
        manager.record_call("tiingo")
        assert mock_emit.call_count == 1

        # Second call within 5 minutes — no new alert
        manager.record_call("tiingo")
        assert mock_emit.call_count == 1  # Still 1


class TestThresholdWarning:
    """Tests for 80% quota threshold warning."""

    @freeze_time("2024-01-02 10:00:00")
    @patch("src.lib.metrics.emit_metric")
    def test_emits_threshold_warning_at_80_percent(self, mock_emit):
        """ThresholdWarning metric emitted when usage crosses 80%."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)

        # Pre-load tracker near 80% threshold
        # Tiingo limit=500, 80%=400. Set used=399 so next call crosses.
        tracker = QuotaTracker.create_default()
        tracker.tiingo.used = 399
        tracker.tiingo.remaining = 101

        from src.lambdas.shared.quota_tracker import _set_cached_tracker

        _set_cached_tracker(tracker)

        manager.record_call("tiingo", count=2)

        # Should have emitted threshold warning
        mock_emit.assert_any_call(
            "QuotaTracker/ThresholdWarning",
            1.0,
            dimensions={"Service": "tiingo"},
        )


class TestFromDynamoDbAtomicCounters:
    """Tests for from_dynamodb_item() reading flat atomic counter fields."""

    def test_prefers_flat_atomic_counter(self):
        """Flat tiingo_used field overrides nested tiingo.used."""
        item = {
            "PK": "SYSTEM#QUOTA",
            "SK": "2024-01-02",
            "updated_at": "2024-01-02T10:00:00+00:00",
            "tiingo": {
                "service": "tiingo",
                "period": "month",
                "limit": 500,
                "used": 10,  # Nested value (stale)
                "remaining": 490,
                "reset_at": "2024-01-02T00:00:00+00:00",
            },
            "tiingo_used": 42,  # Flat atomic counter (accurate)
            "finnhub": {
                "service": "finnhub",
                "period": "minute",
                "limit": 60,
                "used": 5,
                "remaining": 55,
                "reset_at": "2024-01-02T00:00:00+00:00",
            },
            "sendgrid": {
                "service": "sendgrid",
                "period": "day",
                "limit": 100,
                "used": 0,
                "remaining": 100,
                "reset_at": "2024-01-02T00:00:00+00:00",
            },
        }

        tracker = QuotaTracker.from_dynamodb_item(item)
        assert tracker.tiingo.used == 42
        assert tracker.tiingo.remaining == 458  # 500 - 42

    def test_falls_back_to_nested_when_no_atomic(self):
        """Without flat counter, uses nested value (backward compat)."""
        item = {
            "PK": "SYSTEM#QUOTA",
            "SK": "2024-01-02",
            "updated_at": "2024-01-02T10:00:00+00:00",
            "tiingo": {
                "service": "tiingo",
                "period": "month",
                "limit": 500,
                "used": 10,
                "remaining": 490,
                "reset_at": "2024-01-02T00:00:00+00:00",
            },
            "finnhub": {
                "service": "finnhub",
                "period": "minute",
                "limit": 60,
                "used": 5,
                "remaining": 55,
                "reset_at": "2024-01-02T00:00:00+00:00",
            },
            "sendgrid": {
                "service": "sendgrid",
                "period": "day",
                "limit": 100,
                "used": 0,
                "remaining": 100,
                "reset_at": "2024-01-02T00:00:00+00:00",
            },
        }

        tracker = QuotaTracker.from_dynamodb_item(item)
        assert tracker.tiingo.used == 10  # Nested value preserved
        assert tracker.tiingo.remaining == 490


class TestConcurrentAccuracy:
    """Tests for cross-instance quota accuracy with concurrent threads."""

    @freeze_time("2024-01-02 10:00:00")
    def test_concurrent_record_calls_all_reach_dynamodb(self):
        """Multiple threads calling record_call each trigger an atomic increment."""
        table = _make_mock_table()
        manager = QuotaTrackerManager(table)
        num_threads = 10
        calls_per_thread = 5

        def worker():
            for _ in range(calls_per_thread):
                manager.record_call("tiingo")

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each record_call triggers one update_item
        assert table.update_item.call_count == num_threads * calls_per_thread

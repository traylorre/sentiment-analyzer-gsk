"""TDD tests for preloading strategy.

Canonical References:
[CS-008] "IndexedDB optimal for large structured datasets with indexes"
         - MDN IndexedDB
         - Client preloads adjacent time ranges and resolutions

FR-007: System MUST preload adjacent resolutions when user selects a resolution
FR-008: System MUST preload adjacent time ranges when user views historical data

These tests MUST FAIL initially per TDD methodology.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.lib.timeseries import Resolution


class TestAdjacentResolutionPreloading:
    """Test FR-007: Preload adjacent resolutions (±1 level).

    When user selects 5m, system should preload 1m and 10m.
    """

    def test_get_adjacent_resolutions_middle(self) -> None:
        """
        Given: User selects 5m resolution (middle of range)
        When: Calculating adjacent resolutions
        Then: Returns [1m, 10m] as adjacent resolutions to preload
        """
        from src.lib.timeseries.preload import get_adjacent_resolutions

        result = get_adjacent_resolutions(Resolution.FIVE_MINUTES)

        assert Resolution.ONE_MINUTE in result
        assert Resolution.TEN_MINUTES in result
        assert len(result) == 2

    def test_get_adjacent_resolutions_lowest(self) -> None:
        """
        Given: User selects 1m resolution (lowest available)
        When: Calculating adjacent resolutions
        Then: Returns [5m] only (no resolution below 1m)
        """
        from src.lib.timeseries.preload import get_adjacent_resolutions

        result = get_adjacent_resolutions(Resolution.ONE_MINUTE)

        assert Resolution.FIVE_MINUTES in result
        assert len(result) == 1

    def test_get_adjacent_resolutions_highest(self) -> None:
        """
        Given: User selects 24h resolution (highest available)
        When: Calculating adjacent resolutions
        Then: Returns [12h] only (no resolution above 24h)
        """
        from src.lib.timeseries.preload import get_adjacent_resolutions

        result = get_adjacent_resolutions(Resolution.TWENTY_FOUR_HOURS)

        assert Resolution.TWELVE_HOURS in result
        assert len(result) == 1

    def test_resolution_order_is_defined(self) -> None:
        """Resolution enum MUST define ordering for preload logic."""
        # Verify all 8 resolutions exist in defined order
        ordered = [
            Resolution.ONE_MINUTE,
            Resolution.FIVE_MINUTES,
            Resolution.TEN_MINUTES,
            Resolution.ONE_HOUR,
            Resolution.THREE_HOURS,
            Resolution.SIX_HOURS,
            Resolution.TWELVE_HOURS,
            Resolution.TWENTY_FOUR_HOURS,
        ]

        from src.lib.timeseries.preload import RESOLUTION_ORDER

        assert RESOLUTION_ORDER == ordered


class TestAdjacentTimeRangePreloading:
    """Test FR-008: Preload adjacent time ranges.

    When user views 1pm-2pm, system preloads 12pm-1pm and 2pm-3pm.
    """

    def test_get_adjacent_time_ranges(self) -> None:
        """
        Given: User is viewing 1pm-2pm (1 hour range)
        When: Calculating adjacent time ranges
        Then: Returns [12pm-1pm, 2pm-3pm] for preloading
        """
        from src.lib.timeseries.preload import get_adjacent_time_ranges

        current_start = datetime(2025, 12, 21, 13, 0, 0, tzinfo=UTC)
        current_end = datetime(2025, 12, 21, 14, 0, 0, tzinfo=UTC)

        result = get_adjacent_time_ranges(current_start, current_end)

        # Should return previous and next ranges
        assert len(result) == 2

        prev_range, next_range = result

        # Previous: 12pm-1pm
        assert prev_range[0] == datetime(2025, 12, 21, 12, 0, 0, tzinfo=UTC)
        assert prev_range[1] == datetime(2025, 12, 21, 13, 0, 0, tzinfo=UTC)

        # Next: 2pm-3pm
        assert next_range[0] == datetime(2025, 12, 21, 14, 0, 0, tzinfo=UTC)
        assert next_range[1] == datetime(2025, 12, 21, 15, 0, 0, tzinfo=UTC)

    def test_adjacent_ranges_match_current_window_size(self) -> None:
        """
        Given: User is viewing a 30-minute window
        When: Calculating adjacent ranges
        Then: Adjacent ranges are also 30 minutes
        """
        from src.lib.timeseries.preload import get_adjacent_time_ranges

        current_start = datetime(2025, 12, 21, 13, 0, 0, tzinfo=UTC)
        current_end = datetime(2025, 12, 21, 13, 30, 0, tzinfo=UTC)

        result = get_adjacent_time_ranges(current_start, current_end)

        prev_range, next_range = result

        # Previous: 12:30pm-1pm (30 min)
        assert prev_range[1] - prev_range[0] == timedelta(minutes=30)

        # Next: 1:30pm-2pm (30 min)
        assert next_range[1] - next_range[0] == timedelta(minutes=30)

    def test_adjacent_ranges_at_day_boundary(self) -> None:
        """
        Given: User is viewing 11pm-12am (crossing midnight)
        When: Calculating adjacent ranges
        Then: Handles date rollover correctly
        """
        from src.lib.timeseries.preload import get_adjacent_time_ranges

        current_start = datetime(2025, 12, 21, 23, 0, 0, tzinfo=UTC)
        current_end = datetime(2025, 12, 22, 0, 0, 0, tzinfo=UTC)

        result = get_adjacent_time_ranges(current_start, current_end)

        prev_range, next_range = result

        # Previous: 10pm-11pm (Dec 21)
        assert prev_range[0].day == 21
        assert prev_range[0].hour == 22

        # Next: 12am-1am (Dec 22)
        assert next_range[0].day == 22
        assert next_range[0].hour == 0


class TestPreloadPriority:
    """Test preload priority ordering for bandwidth efficiency."""

    def test_adjacent_resolutions_ordered_by_proximity(self) -> None:
        """
        Given: User selects 1h resolution
        When: Getting preload priority
        Then: 10m and 3h are prioritized over 5m and 6h
        """
        from src.lib.timeseries.preload import get_preload_priority

        priorities = get_preload_priority(Resolution.ONE_HOUR)

        # First priority: adjacent resolutions (10m, 3h)
        # Second priority: adjacent time ranges
        # Third priority: one-step-away resolutions (5m, 6h)

        assert priorities[0]["type"] == "resolution"
        assert priorities[0]["target"] in [
            Resolution.TEN_MINUTES,
            Resolution.THREE_HOURS,
        ]

    def test_time_range_preload_prioritized_by_scroll_direction(self) -> None:
        """
        Given: User is scrolling backward in time
        When: Getting preload priority
        Then: Previous time range is higher priority than next
        """
        from src.lib.timeseries.preload import get_preload_priority_for_scroll

        current_start = datetime(2025, 12, 21, 13, 0, 0, tzinfo=UTC)
        current_end = datetime(2025, 12, 21, 14, 0, 0, tzinfo=UTC)

        priorities = get_preload_priority_for_scroll(
            current_start,
            current_end,
            scroll_direction="backward",
        )

        # Previous range should be first
        assert priorities[0]["direction"] == "previous"


class TestPreloadManager:
    """Test PreloadManager coordinates preloading operations."""

    @pytest.fixture
    def mock_fetch(self) -> Any:
        """Mock the data fetching function."""
        from unittest.mock import patch

        with patch("src.lib.timeseries.preload.fetch_timeseries_data") as mock:
            mock.return_value = []
            yield mock

    def test_preload_manager_caches_results(self, mock_fetch: Any) -> None:
        """
        Given: PreloadManager with IndexedDB cache
        When: Preloading adjacent data
        Then: Results are stored in cache for instant access
        """
        from src.lib.timeseries.preload import PreloadManager

        manager = PreloadManager(cache=True)

        # This would trigger preloading in background
        manager.preload_adjacent_resolutions(
            ticker="AAPL",
            current_resolution=Resolution.FIVE_MINUTES,
        )

        # Verify data was fetched
        assert mock_fetch.called

        # Verify fetched for both adjacent resolutions
        call_args = [call[1] for call in mock_fetch.call_args_list]
        resolutions_fetched = [args.get("resolution") for args in call_args]
        assert Resolution.ONE_MINUTE in resolutions_fetched
        assert Resolution.TEN_MINUTES in resolutions_fetched

    def test_preload_manager_debounces_requests(self, mock_fetch: Any) -> None:
        """
        Given: Rapid resolution changes
        When: User quickly switches 5m -> 10m -> 1h
        Then: Only preloads for final resolution (debounced)
        """
        from src.lib.timeseries.preload import PreloadManager

        manager = PreloadManager(cache=True, debounce_ms=100)

        # Rapid succession of changes
        manager.preload_adjacent_resolutions("AAPL", Resolution.FIVE_MINUTES)
        manager.preload_adjacent_resolutions("AAPL", Resolution.TEN_MINUTES)
        manager.preload_adjacent_resolutions("AAPL", Resolution.ONE_HOUR)

        # Wait for debounce
        import time

        time.sleep(0.15)

        # Should only have preloaded for ONE_HOUR (the final resolution)
        # 10m and 3h are adjacent to 1h
        final_calls = mock_fetch.call_args_list[-2:]  # Last 2 calls
        resolutions = [call[1].get("resolution") for call in final_calls]
        assert Resolution.TEN_MINUTES in resolutions
        assert Resolution.THREE_HOURS in resolutions

    def test_preload_manager_respects_bandwidth_budget(self, mock_fetch: Any) -> None:
        """
        Given: Limited bandwidth budget with max_concurrent_preloads=2
        When: Preloading adjacent resolutions
        Then: Only preloads up to max_concurrent_preloads items per call

        Note: Each method respects the limit independently.
        For 1h resolution, adjacent resolutions are 10m and 3h (2 items).
        """
        from src.lib.timeseries.preload import PreloadManager

        # Small budget - only 2 concurrent preloads allowed
        manager = PreloadManager(cache=True, max_concurrent_preloads=2)

        # This should preload up to 2 resolutions (10m and 3h for 1h)
        manager.preload_adjacent_resolutions("AAPL", Resolution.ONE_HOUR)

        # Verify only 2 preloads were made (respecting limit)
        assert mock_fetch.call_count <= 2

        # Reset for next test
        mock_fetch.reset_mock()

        # Preload time ranges - should also respect limit
        manager.preload_adjacent_time_ranges(
            "AAPL",
            Resolution.ONE_HOUR,
            datetime(2025, 12, 21, 13, 0, 0, tzinfo=UTC),
            datetime(2025, 12, 21, 14, 0, 0, tzinfo=UTC),
        )

        # Should not exceed 2 concurrent preloads
        assert mock_fetch.call_count <= 2


class TestClientSidePreload:
    """Test client-side preload integration with IndexedDB."""

    def test_preload_checks_cache_before_fetching(self) -> None:
        """
        Given: Adjacent resolution already in IndexedDB cache
        When: Preloading triggered
        Then: Skips fetch for cached data
        """
        # This tests the JavaScript preload logic conceptually
        # In practice, this would be a Playwright E2E test
        from src.lib.timeseries.preload import should_preload

        # Simulate cache already has 1m data
        cache_contents = {"AAPL#1m": True, "AAPL#10m": False}

        result = should_preload(
            ticker="AAPL",
            resolution=Resolution.ONE_MINUTE,
            cache_contents=cache_contents,
        )

        assert result is False  # Already cached, skip

        result = should_preload(
            ticker="AAPL",
            resolution=Resolution.TEN_MINUTES,
            cache_contents=cache_contents,
        )

        assert result is True  # Not cached, should preload

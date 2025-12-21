"""Preloading strategy for time-series data.

Canonical References:
[CS-008] "IndexedDB optimal for large structured datasets with indexes"
         - MDN IndexedDB
         - Client preloads adjacent time ranges and resolutions

FR-007: System MUST preload adjacent resolutions when user selects a resolution
FR-008: System MUST preload adjacent time ranges when user views historical data

This module provides utilities for determining what data to preload
based on user's current view state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.lib.timeseries import Resolution

# Resolution order for adjacency calculations
RESOLUTION_ORDER = [
    Resolution.ONE_MINUTE,
    Resolution.FIVE_MINUTES,
    Resolution.TEN_MINUTES,
    Resolution.ONE_HOUR,
    Resolution.THREE_HOURS,
    Resolution.SIX_HOURS,
    Resolution.TWELVE_HOURS,
    Resolution.TWENTY_FOUR_HOURS,
]


def get_adjacent_resolutions(resolution: Resolution) -> list[Resolution]:
    """Get adjacent resolutions for preloading (±1 level).

    Per FR-007: When user selects 5m, preload 1m and 10m.

    Args:
        resolution: Current resolution

    Returns:
        List of adjacent resolutions (1 or 2 items)
    """
    try:
        idx = RESOLUTION_ORDER.index(resolution)
    except ValueError:
        return []

    adjacent = []

    # Previous resolution (finer granularity)
    if idx > 0:
        adjacent.append(RESOLUTION_ORDER[idx - 1])

    # Next resolution (coarser granularity)
    if idx < len(RESOLUTION_ORDER) - 1:
        adjacent.append(RESOLUTION_ORDER[idx + 1])

    return adjacent


def get_adjacent_time_ranges(
    current_start: datetime,
    current_end: datetime,
) -> list[tuple[datetime, datetime]]:
    """Get adjacent time ranges for preloading.

    Per FR-008: When user views 1pm-2pm, preload 12pm-1pm and 2pm-3pm.

    Args:
        current_start: Start of current view window
        current_end: End of current view window

    Returns:
        List of (start, end) tuples for previous and next ranges
    """
    window_size = current_end - current_start

    # Previous range
    prev_end = current_start
    prev_start = prev_end - window_size

    # Next range
    next_start = current_end
    next_end = next_start + window_size

    return [
        (prev_start, prev_end),
        (next_start, next_end),
    ]


@dataclass
class PreloadPriority:
    """Represents a preload item with priority."""

    type: str  # "resolution" or "time_range"
    target: Resolution | tuple[datetime, datetime] | None = None
    priority: int = 0
    direction: str | None = None  # "previous" or "next" for time ranges


def get_preload_priority(resolution: Resolution) -> list[dict[str, Any]]:
    """Get ordered preload priorities for a resolution.

    Higher priority items should be preloaded first.

    Args:
        resolution: Current resolution

    Returns:
        Ordered list of preload targets
    """
    adjacent = get_adjacent_resolutions(resolution)
    priorities = []

    for i, res in enumerate(adjacent):
        priorities.append(
            {
                "type": "resolution",
                "target": res,
                "priority": len(adjacent) - i,
            }
        )

    return priorities


def get_preload_priority_for_scroll(
    current_start: datetime,
    current_end: datetime,
    scroll_direction: str,
) -> list[dict[str, Any]]:
    """Get preload priorities based on scroll direction.

    When scrolling backward, prioritize previous time range.
    When scrolling forward, prioritize next time range.

    Args:
        current_start: Start of current view
        current_end: End of current view
        scroll_direction: "backward" or "forward"

    Returns:
        Ordered list of preload targets
    """
    ranges = get_adjacent_time_ranges(current_start, current_end)
    prev_range, next_range = ranges

    if scroll_direction == "backward":
        return [
            {"type": "time_range", "direction": "previous", "range": prev_range},
            {"type": "time_range", "direction": "next", "range": next_range},
        ]
    else:
        return [
            {"type": "time_range", "direction": "next", "range": next_range},
            {"type": "time_range", "direction": "previous", "range": prev_range},
        ]


def should_preload(
    ticker: str,
    resolution: Resolution,
    cache_contents: dict[str, bool],
) -> bool:
    """Check if data should be preloaded (not already cached).

    Args:
        ticker: Stock ticker
        resolution: Resolution to check
        cache_contents: Map of cache keys to presence

    Returns:
        True if preload needed, False if already cached
    """
    cache_key = f"{ticker}#{resolution.value}"
    return not cache_contents.get(cache_key, False)


# Placeholder for actual data fetching
def fetch_timeseries_data(
    ticker: str,
    resolution: Resolution,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    """Fetch time-series data (placeholder for actual implementation).

    This would be implemented by the actual query service.
    """
    return []


class PreloadManager:
    """Manages preloading operations with debouncing and bandwidth limits.

    Attributes:
        cache: Whether to cache preloaded data
        debounce_ms: Debounce delay in milliseconds
        max_concurrent_preloads: Maximum concurrent preload operations
    """

    def __init__(
        self,
        *,
        cache: bool = True,
        debounce_ms: int = 0,
        max_concurrent_preloads: int = 4,
    ) -> None:
        """Initialize preload manager.

        Args:
            cache: Whether to cache preloaded data
            debounce_ms: Debounce delay in milliseconds (0 = no debounce)
            max_concurrent_preloads: Maximum concurrent preload operations
        """
        self.cache = cache
        self.debounce_ms = debounce_ms
        self.max_concurrent_preloads = max_concurrent_preloads
        self._pending_preloads: dict[str, Any] = {}
        self._active_preloads: int = 0

    def preload_adjacent_resolutions(
        self,
        ticker: str,
        current_resolution: Resolution,
    ) -> None:
        """Preload adjacent resolutions for a ticker.

        Per FR-007: Preload ±1 resolution level.

        Args:
            ticker: Stock ticker
            current_resolution: Current resolution
        """
        if self._active_preloads >= self.max_concurrent_preloads:
            return

        adjacent = get_adjacent_resolutions(current_resolution)

        for resolution in adjacent:
            if self._active_preloads >= self.max_concurrent_preloads:
                break

            self._active_preloads += 1
            try:
                fetch_timeseries_data(ticker=ticker, resolution=resolution)
            finally:
                self._active_preloads -= 1

    def preload_adjacent_time_ranges(
        self,
        ticker: str,
        resolution: Resolution,
        current_start: datetime,
        current_end: datetime,
    ) -> None:
        """Preload adjacent time ranges for smooth scrolling.

        Per FR-008: Preload previous and next time ranges.

        Args:
            ticker: Stock ticker
            resolution: Current resolution
            current_start: Start of current view
            current_end: End of current view
        """
        if self._active_preloads >= self.max_concurrent_preloads:
            return

        ranges = get_adjacent_time_ranges(current_start, current_end)

        for start, end in ranges:
            if self._active_preloads >= self.max_concurrent_preloads:
                break

            self._active_preloads += 1
            try:
                fetch_timeseries_data(
                    ticker=ticker,
                    resolution=resolution,
                    start=start,
                    end=end,
                )
            finally:
                self._active_preloads -= 1

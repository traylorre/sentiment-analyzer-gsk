"""Resolution-aware caching for Lambda global scope.

Canonical References:
[CS-005] "Initialize SDK clients and database connections outside of the
         function handler so they can be reused across invocations."
         - AWS Lambda Best Practices

[CS-006] "Objects declared outside of the handler method remain initialized
         across invocations, and can be reused during a subsequent invocation
         if AWS Lambda chooses to reuse the Lambda execution environment."
         - Yan Cui, "Understanding AWS Lambda cold starts"

This module provides ResolutionCache for caching time-series data with
resolution-aware TTLs. Cache entries expire based on the resolution's
duration, ensuring stale data is not served.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from src.lib.timeseries.models import Resolution


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""

    hits: int = 0
    misses: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate as hits / total operations."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    def reset(self) -> None:
        """Reset all counters to zero."""
        self.hits = 0
        self.misses = 0


@dataclass
class CacheEntry:
    """A single cache entry with TTL and access tracking."""

    data: dict[str, Any]
    ttl_seconds: int
    created_at: float  # time.time() when entry was created
    last_accessed: float  # time.time() when entry was last accessed

    @property
    def is_expired(self) -> bool:
        """Check if entry has exceeded its TTL."""
        return time.time() - self.created_at > self.ttl_seconds


class ResolutionCache:
    """Resolution-aware cache with LRU eviction.

    Cache entries are keyed by (ticker, resolution) and expire based on
    the resolution's duration. For example, 1-minute resolution data
    expires after 60 seconds.

    Per [CS-005] and [CS-006], this class is designed to be instantiated
    at module level (Lambda global scope) and reused across invocations.

    Attributes:
        max_entries: Maximum number of entries before LRU eviction.
        stats: Cache statistics for monitoring.

    Example:
        # Module level (global scope)
        cache = ResolutionCache()

        def handler(event, context):
            # Cache is warm across invocations
            data = cache.get("AAPL", Resolution.FIVE_MINUTES)
            if data is None:
                data = fetch_from_dynamodb(...)
                cache.set("AAPL", Resolution.FIVE_MINUTES, data=data)
            return data
    """

    def __init__(self, max_entries: int = 256) -> None:
        """Initialize cache with optional max entries.

        Args:
            max_entries: Maximum entries before LRU eviction.
                         Default 256 supports 13 tickers * 8 resolutions
                         with room for multiple time ranges.
        """
        self.max_entries = max_entries
        self.stats = CacheStats()
        # OrderedDict maintains insertion order for LRU tracking
        self._entries: OrderedDict[tuple[str, Resolution], CacheEntry] = OrderedDict()

    def get(self, ticker: str, resolution: Resolution) -> dict[str, Any] | None:
        """Get cached data for ticker/resolution.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            resolution: Time resolution for data.

        Returns:
            Cached data dict if found and not expired, None otherwise.
        """
        key = (ticker, resolution)
        entry = self._entries.get(key)

        if entry is None:
            self.stats.misses += 1
            return None

        if entry.is_expired:
            # Remove expired entry
            del self._entries[key]
            self.stats.misses += 1
            return None

        # Update access time and move to end (most recently used)
        entry.last_accessed = time.time()
        self._entries.move_to_end(key)
        self.stats.hits += 1
        return entry.data

    def set(self, ticker: str, resolution: Resolution, *, data: dict[str, Any]) -> None:
        """Store data in cache with resolution-based TTL.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            resolution: Time resolution (determines TTL).
            data: Data to cache.
        """
        key = (ticker, resolution)

        # Remove existing entry if present
        if key in self._entries:
            del self._entries[key]

        # Evict oldest entry if at capacity
        while len(self._entries) >= self.max_entries:
            # Remove first (oldest) entry
            self._entries.popitem(last=False)

        # TTL equals resolution duration in seconds
        ttl_seconds = resolution.duration_seconds

        now = time.time()
        self._entries[key] = CacheEntry(
            data=data,
            ttl_seconds=ttl_seconds,
            created_at=now,
            last_accessed=now,
        )

    def clear(self) -> None:
        """Remove all entries and reset stats."""
        self._entries.clear()
        self.stats.reset()


# Global cache instance for Lambda warm invocations per [CS-005], [CS-006]
_global_cache: ResolutionCache | None = None


def get_global_cache() -> ResolutionCache:
    """Get or create the global cache instance.

    This function ensures a single cache instance is used across
    all Lambda invocations within the same execution environment.

    Returns:
        The global ResolutionCache instance.
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = ResolutionCache()
    return _global_cache

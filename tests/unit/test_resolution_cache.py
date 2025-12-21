"""Tests for resolution-aware caching in Lambda global scope.

TDD-CACHE-001: Resolution-aware TTL caching
Canonical: [CS-005] "Initialize outside handler for execution reuse"
[CS-006] "Global scope persists across warm invocations"

This test file implements the TDD test design from spec.md lines 592-656.
All tests MUST FAIL initially until ResolutionCache is implemented.
"""

from __future__ import annotations

import pytest
from freezegun import freeze_time

# Import cache utilities from shared lib location
from src.lib.timeseries import CacheStats, Resolution, ResolutionCache


class TestResolutionAwareCache:
    """
    Canonical: [CS-005] "Initialize outside handler for execution reuse"
    [CS-006] "Global scope persists across warm invocations"
    """

    def test_cache_ttl_matches_resolution(self) -> None:
        """Cache TTL MUST equal resolution duration per [CS-006]."""
        cache = ResolutionCache()

        # 1-minute resolution has 60-second TTL
        cache.set("AAPL", Resolution.ONE_MINUTE, data={"test": 1})
        entry = cache._entries[("AAPL", Resolution.ONE_MINUTE)]
        assert entry.ttl_seconds == 60

        # 1-hour resolution has 3600-second TTL
        cache.set("AAPL", Resolution.ONE_HOUR, data={"test": 2})
        entry = cache._entries[("AAPL", Resolution.ONE_HOUR)]
        assert entry.ttl_seconds == 3600

    @freeze_time("2025-12-21T10:35:00Z")
    def test_cache_hit_within_ttl(self) -> None:
        """Cache GET within TTL MUST return cached data."""
        cache = ResolutionCache()
        cache.set("AAPL", Resolution.FIVE_MINUTES, data={"value": 42})

        with freeze_time("2025-12-21T10:37:00Z"):  # 2 minutes later, within 5m TTL
            result = cache.get("AAPL", Resolution.FIVE_MINUTES)
            assert result == {"value": 42}

    @freeze_time("2025-12-21T10:35:00Z")
    def test_cache_miss_after_ttl(self) -> None:
        """Cache GET after TTL MUST return None."""
        cache = ResolutionCache()
        cache.set("AAPL", Resolution.FIVE_MINUTES, data={"value": 42})

        with freeze_time("2025-12-21T10:45:00Z"):  # 10 minutes later, past 5m TTL
            result = cache.get("AAPL", Resolution.FIVE_MINUTES)
            assert result is None

    def test_cache_stats_tracking(self) -> None:
        """Cache MUST track hits and misses for observability."""
        cache = ResolutionCache()
        cache.set("AAPL", Resolution.ONE_MINUTE, data={"test": 1})

        cache.get("AAPL", Resolution.ONE_MINUTE)  # Hit
        cache.get("AAPL", Resolution.ONE_MINUTE)  # Hit
        cache.get("TSLA", Resolution.ONE_MINUTE)  # Miss

        assert cache.stats.hits == 2
        assert cache.stats.misses == 1
        assert cache.stats.hit_rate == pytest.approx(0.667, rel=0.01)

    def test_cache_size_bounded(self) -> None:
        """Cache MUST evict oldest entries when max size reached."""
        cache = ResolutionCache(max_entries=2)

        cache.set("AAPL", Resolution.ONE_MINUTE, data={"a": 1})
        cache.set("TSLA", Resolution.ONE_MINUTE, data={"b": 2})
        cache.set("MSFT", Resolution.ONE_MINUTE, data={"c": 3})  # Should evict AAPL

        assert cache.get("AAPL", Resolution.ONE_MINUTE) is None
        assert cache.get("TSLA", Resolution.ONE_MINUTE) == {"b": 2}
        assert cache.get("MSFT", Resolution.ONE_MINUTE) == {"c": 3}

    def test_cache_key_composition(self) -> None:
        """Cache key MUST be (ticker, resolution) tuple per [CS-002]."""
        cache = ResolutionCache()

        # Same ticker, different resolutions are separate entries
        cache.set("AAPL", Resolution.ONE_MINUTE, data={"res": "1m"})
        cache.set("AAPL", Resolution.FIVE_MINUTES, data={"res": "5m"})

        assert cache.get("AAPL", Resolution.ONE_MINUTE) == {"res": "1m"}
        assert cache.get("AAPL", Resolution.FIVE_MINUTES) == {"res": "5m"}

    def test_cache_overwrite_updates_data(self) -> None:
        """SET with same key MUST overwrite previous data."""
        cache = ResolutionCache()

        cache.set("AAPL", Resolution.ONE_MINUTE, data={"version": 1})
        cache.set("AAPL", Resolution.ONE_MINUTE, data={"version": 2})

        assert cache.get("AAPL", Resolution.ONE_MINUTE) == {"version": 2}

    def test_cache_clear(self) -> None:
        """CLEAR MUST remove all entries and reset stats."""
        cache = ResolutionCache()
        cache.set("AAPL", Resolution.ONE_MINUTE, data={"test": 1})
        cache.set("TSLA", Resolution.ONE_MINUTE, data={"test": 2})
        cache.get("AAPL", Resolution.ONE_MINUTE)  # Hit

        # Before clear, stats should show 1 hit
        assert cache.stats.hits == 1
        assert cache.stats.misses == 0

        cache.clear()

        # After clear, stats should be reset
        assert cache.stats.hits == 0
        assert cache.stats.misses == 0

        # Entries should be removed (these calls will increment misses)
        assert cache.get("AAPL", Resolution.ONE_MINUTE) is None
        assert cache.get("TSLA", Resolution.ONE_MINUTE) is None

        # After failed lookups, misses are counted correctly
        assert cache.stats.misses == 2

    @freeze_time("2025-12-21T10:35:00Z")
    def test_ttl_varies_by_resolution(self) -> None:
        """Different resolutions MUST have different TTLs per [CS-013, CS-014]."""
        cache = ResolutionCache()

        # Set all 8 resolutions
        for res in Resolution:
            cache.set("AAPL", res, data={"res": res.value})

        # Check TTLs match resolution duration
        expected_ttls = {
            Resolution.ONE_MINUTE: 60,
            Resolution.FIVE_MINUTES: 300,
            Resolution.TEN_MINUTES: 600,
            Resolution.ONE_HOUR: 3600,
            Resolution.THREE_HOURS: 10800,
            Resolution.SIX_HOURS: 21600,
            Resolution.TWELVE_HOURS: 43200,
            Resolution.TWENTY_FOUR_HOURS: 86400,
        }

        for res, expected_ttl in expected_ttls.items():
            entry = cache._entries[("AAPL", res)]
            assert entry.ttl_seconds == expected_ttl, f"{res.value} TTL mismatch"

    def test_global_scope_initialization(self) -> None:
        """Cache MUST be initializable outside Lambda handler per [CS-005]."""
        # This test verifies the cache can be created at module level
        # and reused across handler invocations
        global_cache = ResolutionCache()

        # First "invocation"
        global_cache.set("AAPL", Resolution.ONE_MINUTE, data={"invocation": 1})

        # Second "invocation" should see cached data
        result = global_cache.get("AAPL", Resolution.ONE_MINUTE)
        assert result == {"invocation": 1}

        # Stats persist across "invocations"
        assert global_cache.stats.hits == 1


class TestCacheStats:
    """Tests for cache statistics tracking."""

    def test_hit_rate_zero_when_empty(self) -> None:
        """Hit rate MUST be 0 when no operations performed."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_one_when_all_hits(self) -> None:
        """Hit rate MUST be 1.0 when all operations are hits."""
        stats = CacheStats(hits=10, misses=0)
        assert stats.hit_rate == 1.0

    def test_hit_rate_zero_when_all_misses(self) -> None:
        """Hit rate MUST be 0.0 when all operations are misses."""
        stats = CacheStats(hits=0, misses=10)
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self) -> None:
        """Hit rate MUST be hits / (hits + misses)."""
        stats = CacheStats(hits=3, misses=1)
        assert stats.hit_rate == pytest.approx(0.75)

    def test_stats_reset(self) -> None:
        """Reset MUST zero all counters."""
        stats = CacheStats(hits=10, misses=5)
        stats.reset()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0


class TestCacheEviction:
    """Tests for LRU eviction behavior."""

    def test_lru_eviction_order(self) -> None:
        """Eviction MUST remove least recently USED entry, not oldest."""
        cache = ResolutionCache(max_entries=3)

        cache.set("AAPL", Resolution.ONE_MINUTE, data={"ticker": "AAPL"})
        cache.set("TSLA", Resolution.ONE_MINUTE, data={"ticker": "TSLA"})
        cache.set("MSFT", Resolution.ONE_MINUTE, data={"ticker": "MSFT"})

        # Access AAPL to make it recently used
        cache.get("AAPL", Resolution.ONE_MINUTE)

        # Add new entry - should evict TSLA (least recently used)
        cache.set("GOOG", Resolution.ONE_MINUTE, data={"ticker": "GOOG"})

        assert cache.get("AAPL", Resolution.ONE_MINUTE) is not None
        assert cache.get("TSLA", Resolution.ONE_MINUTE) is None  # Evicted
        assert cache.get("MSFT", Resolution.ONE_MINUTE) is not None
        assert cache.get("GOOG", Resolution.ONE_MINUTE) is not None

    def test_eviction_triggers_at_max_entries(self) -> None:
        """Eviction MUST trigger when max_entries is reached."""
        cache = ResolutionCache(max_entries=5)

        for i in range(6):
            cache.set(f"TICKER{i}", Resolution.ONE_MINUTE, data={"i": i})

        # First entry should be evicted
        assert cache.get("TICKER0", Resolution.ONE_MINUTE) is None
        # Last 5 entries should remain
        for i in range(1, 6):
            assert cache.get(f"TICKER{i}", Resolution.ONE_MINUTE) is not None

    def test_default_max_entries(self) -> None:
        """Default max_entries MUST be reasonable for Lambda memory."""
        cache = ResolutionCache()
        # 13 tickers * 8 resolutions = 104 entries, default should handle this
        assert cache.max_entries >= 104

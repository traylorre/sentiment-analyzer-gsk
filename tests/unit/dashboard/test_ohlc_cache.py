"""Unit tests for OHLC response cache (Feature 1076).

Tests the module-level caching infrastructure that prevents 429 rate limit
errors when users rapidly switch resolution buckets.
"""

import time
from datetime import date
from unittest.mock import patch

import pytest

from src.lambdas.dashboard.ohlc import (
    OHLC_CACHE_DEFAULT_TTL,
    OHLC_CACHE_MAX_ENTRIES,
    OHLC_CACHE_TTLS,
    _get_cached_ohlc,
    _get_ohlc_cache_key,
    _set_cached_ohlc,
    get_ohlc_cache_stats,
    invalidate_ohlc_cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before and after each test."""
    global _ohlc_cache, _ohlc_cache_stats
    # Import fresh to reset module state
    import src.lambdas.dashboard.ohlc as ohlc_module

    ohlc_module._ohlc_cache.clear()
    ohlc_module._ohlc_cache_stats["hits"] = 0
    ohlc_module._ohlc_cache_stats["misses"] = 0
    ohlc_module._ohlc_cache_stats["evictions"] = 0
    yield
    ohlc_module._ohlc_cache.clear()
    ohlc_module._ohlc_cache_stats["hits"] = 0
    ohlc_module._ohlc_cache_stats["misses"] = 0
    ohlc_module._ohlc_cache_stats["evictions"] = 0


class TestOHLCCacheKey:
    """Tests for cache key generation.

    CACHE-001: Cache keys now include end_date for all ranges (not just custom)
    to prevent stale data when the same range is requested on different days.
    Previously, predefined ranges used only the range name, causing the same
    key on different days.
    """

    def test_generates_deterministic_key_predefined_range(self):
        """Cache key should be deterministic for same predefined range and date."""
        end = date(2024, 12, 23)
        start = date(2024, 11, 23)
        key1 = _get_ohlc_cache_key("AAPL", "D", "1M", start, end)
        key2 = _get_ohlc_cache_key("AAPL", "D", "1M", start, end)
        assert key1 == key2

    def test_generates_deterministic_key_custom_range(self):
        """Cache key should be deterministic for same custom date range."""
        key1 = _get_ohlc_cache_key(
            "AAPL", "D", "custom", date(2024, 1, 1), date(2024, 1, 31)
        )
        key2 = _get_ohlc_cache_key(
            "AAPL", "D", "custom", date(2024, 1, 1), date(2024, 1, 31)
        )
        assert key1 == key2

    def test_normalizes_ticker_to_uppercase(self):
        """Cache key should normalize ticker to uppercase."""
        end = date(2024, 12, 23)
        start = date(2024, 11, 23)
        key1 = _get_ohlc_cache_key("aapl", "D", "1M", start, end)
        key2 = _get_ohlc_cache_key("AAPL", "D", "1M", start, end)
        assert key1 == key2

    def test_different_resolutions_different_keys(self):
        """Different resolutions should produce different cache keys."""
        end = date(2024, 12, 23)
        start = date(2024, 11, 23)
        key_daily = _get_ohlc_cache_key("AAPL", "D", "1M", start, end)
        key_5min = _get_ohlc_cache_key("AAPL", "5", "1M", start, end)
        assert key_daily != key_5min

    def test_different_time_ranges_different_keys(self):
        """Different time ranges should produce different cache keys."""
        end = date(2024, 12, 23)
        key_1m = _get_ohlc_cache_key("AAPL", "D", "1M", date(2024, 11, 23), end)
        key_3m = _get_ohlc_cache_key("AAPL", "D", "3M", date(2024, 9, 23), end)
        assert key_1m != key_3m

    def test_different_custom_date_ranges_different_keys(self):
        """Different custom date ranges should produce different cache keys."""
        key1 = _get_ohlc_cache_key(
            "AAPL", "D", "custom", date(2024, 1, 1), date(2024, 1, 31)
        )
        key2 = _get_ohlc_cache_key(
            "AAPL", "D", "custom", date(2024, 2, 1), date(2024, 2, 28)
        )
        assert key1 != key2

    def test_key_format_predefined_range(self):
        """Cache key for predefined range should include end_date (CACHE-001)."""
        end = date(2024, 12, 23)
        start = date(2024, 11, 23)
        key = _get_ohlc_cache_key("MSFT", "15", "1M", start, end)
        # New format includes end_date for day-anchoring
        assert key == "ohlc:MSFT:15:1M:2024-12-23"

    def test_key_format_custom_range(self):
        """Cache key for custom range should include dates."""
        key = _get_ohlc_cache_key(
            "MSFT", "15", "custom", date(2024, 3, 15), date(2024, 3, 20)
        )
        assert key == "ohlc:MSFT:15:custom:2024-03-15:2024-03-20"

    def test_different_days_different_keys(self):
        """CACHE-001: Same range on different days should produce different keys."""
        # Monday request
        key_monday = _get_ohlc_cache_key(
            "AAPL", "D", "1W", date(2024, 12, 16), date(2024, 12, 23)
        )
        # Friday request (different end_date)
        key_friday = _get_ohlc_cache_key(
            "AAPL", "D", "1W", date(2024, 12, 20), date(2024, 12, 27)
        )
        # Keys should differ because end_date is included
        assert key_monday != key_friday
        # Verify the end_date is in the key
        assert "2024-12-23" in key_monday
        assert "2024-12-27" in key_friday


class TestOHLCCacheGetSet:
    """Tests for cache get/set operations."""

    def test_cache_miss_returns_none(self):
        """Cache miss should return None and increment misses."""
        import src.lambdas.dashboard.ohlc as ohlc_module

        result = _get_cached_ohlc("ohlc:AAPL:D:2024-01-01:2024-01-31", "D")
        assert result is None
        assert ohlc_module._ohlc_cache_stats["misses"] == 1

    def test_cache_hit_returns_data(self):
        """Cache hit should return cached data and increment hits."""
        import src.lambdas.dashboard.ohlc as ohlc_module

        test_data = {"ticker": "AAPL", "candles": [], "count": 0}
        cache_key = "ohlc:AAPL:D:2024-01-01:2024-01-31"

        _set_cached_ohlc(cache_key, test_data)
        result = _get_cached_ohlc(cache_key, "D")

        assert result == test_data
        assert ohlc_module._ohlc_cache_stats["hits"] == 1

    def test_cache_expiry(self):
        """Expired cache entries should return None."""
        import src.lambdas.dashboard.ohlc as ohlc_module

        test_data = {"ticker": "AAPL", "candles": []}
        cache_key = "ohlc:AAPL:1:2024-01-01:2024-01-31"

        _set_cached_ohlc(cache_key, test_data)

        # Mock time to simulate expiry (1-minute TTL is 300s)
        with patch("src.lambdas.dashboard.ohlc.time.time") as mock_time:
            # First call at T=0, second call at T=301 (past 5 min TTL)
            ohlc_module._ohlc_cache[cache_key] = (1000.0, test_data)
            mock_time.return_value = 1000.0 + 301  # Past 1-minute TTL (300s)

            result = _get_cached_ohlc(cache_key, "1")
            assert result is None
            assert cache_key not in ohlc_module._ohlc_cache


class TestOHLCCacheTTLs:
    """Tests for resolution-specific TTLs."""

    def test_ttl_1min_resolution(self):
        """1-minute resolution should have 5 minute TTL."""
        assert OHLC_CACHE_TTLS["1"] == 300

    def test_ttl_5min_resolution(self):
        """5-minute resolution should have 15 minute TTL."""
        assert OHLC_CACHE_TTLS["5"] == 900

    def test_ttl_15min_resolution(self):
        """15-minute resolution should have 15 minute TTL."""
        assert OHLC_CACHE_TTLS["15"] == 900

    def test_ttl_30min_resolution(self):
        """30-minute resolution should have 15 minute TTL."""
        assert OHLC_CACHE_TTLS["30"] == 900

    def test_ttl_hourly_resolution(self):
        """Hourly resolution should have 30 minute TTL."""
        assert OHLC_CACHE_TTLS["60"] == 1800

    def test_ttl_daily_resolution(self):
        """Daily resolution should have 1 hour TTL."""
        assert OHLC_CACHE_TTLS["D"] == 3600

    def test_default_ttl(self):
        """Default TTL should be 5 minutes."""
        assert OHLC_CACHE_DEFAULT_TTL == 300


class TestOHLCCacheEviction:
    """Tests for LRU eviction when cache is full."""

    def test_eviction_when_full(self):
        """Oldest entry should be evicted when cache is full."""
        import src.lambdas.dashboard.ohlc as ohlc_module

        # Fill cache with MAX_ENTRIES items
        with patch.object(ohlc_module, "OHLC_CACHE_MAX_ENTRIES", 3):
            # Add 3 entries
            for i in range(3):
                key = f"ohlc:AAPL:{i}:2024-01-01:2024-01-31"
                ohlc_module._ohlc_cache[key] = (1000.0 + i, {"index": i})

            # Add 4th entry - should evict oldest (index 0)
            ohlc_module._set_cached_ohlc(
                "ohlc:AAPL:new:2024-01-01:2024-01-31", {"index": "new"}
            )

            # Check oldest was evicted
            assert "ohlc:AAPL:0:2024-01-01:2024-01-31" not in ohlc_module._ohlc_cache
            # Check new entry exists
            assert "ohlc:AAPL:new:2024-01-01:2024-01-31" in ohlc_module._ohlc_cache
            # Check eviction counter
            assert ohlc_module._ohlc_cache_stats["evictions"] == 1

    def test_max_entries_default(self):
        """Default max entries should be 256."""
        assert OHLC_CACHE_MAX_ENTRIES == 256


class TestOHLCCacheStats:
    """Tests for cache statistics."""

    def test_stats_returns_copy(self):
        """get_ohlc_cache_stats should return a copy, not the original."""
        import src.lambdas.dashboard.ohlc as ohlc_module

        stats = get_ohlc_cache_stats()
        stats["hits"] = 999  # Modify the copy

        # Original should be unchanged
        assert ohlc_module._ohlc_cache_stats["hits"] == 0

    def test_stats_tracks_hits_misses_evictions(self):
        """Stats should track hits, misses, and evictions."""
        stats = get_ohlc_cache_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "evictions" in stats


class TestOHLCCacheInvalidation:
    """Tests for cache invalidation."""

    def test_invalidate_all(self):
        """invalidate_ohlc_cache() with no args should clear entire cache."""
        import src.lambdas.dashboard.ohlc as ohlc_module

        # Add some entries
        ohlc_module._ohlc_cache["ohlc:AAPL:D:2024-01-01:2024-01-31"] = (
            time.time(),
            {"ticker": "AAPL"},
        )
        ohlc_module._ohlc_cache["ohlc:MSFT:D:2024-01-01:2024-01-31"] = (
            time.time(),
            {"ticker": "MSFT"},
        )

        count = invalidate_ohlc_cache()

        assert count == 2
        assert len(ohlc_module._ohlc_cache) == 0

    def test_invalidate_by_ticker(self):
        """invalidate_ohlc_cache(ticker) should only clear that ticker's entries."""
        import src.lambdas.dashboard.ohlc as ohlc_module

        # Add entries for different tickers
        ohlc_module._ohlc_cache["ohlc:AAPL:D:2024-01-01:2024-01-31"] = (
            time.time(),
            {"ticker": "AAPL"},
        )
        ohlc_module._ohlc_cache["ohlc:AAPL:5:2024-01-01:2024-01-31"] = (
            time.time(),
            {"ticker": "AAPL"},
        )
        ohlc_module._ohlc_cache["ohlc:MSFT:D:2024-01-01:2024-01-31"] = (
            time.time(),
            {"ticker": "MSFT"},
        )

        count = invalidate_ohlc_cache("AAPL")

        assert count == 2
        assert "ohlc:AAPL:D:2024-01-01:2024-01-31" not in ohlc_module._ohlc_cache
        assert "ohlc:AAPL:5:2024-01-01:2024-01-31" not in ohlc_module._ohlc_cache
        assert "ohlc:MSFT:D:2024-01-01:2024-01-31" in ohlc_module._ohlc_cache

    def test_invalidate_ticker_case_insensitive(self):
        """Ticker invalidation should be case-insensitive."""
        import src.lambdas.dashboard.ohlc as ohlc_module

        ohlc_module._ohlc_cache["ohlc:AAPL:D:2024-01-01:2024-01-31"] = (
            time.time(),
            {"ticker": "AAPL"},
        )

        count = invalidate_ohlc_cache("aapl")  # lowercase

        assert count == 1
        assert len(ohlc_module._ohlc_cache) == 0

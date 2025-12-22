"""Unit tests for cross-user cache sharing (T049).

Tests for shared caching across users viewing the same ticker+resolution.
The global cache instance should be shared across all connections, allowing
one user's query to warm the cache for subsequent users.

Canonical: [CS-006] "Shared caching across users for same ticker+resolution"
Goal: 80% cache hit rate for shared ticker data (SC-008)
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.lib.timeseries import Resolution, ResolutionCache, get_global_cache


class TestSharedCacheBasics:
    """Tests for basic shared cache functionality."""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache instance."""
        return ResolutionCache(max_entries=10)

    def test_cache_hit_after_first_user_query(self, cache):
        """Second user should get cache hit after first user populates cache."""
        ticker = "AAPL"
        resolution = Resolution.FIVE_MINUTES
        data = {"buckets": [{"timestamp": "2025-12-22T10:00:00Z", "close": 0.5}]}

        # First user miss
        result1 = cache.get(ticker, resolution)
        assert result1 is None
        assert cache.stats.misses == 1
        assert cache.stats.hits == 0

        # First user populates cache
        cache.set(ticker, resolution, data=data)

        # Second user gets cache hit
        result2 = cache.get(ticker, resolution)
        assert result2 == data
        assert cache.stats.hits == 1

    def test_different_resolutions_are_independent(self, cache):
        """Same ticker at different resolutions should be cached separately."""
        ticker = "AAPL"
        data_5m = {"resolution": "5m", "buckets": []}
        data_1h = {"resolution": "1h", "buckets": []}

        cache.set(ticker, Resolution.FIVE_MINUTES, data=data_5m)
        cache.set(ticker, Resolution.ONE_HOUR, data=data_1h)

        assert cache.get(ticker, Resolution.FIVE_MINUTES) == data_5m
        assert cache.get(ticker, Resolution.ONE_HOUR) == data_1h

    def test_different_tickers_are_independent(self, cache):
        """Different tickers at same resolution should be cached separately."""
        resolution = Resolution.FIVE_MINUTES
        data_aapl = {"ticker": "AAPL", "buckets": []}
        data_msft = {"ticker": "MSFT", "buckets": []}

        cache.set("AAPL", resolution, data=data_aapl)
        cache.set("MSFT", resolution, data=data_msft)

        assert cache.get("AAPL", resolution) == data_aapl
        assert cache.get("MSFT", resolution) == data_msft


class TestCacheExpiration:
    """Tests for resolution-based TTL expiration."""

    def test_one_minute_resolution_expires_after_60s(self):
        """1-minute resolution should expire after 60 seconds."""
        cache = ResolutionCache()
        data = {"buckets": []}

        cache.set("AAPL", Resolution.ONE_MINUTE, data=data)

        # Entry exists initially
        assert cache.get("AAPL", Resolution.ONE_MINUTE) is not None

        # Manually expire by adjusting created_at
        entry = cache._entries[("AAPL", Resolution.ONE_MINUTE)]
        entry.created_at = time.time() - 61  # 61 seconds ago

        # Now should be expired
        assert cache.get("AAPL", Resolution.ONE_MINUTE) is None

    def test_one_hour_resolution_expires_after_3600s(self):
        """1-hour resolution should expire after 3600 seconds."""
        cache = ResolutionCache()
        data = {"buckets": []}

        cache.set("AAPL", Resolution.ONE_HOUR, data=data)

        # Entry exists initially
        assert cache.get("AAPL", Resolution.ONE_HOUR) is not None

        # Manually expire by adjusting created_at
        entry = cache._entries[("AAPL", Resolution.ONE_HOUR)]
        entry.created_at = time.time() - 3601  # 1 hour and 1 second ago

        # Now should be expired
        assert cache.get("AAPL", Resolution.ONE_HOUR) is None


class TestCacheLRUEviction:
    """Tests for LRU eviction when cache is at capacity."""

    def test_lru_eviction_removes_oldest_entry(self):
        """Oldest entry should be evicted when cache is full."""
        cache = ResolutionCache(max_entries=3)

        # Fill cache with 3 entries
        cache.set("AAPL", Resolution.ONE_MINUTE, data={"ticker": "AAPL"})
        cache.set("MSFT", Resolution.ONE_MINUTE, data={"ticker": "MSFT"})
        cache.set("GOOGL", Resolution.ONE_MINUTE, data={"ticker": "GOOGL"})

        # Add 4th entry - AAPL should be evicted (oldest)
        cache.set("AMZN", Resolution.ONE_MINUTE, data={"ticker": "AMZN"})

        assert cache.get("AAPL", Resolution.ONE_MINUTE) is None
        assert cache.get("MSFT", Resolution.ONE_MINUTE) is not None
        assert cache.get("GOOGL", Resolution.ONE_MINUTE) is not None
        assert cache.get("AMZN", Resolution.ONE_MINUTE) is not None

    def test_access_updates_lru_order(self):
        """Accessing an entry should move it to end (most recently used)."""
        cache = ResolutionCache(max_entries=3)

        # Fill cache
        cache.set("AAPL", Resolution.ONE_MINUTE, data={"ticker": "AAPL"})
        cache.set("MSFT", Resolution.ONE_MINUTE, data={"ticker": "MSFT"})
        cache.set("GOOGL", Resolution.ONE_MINUTE, data={"ticker": "GOOGL"})

        # Access AAPL (oldest) to move it to end
        cache.get("AAPL", Resolution.ONE_MINUTE)

        # Add new entry - MSFT should be evicted (now oldest)
        cache.set("AMZN", Resolution.ONE_MINUTE, data={"ticker": "AMZN"})

        assert cache.get("AAPL", Resolution.ONE_MINUTE) is not None  # Was accessed
        assert cache.get("MSFT", Resolution.ONE_MINUTE) is None  # Was evicted
        assert cache.get("GOOGL", Resolution.ONE_MINUTE) is not None
        assert cache.get("AMZN", Resolution.ONE_MINUTE) is not None


class TestCacheStatistics:
    """Tests for cache statistics tracking."""

    def test_hit_rate_calculation(self):
        """Hit rate should be calculated correctly."""
        cache = ResolutionCache()
        cache.set("AAPL", Resolution.ONE_MINUTE, data={})

        # 1 miss, then 3 hits
        cache.get("MSFT", Resolution.ONE_MINUTE)  # miss
        cache.get("AAPL", Resolution.ONE_MINUTE)  # hit
        cache.get("AAPL", Resolution.ONE_MINUTE)  # hit
        cache.get("AAPL", Resolution.ONE_MINUTE)  # hit

        assert cache.stats.hits == 3
        assert cache.stats.misses == 1
        assert cache.stats.hit_rate == 0.75

    def test_eighty_percent_hit_rate_achievable(self):
        """Should be possible to achieve 80% cache hit rate (SC-008)."""
        cache = ResolutionCache()

        # Populate cache with 5 tickers
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
        for ticker in tickers:
            cache.set(ticker, Resolution.FIVE_MINUTES, data={"ticker": ticker})

        # Simulate 100 requests (80 hits, 20 misses)
        for i in range(80):
            cache.get(tickers[i % 5], Resolution.FIVE_MINUTES)  # hits

        for i in range(20):
            cache.get(f"NOSUCH{i}", Resolution.FIVE_MINUTES)  # misses

        assert cache.stats.hit_rate >= 0.80, f"Hit rate {cache.stats.hit_rate} < 0.80"


class TestGlobalCacheInstance:
    """Tests for global cache singleton behavior."""

    def test_get_global_cache_returns_same_instance(self):
        """get_global_cache should return the same instance on repeated calls."""
        # Need to reset the global cache first
        import src.lib.timeseries.cache as cache_module

        cache_module._global_cache = None

        cache1 = get_global_cache()
        cache2 = get_global_cache()

        assert cache1 is cache2

    def test_global_cache_shared_across_users(self):
        """Global cache should share data across simulated users."""
        import src.lib.timeseries.cache as cache_module

        cache_module._global_cache = None
        cache = get_global_cache()

        # User 1 populates cache
        cache.set("AAPL", Resolution.FIVE_MINUTES, data={"user": 1})

        # User 2 gets same data (simulated by getting from same cache)
        result = cache.get("AAPL", Resolution.FIVE_MINUTES)
        assert result == {"user": 1}
        assert cache.stats.hits == 1


class TestCacheWithQueryService:
    """Integration tests for cache with TimeseriesQueryService."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        return MagicMock()

    def test_query_service_uses_global_cache(self, mock_table):
        """TimeseriesQueryService should use global cache for warm starts."""
        import src.lib.timeseries.cache as cache_module
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        # Reset global cache
        cache_module._global_cache = None

        with patch("src.lambdas.dashboard.timeseries.boto3") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_boto3.resource.return_value = mock_dynamodb
            mock_dynamodb.Table.return_value = mock_table

            # First query (cache miss)
            mock_table.query.return_value = {
                "Items": [
                    {
                        "pk": "AAPL#5m",
                        "sk": "2025-12-22T10:00:00Z",
                        "ticker": "AAPL",
                        "resolution": "5m",
                        "open": 0.5,
                        "high": 0.6,
                        "low": 0.4,
                        "close": 0.5,
                        "count": 10,
                        "sum": 5.0,
                        "label_counts": {},
                        "sources": [],
                        "is_partial": False,
                    }
                ]
            }

            service = TimeseriesQueryService(
                table_name="test-timeseries",
                use_cache=True,
            )
            service._table = mock_table

            # First query should miss
            result1 = service.query("AAPL", Resolution.FIVE_MINUTES)
            assert result1.cache_hit is False

            # Second query should hit
            result2 = service.query("AAPL", Resolution.FIVE_MINUTES)
            assert result2.cache_hit is True

            # DynamoDB should only be called once
            assert mock_table.query.call_count == 1

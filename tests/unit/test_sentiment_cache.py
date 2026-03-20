"""T004: Unit tests for sentiment history in-memory cache.

Tests get_cached_history, cache_history, clear_cache, and CacheStats
integration for the 2-tier sentiment cache (Feature 1227).
"""

import time
from unittest.mock import patch

import pytest

from src.lambdas.shared.cache.sentiment_cache import (
    cache_history,
    clear_cache,
    get_cached_history,
    get_sentiment_cache_stats,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_cache():
    """Clear cache and reset stats before each test."""
    clear_cache()
    stats = get_sentiment_cache_stats()
    stats.flush()  # reset hit/miss counters
    yield
    clear_cache()


TICKER = "AAPL"
SOURCE = "tiingo"
START = "2024-11-01"
END = "2024-11-30"
RESPONSE_DATA = {
    "ticker": "AAPL",
    "source": "tiingo",
    "history": [{"date": "2024-11-15", "score": 0.42}],
    "count": 1,
}


# ---------------------------------------------------------------------------
# Cache miss / hit
# ---------------------------------------------------------------------------


class TestCacheMissAndHit:
    """Basic cache lifecycle: miss on empty, hit after store."""

    def test_cache_miss_returns_none(self):
        """get_cached_history returns None when nothing has been cached."""
        result = get_cached_history(TICKER, SOURCE, START, END)
        assert result is None

    def test_cache_hit_returns_stored_data(self):
        """After cache_history, get_cached_history returns the stored dict."""
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)

        result = get_cached_history(TICKER, SOURCE, START, END)
        assert result == RESPONSE_DATA

    def test_different_keys_are_independent(self):
        """Caching under one key does not affect a different key."""
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)

        # Different ticker -> miss
        result = get_cached_history("GOOG", SOURCE, START, END)
        assert result is None

        # Different source -> miss
        result = get_cached_history(TICKER, "finnhub", START, END)
        assert result is None

    def test_overwrite_replaces_data(self):
        """Storing a second time under the same key replaces the value."""
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)

        new_data = {**RESPONSE_DATA, "count": 99}
        cache_history(TICKER, SOURCE, START, END, new_data)

        result = get_cached_history(TICKER, SOURCE, START, END)
        assert result is not None
        assert result["count"] == 99


# ---------------------------------------------------------------------------
# TTL expiration
# ---------------------------------------------------------------------------


class TestTTLExpiration:
    """Cache entries expire after their jittered TTL elapses."""

    def test_expired_entry_returns_none(self):
        """After time exceeds TTL, get_cached_history returns None."""
        # Patch jittered_ttl to return a very short TTL (0.05s)
        with patch(
            "src.lambdas.shared.cache.sentiment_cache.jittered_ttl",
            return_value=0.05,
        ):
            cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)

        # Advance past TTL by patching time.monotonic
        original_monotonic = time.monotonic

        with patch("src.lambdas.shared.cache.sentiment_cache.time") as mock_time:
            # First call is for the elapsed calc; return original + 1 second
            mock_time.monotonic.return_value = original_monotonic() + 1.0
            result = get_cached_history(TICKER, SOURCE, START, END)

        assert result is None

    def test_not_expired_entry_returns_data(self):
        """Before TTL elapses, get_cached_history returns cached data."""
        with patch(
            "src.lambdas.shared.cache.sentiment_cache.jittered_ttl",
            return_value=600.0,  # 10 minutes
        ):
            cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)

        # Don't advance time - entry should still be valid
        result = get_cached_history(TICKER, SOURCE, START, END)
        assert result == RESPONSE_DATA


# ---------------------------------------------------------------------------
# CacheStats tracking
# ---------------------------------------------------------------------------


class TestCacheStats:
    """CacheStats records hits and misses correctly."""

    def test_miss_increments_misses(self):
        """A cache miss increments the misses counter."""
        stats = get_sentiment_cache_stats()
        assert stats.misses == 0

        get_cached_history(TICKER, SOURCE, START, END)

        assert stats.misses == 1

    def test_hit_increments_hits(self):
        """A cache hit increments the hits counter."""
        stats = get_sentiment_cache_stats()
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)

        assert stats.hits == 0
        get_cached_history(TICKER, SOURCE, START, END)
        assert stats.hits == 1

    def test_multiple_misses_accumulate(self):
        """Multiple cache misses accumulate in the counter."""
        stats = get_sentiment_cache_stats()

        get_cached_history(TICKER, SOURCE, START, END)
        get_cached_history("GOOG", SOURCE, START, END)
        get_cached_history("MSFT", SOURCE, START, END)

        assert stats.misses == 3

    def test_hit_rate_calculation(self):
        """hit_rate returns correct ratio of hits to total accesses."""
        stats = get_sentiment_cache_stats()

        # 1 miss (cache empty) + store + 2 hits
        get_cached_history(TICKER, SOURCE, START, END)  # miss
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)
        get_cached_history(TICKER, SOURCE, START, END)  # hit
        get_cached_history(TICKER, SOURCE, START, END)  # hit

        # 2 hits / 3 total
        assert stats.hit_rate == pytest.approx(2 / 3, abs=0.01)


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------


class TestClearCache:
    """clear_cache empties all cached entries."""

    def test_clear_removes_all_entries(self):
        """After clear_cache, previously cached entries return None."""
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)
        cache_history("GOOG", SOURCE, START, END, {"count": 2})

        clear_cache()

        assert get_cached_history(TICKER, SOURCE, START, END) is None
        assert get_cached_history("GOOG", SOURCE, START, END) is None

    def test_clear_is_idempotent(self):
        """Calling clear_cache on an already-empty cache does not error."""
        clear_cache()
        clear_cache()  # should not raise

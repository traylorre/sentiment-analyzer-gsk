"""T017: Unit tests for CacheStats integration with sentiment cache.

Verifies that the sentiment cache correctly wires into the CacheStats
observability system: misses increment CacheStats.misses, hits increment
CacheStats.hits, and the stats instance is named 'sentiment_history'.
"""

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


@pytest.fixture(autouse=True)
def _reset_cache_and_stats():
    """Clear cache and flush stats before each test for isolation."""
    clear_cache()
    stats = get_sentiment_cache_stats()
    stats.flush()  # resets all counters to zero
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# Stats instance identity
# ---------------------------------------------------------------------------


class TestStatsInstanceNaming:
    """The CacheStats instance is named 'sentiment_history'."""

    def test_stats_name_is_sentiment_history(self):
        """get_sentiment_cache_stats() returns an instance named 'sentiment_history'."""
        stats = get_sentiment_cache_stats()
        assert stats.name == "sentiment_history"

    def test_stats_is_singleton(self):
        """Multiple calls return the same CacheStats object."""
        stats_a = get_sentiment_cache_stats()
        stats_b = get_sentiment_cache_stats()
        assert stats_a is stats_b


# ---------------------------------------------------------------------------
# Miss tracking
# ---------------------------------------------------------------------------


class TestCacheMissObservability:
    """After a cache miss, CacheStats.misses increments."""

    def test_single_miss_increments(self):
        """One cache miss increments misses from 0 to 1."""
        stats = get_sentiment_cache_stats()
        assert stats.misses == 0

        get_cached_history(TICKER, SOURCE, START, END)

        assert stats.misses == 1

    def test_multiple_misses_accumulate(self):
        """Consecutive cache misses each increment the counter."""
        stats = get_sentiment_cache_stats()

        get_cached_history(TICKER, SOURCE, START, END)
        get_cached_history("GOOG", SOURCE, START, END)

        assert stats.misses == 2

    def test_miss_does_not_increment_hits(self):
        """A cache miss does not affect the hits counter."""
        stats = get_sentiment_cache_stats()

        get_cached_history(TICKER, SOURCE, START, END)

        assert stats.hits == 0


# ---------------------------------------------------------------------------
# Hit tracking
# ---------------------------------------------------------------------------


class TestCacheHitObservability:
    """After a cache hit, CacheStats.hits increments."""

    def test_single_hit_increments(self):
        """One cache hit increments hits from 0 to 1."""
        stats = get_sentiment_cache_stats()
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)

        get_cached_history(TICKER, SOURCE, START, END)

        assert stats.hits == 1

    def test_multiple_hits_accumulate(self):
        """Repeated hits on the same key accumulate."""
        stats = get_sentiment_cache_stats()
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)

        get_cached_history(TICKER, SOURCE, START, END)
        get_cached_history(TICKER, SOURCE, START, END)
        get_cached_history(TICKER, SOURCE, START, END)

        assert stats.hits == 3

    def test_hit_does_not_increment_misses(self):
        """A cache hit does not affect the misses counter."""
        stats = get_sentiment_cache_stats()
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)

        get_cached_history(TICKER, SOURCE, START, END)

        assert stats.misses == 0


# ---------------------------------------------------------------------------
# Mixed hit/miss sequence
# ---------------------------------------------------------------------------


class TestMixedHitMissSequence:
    """Interleaved hits and misses are tracked independently."""

    def test_mixed_sequence_counts_correctly(self):
        """A miss followed by a store and two hits yields misses=1, hits=2."""
        stats = get_sentiment_cache_stats()

        # Miss (cache empty)
        get_cached_history(TICKER, SOURCE, START, END)
        assert stats.misses == 1
        assert stats.hits == 0

        # Store
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)

        # Two hits
        get_cached_history(TICKER, SOURCE, START, END)
        get_cached_history(TICKER, SOURCE, START, END)

        assert stats.misses == 1
        assert stats.hits == 2

    def test_flush_resets_counters(self):
        """After flush(), both hits and misses reset to zero."""
        stats = get_sentiment_cache_stats()

        get_cached_history(TICKER, SOURCE, START, END)  # miss
        cache_history(TICKER, SOURCE, START, END, RESPONSE_DATA)
        get_cached_history(TICKER, SOURCE, START, END)  # hit

        snapshot = stats.flush()
        assert snapshot["misses"] == 1
        assert snapshot["hits"] == 1

        # After flush, counters are zero
        assert stats.misses == 0
        assert stats.hits == 0

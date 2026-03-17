"""Unit tests for src/lib/cache_utils.py — jitter, CacheStats, CacheMetricEmitter."""

import random
import threading

import pytest

from src.lib.cache_utils import (
    CacheMetricEmitter,
    CacheStats,
    jittered_ttl,
    validate_non_empty,
)


class TestJitteredTtl:
    """Tests for jittered_ttl() function."""

    def test_jitter_within_bounds(self):
        """All jittered values fall within [base * 0.9, base * 1.1]."""
        base = 60.0
        for _ in range(1000):
            result = jittered_ttl(base, jitter_pct=0.1)
            assert 54.0 <= result <= 66.0, f"Jittered TTL {result} out of bounds"

    def test_jitter_has_spread(self):
        """Standard deviation of jittered TTLs is >= 5% of base."""
        base = 60.0
        values = [jittered_ttl(base, jitter_pct=0.1) for _ in range(1000)]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = variance**0.5
        assert (
            std_dev >= base * 0.05
        ), f"Standard deviation {std_dev:.2f} is less than 5% of base ({base * 0.05})"

    def test_jitter_deterministic_with_seed(self):
        """Jitter is deterministic when random seed is set."""
        random.seed(42)
        a = jittered_ttl(60.0, jitter_pct=0.1)
        random.seed(42)
        b = jittered_ttl(60.0, jitter_pct=0.1)
        assert a == b

    def test_zero_ttl_returns_zero(self):
        """Zero TTL is passed through unchanged."""
        assert jittered_ttl(0.0) == 0.0

    def test_negative_ttl_returns_negative(self):
        """Negative TTL is passed through unchanged."""
        assert jittered_ttl(-10.0) == -10.0

    def test_zero_jitter_returns_base(self):
        """Zero jitter percentage returns exact base TTL."""
        assert jittered_ttl(60.0, jitter_pct=0.0) == 60.0

    def test_custom_jitter_pct(self):
        """Custom jitter percentage is respected."""
        base = 100.0
        for _ in range(100):
            result = jittered_ttl(base, jitter_pct=0.2)
            assert 80.0 <= result <= 120.0


class TestValidateNonEmpty:
    """Tests for validate_non_empty() function."""

    def test_none_raises(self):
        with pytest.raises(ValueError, match="received None"):
            validate_non_empty(None, "test_cache")

    def test_empty_dict_raises(self):
        with pytest.raises(ValueError, match="empty dict"):
            validate_non_empty({}, "test_cache")

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="empty list"):
            validate_non_empty([], "test_cache")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="empty str"):
            validate_non_empty("", "test_cache")

    def test_non_empty_dict_passes(self):
        validate_non_empty({"key": "value"}, "test_cache")

    def test_non_empty_list_passes(self):
        validate_non_empty([1, 2, 3], "test_cache")

    def test_non_empty_string_passes(self):
        validate_non_empty("hello", "test_cache")

    def test_integer_passes(self):
        """Non-collection types pass validation (no length check)."""
        validate_non_empty(42, "test_cache")

    def test_zero_passes(self):
        """Zero is a valid non-None value."""
        validate_non_empty(0, "test_cache")


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_initial_values(self):
        stats = CacheStats(name="test")
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.refresh_failures == 0

    def test_record_hit(self):
        stats = CacheStats(name="test")
        stats.record_hit()
        stats.record_hit()
        assert stats.hits == 2

    def test_record_miss(self):
        stats = CacheStats(name="test")
        stats.record_miss()
        assert stats.misses == 1

    def test_record_eviction(self):
        stats = CacheStats(name="test")
        stats.record_eviction()
        stats.record_eviction()
        stats.record_eviction()
        assert stats.evictions == 3

    def test_record_refresh_failure(self):
        stats = CacheStats(name="test")
        stats.record_refresh_failure()
        assert stats.refresh_failures == 1

    def test_hit_rate_no_accesses(self):
        stats = CacheStats(name="test")
        assert stats.hit_rate == 0.0

    def test_hit_rate_all_hits(self):
        stats = CacheStats(name="test")
        for _ in range(10):
            stats.record_hit()
        assert stats.hit_rate == 1.0

    def test_hit_rate_mixed(self):
        stats = CacheStats(name="test")
        for _ in range(7):
            stats.record_hit()
        for _ in range(3):
            stats.record_miss()
        assert abs(stats.hit_rate - 0.7) < 0.001

    def test_flush_returns_snapshot_and_resets(self):
        stats = CacheStats(name="test")
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        stats.record_eviction()

        snapshot = stats.flush()

        assert snapshot == {
            "hits": 2,
            "misses": 1,
            "evictions": 1,
            "refresh_failures": 0,
        }
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0

    def test_thread_safety(self):
        """Concurrent access from multiple threads doesn't corrupt counters."""
        stats = CacheStats(name="test")
        iterations = 1000

        def increment_hits():
            for _ in range(iterations):
                stats.record_hit()

        def increment_misses():
            for _ in range(iterations):
                stats.record_miss()

        threads = [
            threading.Thread(target=increment_hits),
            threading.Thread(target=increment_misses),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert stats.hits == iterations
        assert stats.misses == iterations


class TestCacheMetricEmitter:
    """Tests for CacheMetricEmitter class."""

    def test_register_and_flush(self):
        emitter = CacheMetricEmitter(flush_interval=0)
        stats = CacheStats(name="test_cache")
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        emitter.register(stats)

        metrics = emitter.flush()

        names = {m["name"] for m in metrics}
        assert "Cache/Hits" in names
        assert "Cache/Misses" in names

    def test_flush_resets_stats(self):
        emitter = CacheMetricEmitter(flush_interval=0)
        stats = CacheStats(name="test_cache")
        stats.record_hit()
        emitter.register(stats)

        emitter.flush()
        second_flush = emitter.flush()

        assert second_flush == []  # No new data since last flush

    def test_flush_skips_zero_values(self):
        emitter = CacheMetricEmitter(flush_interval=0)
        stats = CacheStats(name="test_cache")
        stats.record_hit()
        emitter.register(stats)

        metrics = emitter.flush()

        # Only "Cache/Hits" should be present, not misses/evictions (they're 0)
        assert len(metrics) == 1
        assert metrics[0]["name"] == "Cache/Hits"

    def test_dimensions_include_cache_name(self):
        emitter = CacheMetricEmitter(flush_interval=0)
        stats = CacheStats(name="jwks")
        stats.record_miss()
        emitter.register(stats)

        metrics = emitter.flush()

        assert metrics[0]["dimensions"] == {"Cache": "jwks"}

    def test_multiple_caches(self):
        emitter = CacheMetricEmitter(flush_interval=0)
        for name in ["jwks", "quota", "ticker"]:
            s = CacheStats(name=name)
            s.record_hit()
            emitter.register(s)

        metrics = emitter.flush()
        cache_names = {m["dimensions"]["Cache"] for m in metrics}
        assert cache_names == {"jwks", "quota", "ticker"}

    def test_should_flush_respects_interval(self):
        emitter = CacheMetricEmitter(flush_interval=60)
        assert not emitter.should_flush()

        # Force last_flush to be in the past
        emitter._last_flush = 0
        assert emitter.should_flush()

    def test_get_stats(self):
        emitter = CacheMetricEmitter()
        stats = CacheStats(name="test")
        emitter.register(stats)
        assert emitter.get_stats("test") is stats
        assert emitter.get_stats("nonexistent") is None

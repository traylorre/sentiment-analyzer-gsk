"""Test that the metrics cache is bounded and evicts oldest entries (Feature 1224.2).

The metrics cache was previously unbounded. Feature 1224 added
METRICS_CACHE_MAX_ENTRIES=100 with LRU eviction. This test verifies
the bound is enforced — if someone removes the eviction logic, this fails.
"""

import src.lambdas.dashboard.metrics as metrics_mod


class TestMetricsCacheBound:
    def test_cache_evicts_oldest_when_full(self):
        """Adding entries beyond max_entries triggers LRU eviction."""
        metrics_mod.clear_metrics_cache()
        max_entries = metrics_mod.METRICS_CACHE_MAX_ENTRIES

        # Fill cache to capacity
        for i in range(max_entries):
            metrics_mod._set_cached_result(f"key-{i}", {"data": i})

        assert len(metrics_mod._metrics_cache) == max_entries

        # Add one more — should evict oldest (key-0)
        metrics_mod._set_cached_result("overflow-key", {"data": "new"})

        assert len(metrics_mod._metrics_cache) == max_entries
        assert "overflow-key" in metrics_mod._metrics_cache
        assert "key-0" not in metrics_mod._metrics_cache

    def test_eviction_counter_increments(self):
        """Eviction counter tracks number of LRU evictions."""
        metrics_mod.clear_metrics_cache()
        max_entries = metrics_mod.METRICS_CACHE_MAX_ENTRIES

        # Fill cache
        for i in range(max_entries):
            metrics_mod._set_cached_result(f"key-{i}", {"data": i})

        # Add 3 more — should trigger 3 evictions
        for i in range(3):
            metrics_mod._set_cached_result(f"extra-{i}", {"data": "extra"})

        stats = metrics_mod.get_metrics_cache_stats()
        assert stats["evictions"] == 3

    def test_cache_size_never_exceeds_max(self):
        """Cache size stays at max_entries even with many insertions."""
        metrics_mod.clear_metrics_cache()
        max_entries = metrics_mod.METRICS_CACHE_MAX_ENTRIES

        # Insert 2x max_entries
        for i in range(max_entries * 2):
            metrics_mod._set_cached_result(f"key-{i}", {"data": i})

        assert len(metrics_mod._metrics_cache) == max_entries

"""Integration tests verifying CacheStats is wired into each cache module.

Feature 1224.3: Each cache must increment its CacheStats instance on
hit and miss. If someone removes a record_hit()/record_miss() call,
exactly one test fails.
"""

from unittest.mock import MagicMock


class TestCircuitBreakerCacheStats:
    def test_hit_increments_stats(self):
        import src.lambdas.shared.circuit_breaker as mod

        mod.clear_cache()
        mod._cb_cache_stats.hits = 0

        state = mod.CircuitBreakerState.create_default("tiingo")
        mod._set_cached_state("tiingo", state)
        mod._get_cached_state("tiingo")  # Hit

        assert mod._cb_cache_stats.hits >= 1

    def test_miss_increments_stats(self):
        import src.lambdas.shared.circuit_breaker as mod

        mod.clear_cache()
        mod._cb_cache_stats.misses = 0

        mod._get_cached_state("nonexistent")  # Miss

        assert mod._cb_cache_stats.misses >= 1


class TestTiingoCacheStats:
    def test_hit_increments_stats(self):
        import src.lambdas.shared.adapters.tiingo as mod

        mod.clear_cache()
        mod._tiingo_stats.hits = 0

        mod._put_in_cache("test", "value", 1800)
        mod._get_from_cache("test", 1800)  # Hit

        assert mod._tiingo_stats.hits >= 1

    def test_miss_increments_stats(self):
        import src.lambdas.shared.adapters.tiingo as mod

        mod.clear_cache()
        mod._tiingo_stats.misses = 0

        mod._get_from_cache("nonexistent", 1800)  # Miss

        assert mod._tiingo_stats.misses >= 1


class TestFinnhubCacheStats:
    def test_hit_increments_stats(self):
        import src.lambdas.shared.adapters.finnhub as mod

        mod.clear_cache()
        mod._finnhub_stats.hits = 0

        mod._put_in_cache("test", "value", 1800)
        mod._get_from_cache("test", 1800)  # Hit

        assert mod._finnhub_stats.hits >= 1

    def test_miss_increments_stats(self):
        import src.lambdas.shared.adapters.finnhub as mod

        mod.clear_cache()
        mod._finnhub_stats.misses = 0

        mod._get_from_cache("nonexistent", 1800)  # Miss

        assert mod._finnhub_stats.misses >= 1


class TestSecretsCacheStats:
    def test_hit_increments_stats(self):
        import src.lambdas.shared.secrets as mod

        mod.clear_cache()
        mod._secrets_cw_stats.hits = 0

        mod._set_in_cache("test-secret", {"key": "val"})
        mod._get_from_cache("test-secret")  # Hit

        assert mod._secrets_cw_stats.hits >= 1

    def test_miss_increments_stats(self):
        import src.lambdas.shared.secrets as mod

        mod.clear_cache()
        mod._secrets_cw_stats.misses = 0

        mod._get_from_cache("nonexistent")  # Miss

        assert mod._secrets_cw_stats.misses >= 1


class TestMetricsCacheStats:
    def test_hit_increments_stats(self):
        import src.lambdas.dashboard.metrics as mod

        mod.clear_metrics_cache()
        mod._metrics_cw_stats.hits = 0

        mod._set_cached_result("test-key", {"data": 1})
        mod._get_cached_result("test-key")  # Hit

        assert mod._metrics_cw_stats.hits >= 1

    def test_miss_increments_stats(self):
        import src.lambdas.dashboard.metrics as mod

        mod.clear_metrics_cache()
        mod._metrics_cw_stats.misses = 0

        mod._get_cached_result("nonexistent")  # Miss

        assert mod._metrics_cw_stats.misses >= 1


class TestSentimentCacheStats:
    def test_hit_increments_stats(self):
        import src.lambdas.dashboard.sentiment as mod

        mod.clear_sentiment_cache()
        mod._sentiment_cw_stats.hits = 0

        mock_response = MagicMock()
        mod._set_cached_sentiment("test-key", mock_response)
        mod._get_cached_sentiment("test-key")  # Hit

        assert mod._sentiment_cw_stats.hits >= 1

    def test_miss_increments_stats(self):
        import src.lambdas.dashboard.sentiment as mod

        mod.clear_sentiment_cache()
        mod._sentiment_cw_stats.misses = 0

        mod._get_cached_sentiment("nonexistent")  # Miss

        assert mod._sentiment_cw_stats.misses >= 1


class TestConfigCacheStats:
    def test_list_hit_increments_stats(self):
        import src.lambdas.dashboard.configurations as mod

        mod.clear_config_cache()
        mod._config_cw_stats.hits = 0

        mock_response = MagicMock()
        mod._set_cached_config_list("user-1", mock_response)
        mod._get_cached_config_list("user-1")  # Hit

        assert mod._config_cw_stats.hits >= 1

    def test_list_miss_increments_stats(self):
        import src.lambdas.dashboard.configurations as mod

        mod.clear_config_cache()
        mod._config_cw_stats.misses = 0

        mod._get_cached_config_list("nonexistent")  # Miss

        assert mod._config_cw_stats.misses >= 1


class TestOHLCResponseCacheStats:
    def test_hit_increments_stats(self):
        import src.lambdas.dashboard.ohlc as mod

        mod._ohlc_cache.clear()
        mod._ohlc_cw_stats.hits = 0

        mod._set_cached_ohlc("test-key", {"data": 1}, "D")
        mod._get_cached_ohlc("test-key", "D")  # Hit

        assert mod._ohlc_cw_stats.hits >= 1

    def test_miss_increments_stats(self):
        import src.lambdas.dashboard.ohlc as mod

        mod._ohlc_cache.clear()
        mod._ohlc_cw_stats.misses = 0

        mod._get_cached_ohlc("nonexistent", "D")  # Miss

        assert mod._ohlc_cw_stats.misses >= 1

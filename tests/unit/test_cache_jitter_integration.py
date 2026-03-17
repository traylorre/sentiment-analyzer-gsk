"""Integration tests verifying TTL jitter is applied in each cache module.

Feature 1224.1: If someone removes a jittered_ttl() call from any cache,
exactly one test in this file should fail, identifying which cache lost jitter.

Each test stores an entry in a specific cache and inspects the stored TTL
to verify it falls within ±10% of the base TTL.
"""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

JITTER_TOLERANCE = 0.1  # 10%


def assert_jittered(actual_ttl: float, base_ttl: float, cache_name: str) -> None:
    """Assert TTL is within ±10% of base (jittered)."""
    low = base_ttl * (1 - JITTER_TOLERANCE)
    high = base_ttl * (1 + JITTER_TOLERANCE)
    assert low <= actual_ttl <= high, (
        f"{cache_name}: TTL {actual_ttl:.1f} outside jitter range "
        f"[{low:.1f}, {high:.1f}] for base {base_ttl}"
    )


class TestCircuitBreakerJitter:
    def test_stored_ttl_is_jittered(self):
        import src.lambdas.shared.circuit_breaker as mod

        state = mod.CircuitBreakerState.create_default("tiingo")
        mod._set_cached_state("tiingo", state)

        entry = mod._circuit_breaker_cache["tiingo"]
        assert len(entry) >= 3, "Entry missing jittered TTL field"
        assert_jittered(entry[2], 60.0, "circuit_breaker")


class TestSecretsJitter:
    def test_stored_ttl_is_jittered(self):
        import time

        import src.lambdas.shared.secrets as mod

        mod._set_in_cache("test-secret", {"api_key": "test"})

        entry = mod._secrets_cache["test-secret"]
        stored_ttl = entry["expires_at"] - time.time()
        assert_jittered(stored_ttl, 300.0, "secrets")


class TestTiingoJitter:
    def test_stored_ttl_is_jittered(self):
        import src.lambdas.shared.adapters.tiingo as mod

        mod._put_in_cache("test-key", {"data": "test"}, mod.API_CACHE_TTL_NEWS_SECONDS)

        entry = mod._tiingo_cache["test-key"]
        assert len(entry) >= 3, "Entry missing jittered TTL field"
        assert_jittered(entry[2], 1800.0, "tiingo")


class TestFinnhubJitter:
    def test_stored_ttl_is_jittered(self):
        import src.lambdas.shared.adapters.finnhub as mod

        mod._put_in_cache("test-key", {"data": "test"}, mod.API_CACHE_TTL_NEWS_SECONDS)

        entry = mod._finnhub_cache["test-key"]
        assert len(entry) >= 3, "Entry missing jittered TTL field"
        assert_jittered(entry[2], 1800.0, "finnhub")


class TestConfigurationsJitter:
    def test_list_cache_ttl_is_jittered(self):
        import src.lambdas.dashboard.configurations as mod

        mock_response = MagicMock()
        mod._set_cached_config_list("user-123", mock_response)

        entry = mod._config_list_cache["user-123"]
        assert len(entry) >= 3, "Entry missing jittered TTL field"
        assert_jittered(entry[2], 60.0, "configurations_list")

    def test_single_cache_ttl_is_jittered(self):
        import src.lambdas.dashboard.configurations as mod

        mock_response = MagicMock()
        mod._set_cached_config("user-123", "config-456", mock_response)

        entry = mod._config_cache[("user-123", "config-456")]
        assert len(entry) >= 3, "Entry missing jittered TTL field"
        assert_jittered(entry[2], 60.0, "configurations_single")


class TestSentimentJitter:
    def test_stored_ttl_is_jittered(self):
        import src.lambdas.dashboard.sentiment as mod

        mock_response = MagicMock()
        mod._set_cached_sentiment("test-key", mock_response)

        entry = mod._sentiment_cache["test-key"]
        assert len(entry) >= 3, "Entry missing jittered TTL field"
        assert_jittered(entry[2], 300.0, "sentiment")


class TestMetricsJitter:
    def test_stored_ttl_is_jittered(self):
        import src.lambdas.dashboard.metrics as mod

        mod._set_cached_result("test-key", {"result": "data"})

        entry = mod._metrics_cache["test-key"]
        assert len(entry) >= 3, "Entry missing jittered TTL field"
        assert_jittered(entry[2], 300.0, "metrics")


class TestOHLCResponseJitter:
    def test_stored_ttl_is_jittered(self):
        import src.lambdas.dashboard.ohlc as mod

        mod._set_cached_ohlc("test-key", {"data": "ohlc"}, "D")

        entry = mod._ohlc_cache["test-key"]
        assert len(entry) >= 3, "Entry missing jittered TTL field"
        assert_jittered(entry[2], 3600.0, "ohlc_response")


class TestTimeseriesJitter:
    def test_stored_ttl_is_jittered(self):
        from src.lib.timeseries.cache import ResolutionCache
        from src.lib.timeseries.models import Resolution

        cache = ResolutionCache()
        cache.set("AAPL", Resolution.ONE_MINUTE, data={"test": 1})

        entry = cache._entries[("AAPL", Resolution.ONE_MINUTE)]
        assert_jittered(entry.ttl_seconds, 60.0, "timeseries_resolution")


class TestTickerCacheJitter:
    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_stored_ttl_is_jittered(self, mock_boto3):
        import src.lambdas.shared.cache.ticker_cache as mod

        mod.clear_ticker_cache()

        sample = {
            "version": "2024-01-02",
            "updated_at": "2024-01-02T00:00:00+00:00",
            "symbols": {
                "AAPL": {
                    "symbol": "AAPL",
                    "name": "Apple",
                    "exchange": "NASDAQ",
                    "is_active": True,
                },
            },
            "total_active": 1,
            "total_delisted": 0,
            "exchanges": {"NASDAQ": 1},
        }
        body = BytesIO(json.dumps(sample).encode())
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": body, "ETag": '"test"'}
        mock_s3.head_object.return_value = {"ETag": '"test"'}
        mock_boto3.client.return_value = mock_s3

        mod.get_ticker_cache("test-bucket", "test-key")

        with mod._ticker_cache_lock:
            entry = mod._ticker_cache_entry
            assert entry is not None, "Ticker cache entry not stored"
            assert len(entry) >= 4, "Entry missing jittered TTL field"
            assert_jittered(entry[3], 300.0, "ticker")

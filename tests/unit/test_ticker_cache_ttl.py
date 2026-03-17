"""Unit tests for Feature 1224: Ticker cache TTL + S3 ETag conditional refresh.

Tests TTL expiry, ETag-based conditional download, empty-list rejection,
and S3 failure fallback.
"""

import json
import time
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.lambdas.shared.cache.ticker_cache import (
    _ticker_cache_lock,
    _ticker_stats,
    clear_ticker_cache,
    get_ticker_cache,
    get_ticker_cache_stats,
)

# Sample ticker data for tests
SAMPLE_TICKERS = {
    "version": "2024-01-02",
    "updated_at": "2024-01-02T00:00:00+00:00",
    "symbols": {
        "AAPL": {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "is_active": True,
        },
        "MSFT": {
            "symbol": "MSFT",
            "name": "Microsoft Corp.",
            "exchange": "NASDAQ",
            "is_active": True,
        },
    },
    "total_active": 2,
    "total_delisted": 0,
    "exchanges": {"NASDAQ": 2},
}

UPDATED_TICKERS = {
    **SAMPLE_TICKERS,
    "symbols": {
        **SAMPLE_TICKERS["symbols"],
        "GOOG": {
            "symbol": "GOOG",
            "name": "Alphabet Inc.",
            "exchange": "NASDAQ",
            "is_active": True,
        },
    },
    "total_active": 3,
    "exchanges": {"NASDAQ": 3},
}


@pytest.fixture(autouse=True)
def _clean_ticker_state():
    """Reset ticker cache between tests."""
    clear_ticker_cache()
    # Reset stats counters
    _ticker_stats.hits = 0
    _ticker_stats.misses = 0
    _ticker_stats.evictions = 0
    _ticker_stats.refresh_failures = 0
    yield
    clear_ticker_cache()


def _mock_s3_client(ticker_data=None, etag='"abc123"'):
    """Create a mock S3 client that returns ticker data."""
    if ticker_data is None:
        ticker_data = SAMPLE_TICKERS

    body = BytesIO(json.dumps(ticker_data).encode())
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": body, "ETag": etag}
    mock_client.head_object.return_value = {"ETag": etag}
    return mock_client


def _force_expire_cache():
    """Set the cache entry's loaded_at to the past so TTL is expired."""
    import src.lambdas.shared.cache.ticker_cache as mod

    with _ticker_cache_lock:
        if mod._ticker_cache_entry is not None:
            _, cache, etag, ttl = mod._ticker_cache_entry
            # Set loaded_at to 1000s in the past (well past any TTL)
            mod._ticker_cache_entry = (time.time() - 1000, cache, etag, ttl)


class TestTickerCacheTTLRefresh:
    """Tests for TTL-based refresh behavior."""

    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_initial_load_from_s3(self, mock_boto3):
        """First call loads from S3 and caches."""
        mock_s3 = _mock_s3_client()
        mock_boto3.client.return_value = mock_s3

        cache = get_ticker_cache("test-bucket", "test-key")

        assert cache.total_active == 2
        assert "AAPL" in cache.symbols

    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_second_call_within_ttl_returns_cached(self, mock_boto3):
        """Second call within TTL returns cached data without S3 call."""
        mock_s3 = _mock_s3_client()
        mock_boto3.client.return_value = mock_s3

        cache1 = get_ticker_cache("test-bucket", "test-key")
        mock_s3.head_object.reset_mock()
        mock_s3.get_object.reset_mock()

        cache2 = get_ticker_cache("test-bucket", "test-key")

        assert cache2 is cache1
        mock_s3.head_object.assert_not_called()
        mock_s3.get_object.assert_not_called()

    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_ttl_expired_triggers_etag_check(self, mock_boto3):
        """After TTL expires, head_object is called to check ETag."""
        mock_s3 = _mock_s3_client(etag='"same-etag"')
        mock_boto3.client.return_value = mock_s3

        get_ticker_cache("test-bucket", "test-key")
        mock_s3.head_object.reset_mock()

        # Force cache expiry
        _force_expire_cache()

        get_ticker_cache("test-bucket", "test-key")
        mock_s3.head_object.assert_called()


class TestETagConditionalRefresh:
    """Tests for S3 ETag-based conditional download."""

    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_etag_unchanged_skips_download(self, mock_boto3):
        """If ETag hasn't changed, skip get_object download."""
        mock_s3 = _mock_s3_client(etag='"same-etag"')
        mock_boto3.client.return_value = mock_s3

        get_ticker_cache("test-bucket", "test-key")
        initial_get_count = mock_s3.get_object.call_count

        _force_expire_cache()
        get_ticker_cache("test-bucket", "test-key")

        # get_object should NOT be called again (ETag unchanged)
        assert mock_s3.get_object.call_count == initial_get_count

    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_etag_changed_downloads_new_list(self, mock_boto3):
        """If ETag changed, download new list and update cache."""
        mock_s3 = _mock_s3_client(etag='"etag-v1"')
        mock_boto3.client.return_value = mock_s3

        cache1 = get_ticker_cache("test-bucket", "test-key")
        assert cache1.total_active == 2

        _force_expire_cache()

        # Change S3 response for refresh
        updated_body = BytesIO(json.dumps(UPDATED_TICKERS).encode())
        mock_s3.head_object.return_value = {"ETag": '"etag-v2"'}
        mock_s3.get_object.return_value = {"Body": updated_body, "ETag": '"etag-v2"'}

        cache2 = get_ticker_cache("test-bucket", "test-key")
        assert cache2.total_active == 3
        assert "GOOG" in cache2.symbols


class TestEmptyListRejection:
    """Tests for FR-005: Reject empty ticker lists."""

    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_empty_list_rejected_keeps_previous(self, mock_boto3):
        """Empty ticker list from S3 is rejected, previous list preserved."""
        mock_s3 = _mock_s3_client(etag='"etag-v1"')
        mock_boto3.client.return_value = mock_s3

        cache1 = get_ticker_cache("test-bucket", "test-key")
        assert cache1.total_active == 2

        _force_expire_cache()

        # S3 now returns empty symbols
        empty_data = {**SAMPLE_TICKERS, "symbols": {}, "total_active": 0}
        empty_body = BytesIO(json.dumps(empty_data).encode())
        mock_s3.head_object.return_value = {"ETag": '"etag-v2"'}
        mock_s3.get_object.return_value = {"Body": empty_body, "ETag": '"etag-v2"'}

        # Empty list rejected — returns stale cache
        cache2 = get_ticker_cache("test-bucket", "test-key")
        assert cache2.total_active == 2
        assert "AAPL" in cache2.symbols


class TestS3FailureFallback:
    """Tests for fail-open behavior when S3 is unreachable."""

    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_s3_failure_serves_stale_cache(self, mock_boto3):
        """S3 failure during refresh returns stale cached data."""
        mock_s3 = _mock_s3_client(etag='"etag-v1"')
        mock_boto3.client.return_value = mock_s3

        cache1 = get_ticker_cache("test-bucket", "test-key")
        assert cache1.total_active == 2

        _force_expire_cache()

        # S3 goes down
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "down"}},
            "HeadObject",
        )

        cache2 = get_ticker_cache("test-bucket", "test-key")
        assert cache2.total_active == 2
        assert cache2 is cache1

    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_s3_failure_records_refresh_failure_stat(self, mock_boto3):
        """S3 failure increments refresh_failures counter."""
        mock_s3 = _mock_s3_client(etag='"etag-v1"')
        mock_boto3.client.return_value = mock_s3

        get_ticker_cache("test-bucket", "test-key")

        _force_expire_cache()

        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "down"}},
            "HeadObject",
        )

        get_ticker_cache("test-bucket", "test-key")

        stats = get_ticker_cache_stats()
        assert stats.refresh_failures >= 1


class TestCacheHitMissStats:
    """Tests for ticker cache hit/miss tracking."""

    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_cache_hit_tracked(self, mock_boto3):
        """Cache hit increments hit counter."""
        mock_s3 = _mock_s3_client()
        mock_boto3.client.return_value = mock_s3

        get_ticker_cache("test-bucket", "test-key")  # Miss (cold start)
        get_ticker_cache("test-bucket", "test-key")  # Hit

        stats = get_ticker_cache_stats()
        assert stats.hits >= 1

    @patch("src.lambdas.shared.cache.ticker_cache.boto3")
    def test_cache_miss_tracked(self, mock_boto3):
        """Cache miss increments miss counter."""
        mock_s3 = _mock_s3_client()
        mock_boto3.client.return_value = mock_s3

        get_ticker_cache("test-bucket", "test-key")  # Miss (cold start)

        stats = get_ticker_cache_stats()
        assert stats.misses >= 1

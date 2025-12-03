"""Unit tests for TickerCache."""

import json
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.shared.cache.ticker_cache import (
    TickerCache,
    TickerInfo,
    clear_ticker_cache,
    get_ticker_cache,
)


@pytest.fixture
def sample_ticker_data() -> dict:
    """Sample ticker data for testing."""
    return {
        "version": "2025-01-01",
        "updated_at": "2025-01-01T00:00:00",
        "description": "Test ticker data",
        "symbols": {
            "AAPL": {
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "is_active": True,
            },
            "MSFT": {
                "name": "Microsoft Corporation",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "industry": "Software - Infrastructure",
                "is_active": True,
            },
            "JPM": {
                "name": "JPMorgan Chase & Co.",
                "exchange": "NYSE",
                "sector": "Financial Services",
                "industry": "Banks - Diversified",
                "is_active": True,
            },
            "FB": {
                "name": "Meta Platforms Inc. (former)",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "industry": "Internet Content & Information",
                "is_active": False,
                "delisted_at": "2022-06-09T00:00:00",
                "successor_symbol": "META",
                "delisting_reason": "Ticker changed from FB to META",
            },
            "META": {
                "name": "Meta Platforms Inc.",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "industry": "Internet Content & Information",
                "is_active": True,
            },
        },
    }


@pytest.fixture
def ticker_cache(sample_ticker_data: dict) -> TickerCache:
    """Create a TickerCache from sample data."""
    return TickerCache._from_json(sample_ticker_data)


class TestTickerInfo:
    """Tests for TickerInfo model."""

    def test_valid_ticker_info(self):
        """Test creating valid TickerInfo."""
        info = TickerInfo(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            sector="Technology",
            industry="Consumer Electronics",
        )
        assert info.symbol == "AAPL"
        assert info.name == "Apple Inc."
        assert info.exchange == "NASDAQ"
        assert info.is_active is True

    def test_ticker_symbol_validation(self):
        """Test ticker symbol pattern validation."""
        # Valid symbols: 1-5 uppercase letters
        for symbol in ["A", "AA", "AAPL", "GOOGL"]:
            info = TickerInfo(symbol=symbol, name="Test", exchange="NYSE")
            assert info.symbol == symbol

    def test_invalid_ticker_symbol(self):
        """Test invalid ticker symbols are rejected."""
        with pytest.raises(ValueError):
            TickerInfo(symbol="aapl", name="Test", exchange="NYSE")  # lowercase

        with pytest.raises(ValueError):
            TickerInfo(symbol="TOOLONG", name="Test", exchange="NYSE")  # > 5 chars

        with pytest.raises(ValueError):
            TickerInfo(symbol="", name="Test", exchange="NYSE")  # empty

    def test_delisted_ticker_info(self):
        """Test TickerInfo with delisting information."""
        info = TickerInfo(
            symbol="FB",
            name="Meta Platforms Inc. (former)",
            exchange="NASDAQ",
            is_active=False,
            delisted_at=datetime(2022, 6, 9),
            successor_symbol="META",
            delisting_reason="Ticker changed from FB to META",
        )
        assert info.is_active is False
        assert info.successor_symbol == "META"
        assert info.delisting_reason == "Ticker changed from FB to META"


class TestTickerCacheFromJson:
    """Tests for TickerCache JSON parsing."""

    def test_from_json_basic(self, sample_ticker_data: dict):
        """Test basic JSON parsing."""
        cache = TickerCache._from_json(sample_ticker_data)
        assert cache.version == "2025-01-01"
        assert len(cache.symbols) == 5
        assert "AAPL" in cache.symbols
        assert "FB" in cache.symbols

    def test_from_json_statistics(self, sample_ticker_data: dict):
        """Test statistics calculation."""
        cache = TickerCache._from_json(sample_ticker_data)
        # 4 active (AAPL, MSFT, JPM, META), 1 delisted (FB)
        assert cache.total_active == 4
        assert cache.total_delisted == 1

    def test_from_json_exchange_counts(self, sample_ticker_data: dict):
        """Test exchange counts."""
        cache = TickerCache._from_json(sample_ticker_data)
        # NASDAQ: AAPL, MSFT, META (FB is delisted, not counted)
        # NYSE: JPM
        assert cache.exchanges["NASDAQ"] == 3
        assert cache.exchanges["NYSE"] == 1

    def test_from_json_delisted_not_counted(self, sample_ticker_data: dict):
        """Test that delisted tickers aren't counted in exchange stats."""
        cache = TickerCache._from_json(sample_ticker_data)
        # FB is NASDAQ but delisted, so not counted
        assert cache.total_active == 4
        assert "FB" in cache.symbols
        assert cache.symbols["FB"].is_active is False


class TestTickerCacheLoadFromFile:
    """Tests for loading TickerCache from file."""

    def test_load_from_file(self, sample_ticker_data: dict):
        """Test loading from a local file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_ticker_data, f)
            f.flush()

            cache = TickerCache.load_from_file(f.name)
            assert cache.version == "2025-01-01"
            assert len(cache.symbols) == 5


class TestTickerCacheLoadFromS3:
    """Tests for loading TickerCache from S3."""

    def test_load_from_s3_success(self, sample_ticker_data: dict):
        """Test successful S3 load."""
        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(sample_ticker_data).encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch("boto3.client", return_value=mock_s3):
            cache = TickerCache.load_from_s3(
                "test-bucket", "ticker-cache/us-symbols.json"
            )
            assert cache.version == "2025-01-01"
            assert len(cache.symbols) == 5

        mock_s3.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="ticker-cache/us-symbols.json"
        )

    def test_load_from_s3_failure(self):
        """Test S3 load failure raises ValueError."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("S3 error")

        with patch("boto3.client", return_value=mock_s3):
            with pytest.raises(ValueError, match="Failed to load ticker cache"):
                TickerCache.load_from_s3("test-bucket", "ticker-cache/us-symbols.json")


class TestTickerCacheSearch:
    """Tests for TickerCache search functionality."""

    def test_search_exact_symbol_match(self, ticker_cache: TickerCache):
        """Test exact symbol match."""
        results = ticker_cache.search("AAPL")
        assert len(results) >= 1
        assert results[0].symbol == "AAPL"

    def test_search_case_insensitive(self, ticker_cache: TickerCache):
        """Test case insensitive search."""
        results = ticker_cache.search("aapl")
        assert len(results) >= 1
        assert results[0].symbol == "AAPL"

    def test_search_prefix_match(self, ticker_cache: TickerCache):
        """Test symbol prefix matching."""
        results = ticker_cache.search("M")
        symbols = [r.symbol for r in results]
        assert "MSFT" in symbols
        assert "META" in symbols

    def test_search_company_name(self, ticker_cache: TickerCache):
        """Test company name search."""
        results = ticker_cache.search("Apple")
        assert len(results) >= 1
        assert results[0].symbol == "AAPL"

    def test_search_company_name_partial(self, ticker_cache: TickerCache):
        """Test partial company name match."""
        results = ticker_cache.search("Microsoft")
        assert len(results) >= 1
        assert results[0].symbol == "MSFT"

    def test_search_excludes_delisted(self, ticker_cache: TickerCache):
        """Test that search excludes delisted tickers."""
        results = ticker_cache.search("FB")
        symbols = [r.symbol for r in results]
        assert "FB" not in symbols

    def test_search_limit(self, ticker_cache: TickerCache):
        """Test search result limit."""
        results = ticker_cache.search("", limit=2)
        assert len(results) <= 2

    def test_search_no_results(self, ticker_cache: TickerCache):
        """Test search with no matches."""
        results = ticker_cache.search("ZZZZZ")
        assert len(results) == 0


class TestTickerCacheValidate:
    """Tests for TickerCache validate functionality."""

    def test_validate_active_symbol(self, ticker_cache: TickerCache):
        """Test validating an active symbol."""
        status, info = ticker_cache.validate("AAPL")
        assert status == "valid"
        assert info is not None
        assert info.symbol == "AAPL"
        assert info.is_active is True

    def test_validate_case_insensitive(self, ticker_cache: TickerCache):
        """Test case insensitive validation."""
        status, info = ticker_cache.validate("aapl")
        assert status == "valid"
        assert info.symbol == "AAPL"

    def test_validate_delisted_symbol(self, ticker_cache: TickerCache):
        """Test validating a delisted symbol."""
        status, info = ticker_cache.validate("FB")
        assert status == "delisted"
        assert info is not None
        assert info.symbol == "FB"
        assert info.is_active is False
        assert info.successor_symbol == "META"

    def test_validate_invalid_symbol(self, ticker_cache: TickerCache):
        """Test validating an unknown symbol."""
        status, info = ticker_cache.validate("ZZZZ")
        assert status == "invalid"
        assert info is None


class TestTickerCacheGetByExchange:
    """Tests for TickerCache get_by_exchange functionality."""

    def test_get_by_exchange_nasdaq(self, ticker_cache: TickerCache):
        """Test getting NASDAQ tickers."""
        results = ticker_cache.get_by_exchange("NASDAQ")
        assert len(results) >= 1
        for ticker in results:
            assert ticker.exchange == "NASDAQ"
            assert ticker.is_active is True

    def test_get_by_exchange_nyse(self, ticker_cache: TickerCache):
        """Test getting NYSE tickers."""
        results = ticker_cache.get_by_exchange("NYSE")
        assert len(results) >= 1
        for ticker in results:
            assert ticker.exchange == "NYSE"
            assert ticker.is_active is True

    def test_get_by_exchange_excludes_delisted(self, ticker_cache: TickerCache):
        """Test that get_by_exchange excludes delisted."""
        results = ticker_cache.get_by_exchange("NASDAQ")
        symbols = [r.symbol for r in results]
        assert "FB" not in symbols

    def test_get_by_exchange_limit(self, ticker_cache: TickerCache):
        """Test get_by_exchange with limit."""
        results = ticker_cache.get_by_exchange("NASDAQ", limit=1)
        assert len(results) == 1


class TestTickerCacheGlobalInstance:
    """Tests for global ticker cache instance."""

    def test_clear_ticker_cache(self, sample_ticker_data: dict):
        """Test clearing the global cache."""
        # Set up mock S3
        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(sample_ticker_data).encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch("boto3.client", return_value=mock_s3):
            # Load cache - call triggers S3 get
            get_ticker_cache("test-bucket", "test-key")

            # Clear cache
            clear_ticker_cache()

            # Load again - should make new S3 call
            get_ticker_cache("test-bucket", "test-key")

            # Should have called S3 twice
            assert mock_s3.get_object.call_count == 2

    def test_get_ticker_cache_lru(self, sample_ticker_data: dict):
        """Test LRU caching of ticker cache."""
        # Clear any existing cache
        clear_ticker_cache()

        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(sample_ticker_data).encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch("boto3.client", return_value=mock_s3):
            # Load cache multiple times with same args
            cache1 = get_ticker_cache("bucket", "key")
            cache2 = get_ticker_cache("bucket", "key")

            # Should only call S3 once due to LRU
            assert mock_s3.get_object.call_count == 1
            assert cache1 is cache2

        # Clean up
        clear_ticker_cache()


class TestTickerCacheSerialization:
    """Tests for TickerCache serialization."""

    def test_roundtrip_serialization(self, sample_ticker_data: dict):
        """Test that cache can be serialized and deserialized."""
        cache = TickerCache._from_json(sample_ticker_data)

        # Serialize to dict
        data = cache.model_dump()

        # Verify key fields exist
        assert "version" in data
        assert "symbols" in data
        assert "total_active" in data
        assert "total_delisted" in data
        assert "exchanges" in data

    def test_ticker_info_serialization(self):
        """Test TickerInfo serialization."""
        info = TickerInfo(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            sector="Technology",
            industry="Consumer Electronics",
        )

        data = info.model_dump()
        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["exchange"] == "NASDAQ"
        assert data["is_active"] is True

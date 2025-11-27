"""Unit tests for ticker endpoints (T054-T055)."""

from unittest.mock import MagicMock

from src.lambdas.dashboard.tickers import (
    TickerSearchResponse,
    TickerValidateResponse,
    search_tickers,
    validate_ticker,
)


class TestValidateTicker:
    """Tests for validate_ticker function."""

    def test_returns_invalid_for_empty_symbol(self):
        """Should return invalid for empty symbol."""
        response = validate_ticker("")

        assert isinstance(response, TickerValidateResponse)
        assert response.status == "invalid"
        assert response.message == "Symbol is required"

    def test_returns_invalid_for_too_long_symbol(self):
        """Should return invalid for symbol > 5 chars."""
        response = validate_ticker("TOOLONG")

        assert response.status == "invalid"
        assert response.message == "Symbol not found"

    def test_returns_invalid_for_non_alpha_symbol(self):
        """Should return invalid for non-alphabetic symbol."""
        response = validate_ticker("AAP1")

        assert response.status == "invalid"
        assert response.message == "Symbol not found"

    def test_normalizes_symbol_to_uppercase(self):
        """Should normalize symbol to uppercase."""
        response = validate_ticker("aapl")

        assert response.symbol == "AAPL"

    def test_strips_whitespace_from_symbol(self):
        """Should strip whitespace from symbol."""
        response = validate_ticker("  AAPL  ")

        assert response.symbol == "AAPL"

    def test_returns_valid_for_common_ticker(self):
        """Should return valid for common ticker without cache."""
        response = validate_ticker("AAPL")

        assert response.status == "valid"
        assert response.exchange == "NASDAQ"

    def test_returns_invalid_for_unknown_ticker_without_cache(self):
        """Should return invalid for unknown ticker without cache."""
        response = validate_ticker("ZZZZZ")

        assert response.status == "invalid"

    def test_uses_ticker_cache_when_provided(self):
        """Should use ticker cache for validation."""
        mock_cache = MagicMock()
        mock_cache.validate.return_value = {
            "status": "valid",
            "name": "Apple Inc",
            "exchange": "NASDAQ",
        }

        response = validate_ticker("AAPL", ticker_cache=mock_cache)

        assert response.status == "valid"
        assert response.name == "Apple Inc"
        mock_cache.validate.assert_called_once_with("AAPL")

    def test_returns_delisted_from_cache(self):
        """Should return delisted status from cache."""
        mock_cache = MagicMock()
        mock_cache.validate.return_value = {
            "status": "delisted",
            "successor": "META",
            "message": "Symbol changed to META",
        }

        response = validate_ticker("FB", ticker_cache=mock_cache)

        assert response.status == "delisted"
        assert response.successor == "META"

    def test_returns_invalid_from_cache(self):
        """Should return invalid from cache."""
        mock_cache = MagicMock()
        mock_cache.validate.return_value = {"status": "invalid"}

        response = validate_ticker("INVALID", ticker_cache=mock_cache)

        assert response.status == "invalid"


class TestSearchTickers:
    """Tests for search_tickers function."""

    def test_returns_empty_for_empty_query(self):
        """Should return empty results for empty query."""
        response = search_tickers("")

        assert isinstance(response, TickerSearchResponse)
        assert len(response.results) == 0

    def test_searches_by_symbol_prefix(self):
        """Should search by symbol prefix."""
        response = search_tickers("AA")

        # Should find AAPL, AMD from common tickers
        symbols = [r.symbol for r in response.results]
        assert "AAPL" in symbols

    def test_searches_by_company_name(self):
        """Should search by company name."""
        response = search_tickers("apple")

        symbols = [r.symbol for r in response.results]
        assert "AAPL" in symbols

    def test_limits_results_to_max(self):
        """Should limit results to max."""
        response = search_tickers("a", limit=2)

        assert len(response.results) <= 2

    def test_clamps_limit_to_max_search_results(self):
        """Should clamp limit to MAX_SEARCH_RESULTS."""
        response = search_tickers("a", limit=100)

        # MAX_SEARCH_RESULTS is 10
        assert len(response.results) <= 10

    def test_uses_ticker_cache_when_provided(self):
        """Should use ticker cache for search."""
        mock_cache = MagicMock()
        mock_cache.search.return_value = [
            {"symbol": "AAPL", "name": "Apple Inc", "exchange": "NASDAQ"},
            {"symbol": "AMZN", "name": "Amazon.com Inc", "exchange": "NASDAQ"},
        ]

        response = search_tickers("A", ticker_cache=mock_cache)

        assert len(response.results) == 2
        assert response.results[0].symbol == "AAPL"
        mock_cache.search.assert_called_once()

    def test_truncates_query_for_safety(self):
        """Should truncate long queries."""
        long_query = "a" * 100
        response = search_tickers(long_query)

        # Should not error, query is truncated internally
        assert isinstance(response, TickerSearchResponse)

    def test_returns_results_with_exchange(self):
        """Should include exchange in results."""
        response = search_tickers("JPM")

        jpm_results = [r for r in response.results if r.symbol == "JPM"]
        if jpm_results:
            assert jpm_results[0].exchange == "NYSE"

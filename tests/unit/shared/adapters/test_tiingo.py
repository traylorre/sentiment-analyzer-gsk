"""Unit tests for Tiingo adapter."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.lambdas.shared.adapters.base import AdapterError, RateLimitError
from src.lambdas.shared.adapters.tiingo import TiingoAdapter


@pytest.fixture
def tiingo_adapter():
    """Create Tiingo adapter for testing."""
    return TiingoAdapter(api_key="test-api-key")


class TestTiingoAdapterInit:
    """Tests for TiingoAdapter initialization."""

    def test_init_sets_api_key(self):
        """Test that init stores API key."""
        adapter = TiingoAdapter(api_key="my-key")
        assert adapter.api_key == "my-key"

    def test_source_name(self, tiingo_adapter: TiingoAdapter):
        """Test source name property."""
        assert tiingo_adapter.source_name == "tiingo"

    def test_client_creation(self, tiingo_adapter: TiingoAdapter):
        """Test HTTP client is created with correct headers."""
        client = tiingo_adapter.client
        assert client is not None
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == "Token test-api-key"


class TestTiingoGetNews:
    """Tests for Tiingo get_news method."""

    def test_get_news_empty_tickers(self, tiingo_adapter: TiingoAdapter):
        """Test get_news returns empty list for empty tickers."""
        result = tiingo_adapter.get_news([])
        assert result == []

    def test_get_news_success(self, tiingo_adapter: TiingoAdapter):
        """Test successful news fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = [
            {
                "id": 12345,
                "title": "Apple Reports Record Earnings",
                "description": "Apple Inc. reported strong Q4 results",
                "url": "https://example.com/article",
                "publishedDate": "2025-01-15T14:30:00Z",
                "tickers": ["AAPL"],
                "tags": ["earnings", "technology"],
                "source": "reuters",
            },
            {
                "id": 12346,
                "title": "Microsoft Azure Growth",
                "description": "Azure revenue up 30%",
                "publishedDate": "2025-01-15T12:00:00Z",
                "tickers": ["MSFT"],
                "tags": ["cloud"],
                "source": "bloomberg",
            },
        ]

        with patch.object(tiingo_adapter.client, "get", return_value=mock_response):
            result = tiingo_adapter.get_news(["AAPL", "MSFT"])

        assert len(result) == 2
        assert result[0].article_id == "12345"
        assert result[0].title == "Apple Reports Record Earnings"
        assert result[0].source == "tiingo"
        assert "AAPL" in result[0].tickers
        assert result[0].source_name == "reuters"

    def test_get_news_with_date_range(self, tiingo_adapter: TiingoAdapter):
        """Test news fetch with custom date range."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = []

        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 15)

        with patch.object(
            tiingo_adapter.client, "get", return_value=mock_response
        ) as mock_get:
            tiingo_adapter.get_news(["AAPL"], start_date=start_date, end_date=end_date)

        # Verify dates were passed correctly
        call_params = mock_get.call_args[1]["params"]
        assert call_params["startDate"] == "2025-01-01"
        assert call_params["endDate"] == "2025-01-15"

    def test_get_news_max_10_tickers(self, tiingo_adapter: TiingoAdapter):
        """Test that only first 10 tickers are sent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = []

        tickers = [f"TICK{i}" for i in range(15)]

        with patch.object(
            tiingo_adapter.client, "get", return_value=mock_response
        ) as mock_get:
            tiingo_adapter.get_news(tickers)

        # Verify only 10 tickers sent
        call_params = mock_get.call_args[1]["params"]
        tickers_sent = call_params["tickers"].split(",")
        assert len(tickers_sent) == 10

    def test_get_news_rate_limit_error(self, tiingo_adapter: TiingoAdapter):
        """Test rate limit error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        with patch.object(tiingo_adapter.client, "get", return_value=mock_response):
            with pytest.raises(RateLimitError) as exc_info:
                tiingo_adapter.get_news(["AAPL"])

        assert exc_info.value.retry_after == 60

    def test_get_news_auth_error(self, tiingo_adapter: TiingoAdapter):
        """Test authentication error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(tiingo_adapter.client, "get", return_value=mock_response):
            with pytest.raises(AdapterError, match="authentication failed"):
                tiingo_adapter.get_news(["AAPL"])

    def test_get_news_request_error(self, tiingo_adapter: TiingoAdapter):
        """Test request error handling."""
        with patch.object(
            tiingo_adapter.client,
            "get",
            side_effect=httpx.RequestError("Connection failed"),
        ):
            with pytest.raises(AdapterError, match="request failed"):
                tiingo_adapter.get_news(["AAPL"])


class TestTiingoGetSentiment:
    """Tests for Tiingo get_sentiment method."""

    def test_get_sentiment_returns_none(self, tiingo_adapter: TiingoAdapter):
        """Test that Tiingo returns None for sentiment (not supported)."""
        result = tiingo_adapter.get_sentiment("AAPL")
        assert result is None


class TestTiingoGetOHLC:
    """Tests for Tiingo get_ohlc method."""

    def test_get_ohlc_success(self, tiingo_adapter: TiingoAdapter):
        """Test successful OHLC fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = [
            {
                "date": "2025-01-15T00:00:00Z",
                "open": 150.0,
                "high": 155.0,
                "low": 149.0,
                "close": 153.0,
                "volume": 1000000,
            },
            {
                "date": "2025-01-14T00:00:00Z",
                "open": 148.0,
                "high": 151.0,
                "low": 147.0,
                "close": 150.0,
                "volume": 900000,
            },
        ]

        with patch.object(tiingo_adapter.client, "get", return_value=mock_response):
            result = tiingo_adapter.get_ohlc("AAPL")

        assert len(result) == 2
        assert result[0].open == 150.0
        assert result[0].high == 155.0
        assert result[0].low == 149.0
        assert result[0].close == 153.0
        assert result[0].volume == 1000000

    def test_get_ohlc_with_date_range(self, tiingo_adapter: TiingoAdapter):
        """Test OHLC fetch with custom date range."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = []

        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 15)

        with patch.object(
            tiingo_adapter.client, "get", return_value=mock_response
        ) as mock_get:
            tiingo_adapter.get_ohlc("AAPL", start_date=start_date, end_date=end_date)

        call_params = mock_get.call_args[1]["params"]
        assert call_params["startDate"] == "2025-01-01"
        assert call_params["endDate"] == "2025-01-15"

    def test_get_ohlc_default_date_range(self, tiingo_adapter: TiingoAdapter):
        """Test OHLC uses 30-day default range."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = []

        with patch.object(
            tiingo_adapter.client, "get", return_value=mock_response
        ) as mock_get:
            tiingo_adapter.get_ohlc("AAPL")

        call_params = mock_get.call_args[1]["params"]
        # Verify start is ~30 days ago
        start = datetime.strptime(call_params["startDate"], "%Y-%m-%d")
        end = datetime.strptime(call_params["endDate"], "%Y-%m-%d")
        assert (end - start).days >= 29

    def test_get_ohlc_404_returns_empty(self, tiingo_adapter: TiingoAdapter):
        """Test OHLC returns empty list for 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(tiingo_adapter.client, "get", return_value=mock_response):
            result = tiingo_adapter.get_ohlc("INVALID")

        assert result == []


class TestTiingoContextManager:
    """Tests for context manager protocol."""

    def test_context_manager_closes_client(self):
        """Test that context manager closes client."""
        with TiingoAdapter(api_key="test") as adapter:
            # Access client to ensure it's created
            _client = adapter.client
            assert adapter._client is not None

        assert adapter._client is None

    def test_close_without_client(self):
        """Test close when client wasn't created."""
        adapter = TiingoAdapter(api_key="test")
        adapter.close()  # Should not raise
        assert adapter._client is None

"""Unit tests for Finnhub adapter."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.lambdas.shared.adapters.base import AdapterError, RateLimitError
from src.lambdas.shared.adapters.finnhub import FinnhubAdapter, clear_cache


@pytest.fixture(autouse=True)
def clear_finnhub_cache():
    """Clear Finnhub cache before each test to ensure isolation."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def finnhub_adapter():
    """Create Finnhub adapter for testing."""
    return FinnhubAdapter(api_key="test-api-key")


class TestFinnhubAdapterInit:
    """Tests for FinnhubAdapter initialization."""

    def test_init_sets_api_key(self):
        """Test that init stores API key."""
        adapter = FinnhubAdapter(api_key="my-key")
        assert adapter.api_key == "my-key"

    def test_source_name(self, finnhub_adapter: FinnhubAdapter):
        """Test source name property."""
        assert finnhub_adapter.source_name == "finnhub"

    def test_client_creation(self, finnhub_adapter: FinnhubAdapter):
        """Test HTTP client is created with correct params."""
        client = finnhub_adapter.client
        assert client is not None
        # Finnhub uses query param for auth
        assert client.params["token"] == "test-api-key"


class TestFinnhubGetNews:
    """Tests for Finnhub get_news method."""

    def test_get_news_empty_tickers(self, finnhub_adapter: FinnhubAdapter):
        """Test get_news returns empty list for empty tickers."""
        result = finnhub_adapter.get_news([])
        assert result == []

    def test_get_news_success(self, finnhub_adapter: FinnhubAdapter):
        """Test successful news fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = [
            {
                "id": 12345,
                "headline": "Apple Reports Record Earnings",
                "summary": "Apple Inc. reported strong Q4 results",
                "url": "https://example.com/article",
                "datetime": 1705330200,  # Unix timestamp
                "category": "earnings,technology",
                "source": "reuters",
            },
            {
                "id": 12346,
                "headline": "iPhone Sales Surge",
                "summary": "iPhone sales exceed expectations",
                "datetime": 1705243800,
                "category": "product",
                "source": "bloomberg",
            },
        ]

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            result = finnhub_adapter.get_news(["AAPL"])

        assert len(result) == 2
        assert result[0].article_id == "12345"
        assert result[0].title == "Apple Reports Record Earnings"
        assert result[0].source == "finnhub"
        assert "AAPL" in result[0].tickers
        assert result[0].source_name == "reuters"
        assert "earnings" in result[0].tags

    def test_get_news_multiple_tickers(self, finnhub_adapter: FinnhubAdapter):
        """Test news fetch for multiple tickers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = [
            {
                "id": 1,
                "headline": "News Item",
                "datetime": 1705330200,
                "source": "test",
            }
        ]

        with patch.object(
            finnhub_adapter.client, "get", return_value=mock_response
        ) as mock_get:
            result = finnhub_adapter.get_news(["AAPL", "MSFT", "GOOGL"])

        # Finnhub requires one call per ticker
        assert mock_get.call_count == 3
        assert len(result) == 3

    def test_get_news_rate_limit_error(self, finnhub_adapter: FinnhubAdapter):
        """Test rate limit error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            with pytest.raises(RateLimitError) as exc_info:
                finnhub_adapter.get_news(["AAPL"])

        assert exc_info.value.retry_after == 30

    def test_get_news_auth_error(self, finnhub_adapter: FinnhubAdapter):
        """Test authentication error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            with pytest.raises(AdapterError, match="authentication failed"):
                finnhub_adapter.get_news(["AAPL"])

    def test_get_news_continues_on_ticker_error(self, finnhub_adapter: FinnhubAdapter):
        """Test that news fetch continues if one ticker fails."""
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.is_success = True
        mock_success.json.return_value = [
            {"id": 1, "headline": "News", "datetime": 1705330200}
        ]

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:  # Second ticker fails
                raise httpx.RequestError("Connection failed")
            return mock_success

        with patch.object(finnhub_adapter.client, "get", side_effect=side_effect):
            result = finnhub_adapter.get_news(["AAPL", "MSFT", "GOOGL"])

        # Should get news from 2 tickers (one failed)
        assert len(result) == 2


class TestFinnhubGetSentiment:
    """Tests for Finnhub get_sentiment method."""

    def test_get_sentiment_success(self, finnhub_adapter: FinnhubAdapter):
        """Test successful sentiment fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "symbol": "AAPL",
            "buzz": {
                "articlesInLastWeek": 150,
                "buzz": 0.95,
            },
            "companyNewsScore": 0.7123,
            "sectorAverageNewsScore": 0.52,
            "sentiment": {
                "bearishPercent": 0.15,
                "bullishPercent": 0.85,
            },
        }

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            result = finnhub_adapter.get_sentiment("AAPL")

        assert result is not None
        assert result.ticker == "AAPL"
        assert result.source == "finnhub"
        assert result.bullish_percent == 0.85
        assert result.bearish_percent == 0.15
        assert result.sentiment_score == 0.7  # 0.85 - 0.15
        assert result.articles_count == 150
        assert result.buzz_score == 0.95
        assert result.sector_average_score == 0.52

    def test_get_sentiment_no_data(self, finnhub_adapter: FinnhubAdapter):
        """Test sentiment fetch with no data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {}

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            result = finnhub_adapter.get_sentiment("UNKNOWN")

        assert result is None

    def test_get_sentiment_negative(self, finnhub_adapter: FinnhubAdapter):
        """Test sentiment with negative score."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "sentiment": {
                "bearishPercent": 0.8,
                "bullishPercent": 0.2,
            },
        }

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            result = finnhub_adapter.get_sentiment("BAD")

        assert result is not None
        assert result.sentiment_score == pytest.approx(-0.6)  # 0.2 - 0.8


class TestFinnhubGetOHLC:
    """Tests for Finnhub get_ohlc method."""

    def test_get_ohlc_success(self, finnhub_adapter: FinnhubAdapter):
        """Test successful OHLC fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "s": "ok",
            "t": [1705276800, 1705190400],  # Unix timestamps
            "o": [150.0, 148.0],
            "h": [155.0, 151.0],
            "l": [149.0, 147.0],
            "c": [153.0, 150.0],
            "v": [1000000, 900000],
        }

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            result = finnhub_adapter.get_ohlc("AAPL")

        assert len(result) == 2
        assert result[0].open == 150.0
        assert result[0].high == 155.0
        assert result[0].low == 149.0
        assert result[0].close == 153.0
        assert result[0].volume == 1000000

    def test_get_ohlc_no_data(self, finnhub_adapter: FinnhubAdapter):
        """Test OHLC fetch with no data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {"s": "no_data"}

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            result = finnhub_adapter.get_ohlc("INVALID")

        assert result == []

    def test_get_ohlc_uses_unix_timestamps(self, finnhub_adapter: FinnhubAdapter):
        """Test that OHLC uses Unix timestamps for date params."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {"s": "no_data"}

        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 15)

        with patch.object(
            finnhub_adapter.client, "get", return_value=mock_response
        ) as mock_get:
            finnhub_adapter.get_ohlc("AAPL", start_date=start_date, end_date=end_date)

        call_params = mock_get.call_args[1]["params"]
        # Verify Unix timestamps
        assert call_params["from"] == int(start_date.timestamp())
        assert call_params["to"] == int(end_date.timestamp())
        assert call_params["resolution"] == "D"

    def test_get_ohlc_rate_limit(self, finnhub_adapter: FinnhubAdapter):
        """Test OHLC rate limit handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            with pytest.raises(RateLimitError):
                finnhub_adapter.get_ohlc("AAPL")


class TestFinnhubContextManager:
    """Tests for context manager protocol."""

    def test_context_manager_closes_client(self):
        """Test that context manager closes client."""
        with FinnhubAdapter(api_key="test") as adapter:
            _client = adapter.client
            assert adapter._client is not None

        assert adapter._client is None

    def test_close_without_client(self):
        """Test close when client wasn't created."""
        adapter = FinnhubAdapter(api_key="test")
        adapter.close()
        assert adapter._client is None


class TestFinnhubErrorHandling:
    """Tests for error handling."""

    def test_forbidden_error(self, finnhub_adapter: FinnhubAdapter):
        """Test 403 forbidden error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            with pytest.raises(AdapterError, match="access denied"):
                finnhub_adapter.get_sentiment("AAPL")

    def test_generic_error(self, finnhub_adapter: FinnhubAdapter):
        """Test generic error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.is_success = False
        mock_response.text = "Internal Server Error"

        with patch.object(finnhub_adapter.client, "get", return_value=mock_response):
            with pytest.raises(AdapterError, match="500"):
                finnhub_adapter.get_sentiment("AAPL")

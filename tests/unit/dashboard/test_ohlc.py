"""Unit tests for OHLC endpoint (Feature 011)."""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.lambdas.dashboard.ohlc import router
from src.lambdas.shared.adapters.base import OHLCCandle
from src.lambdas.shared.models import TimeRange


# Test helpers
def _create_ohlc_candles(
    count: int, start_date: date | None = None
) -> list[OHLCCandle]:
    """Create test OHLC candles."""
    base_date = start_date or date.today() - timedelta(days=count)
    candles = []
    for i in range(count):
        candles.append(
            OHLCCandle(
                date=datetime.combine(
                    base_date + timedelta(days=i), datetime.min.time()
                ),
                open=100 + i,
                high=102 + i,
                low=99 + i,
                close=101 + i,
                volume=1000000 + i * 10000,
            )
        )
    return candles


# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestOHLCEndpoint:
    """Tests for GET /api/v2/tickers/{ticker}/ohlc endpoint."""

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_returns_ohlc_response(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should return OHLCResponse with candles."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_tiingo_cls.return_value = mock_tiingo

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc",
            headers={"X-User-ID": "test-user"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert "candles" in data
        assert data["count"] > 0
        assert data["source"] == "tiingo"

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_validates_user_id_header(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should require X-User-ID header."""
        response = client.get("/api/v2/tickers/AAPL/ohlc")

        assert response.status_code == 401
        assert "Missing user identification" in response.json()["detail"]

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_validates_ticker_symbol(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should reject invalid ticker symbols."""
        response = client.get(
            "/api/v2/tickers/INVALID123/ohlc",
            headers={"X-User-ID": "test-user"},
        )

        assert response.status_code == 400
        assert "Invalid ticker symbol" in response.json()["detail"]

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_falls_back_to_finnhub(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should fall back to Finnhub if Tiingo fails."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.side_effect = Exception("Tiingo error")
        mock_tiingo_cls.return_value = mock_tiingo

        mock_finnhub = MagicMock()
        mock_finnhub.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_finnhub_cls.return_value = mock_finnhub

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc",
            headers={"X-User-ID": "test-user"},
        )

        assert response.status_code == 200
        assert response.json()["source"] == "finnhub"

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_returns_404_when_no_data(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should return 404 when no data available."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = []
        mock_tiingo_cls.return_value = mock_tiingo

        mock_finnhub = MagicMock()
        mock_finnhub.get_ohlc.return_value = []
        mock_finnhub_cls.return_value = mock_finnhub

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc",
            headers={"X-User-ID": "test-user"},
        )

        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_supports_time_range_param(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should support time range query parameter."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(90)
        mock_tiingo_cls.return_value = mock_tiingo

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc?range=3M",
            headers={"X-User-ID": "test-user"},
        )

        assert response.status_code == 200
        assert response.json()["time_range"] == "3M"

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_supports_custom_date_range(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should support custom start_date and end_date."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(30)
        mock_tiingo_cls.return_value = mock_tiingo

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc?start_date=2024-01-01&end_date=2024-01-31",
            headers={"X-User-ID": "test-user"},
        )

        assert response.status_code == 200
        assert response.json()["time_range"] == "custom"

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_validates_date_range_order(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should reject when start_date is after end_date."""
        response = client.get(
            "/api/v2/tickers/AAPL/ohlc?start_date=2024-12-31&end_date=2024-01-01",
            headers={"X-User-ID": "test-user"},
        )

        assert response.status_code == 400
        assert "start_date must be before end_date" in response.json()["detail"]

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_includes_cache_expiration(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should include cache_expires_at in response."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_tiingo_cls.return_value = mock_tiingo

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc",
            headers={"X-User-ID": "test-user"},
        )

        assert response.status_code == 200
        assert "cache_expires_at" in response.json()

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_normalizes_ticker_to_uppercase(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should normalize ticker to uppercase."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_tiingo_cls.return_value = mock_tiingo

        response = client.get(
            "/api/v2/tickers/aapl/ohlc",
            headers={"X-User-ID": "test-user"},
        )

        assert response.status_code == 200
        assert response.json()["ticker"] == "AAPL"


class TestTimeRangeEnum:
    """Tests for TimeRange enum."""

    def test_time_range_values(self):
        """Should have correct time range values."""
        assert TimeRange.ONE_WEEK.value == "1W"
        assert TimeRange.ONE_MONTH.value == "1M"
        assert TimeRange.THREE_MONTHS.value == "3M"
        assert TimeRange.SIX_MONTHS.value == "6M"
        assert TimeRange.ONE_YEAR.value == "1Y"

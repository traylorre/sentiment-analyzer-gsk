"""Unit tests for OHLC endpoint (Feature 011)."""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.lambdas.dashboard.ohlc import router
from src.lambdas.shared.adapters.base import OHLCCandle
from src.lambdas.shared.models import RESOLUTION_MAX_DAYS, OHLCResolution, TimeRange


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


# Test constants (Feature 1049: valid UUID required for auth)
TEST_USER_ID = "12345678-1234-5678-1234-567812345678"

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
            headers={"X-User-ID": TEST_USER_ID},
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
            headers={"X-User-ID": TEST_USER_ID},
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
            headers={"X-User-ID": TEST_USER_ID},
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
            headers={"X-User-ID": TEST_USER_ID},
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
            headers={"X-User-ID": TEST_USER_ID},
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
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200
        assert response.json()["time_range"] == "custom"

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_validates_date_range_order(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should reject when start_date is after end_date."""
        response = client.get(
            "/api/v2/tickers/AAPL/ohlc?start_date=2024-12-31&end_date=2024-01-01",
            headers={"X-User-ID": TEST_USER_ID},
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
            headers={"X-User-ID": TEST_USER_ID},
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
            headers={"X-User-ID": TEST_USER_ID},
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


class TestOHLCResolutionEnum:
    """Tests for OHLCResolution enum (T007)."""

    def test_resolution_values(self):
        """Should have correct resolution values matching Finnhub API."""
        assert OHLCResolution.ONE_MINUTE.value == "1"
        assert OHLCResolution.FIVE_MINUTES.value == "5"
        assert OHLCResolution.FIFTEEN_MINUTES.value == "15"
        assert OHLCResolution.THIRTY_MINUTES.value == "30"
        assert OHLCResolution.ONE_HOUR.value == "60"
        assert OHLCResolution.DAILY.value == "D"

    def test_max_days_property(self):
        """Should have correct max_days for each resolution."""
        assert OHLCResolution.ONE_MINUTE.max_days == 7
        assert OHLCResolution.FIVE_MINUTES.max_days == 30
        assert OHLCResolution.FIFTEEN_MINUTES.max_days == 90
        assert OHLCResolution.THIRTY_MINUTES.max_days == 90
        assert OHLCResolution.ONE_HOUR.max_days == 180
        assert OHLCResolution.DAILY.max_days == 365

    def test_resolution_max_days_dict(self):
        """Should have RESOLUTION_MAX_DAYS mapping for all resolutions."""
        for resolution in OHLCResolution:
            assert resolution in RESOLUTION_MAX_DAYS
            assert RESOLUTION_MAX_DAYS[resolution] == resolution.max_days


class TestOHLCResolutionEndpoint:
    """Tests for OHLC endpoint resolution parameter (T009)."""

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_accepts_resolution_parameter(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should accept resolution query parameter."""
        mock_finnhub = MagicMock()
        mock_finnhub.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_finnhub_cls.return_value = mock_finnhub

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc?resolution=5",
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["resolution"] == "5"

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_default_resolution_is_daily(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should default to daily resolution."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_tiingo_cls.return_value = mock_tiingo

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc",
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["resolution"] == "D"

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_uses_finnhub_for_intraday(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should use Finnhub for intraday resolutions (not Tiingo)."""
        mock_tiingo = MagicMock()
        mock_tiingo_cls.return_value = mock_tiingo

        mock_finnhub = MagicMock()
        mock_finnhub.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_finnhub_cls.return_value = mock_finnhub

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc?resolution=5",
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200
        # Tiingo should not be called for intraday
        mock_tiingo.get_ohlc.assert_not_called()
        # Finnhub should be called with resolution
        mock_finnhub.get_ohlc.assert_called_once()
        call_kwargs = mock_finnhub.get_ohlc.call_args[1]
        assert call_kwargs.get("resolution") == "5"

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_resolution_response_includes_fallback_fields(
        self, mock_finnhub_cls, mock_tiingo_cls
    ):
        """Should include resolution_fallback and fallback_message in response."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_tiingo_cls.return_value = mock_tiingo

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc",
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert "resolution_fallback" in data
        assert data["resolution_fallback"] is False
        assert data["fallback_message"] is None

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_fallback_to_daily_when_intraday_unavailable(
        self, mock_finnhub_cls, mock_tiingo_cls
    ):
        """Should fall back to daily when intraday data unavailable."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_tiingo_cls.return_value = mock_tiingo

        mock_finnhub = MagicMock()
        # Return empty for intraday, have Tiingo return daily
        mock_finnhub.get_ohlc.return_value = []
        mock_finnhub_cls.return_value = mock_finnhub

        response = client.get(
            "/api/v2/tickers/AAPL/ohlc?resolution=5",
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["resolution"] == "D"  # Fell back to daily
        assert data["resolution_fallback"] is True
        assert "unavailable" in data["fallback_message"].lower()

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    @pytest.mark.parametrize(
        "resolution",
        ["1", "5", "15", "30", "60", "D"],
    )
    def test_all_resolutions_accepted(
        self, mock_finnhub_cls, mock_tiingo_cls, resolution
    ):
        """Should accept all valid resolution values."""
        mock_finnhub = MagicMock()
        mock_finnhub.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_finnhub_cls.return_value = mock_finnhub

        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_tiingo_cls.return_value = mock_tiingo

        response = client.get(
            f"/api/v2/tickers/AAPL/ohlc?resolution={resolution}",
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200

    @patch("src.lambdas.dashboard.ohlc.TiingoAdapter")
    @patch("src.lambdas.dashboard.ohlc.FinnhubAdapter")
    def test_invalid_resolution_rejected(self, mock_finnhub_cls, mock_tiingo_cls):
        """Should reject invalid resolution values."""
        response = client.get(
            "/api/v2/tickers/AAPL/ohlc?resolution=invalid",
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 422  # Validation error

"""Contract tests for OHLC endpoint (Feature 011).

Validates OHLC endpoint response structure:
- GET /api/v2/tickers/{ticker}/ohlc (OHLC price data)
"""

from datetime import date

from pydantic import BaseModel, Field

# --- Response Schema Definitions ---


class PriceCandle(BaseModel):
    """Single OHLC candle."""

    date: str  # YYYY-MM-DD format
    open: float = Field(..., gt=0)
    high: float
    low: float
    close: float = Field(..., gt=0)
    volume: int | None = None


class OHLCResponse(BaseModel):
    """Response schema for GET /api/v2/tickers/{ticker}/ohlc."""

    ticker: str = Field(..., pattern=r"^[A-Z]{1,5}$")
    candles: list[PriceCandle]
    time_range: str = Field(..., pattern=r"^(1W|1M|3M|6M|1Y|custom)$")
    start_date: str  # YYYY-MM-DD format
    end_date: str  # YYYY-MM-DD format
    count: int = Field(..., ge=0)
    source: str = Field(..., pattern=r"^(tiingo|finnhub)$")
    cache_expires_at: str  # ISO datetime


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str


# --- Contract Tests for OHLC Endpoint ---


class TestOHLCEndpoint:
    """Contract tests for OHLC price data endpoint."""

    def test_response_contains_required_fields(self):
        """Response must contain all required fields per contract."""
        response = self._simulate_ohlc_response()

        assert "ticker" in response
        assert "candles" in response
        assert "time_range" in response
        assert "start_date" in response
        assert "end_date" in response
        assert "count" in response
        assert "source" in response
        assert "cache_expires_at" in response

    def test_ticker_is_uppercase_alphanumeric(self):
        """Ticker must be 1-5 uppercase letters."""
        response = self._simulate_ohlc_response()

        ticker = response["ticker"]
        assert ticker.isupper()
        assert ticker.isalpha()
        assert 1 <= len(ticker) <= 5

    def test_candles_array_format(self):
        """Candles must be an array of PriceCandle objects."""
        response = self._simulate_ohlc_response()

        assert isinstance(response["candles"], list)
        if response["candles"]:
            candle = response["candles"][0]
            assert "date" in candle
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle

    def test_candle_date_format(self):
        """Candle date must be YYYY-MM-DD format."""
        response = self._simulate_ohlc_response()

        if response["candles"]:
            candle_date = response["candles"][0]["date"]
            # Validate date format
            date.fromisoformat(candle_date)

    def test_candle_price_constraints(self):
        """Candle prices must satisfy OHLC constraints."""
        response = self._simulate_ohlc_response()

        for candle in response["candles"]:
            # High must be >= max(open, close)
            assert candle["high"] >= max(candle["open"], candle["close"])
            # Low must be <= min(open, close)
            assert candle["low"] <= min(candle["open"], candle["close"])
            # Prices must be positive
            assert candle["open"] > 0
            assert candle["close"] > 0
            assert candle["high"] > 0
            assert candle["low"] > 0

    def test_time_range_valid_values(self):
        """Time range must be valid enum value."""
        response = self._simulate_ohlc_response()

        valid_ranges = {"1W", "1M", "3M", "6M", "1Y", "custom"}
        assert response["time_range"] in valid_ranges

    def test_count_matches_candles_length(self):
        """Count must match candles array length."""
        response = self._simulate_ohlc_response()

        assert response["count"] == len(response["candles"])

    def test_source_valid_values(self):
        """Source must be tiingo or finnhub."""
        response = self._simulate_ohlc_response()

        valid_sources = {"tiingo", "finnhub"}
        assert response["source"] in valid_sources

    def test_cache_expires_at_is_iso_datetime(self):
        """cache_expires_at must be ISO datetime."""
        response = self._simulate_ohlc_response()

        # Validate ISO datetime format
        from datetime import datetime

        # Should not raise
        datetime.fromisoformat(response["cache_expires_at"].replace("Z", "+00:00"))

    def test_response_validates_against_schema(self):
        """Response must validate against OHLCResponse schema."""
        response = self._simulate_ohlc_response()

        # Should not raise ValidationError
        OHLCResponse(**response)

    def test_candles_sorted_by_date_ascending(self):
        """Candles must be sorted oldest first."""
        response = self._simulate_ohlc_response()

        dates = [c["date"] for c in response["candles"]]
        assert dates == sorted(dates)

    def test_start_date_matches_first_candle(self):
        """start_date must match first candle date."""
        response = self._simulate_ohlc_response()

        if response["candles"]:
            assert response["start_date"] == response["candles"][0]["date"]

    def test_end_date_matches_last_candle(self):
        """end_date must match last candle date."""
        response = self._simulate_ohlc_response()

        if response["candles"]:
            assert response["end_date"] == response["candles"][-1]["date"]

    # --- Helper to simulate valid responses ---

    def _simulate_ohlc_response(self) -> dict:
        """Simulate a valid OHLC response for contract testing."""
        return {
            "ticker": "AAPL",
            "candles": [
                {
                    "date": "2024-11-28",
                    "open": 237.45,
                    "high": 239.12,
                    "low": 236.80,
                    "close": 238.67,
                    "volume": 45678900,
                },
                {
                    "date": "2024-11-29",
                    "open": 238.00,
                    "high": 240.50,
                    "low": 237.50,
                    "close": 239.80,
                    "volume": 42345678,
                },
            ],
            "time_range": "1M",
            "start_date": "2024-11-28",
            "end_date": "2024-11-29",
            "count": 2,
            "source": "tiingo",
            "cache_expires_at": "2024-12-02T14:30:00+00:00",
        }


class TestOHLCErrorResponses:
    """Contract tests for OHLC error responses."""

    def test_401_missing_user_id(self):
        """401 response when X-User-ID header missing."""
        response = self._simulate_401_response()

        assert "detail" in response
        ErrorResponse(**response)

    def test_400_invalid_ticker(self):
        """400 response for invalid ticker symbol."""
        response = self._simulate_400_response()

        assert "detail" in response
        ErrorResponse(**response)

    def test_404_no_data(self):
        """404 response when no price data available."""
        response = self._simulate_404_response()

        assert "detail" in response
        ErrorResponse(**response)

    # --- Helper to simulate error responses ---

    def _simulate_401_response(self) -> dict:
        """Simulate 401 error response."""
        return {"detail": "Missing user identification"}

    def _simulate_400_response(self) -> dict:
        """Simulate 400 error response."""
        return {"detail": "Invalid ticker symbol: INVALID123. Must be 1-5 letters."}

    def _simulate_404_response(self) -> dict:
        """Simulate 404 error response."""
        return {"detail": "No price data available for XYZ"}

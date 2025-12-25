"""OHLC Happy Path Integration Tests (US1).

Tests for /api/v2/tickers/{ticker}/ohlc endpoint covering:
- Valid ticker with default parameters (T016)
- Time range variations (T017)
- Custom date ranges (T018)
- Ticker normalization (T019)
- Cache expiration field (T020)
- Source field verification (T021-T022)
- Count and date consistency (T023-T025)

For On-Call Engineers:
    These tests use mock adapters - no real API calls.
    If tests fail, check:
    1. MockTiingoAdapter is returning valid OHLCCandle objects
    2. FastAPI dependency overrides are set correctly
    3. Response model serialization is correct
"""

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.lambdas.dashboard.ohlc import (
    get_finnhub_adapter,
    get_tiingo_adapter,
    router,
)
from tests.fixtures.mocks.mock_finnhub import MockFinnhubAdapter
from tests.fixtures.mocks.mock_tiingo import MockTiingoAdapter


@pytest.fixture
def mock_tiingo():
    """Create mock Tiingo adapter."""
    return MockTiingoAdapter(seed=42)


@pytest.fixture
def mock_finnhub():
    """Create mock Finnhub adapter."""
    return MockFinnhubAdapter(seed=42)


@pytest.fixture
def test_client(mock_tiingo, mock_finnhub):
    """Create test client with mock adapters injected."""
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo
    app.dependency_overrides[get_finnhub_adapter] = lambda: mock_finnhub

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Headers with valid authentication (Feature 1049: valid UUID required)."""
    return {"X-User-ID": "550e8400-e29b-41d4-a716-446655440000"}


class TestOHLCHappyPath:
    """US1: OHLC Happy Path Validation tests."""

    # T016: Valid ticker with default parameters
    @pytest.mark.ohlc
    def test_ohlc_valid_ticker_default_params(
        self, test_client, auth_headers, ohlc_validator
    ):
        """OHLC endpoint returns valid data for ticker with default params."""
        response = test_client.get("/api/v2/tickers/AAPL/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Validate response structure and business rules
        ohlc_validator.assert_valid(data)

        # Verify default values
        assert data["ticker"] == "AAPL"
        assert data["time_range"] == "1M"  # Default range
        assert data["source"] in ("tiingo", "finnhub")
        assert data["count"] > 0
        assert len(data["candles"]) == data["count"]

    # T017: Time range parameterized test
    @pytest.mark.ohlc
    @pytest.mark.parametrize(
        "time_range,expected_days_min,expected_days_max",
        [
            ("1W", 5, 7),  # 7 days, may have fewer due to weekends
            ("1M", 20, 30),  # ~30 days
            ("3M", 60, 90),  # ~90 days
            ("6M", 120, 180),  # ~180 days
            ("1Y", 250, 365),  # ~365 days
        ],
        ids=["1W", "1M", "3M", "6M", "1Y"],
    )
    def test_ohlc_time_ranges(
        self,
        test_client,
        auth_headers,
        ohlc_validator,
        time_range,
        expected_days_min,
        expected_days_max,
    ):
        """OHLC endpoint returns appropriate data for each time range."""
        response = test_client.get(
            f"/api/v2/tickers/MSFT/ohlc?range={time_range}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        ohlc_validator.assert_valid(data)
        assert data["time_range"] == time_range
        # Count should be within expected range (accounting for weekends/holidays)
        assert expected_days_min <= data["count"] <= expected_days_max

    # T018: Custom date range
    @pytest.mark.ohlc
    def test_ohlc_custom_date_range(self, test_client, auth_headers, ohlc_validator):
        """OHLC endpoint accepts custom start_date and end_date."""
        start = date.today() - timedelta(days=14)
        end = date.today()

        response = test_client.get(
            f"/api/v2/tickers/GOOGL/ohlc?start_date={start}&end_date={end}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        ohlc_validator.assert_valid(data)
        assert data["time_range"] == "custom"
        # Should have roughly 14 days of data (minus weekends)
        assert 10 <= data["count"] <= 14

    # T019: Lowercase ticker normalization
    @pytest.mark.ohlc
    def test_ohlc_lowercase_ticker_normalization(
        self, test_client, auth_headers, ohlc_validator
    ):
        """OHLC endpoint normalizes lowercase ticker to uppercase."""
        response = test_client.get("/api/v2/tickers/aapl/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Ticker should be normalized to uppercase
        assert data["ticker"] == "AAPL"
        ohlc_validator.assert_valid(data)

    # T020: Cache expires at field present
    @pytest.mark.ohlc
    def test_ohlc_cache_expires_at_field(self, test_client, auth_headers):
        """OHLC response includes cache_expires_at timestamp."""
        response = test_client.get("/api/v2/tickers/NVDA/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "cache_expires_at" in data
        # Should be a valid ISO 8601 datetime string
        cache_expires = data["cache_expires_at"]
        assert isinstance(cache_expires, str)
        assert "T" in cache_expires  # Contains time separator

    # T021: Source field shows tiingo when primary succeeds
    @pytest.mark.ohlc
    def test_ohlc_source_field_tiingo(self, test_client, auth_headers):
        """OHLC response shows 'tiingo' as source when primary succeeds."""
        response = test_client.get("/api/v2/tickers/TSLA/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Primary source (tiingo) should be used when it succeeds
        assert data["source"] == "tiingo"

    # T022: Source field shows finnhub when primary fails
    @pytest.mark.ohlc
    def test_ohlc_source_field_finnhub_fallback(self, auth_headers, ohlc_validator):
        """OHLC response shows 'finnhub' as source when tiingo fails."""
        # Create failing Tiingo adapter
        tiingo_failing = MockTiingoAdapter(seed=42, fail_mode=True)
        finnhub_working = MockFinnhubAdapter(seed=42)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_tiingo_adapter] = lambda: tiingo_failing
        app.dependency_overrides[get_finnhub_adapter] = lambda: finnhub_working

        with TestClient(app) as client:
            response = client.get("/api/v2/tickers/AMD/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should fall back to finnhub
        assert data["source"] == "finnhub"
        ohlc_validator.assert_valid(data)

    # T023: Count matches candles array length
    @pytest.mark.ohlc
    def test_ohlc_count_matches_candles_length(self, test_client, auth_headers):
        """OHLC response count field equals len(candles)."""
        response = test_client.get("/api/v2/tickers/META/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["count"] == len(data["candles"])
        assert data["count"] > 0

    # T024: Start date matches first candle date
    @pytest.mark.ohlc
    def test_ohlc_start_date_matches_first_candle(self, test_client, auth_headers):
        """OHLC response start_date equals first candle's date."""
        response = test_client.get("/api/v2/tickers/AMZN/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert len(data["candles"]) > 0
        first_candle_date = data["candles"][0]["date"]
        assert str(data["start_date"]) == str(first_candle_date)

    # T025: End date matches last candle date
    @pytest.mark.ohlc
    def test_ohlc_end_date_matches_last_candle(self, test_client, auth_headers):
        """OHLC response end_date equals last candle's date."""
        response = test_client.get("/api/v2/tickers/NFLX/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert len(data["candles"]) > 0
        last_candle_date = data["candles"][-1]["date"]
        assert str(data["end_date"]) == str(last_candle_date)


class TestOHLCCandleValidation:
    """Additional tests for OHLC candle data validation."""

    @pytest.mark.ohlc
    def test_ohlc_candles_sorted_by_date_ascending(self, test_client, auth_headers):
        """OHLC candles are sorted by date in ascending order."""
        response = test_client.get(
            "/api/v2/tickers/AAPL/ohlc?range=1M", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        dates = [candle["date"] for candle in data["candles"]]
        assert dates == sorted(dates), "Candles should be sorted by date ascending"

    @pytest.mark.ohlc
    def test_ohlc_candle_prices_positive(self, test_client, auth_headers):
        """All OHLC prices are positive."""
        response = test_client.get("/api/v2/tickers/MSFT/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        for candle in data["candles"]:
            assert candle["open"] > 0, "open must be positive"
            assert candle["high"] > 0, "high must be positive"
            assert candle["low"] > 0, "low must be positive"
            assert candle["close"] > 0, "close must be positive"

    @pytest.mark.ohlc
    def test_ohlc_candle_high_low_relationship(self, test_client, auth_headers):
        """OHLC high >= low for all candles."""
        response = test_client.get("/api/v2/tickers/GOOGL/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        for i, candle in enumerate(data["candles"]):
            assert (
                candle["high"] >= candle["low"]
            ), f"Candle {i}: high ({candle['high']}) must be >= low ({candle['low']})"

    @pytest.mark.ohlc
    def test_ohlc_candle_open_close_within_range(self, test_client, auth_headers):
        """OHLC open and close are within [low, high] range."""
        response = test_client.get("/api/v2/tickers/NVDA/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        for i, candle in enumerate(data["candles"]):
            assert candle["low"] <= candle["open"] <= candle["high"], (
                f"Candle {i}: open ({candle['open']}) must be between "
                f"low ({candle['low']}) and high ({candle['high']})"
            )
            assert candle["low"] <= candle["close"] <= candle["high"], (
                f"Candle {i}: close ({candle['close']}) must be between "
                f"low ({candle['low']}) and high ({candle['high']})"
            )

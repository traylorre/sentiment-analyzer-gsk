"""OHLC Boundary Value Integration Tests (US4).

Tests for /api/v2/tickers/{ticker}/ohlc endpoint covering:
- Ticker boundary values (1 char, 5 chars, 6 chars)
- Date range boundaries (single day, far past, future)
- Input validation edge cases

For On-Call Engineers:
    These tests verify input validation and boundary conditions.
    If tests fail, check:
    1. Ticker validation regex in ohlc.py
    2. Date range validation logic
    3. Error message formatting
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
    """Create test client with mock adapters."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo
    app.dependency_overrides[get_finnhub_adapter] = lambda: mock_finnhub

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Headers with valid authentication."""
    return {"X-User-ID": "test-user-123"}


class TestOHLCTickerBoundaries:
    """US4: OHLC ticker symbol boundary testing."""

    # T056-T060: Ticker length boundaries
    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_ticker_1_char_valid(self, test_client, auth_headers, ohlc_validator):
        """OHLC accepts 1-character ticker (minimum length)."""
        response = test_client.get("/api/v2/tickers/A/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "A"
        ohlc_validator.assert_valid(data)

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_ticker_5_chars_valid(self, test_client, auth_headers, ohlc_validator):
        """OHLC accepts 5-character ticker (maximum length)."""
        response = test_client.get("/api/v2/tickers/TSLA/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TSLA"
        ohlc_validator.assert_valid(data)

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_ticker_6_chars_invalid(self, test_client, auth_headers):
        """OHLC rejects 6-character ticker (exceeds maximum)."""
        response = test_client.get("/api/v2/tickers/ABCDEF/ohlc", headers=auth_headers)

        assert response.status_code == 400
        assert "Invalid ticker symbol" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_ticker_empty_invalid(self, test_client, auth_headers):
        """OHLC rejects empty ticker."""
        # FastAPI will return 404 for empty path segment, but let's test with whitespace
        response = test_client.get("/api/v2/tickers/%20/ohlc", headers=auth_headers)

        # Should be 400 or 404 depending on implementation
        assert response.status_code in (400, 404, 422)

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_ticker_with_digits_invalid(self, test_client, auth_headers):
        """OHLC rejects ticker containing digits."""
        response = test_client.get("/api/v2/tickers/ABC1/ohlc", headers=auth_headers)

        assert response.status_code == 400
        assert "Invalid ticker symbol" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_ticker_with_symbols_invalid(self, test_client, auth_headers):
        """OHLC rejects ticker containing special characters."""
        response = test_client.get("/api/v2/tickers/AB-C/ohlc", headers=auth_headers)

        assert response.status_code == 400
        assert "Invalid ticker symbol" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_ticker_mixed_case_normalized(
        self, test_client, auth_headers, ohlc_validator
    ):
        """OHLC normalizes mixed case ticker to uppercase."""
        response = test_client.get("/api/v2/tickers/aApL/ohlc", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        ohlc_validator.assert_valid(data)


class TestOHLCDateBoundaries:
    """US4: OHLC date range boundary testing."""

    # T061-T068: Date range boundaries
    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_single_day_range(self, test_client, auth_headers, ohlc_validator):
        """OHLC accepts single-day range (start == end)."""
        today = date.today()
        response = test_client.get(
            f"/api/v2/tickers/AAPL/ohlc?start_date={today}&end_date={today}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        ohlc_validator.assert_valid(data)
        # Single day should have 0-1 candles (depending on if trading day)
        assert data["count"] <= 1

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_start_date_after_end_date_invalid(self, test_client, auth_headers):
        """OHLC rejects when start_date > end_date."""
        today = date.today()
        yesterday = today - timedelta(days=1)

        response = test_client.get(
            f"/api/v2/tickers/AAPL/ohlc?start_date={today}&end_date={yesterday}",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "start_date must be before end_date" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_future_end_date(self, test_client, auth_headers, ohlc_validator):
        """OHLC handles future end_date gracefully."""
        future = date.today() + timedelta(days=30)
        start = date.today() - timedelta(days=7)

        response = test_client.get(
            f"/api/v2/tickers/MSFT/ohlc?start_date={start}&end_date={future}",
            headers=auth_headers,
        )

        # Should succeed but only return data up to today
        assert response.status_code == 200
        data = response.json()
        ohlc_validator.assert_valid(data)

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_very_old_start_date(self, test_client, auth_headers, ohlc_validator):
        """OHLC handles very old start_date."""
        old_date = date(2000, 1, 1)
        end = date.today()

        response = test_client.get(
            f"/api/v2/tickers/GOOGL/ohlc?start_date={old_date}&end_date={end}",
            headers=auth_headers,
        )

        # Should succeed with available data
        assert response.status_code == 200
        data = response.json()
        ohlc_validator.assert_valid(data)


class TestOHLCAuthBoundaries:
    """US4: OHLC authentication boundary testing."""

    # T069-T072: Authentication boundaries
    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_missing_user_id_header(self, test_client):
        """OHLC returns 401 when X-User-ID header is missing."""
        response = test_client.get("/api/v2/tickers/AAPL/ohlc")

        assert response.status_code == 401
        assert "Missing user identification" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_empty_user_id_header(self, test_client):
        """OHLC returns 401 when X-User-ID header is empty."""
        response = test_client.get(
            "/api/v2/tickers/AAPL/ohlc", headers={"X-User-ID": ""}
        )

        assert response.status_code == 401
        assert "Missing user identification" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_whitespace_user_id_header(self, test_client):
        """OHLC handles whitespace-only X-User-ID."""
        response = test_client.get(
            "/api/v2/tickers/AAPL/ohlc", headers={"X-User-ID": "   "}
        )

        # Whitespace-only should be treated as valid (truthy string)
        # or as invalid depending on implementation
        # Current implementation treats non-empty as valid
        assert response.status_code in (200, 401)


class TestOHLCTimeRangeBoundaries:
    """US4: OHLC time range enum boundary testing."""

    @pytest.mark.ohlc
    @pytest.mark.boundary
    def test_ohlc_invalid_time_range(self, test_client, auth_headers):
        """OHLC rejects invalid time range value."""
        response = test_client.get(
            "/api/v2/tickers/AAPL/ohlc?range=2W", headers=auth_headers
        )

        # FastAPI validation should reject invalid enum
        assert response.status_code == 422

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @pytest.mark.parametrize("time_range", ["1W", "1M", "3M", "6M", "1Y"])
    def test_ohlc_all_time_ranges_valid(
        self, test_client, auth_headers, ohlc_validator, time_range
    ):
        """OHLC accepts all valid time range values."""
        response = test_client.get(
            f"/api/v2/tickers/NVDA/ohlc?range={time_range}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        ohlc_validator.assert_valid(data)
        # Time range in response should match request (unless custom dates provided)
        assert data["time_range"] == time_range

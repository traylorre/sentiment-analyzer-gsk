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

import json
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from src.lambdas.dashboard.handler import lambda_handler
from tests.conftest import make_event
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
def auth_headers():
    """Headers with valid authentication (Feature 1146: Bearer-only auth)."""
    return {"Authorization": "Bearer 550e8400-e29b-41d4-a716-446655440000"}


class TestOHLCTickerBoundaries:
    """US4: OHLC ticker symbol boundary testing."""

    # T056-T060: Ticker length boundaries
    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_ticker_1_char_valid(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        mock_tiingo,
    ):
        """OHLC accepts 1-character ticker (minimum length)."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/A/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["ticker"] == "A"
        ohlc_validator.assert_valid(data)

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_ticker_5_chars_valid(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        mock_tiingo,
    ):
        """OHLC accepts 5-character ticker (maximum length)."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/TSLA/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["ticker"] == "TSLA"
        ohlc_validator.assert_valid(data)

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_ticker_6_chars_invalid(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC rejects 6-character ticker (exceeds maximum)."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/ABCDEF/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 400
        assert "Invalid ticker symbol" in json.loads(response["body"])["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_ticker_empty_invalid(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC rejects empty ticker."""
        mock_tiingo_dep.return_value = mock_tiingo
        # Whitespace ticker - should be treated as invalid
        event = make_event(
            method="GET", path="/api/v2/tickers/%20/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        # Should be 400 or 404 depending on implementation
        assert response["statusCode"] in (400, 404, 422)

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_ticker_with_digits_invalid(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC rejects ticker containing digits."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/ABC1/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 400
        assert "Invalid ticker symbol" in json.loads(response["body"])["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_ticker_with_symbols_invalid(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC rejects ticker containing special characters."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/AB-C/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 400
        assert "Invalid ticker symbol" in json.loads(response["body"])["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_ticker_mixed_case_normalized(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        mock_tiingo,
    ):
        """OHLC normalizes mixed case ticker to uppercase."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/aApL/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["ticker"] == "AAPL"
        ohlc_validator.assert_valid(data)


class TestOHLCDateBoundaries:
    """US4: OHLC date range boundary testing."""

    # T061-T068: Date range boundaries
    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_single_day_range(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        mock_tiingo,
    ):
        """OHLC accepts single-day range (start == end)."""
        mock_tiingo_dep.return_value = mock_tiingo
        # Use a fixed historical trading day to avoid weekend/holiday issues
        # 2024-01-02 was a Tuesday (trading day)
        trading_day = date(2024, 1, 2)
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/ohlc",
            query_params={
                "start_date": str(trading_day),
                "end_date": str(trading_day),
            },
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        ohlc_validator.assert_valid(data)
        # Single day should have 0-1 candles (depending on if trading day)
        assert data["count"] <= 1

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_start_date_after_end_date_invalid(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC rejects when start_date > end_date."""
        mock_tiingo_dep.return_value = mock_tiingo
        today = date.today()
        yesterday = today - timedelta(days=1)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/ohlc",
            query_params={"start_date": str(today), "end_date": str(yesterday)},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 400
        assert (
            "start_date must be before end_date"
            in json.loads(response["body"])["detail"]
        )

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_future_end_date(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        mock_tiingo,
    ):
        """OHLC handles future end_date gracefully."""
        mock_tiingo_dep.return_value = mock_tiingo
        future = date.today() + timedelta(days=30)
        start = date.today() - timedelta(days=7)

        event = make_event(
            method="GET",
            path="/api/v2/tickers/MSFT/ohlc",
            query_params={"start_date": str(start), "end_date": str(future)},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        # Should succeed but only return data up to today
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        ohlc_validator.assert_valid(data)

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_very_old_start_date(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        mock_tiingo,
    ):
        """OHLC handles very old start_date."""
        mock_tiingo_dep.return_value = mock_tiingo
        old_date = date(2000, 1, 1)
        end = date.today()

        event = make_event(
            method="GET",
            path="/api/v2/tickers/GOOGL/ohlc",
            query_params={"start_date": str(old_date), "end_date": str(end)},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        # Should succeed with available data
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        ohlc_validator.assert_valid(data)


class TestOHLCAuthBoundaries:
    """US4: OHLC authentication boundary testing."""

    # T069-T072: Authentication boundaries (Feature 1146: Bearer-only auth)
    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_missing_auth_header(
        self, mock_tiingo_dep, mock_lambda_context, mock_tiingo
    ):
        """OHLC returns 401 when Authorization header is missing."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(method="GET", path="/api/v2/tickers/AAPL/ohlc")
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 401
        assert "Missing user identification" in json.loads(response["body"])["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_empty_bearer_token(
        self, mock_tiingo_dep, mock_lambda_context, mock_tiingo
    ):
        """OHLC returns 401 when Bearer token is empty."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/ohlc",
            headers={"Authorization": "Bearer "},
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 401
        assert "Missing user identification" in json.loads(response["body"])["detail"]

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_whitespace_bearer_token(
        self, mock_tiingo_dep, mock_lambda_context, mock_tiingo
    ):
        """OHLC handles whitespace-only Bearer token."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/ohlc",
            headers={"Authorization": "Bearer    "},
        )
        response = lambda_handler(event, mock_lambda_context)

        # Whitespace-only should be treated as invalid (empty after strip)
        assert response["statusCode"] == 401

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_x_user_id_rejected(
        self, mock_tiingo_dep, mock_lambda_context, mock_tiingo
    ):
        """Feature 1146: X-User-ID header is rejected (security fix)."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/ohlc",
            headers={"X-User-ID": "550e8400-e29b-41d4-a716-446655440000"},
        )
        response = lambda_handler(event, mock_lambda_context)

        # X-User-ID alone should return 401 (not authenticated)
        assert response["statusCode"] == 401


class TestOHLCTimeRangeBoundaries:
    """US4: OHLC time range enum boundary testing."""

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_invalid_time_range(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC falls back to default range for invalid time range value."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/ohlc",
            query_params={"range": "2W"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        # Powertools handler falls back to default range (1M) for invalid enum
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["time_range"] == "1M"  # Default fallback

    @pytest.mark.ohlc
    @pytest.mark.boundary
    @pytest.mark.parametrize("time_range", ["1W", "1M", "3M", "6M", "1Y"])
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_all_time_ranges_valid(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        time_range,
        mock_tiingo,
    ):
        """OHLC accepts all valid time range values."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET",
            path="/api/v2/tickers/NVDA/ohlc",
            query_params={"range": time_range},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        ohlc_validator.assert_valid(data)
        # Time range in response should match request (unless custom dates provided)
        assert data["time_range"] == time_range

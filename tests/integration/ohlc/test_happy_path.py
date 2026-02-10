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
    2. Mock patches for get_tiingo_adapter are correct
    3. Response model serialization is correct
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


class TestOHLCHappyPath:
    """US1: OHLC Happy Path Validation tests."""

    # T016: Valid ticker with default parameters
    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_valid_ticker_default_params(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        mock_tiingo,
    ):
        """OHLC endpoint returns valid data for ticker with default params."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/AAPL/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        # Validate response structure and business rules
        ohlc_validator.assert_valid(data)

        # Verify default values
        assert data["ticker"] == "AAPL"
        assert data["time_range"] == "1M"  # Default range
        assert data["source"] in ("tiingo", "finnhub")
        assert data["count"] > 0
        assert len(data["candles"]) == data["count"]

    # T016b: Intraday resolutions (Feature 1056)
    @pytest.mark.ohlc
    @pytest.mark.parametrize(
        "resolution",
        ["1", "5", "15", "30", "60"],
        ids=["1min", "5min", "15min", "30min", "60min"],
    )
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_intraday_resolutions(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        resolution,
        mock_tiingo,
    ):
        """OHLC endpoint returns valid data for intraday resolutions (Feature 1056)."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/ohlc",
            query_params={"resolution": resolution, "range": "1W"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        ohlc_validator.assert_valid(data)
        assert data["ticker"] == "AAPL"
        # Resolution should match requested or fallback to daily
        assert data["resolution"] in (resolution, "D")
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
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_time_ranges(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        time_range,
        expected_days_min,
        expected_days_max,
        mock_tiingo,
    ):
        """OHLC endpoint returns appropriate data for each time range."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET",
            path="/api/v2/tickers/MSFT/ohlc",
            query_params={"range": time_range},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        ohlc_validator.assert_valid(data)
        assert data["time_range"] == time_range
        # Count should be within expected range (accounting for weekends/holidays)
        assert expected_days_min <= data["count"] <= expected_days_max

    # T018: Custom date range
    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_custom_date_range(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        mock_tiingo,
    ):
        """OHLC endpoint accepts custom start_date and end_date."""
        mock_tiingo_dep.return_value = mock_tiingo
        start = date.today() - timedelta(days=14)
        end = date.today()

        event = make_event(
            method="GET",
            path="/api/v2/tickers/GOOGL/ohlc",
            query_params={"start_date": str(start), "end_date": str(end)},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        ohlc_validator.assert_valid(data)
        assert data["time_range"] == "custom"
        # Should have roughly 14 days of data (minus weekends)
        assert 10 <= data["count"] <= 14

    # T019: Lowercase ticker normalization
    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_lowercase_ticker_normalization(
        self,
        mock_tiingo_dep,
        mock_lambda_context,
        auth_headers,
        ohlc_validator,
        mock_tiingo,
    ):
        """OHLC endpoint normalizes lowercase ticker to uppercase."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/aapl/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        # Ticker should be normalized to uppercase
        assert data["ticker"] == "AAPL"
        ohlc_validator.assert_valid(data)

    # T020: Cache expires at field present
    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_cache_expires_at_field(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC response includes cache_expires_at timestamp."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/NVDA/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        assert "cache_expires_at" in data
        # Should be a valid ISO 8601 datetime string
        cache_expires = data["cache_expires_at"]
        assert isinstance(cache_expires, str)
        assert "T" in cache_expires  # Contains time separator

    # T021: Source field shows tiingo when primary succeeds
    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_source_field_tiingo(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC response shows 'tiingo' as source when primary succeeds."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/TSLA/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        # Primary source (tiingo) should be used when it succeeds
        assert data["source"] == "tiingo"

    # T022: Returns 404 when Tiingo fails (Feature 1055: no Finnhub fallback)
    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_returns_404_when_tiingo_fails(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers
    ):
        """OHLC returns 404 when tiingo fails (Feature 1055: no Finnhub fallback for OHLC)."""
        # Create failing Tiingo adapter
        tiingo_failing = MockTiingoAdapter(seed=42, fail_mode=True)
        mock_tiingo_dep.return_value = tiingo_failing

        event = make_event(
            method="GET", path="/api/v2/tickers/AMD/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        # Feature 1055: No Finnhub fallback - Tiingo failure returns 404
        assert response["statusCode"] == 404
        assert "No price data available" in json.loads(response["body"])["detail"]

    # T023: Count matches candles array length
    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_count_matches_candles_length(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC response count field equals len(candles)."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/META/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        assert data["count"] == len(data["candles"])
        assert data["count"] > 0

    # T024: Start date matches first candle date
    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_start_date_matches_first_candle(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC response start_date equals first candle's date."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/AMZN/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        assert len(data["candles"]) > 0
        first_candle_date = data["candles"][0]["date"]
        assert str(data["start_date"]) == str(first_candle_date)

    # T025: End date matches last candle date
    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_end_date_matches_last_candle(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC response end_date equals last candle's date."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/NFLX/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        assert len(data["candles"]) > 0
        last_candle_date = data["candles"][-1]["date"]
        assert str(data["end_date"]) == str(last_candle_date)


class TestOHLCCandleValidation:
    """Additional tests for OHLC candle data validation."""

    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_candles_sorted_by_date_ascending(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC candles are sorted by date in ascending order."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/ohlc",
            query_params={"range": "1M"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        dates = [candle["date"] for candle in data["candles"]]
        assert dates == sorted(dates), "Candles should be sorted by date ascending"

    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_candle_prices_positive(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """All OHLC prices are positive."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/MSFT/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        for candle in data["candles"]:
            assert candle["open"] > 0, "open must be positive"
            assert candle["high"] > 0, "high must be positive"
            assert candle["low"] > 0, "low must be positive"
            assert candle["close"] > 0, "close must be positive"

    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_candle_high_low_relationship(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC high >= low for all candles."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/GOOGL/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        for i, candle in enumerate(data["candles"]):
            assert (
                candle["high"] >= candle["low"]
            ), f"Candle {i}: high ({candle['high']}) must be >= low ({candle['low']})"

    @pytest.mark.ohlc
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_ohlc_candle_open_close_within_range(
        self, mock_tiingo_dep, mock_lambda_context, auth_headers, mock_tiingo
    ):
        """OHLC open and close are within [low, high] range."""
        mock_tiingo_dep.return_value = mock_tiingo
        event = make_event(
            method="GET", path="/api/v2/tickers/NVDA/ohlc", headers=auth_headers
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])

        for i, candle in enumerate(data["candles"]):
            assert candle["low"] <= candle["open"] <= candle["high"], (
                f"Candle {i}: open ({candle['open']}) must be between "
                f"low ({candle['low']}) and high ({candle['high']})"
            )
            assert candle["low"] <= candle["close"] <= candle["high"], (
                f"Candle {i}: close ({candle['close']}) must be between "
                f"low ({candle['low']}) and high ({candle['high']})"
            )

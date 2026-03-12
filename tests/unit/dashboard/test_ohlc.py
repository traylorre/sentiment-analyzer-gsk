"""Unit tests for OHLC endpoint (Feature 011)."""

import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.handler import lambda_handler
from src.lambdas.shared.adapters.base import OHLCCandle
from src.lambdas.shared.models import RESOLUTION_MAX_DAYS, OHLCResolution, TimeRange
from tests.conftest import make_event


@pytest.fixture(autouse=True)
def clear_ohlc_cache():
    """Clear OHLC cache before and after each test to ensure test isolation."""
    import src.lambdas.dashboard.ohlc as ohlc_module

    ohlc_module._ohlc_cache.clear()
    ohlc_module._ohlc_cache_stats["hits"] = 0
    ohlc_module._ohlc_cache_stats["misses"] = 0
    ohlc_module._ohlc_cache_stats["evictions"] = 0
    yield
    ohlc_module._ohlc_cache.clear()
    ohlc_module._ohlc_cache_stats["hits"] = 0
    ohlc_module._ohlc_cache_stats["misses"] = 0
    ohlc_module._ohlc_cache_stats["evictions"] = 0


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


class TestOHLCEndpoint:
    """Tests for GET /api/v2/tickers/{ticker}/ohlc endpoint."""

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_returns_ohlc_response(self, mock_get_tiingo, mock_lambda_context):
        """Should return OHLCResponse with candles."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["ticker"] == "AAPL"
        assert "candles" in data
        assert data["count"] > 0
        assert data["source"] == "tiingo"

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_validates_user_id_header(self, mock_get_tiingo, mock_lambda_context):
        """Should require X-User-ID header."""
        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 401
        assert "Missing user identification" in json.loads(response["body"])["detail"]

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_validates_ticker_symbol(self, mock_get_tiingo, mock_lambda_context):
        """Should reject invalid ticker symbols."""
        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/INVALID123/ohlc",
                path_params={"ticker": "INVALID123"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 400
        assert "Invalid ticker symbol" in json.loads(response["body"])["detail"]

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_returns_404_when_tiingo_fails(self, mock_get_tiingo, mock_lambda_context):
        """Should return 404 if Tiingo daily fails (no Finnhub fallback).

        Feature 1055: Finnhub free tier doesn't support stock candles (403 error),
        so we use Tiingo exclusively. If Tiingo fails, return 404.
        """
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.side_effect = Exception("Tiingo error")
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 404
        assert "No price data available" in json.loads(response["body"])["detail"]

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_returns_404_when_no_data(self, mock_get_tiingo, mock_lambda_context):
        """Should return 404 when no data available."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = []
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 404
        assert "No price data available" in json.loads(response["body"])["detail"]

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_supports_time_range_param(self, mock_get_tiingo, mock_lambda_context):
        """Should support time range query parameter."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(90)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                query_params={"range": "3M"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        assert json.loads(response["body"])["time_range"] == "3M"

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_supports_custom_date_range(self, mock_get_tiingo, mock_lambda_context):
        """Should support custom start_date and end_date."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(30)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                query_params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        assert json.loads(response["body"])["time_range"] == "custom"

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_validates_date_range_order(self, mock_get_tiingo, mock_lambda_context):
        """Should reject when start_date is after end_date."""
        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                query_params={"start_date": "2024-12-31", "end_date": "2024-01-01"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 400
        assert (
            "start_date must be before end_date"
            in json.loads(response["body"])["detail"]
        )

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_includes_cache_expiration(self, mock_get_tiingo, mock_lambda_context):
        """Should include cache_expires_at in response."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        assert "cache_expires_at" in json.loads(response["body"])

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_normalizes_ticker_to_uppercase(self, mock_get_tiingo, mock_lambda_context):
        """Should normalize ticker to uppercase."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/aapl/ohlc",
                path_params={"ticker": "aapl"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        assert json.loads(response["body"])["ticker"] == "AAPL"


def _get_header(response: dict, name: str) -> str | None:
    """Extract a header value from Lambda response (handles multiValueHeaders)."""
    # Lambda Powertools may use multiValueHeaders (lists) or headers (strings)
    mv = response.get("multiValueHeaders", {})
    if name in mv:
        val = mv[name]
        return val[0] if isinstance(val, list) else val
    h = response.get("headers", {})
    if name in h:
        val = h[name]
        return val[0] if isinstance(val, list) else val
    return None


class TestCacheDegradation:
    """Tests for explicit cache degradation (Feature 1218, US1).

    When DynamoDB is broken, the handler MUST:
    - Log ERROR
    - Fetch from Tiingo (explicit degradation)
    - Return 200 with X-Cache-Source: live-api-degraded and X-Cache-Error headers
    """

    @patch("src.lambdas.dashboard.ohlc._read_from_dynamodb")
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_cache_read_error_returns_degraded_headers(
        self, mock_get_tiingo, mock_read_ddb, mock_lambda_context
    ):
        """T007: When get_cached_candles raises, response has degraded headers."""
        from botocore.exceptions import ClientError

        mock_read_ddb.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}},
            "Query",
        )
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        assert _get_header(response, "X-Cache-Source") == "live-api-degraded"
        assert _get_header(response, "X-Cache-Error") is not None
        assert "AccessDeniedException" in _get_header(response, "X-Cache-Error")
        assert _get_header(response, "X-Cache-Age") == "0"

    @patch("src.lambdas.dashboard.ohlc._read_from_dynamodb")
    @patch("src.lambdas.dashboard.ohlc._write_through_to_dynamodb")
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_cache_write_error_returns_write_error_header(
        self, mock_get_tiingo, mock_write_ddb, mock_read_ddb, mock_lambda_context
    ):
        """T008: When put_cached_candles raises, response has X-Cache-Write-Error."""
        from botocore.exceptions import ClientError

        mock_read_ddb.return_value = None  # Normal cache miss
        mock_write_ddb.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "Throttled",
                }
            },
            "BatchWriteItem",
        )
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        assert _get_header(response, "X-Cache-Write-Error") == "true"
        # Data should still be returned
        data = json.loads(response["body"])
        assert data["count"] > 0

    @patch("src.lambdas.dashboard.ohlc._read_from_dynamodb")
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_cache_read_error_still_returns_data(
        self, mock_get_tiingo, mock_read_ddb, mock_lambda_context
    ):
        """T009: Degraded response still contains valid OHLC data from Tiingo."""
        from botocore.exceptions import ClientError

        mock_read_ddb.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "Query",
        )
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["ticker"] == "AAPL"
        assert data["count"] > 0
        assert len(data["candles"]) > 0


class TestCacheObservabilityHeaders:
    """Tests for cache observability headers (Feature 1218, US2).

    Every OHLC response MUST include X-Cache-Source and X-Cache-Age headers.
    """

    @patch("src.lambdas.dashboard.ohlc._write_through_to_dynamodb")
    @patch("src.lambdas.dashboard.ohlc._read_from_dynamodb")
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_in_memory_cache_hit_headers(
        self, mock_get_tiingo, mock_read_ddb, mock_write_ddb, mock_lambda_context
    ):
        """T015: In-memory cache hit has X-Cache-Source: in-memory.

        Uses custom date range so the cache lookup key (start_date, end_date)
        matches the storage key (derived from candle dates).  With predefined
        ranges the lookup key uses today + offset, but the storage key uses
        candle[0].date / candle[-1].date which differ — causing a miss.
        """
        mock_read_ddb.return_value = None  # Normal cache miss
        mock_write_ddb.return_value = None  # Write succeeds silently

        # Create candles spanning a known date range
        start = date.today() - timedelta(days=10)
        end = date.today() - timedelta(days=1)
        candles = _create_ohlc_candles(10, start_date=start)

        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = candles
        mock_get_tiingo.return_value = mock_tiingo

        event = make_event(
            method="GET",
            path="/api/v2/tickers/AAPL/ohlc",
            path_params={"ticker": "AAPL"},
            query_params={
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
            headers={"Authorization": f"Bearer {TEST_USER_ID}"},
        )

        # First request — populates in-memory cache
        lambda_handler(event, mock_lambda_context)
        # Second request — should hit in-memory cache
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        assert _get_header(response, "X-Cache-Source") == "in-memory"
        # Age should be >= 0 (test runs fast, may be 0)
        assert int(_get_header(response, "X-Cache-Age") or "-1") >= 0

    @patch("src.lambdas.dashboard.ohlc._write_through_to_dynamodb")
    @patch("src.lambdas.dashboard.ohlc._read_from_dynamodb")
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_persistent_cache_hit_headers(
        self, mock_get_tiingo, mock_read_ddb, mock_write_ddb, mock_lambda_context
    ):
        """T016: Persistent cache hit has X-Cache-Source: persistent-cache."""
        from src.lambdas.shared.models import PriceCandle

        # _read_from_dynamodb returns PriceCandle list when cache hits
        start = date.today() - timedelta(days=10)
        candles = [
            PriceCandle(
                date=start + timedelta(days=i),
                open=100 + i,
                high=102 + i,
                low=99 + i,
                close=101 + i,
                volume=1000000,
            )
            for i in range(10)
        ]
        mock_read_ddb.return_value = candles
        mock_write_ddb.return_value = None
        mock_tiingo = MagicMock()
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        assert _get_header(response, "X-Cache-Source") == "persistent-cache"
        assert _get_header(response, "X-Cache-Age") is not None
        # Tiingo should NOT be called — data came from persistent cache
        mock_tiingo.get_ohlc.assert_not_called()

    @patch("src.lambdas.dashboard.ohlc._read_from_dynamodb")
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_live_api_fetch_headers(
        self, mock_get_tiingo, mock_read_ddb, mock_lambda_context
    ):
        """T017: Live API fetch has X-Cache-Source: live-api and X-Cache-Age: 0."""
        mock_read_ddb.return_value = None  # Normal cache miss
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        assert _get_header(response, "X-Cache-Source") == "live-api"
        assert _get_header(response, "X-Cache-Age") == "0"

    @patch("src.lambdas.dashboard.ohlc._read_from_dynamodb")
    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_degraded_response_headers(
        self, mock_get_tiingo, mock_read_ddb, mock_lambda_context
    ):
        """T018: Degraded response has X-Cache-Source: live-api-degraded + X-Cache-Error."""
        from botocore.exceptions import ClientError

        mock_read_ddb.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}},
            "Query",
        )
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        assert _get_header(response, "X-Cache-Source") == "live-api-degraded"
        assert _get_header(response, "X-Cache-Error") is not None
        assert _get_header(response, "X-Cache-Age") == "0"


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

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_accepts_resolution_parameter(self, mock_get_tiingo, mock_lambda_context):
        """Should accept resolution query parameter.

        Feature 1055: Tiingo IEX is used for intraday resolutions.
        """
        mock_tiingo = MagicMock()
        mock_tiingo.get_intraday_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                query_params={"resolution": "5"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["resolution"] == "5"

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_default_resolution_is_daily(self, mock_get_tiingo, mock_lambda_context):
        """Should default to daily resolution."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["resolution"] == "D"

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_uses_tiingo_iex_for_intraday(self, mock_get_tiingo, mock_lambda_context):
        """Should use Tiingo IEX for intraday resolutions.

        Feature 1055: Finnhub free tier returns 403 for stock candles,
        so we use Tiingo IEX endpoint for all intraday resolutions.
        """
        mock_tiingo = MagicMock()
        mock_tiingo.get_intraday_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                query_params={"resolution": "5"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        # Tiingo IEX should be called for intraday
        mock_tiingo.get_intraday_ohlc.assert_called_once()
        # Tiingo daily should not be called for intraday
        mock_tiingo.get_ohlc.assert_not_called()

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_resolution_response_includes_fallback_fields(
        self, mock_get_tiingo, mock_lambda_context
    ):
        """Should include resolution_fallback and fallback_message in response."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert "resolution_fallback" in data
        assert data["resolution_fallback"] is False
        assert data["fallback_message"] is None

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_fallback_to_daily_when_intraday_unavailable(
        self, mock_get_tiingo, mock_lambda_context
    ):
        """Should fall back to daily when intraday data unavailable.

        Feature 1055: When Tiingo IEX returns no data for intraday,
        fall back to Tiingo daily endpoint.
        """
        mock_tiingo = MagicMock()
        # Return empty for intraday, return data for daily
        mock_tiingo.get_intraday_ohlc.return_value = []
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                query_params={"resolution": "5"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["resolution"] == "D"  # Fell back to daily
        assert data["resolution_fallback"] is True
        assert "unavailable" in data["fallback_message"].lower()

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    @pytest.mark.parametrize(
        "resolution",
        ["1", "5", "15", "30", "60", "D"],
    )
    def test_all_resolutions_accepted(
        self, mock_get_tiingo, resolution, mock_lambda_context
    ):
        """Should accept all valid resolution values.

        Feature 1055: Daily uses Tiingo daily, intraday uses Tiingo IEX.
        """
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_candles(10)
        mock_tiingo.get_intraday_ohlc.return_value = _create_ohlc_candles(10)
        mock_get_tiingo.return_value = mock_tiingo

        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                query_params={"resolution": resolution},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_invalid_resolution_rejected(self, mock_get_tiingo, mock_lambda_context):
        """Should reject invalid resolution values."""
        response = lambda_handler(
            make_event(
                method="GET",
                path="/api/v2/tickers/AAPL/ohlc",
                path_params={"ticker": "AAPL"},
                query_params={"resolution": "invalid"},
                headers={"Authorization": f"Bearer {TEST_USER_ID}"},
            ),
            mock_lambda_context,
        )

        assert response["statusCode"] == 422  # Validation error

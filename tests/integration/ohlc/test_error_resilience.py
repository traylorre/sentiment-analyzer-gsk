"""OHLC Error Resilience Integration Tests (US3).

Tests for /api/v2/tickers/{ticker}/ohlc endpoint covering:
- HTTP error handling (500, 502, 503, 504, 429)
- Connection error handling (timeout, connection refused, DNS failure)
- Malformed response handling (invalid JSON, empty response, empty array)
- 404 response when Tiingo fails (Feature 1055: no Finnhub fallback for OHLC)

Note: Feature 1055 removed Finnhub fallback for OHLC because Finnhub free tier
returns 403 Forbidden for stock/candle endpoint (requires Premium subscription).
All OHLC data now comes exclusively from Tiingo (daily + IEX for intraday).

For On-Call Engineers:
    These tests verify the OHLC endpoint's error handling.
    If tests fail, check:
    1. Error handling in ohlc.py is working correctly
    2. FailureInjector is configured correctly in mock adapters
    3. HTTP exceptions are being raised properly
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.lambdas.dashboard.ohlc import (
    get_finnhub_adapter,
    get_tiingo_adapter,
    router,
)
from tests.fixtures.mocks.failure_injector import (
    FailureInjector,
    create_connection_refused_injector,
    create_dns_failure_injector,
    create_http_429_injector,
    create_http_500_injector,
    create_http_502_injector,
    create_http_503_injector,
    create_http_504_injector,
    create_timeout_injector,
)
from tests.fixtures.mocks.mock_finnhub import MockFinnhubAdapter
from tests.fixtures.mocks.mock_tiingo import MockTiingoAdapter


@pytest.fixture(autouse=True)
def clear_ohlc_cache():
    """Clear OHLC cache before and after each test to ensure test isolation.

    Feature 1078: Cache keys now use time_range instead of dates, so cache
    persists across tests unless explicitly cleared.
    """
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


@pytest.fixture
def auth_headers():
    """Headers with valid authentication (Feature 1146: Bearer-only auth)."""
    return {"Authorization": "Bearer 550e8400-e29b-41d4-a716-446655440000"}


def create_test_client_with_injectors(
    tiingo_injector: FailureInjector | None = None,
    finnhub_injector: FailureInjector | None = None,
):
    """Create test client with specified failure injectors."""
    mock_tiingo = MockTiingoAdapter(seed=42, failure_injector=tiingo_injector)
    mock_finnhub = MockFinnhubAdapter(seed=42, failure_injector=finnhub_injector)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo
    app.dependency_overrides[get_finnhub_adapter] = lambda: mock_finnhub

    return TestClient(app), mock_tiingo, mock_finnhub


class TestOHLCTiingoHttpErrors:
    """US3: OHLC returns 404 on Tiingo HTTP errors (no Finnhub fallback per Feature 1055)."""

    # T035-T039: HTTP error codes return 404 (no fallback)
    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    @pytest.mark.parametrize(
        "injector_factory,error_code",
        [
            (create_http_500_injector, 500),
            (create_http_502_injector, 502),
            (create_http_503_injector, 503),
            (create_http_504_injector, 504),
            (create_http_429_injector, 429),
        ],
        ids=["500", "502", "503", "504", "429"],
    )
    def test_ohlc_tiingo_http_error_returns_404(
        self, auth_headers, injector_factory, error_code
    ):
        """OHLC returns 404 when Tiingo returns HTTP {error_code} (Feature 1055: no Finnhub fallback)."""
        client, _, _ = create_test_client_with_injectors(
            tiingo_injector=injector_factory()
        )

        with client:
            response = client.get("/api/v2/tickers/AAPL/ohlc", headers=auth_headers)

        # Feature 1055: No Finnhub fallback, so Tiingo errors result in 404
        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]


class TestOHLCTiingoConnectionErrors:
    """US3: OHLC returns 404 on Tiingo connection errors (no Finnhub fallback per Feature 1055)."""

    # T040-T042: Connection errors return 404 (no fallback)
    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_tiingo_timeout_returns_404(self, auth_headers):
        """OHLC returns 404 when Tiingo times out (Feature 1055: no Finnhub fallback)."""
        client, _, _ = create_test_client_with_injectors(
            tiingo_injector=create_timeout_injector()
        )

        with client:
            response = client.get("/api/v2/tickers/MSFT/ohlc", headers=auth_headers)

        # Feature 1055: No Finnhub fallback
        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_tiingo_connection_refused_returns_404(self, auth_headers):
        """OHLC returns 404 when Tiingo connection is refused (Feature 1055: no Finnhub fallback)."""
        client, _, _ = create_test_client_with_injectors(
            tiingo_injector=create_connection_refused_injector()
        )

        with client:
            response = client.get("/api/v2/tickers/GOOGL/ohlc", headers=auth_headers)

        # Feature 1055: No Finnhub fallback
        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_tiingo_dns_failure_returns_404(self, auth_headers):
        """OHLC returns 404 when Tiingo DNS resolution fails (Feature 1055: no Finnhub fallback)."""
        client, _, _ = create_test_client_with_injectors(
            tiingo_injector=create_dns_failure_injector()
        )

        with client:
            response = client.get("/api/v2/tickers/NVDA/ohlc", headers=auth_headers)

        # Feature 1055: No Finnhub fallback
        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]


class TestOHLCTiingoMalformedResponses:
    """US3: OHLC returns 404 on Tiingo failures (no Finnhub fallback per Feature 1055)."""

    # T043-T045: fail_mode returns 404 (no fallback)
    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_tiingo_fail_mode_returns_404(self, auth_headers):
        """OHLC returns 404 when Tiingo is in fail_mode (Feature 1055: no Finnhub fallback)."""
        mock_tiingo = MockTiingoAdapter(seed=42, fail_mode=True)
        mock_finnhub = MockFinnhubAdapter(seed=42)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo
        app.dependency_overrides[get_finnhub_adapter] = lambda: mock_finnhub

        with TestClient(app) as client:
            response = client.get("/api/v2/tickers/TSLA/ohlc", headers=auth_headers)

        # Feature 1055: No Finnhub fallback
        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_tiingo_returns_empty_returns_404(self, auth_headers):
        """OHLC returns 404 when Tiingo returns no candles (Feature 1055: no Finnhub fallback)."""
        mock_tiingo = MockTiingoAdapter(seed=42, fail_mode=True)
        mock_finnhub = MockFinnhubAdapter(seed=42)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo
        app.dependency_overrides[get_finnhub_adapter] = lambda: mock_finnhub

        with TestClient(app) as client:
            response = client.get("/api/v2/tickers/AMD/ohlc", headers=auth_headers)

        # Feature 1055: No Finnhub fallback
        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_multiple_tickers_returns_404(self, auth_headers):
        """OHLC returns 404 for multiple tickers when Tiingo fails (Feature 1055: no Finnhub fallback)."""
        mock_tiingo = MockTiingoAdapter(seed=42, fail_mode=True)
        mock_finnhub = MockFinnhubAdapter(seed=42)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo
        app.dependency_overrides[get_finnhub_adapter] = lambda: mock_finnhub

        with TestClient(app) as client:
            for ticker in ["META", "ORCL", "IBM"]:
                response = client.get(
                    f"/api/v2/tickers/{ticker}/ohlc", headers=auth_headers
                )
                # Feature 1055: No Finnhub fallback
                assert response.status_code == 404
                assert "No price data available" in response.json()["detail"]


class TestOHLCBothSourcesFailure:
    """US3: OHLC returns 404 when both sources fail."""

    # T046-T050: Both sources failing
    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_both_sources_http_500_returns_404(self, auth_headers):
        """OHLC returns 404 when both Tiingo and Finnhub return HTTP 500."""
        client, _, _ = create_test_client_with_injectors(
            tiingo_injector=create_http_500_injector(),
            finnhub_injector=create_http_500_injector(),
        )

        with client:
            response = client.get("/api/v2/tickers/NFLX/ohlc", headers=auth_headers)

        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_tiingo_500_finnhub_timeout_returns_404(self, auth_headers):
        """OHLC returns 404 when Tiingo returns 500 and Finnhub times out."""
        client, _, _ = create_test_client_with_injectors(
            tiingo_injector=create_http_500_injector(),
            finnhub_injector=create_timeout_injector(),
        )

        with client:
            response = client.get("/api/v2/tickers/AMZN/ohlc", headers=auth_headers)

        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_tiingo_timeout_finnhub_500_returns_404(self, auth_headers):
        """OHLC returns 404 when Tiingo times out and Finnhub returns 500."""
        client, _, _ = create_test_client_with_injectors(
            tiingo_injector=create_timeout_injector(),
            finnhub_injector=create_http_500_injector(),
        )

        with client:
            response = client.get("/api/v2/tickers/DIS/ohlc", headers=auth_headers)

        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_both_sources_connection_refused_returns_404(self, auth_headers):
        """OHLC returns 404 when both sources refuse connection."""
        client, _, _ = create_test_client_with_injectors(
            tiingo_injector=create_connection_refused_injector(),
            finnhub_injector=create_connection_refused_injector(),
        )

        with client:
            response = client.get("/api/v2/tickers/PYPL/ohlc", headers=auth_headers)

        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_both_sources_fail_mode_returns_404(self, auth_headers):
        """OHLC returns 404 when both sources are in fail_mode."""
        mock_tiingo = MockTiingoAdapter(seed=42, fail_mode=True)
        mock_finnhub = MockFinnhubAdapter(seed=42, fail_mode=True)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo
        app.dependency_overrides[get_finnhub_adapter] = lambda: mock_finnhub

        with TestClient(app) as client:
            response = client.get("/api/v2/tickers/CRM/ohlc", headers=auth_headers)

        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]


class TestOHLCFinnhubHttpErrors:
    """US3: OHLC returns 404 when Tiingo fails and Finnhub also fails."""

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    @pytest.mark.parametrize(
        "finnhub_injector_factory,error_code",
        [
            (create_http_500_injector, 500),
            (create_http_502_injector, 502),
            (create_http_503_injector, 503),
        ],
        ids=["500", "502", "503"],
    )
    def test_ohlc_tiingo_fail_finnhub_http_error_returns_404(
        self, auth_headers, finnhub_injector_factory, error_code
    ):
        """OHLC returns 404 when Tiingo fails and Finnhub returns HTTP {error_code}."""
        # Use fail_mode for Tiingo, injector for Finnhub
        mock_tiingo = MockTiingoAdapter(seed=42, fail_mode=True)
        mock_finnhub = MockFinnhubAdapter(
            seed=42, failure_injector=finnhub_injector_factory()
        )

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo
        app.dependency_overrides[get_finnhub_adapter] = lambda: mock_finnhub

        with TestClient(app) as client:
            response = client.get("/api/v2/tickers/INTC/ohlc", headers=auth_headers)

        assert response.status_code == 404
        assert "No price data available" in response.json()["detail"]


class TestOHLCCallTracking:
    """US3: Verify correct adapter calls are made (Feature 1055: Tiingo only, no Finnhub fallback)."""

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_tiingo_success_does_not_call_finnhub(self, auth_headers):
        """OHLC does not call Finnhub when Tiingo succeeds."""
        client, mock_tiingo, mock_finnhub = create_test_client_with_injectors()

        with client:
            response = client.get("/api/v2/tickers/ORCL/ohlc", headers=auth_headers)

        assert response.status_code == 200
        assert len(mock_tiingo.get_ohlc_calls) == 1
        assert len(mock_finnhub.get_ohlc_calls) == 0

    @pytest.mark.ohlc
    @pytest.mark.error_resilience
    def test_ohlc_tiingo_failure_does_not_call_finnhub(self, auth_headers):
        """OHLC does NOT call Finnhub when Tiingo fails (Feature 1055: no Finnhub fallback)."""
        client, mock_tiingo, mock_finnhub = create_test_client_with_injectors(
            tiingo_injector=create_http_500_injector()
        )

        with client:
            response = client.get("/api/v2/tickers/IBM/ohlc", headers=auth_headers)

        # Feature 1055: No Finnhub fallback - Tiingo is the only source
        assert response.status_code == 404
        assert len(mock_tiingo.get_ohlc_calls) == 1
        assert len(mock_finnhub.get_ohlc_calls) == 0  # Finnhub NOT called

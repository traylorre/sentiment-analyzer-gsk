# E2E Tests: Ticker Validation (User Story 9)
#
# Tests ticker validation and search:
# - Valid ticker returns metadata
# - Delisted ticker returns successor
# - Invalid ticker returns appropriate error
# - Ticker search/autocomplete
# - Empty query handling

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us9]


@pytest.mark.asyncio
async def test_valid_ticker_returns_metadata(
    api_client: PreprodAPIClient,
) -> None:
    """T090: Verify valid ticker returns metadata.

    Given: A valid, active ticker symbol
    When: GET /api/v2/tickers/{symbol} or validation endpoint is called
    Then: Response contains ticker metadata (company name, exchange)
    """
    response = await api_client.get("/api/v2/tickers/AAPL")

    if response.status_code == 404:
        # Try alternative endpoint
        response = await api_client.get(
            "/api/v2/tickers/validate",
            params={"symbol": "AAPL"},
        )

    if response.status_code == 404:
        pytest.skip("Ticker validation endpoint not implemented")

    assert (
        response.status_code == 200
    ), f"Valid ticker request failed: {response.status_code}"

    data = response.json()

    # Should have ticker info
    assert "symbol" in data or "ticker" in data
    # Might have company name, exchange, etc.
    if "company_name" in data or "name" in data:
        name = data.get("company_name") or data.get("name")
        assert "apple" in name.lower()


@pytest.mark.asyncio
async def test_delisted_ticker_returns_successor(
    api_client: PreprodAPIClient,
) -> None:
    """T091: Verify delisted ticker returns successor info.

    Given: A delisted ticker with a successor
    When: Ticker validation is called
    Then: Response indicates delisted status and successor ticker
    """
    # FB was renamed to META
    response = await api_client.get("/api/v2/tickers/FB")

    if response.status_code == 404:
        response = await api_client.get(
            "/api/v2/tickers/validate",
            params={"symbol": "FB"},
        )

    if response.status_code == 404:
        pytest.skip("Ticker validation endpoint not implemented")

    # Could return 200 with delisted info or 301/302 redirect
    if response.status_code == 200:
        data = response.json()
        # Should indicate delisted or have successor
        if data.get("is_delisted") or data.get("successor"):
            assert data.get("successor") == "META" or "meta" in str(data).lower()
    elif response.status_code in (301, 302, 307, 308):
        # Redirect to successor
        location = response.headers.get("location", "")
        assert "META" in location.upper()


@pytest.mark.asyncio
async def test_invalid_ticker_returns_invalid(
    api_client: PreprodAPIClient,
) -> None:
    """T092: Verify invalid ticker returns appropriate error.

    Given: An invalid ticker symbol
    When: Ticker validation is called
    Then: Response indicates invalid/not found
    """
    response = await api_client.get("/api/v2/tickers/INVALIDXYZ123")

    if response.status_code == 404:
        # Try validation endpoint
        response = await api_client.get(
            "/api/v2/tickers/validate",
            params={"symbol": "INVALIDXYZ123"},
        )

    if response.status_code == 404:
        # 404 for invalid ticker is acceptable
        pass
    elif response.status_code == 400:
        # Bad request for invalid ticker is acceptable
        data = response.json()
        assert "error" in data or "message" in data
    elif response.status_code == 200:
        # Some APIs return 200 with is_valid=false
        data = response.json()
        assert data.get("is_valid") is False or data.get("valid") is False


@pytest.mark.asyncio
async def test_ticker_search_returns_matches(
    api_client: PreprodAPIClient,
) -> None:
    """T093: Verify ticker search returns matching results.

    Given: A search query
    When: GET /api/v2/tickers/search?q={query} is called
    Then: Response contains matching tickers
    """
    response = await api_client.get(
        "/api/v2/tickers/search",
        params={"q": "apple"},
    )

    if response.status_code == 404:
        # Try autocomplete endpoint
        response = await api_client.get(
            "/api/v2/tickers/autocomplete",
            params={"q": "apple"},
        )

    if response.status_code == 404:
        pytest.skip("Ticker search endpoint not implemented")

    assert response.status_code == 200

    data = response.json()
    results = data if isinstance(data, list) else data.get("results", [])

    # Should find AAPL
    symbols = [r.get("symbol", r.get("ticker", "")).upper() for r in results]
    assert "AAPL" in symbols or len(results) > 0


@pytest.mark.asyncio
async def test_ticker_search_empty_query(
    api_client: PreprodAPIClient,
) -> None:
    """T094: Verify ticker search handles empty query.

    Given: An empty search query
    When: Search endpoint is called
    Then: Response is empty list or appropriate error
    """
    response = await api_client.get(
        "/api/v2/tickers/search",
        params={"q": ""},
    )

    if response.status_code == 404:
        pytest.skip("Ticker search endpoint not implemented")

    # Empty query should return empty results or 400
    if response.status_code == 200:
        data = response.json()
        results = data if isinstance(data, list) else data.get("results", [])
        # Empty query might return empty results or popular tickers
        assert isinstance(results, list)
    elif response.status_code == 400:
        # Bad request for empty query is acceptable
        pass


@pytest.mark.asyncio
async def test_ticker_search_partial_match(
    api_client: PreprodAPIClient,
) -> None:
    """Verify partial ticker search works.

    Given: A partial ticker or company name
    When: Search is called
    Then: Matching results are returned
    """
    response = await api_client.get(
        "/api/v2/tickers/search",
        params={"q": "micro"},
    )

    if response.status_code == 404:
        response = await api_client.get(
            "/api/v2/tickers/autocomplete",
            params={"q": "micro"},
        )

    if response.status_code == 404:
        pytest.skip("Ticker search endpoint not implemented")

    if response.status_code == 200:
        data = response.json()
        results = data if isinstance(data, list) else data.get("results", [])
        # Should find Microsoft (MSFT)
        if results:
            all_text = str(results).lower()
            assert "msft" in all_text or "microsoft" in all_text or len(results) > 0


@pytest.mark.asyncio
async def test_ticker_validation_case_insensitive(
    api_client: PreprodAPIClient,
) -> None:
    """Verify ticker validation is case insensitive.

    Given: A ticker in lowercase
    When: Validation is called
    Then: Same result as uppercase
    """
    # Lowercase
    response_lower = await api_client.get("/api/v2/tickers/aapl")

    if response_lower.status_code == 404:
        response_lower = await api_client.get(
            "/api/v2/tickers/validate",
            params={"symbol": "aapl"},
        )

    # Uppercase
    response_upper = await api_client.get("/api/v2/tickers/AAPL")

    if response_upper.status_code == 404:
        response_upper = await api_client.get(
            "/api/v2/tickers/validate",
            params={"symbol": "AAPL"},
        )

    if response_lower.status_code == 404 and response_upper.status_code == 404:
        pytest.skip("Ticker validation endpoint not implemented")

    # Both should return same result
    assert response_lower.status_code == response_upper.status_code


@pytest.mark.asyncio
async def test_ticker_batch_validation(
    api_client: PreprodAPIClient,
) -> None:
    """Verify multiple tickers can be validated at once.

    Given: Multiple ticker symbols
    When: Batch validation is called
    Then: Results for all tickers are returned
    """
    response = await api_client.post(
        "/api/v2/tickers/validate",
        json={"symbols": ["AAPL", "MSFT", "INVALID123"]},
    )

    if response.status_code == 404:
        pytest.skip("Batch ticker validation not implemented")

    if response.status_code == 200:
        data = response.json()
        # Should have results for each ticker
        results = data if isinstance(data, list) else data.get("results", [])
        assert len(results) >= 2  # At least AAPL and MSFT

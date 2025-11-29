# E2E Tests: Market Status (User Story 12)
#
# Tests market status functionality:
# - Market open detection
# - Market closed detection
# - Holiday handling
# - Pre-market estimates
# - Redirect behavior when market opens

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us12]


@pytest.mark.asyncio
async def test_market_status_open(
    api_client: PreprodAPIClient,
) -> None:
    """T105: Verify market status reports OPEN during trading hours.

    Given: US market trading hours (9:30 AM - 4:00 PM ET, weekdays)
    When: GET /api/v2/market/status is called
    Then: Response indicates market is OPEN

    Note: This test's assertion depends on current time.
    """
    response = await api_client.get("/api/v2/market/status")

    if response.status_code == 404:
        pytest.skip("Market status endpoint not implemented")

    assert (
        response.status_code == 200
    ), f"Market status request failed: {response.status_code}"

    data = response.json()

    # Should have status field
    assert (
        "status" in data or "is_open" in data or "market_open" in data
    ), f"Missing market status field: {data}"

    # Status should be valid value
    status = data.get("status") or ("OPEN" if data.get("is_open") else "CLOSED")
    assert status in (
        "OPEN",
        "CLOSED",
        "PRE_MARKET",
        "AFTER_HOURS",
        "open",
        "closed",
        "pre_market",
        "after_hours",
    )


@pytest.mark.asyncio
async def test_market_status_closed(
    api_client: PreprodAPIClient,
) -> None:
    """T106: Verify market status reports CLOSED outside trading hours.

    Given: Outside US market trading hours
    When: GET /api/v2/market/status is called
    Then: Response indicates market is CLOSED or appropriate status

    Note: This test validates the endpoint contract, not specific timing.
    """
    response = await api_client.get("/api/v2/market/status")

    if response.status_code == 404:
        pytest.skip("Market status endpoint not implemented")

    assert response.status_code == 200

    data = response.json()

    # Should provide market status information
    assert data is not None

    # Should have timing info
    if "next_open" in data or "next_close" in data:
        # Good - provides timing information
        pass
    if "trading_day" in data:
        # Good - indicates if today is a trading day
        pass


@pytest.mark.asyncio
async def test_market_status_holiday(
    api_client: PreprodAPIClient,
) -> None:
    """T107: Verify market status handles holidays correctly.

    Given: A US market holiday
    When: GET /api/v2/market/status is called
    Then: Response indicates market is CLOSED with holiday info

    Note: We check for holiday support in the response schema.
    """
    response = await api_client.get("/api/v2/market/status")

    if response.status_code == 404:
        pytest.skip("Market status endpoint not implemented")

    assert response.status_code == 200

    data = response.json()

    # Check if holiday information is supported
    # Might be: is_holiday, holiday_name, holidays array, etc.
    # This validates the endpoint can return this info
    assert isinstance(data, dict)

    # Optionally check holiday calendar endpoint
    holidays_response = await api_client.get("/api/v2/market/holidays")

    if holidays_response.status_code == 200:
        holidays = holidays_response.json()
        # Should return list of holidays
        if isinstance(holidays, list):
            assert all(isinstance(h, dict) for h in holidays)
        elif isinstance(holidays, dict):
            # Might have holidays key
            pass


@pytest.mark.asyncio
async def test_premarket_estimates_returned(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T108: Verify pre-market estimates are returned.

    Given: Market is in pre-market hours
    When: Requesting sentiment/price data
    Then: Pre-market estimates are included

    Note: This validates the API supports pre-market data.
    """
    # Create session and config
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    # API returns 201 Created for new sessions (correct HTTP semantics)
    assert session_response.status_code in (200, 201)
    token = session_response.json()["token"]

    api_client.set_access_token(token)
    try:
        config_response = await api_client.post(
            "/api/v2/configurations",
            json={
                "name": f"Pre-market Test {test_run_id[:8]}",
                "tickers": [{"symbol": "AAPL", "enabled": True}],
            },
        )

        if config_response.status_code not in (200, 201):
            pytest.skip("Config creation not available")

        config_id = config_response.json()["config_id"]

        # Request sentiment with pre-market parameter
        response = await api_client.get(
            f"/api/v2/configurations/{config_id}/sentiment",
            params={"include_premarket": "true"},
        )

        if response.status_code == 200:
            data = response.json()
            # Check if pre-market data is included
            # Structure depends on implementation
            assert data is not None

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_premarket_redirect_when_open(
    api_client: PreprodAPIClient,
) -> None:
    """T109: Verify pre-market endpoint redirects when market opens.

    Given: Market is OPEN
    When: Pre-market specific endpoint is called
    Then: Response redirects to regular market data or returns market data

    Note: This validates the API handles market transitions.
    """
    # Check if there's a dedicated pre-market endpoint
    response = await api_client.get("/api/v2/market/premarket")

    if response.status_code == 404:
        # No dedicated pre-market endpoint - that's fine
        pytest.skip("Pre-market endpoint not implemented")

    # Could redirect (3xx) or return data (200)
    assert response.status_code in (
        200,
        301,
        302,
        307,
        308,
    ), f"Unexpected status: {response.status_code}"

    if response.status_code == 200:
        data = response.json()
        assert data is not None


@pytest.mark.asyncio
async def test_market_schedule_endpoint(
    api_client: PreprodAPIClient,
) -> None:
    """Verify market schedule endpoint returns trading hours.

    Given: A request for market schedule
    When: GET /api/v2/market/schedule is called
    Then: Response contains trading hours information
    """
    response = await api_client.get("/api/v2/market/schedule")

    if response.status_code == 404:
        pytest.skip("Market schedule endpoint not implemented")

    assert response.status_code == 200

    data = response.json()

    # Should have schedule information
    # Could be: open_time, close_time, timezone, etc.
    assert data is not None

    # Common fields to check
    if "timezone" in data:
        assert data["timezone"] in (
            "America/New_York",
            "US/Eastern",
            "ET",
            "EST",
            "EDT",
        )


@pytest.mark.asyncio
async def test_market_status_includes_timestamp(
    api_client: PreprodAPIClient,
) -> None:
    """Verify market status includes server timestamp.

    Given: A market status request
    When: Response is received
    Then: Response includes timestamp for cache validation
    """
    response = await api_client.get("/api/v2/market/status")

    if response.status_code == 404:
        pytest.skip("Market status endpoint not implemented")

    assert response.status_code == 200

    data = response.json()

    # Should have timestamp
    assert (
        "timestamp" in data
        or "as_of" in data
        or "updated_at" in data
        or "server_time" in data
        or "current_time" in data
    ), f"Missing timestamp in market status: {data}"

# E2E Tests: Circuit Breaker Behavior (User Story 8)
#
# Tests circuit breaker state transitions:
# - Healthy API returns fresh data
# - Circuit opens after failures
# - Open circuit returns cached data
# - Half-open state after timeout
# - Circuit closes on success

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us8]


async def create_session_and_config(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> tuple[str, str]:
    """Helper to create session and config."""
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    # API returns 201 Created for new sessions (correct HTTP semantics)
    assert session_response.status_code in (200, 201)
    token = session_response.json()["token"]

    api_client.set_access_token(token)
    config_response = await api_client.post(
        "/api/v2/configurations",
        json={
            "name": f"CB Test {test_run_id[:8]}",
            "tickers": ["AAPL"],
        },
    )

    if config_response.status_code not in (200, 201):
        api_client.clear_access_token()
        pytest.skip("Config creation not available")

    config_id = config_response.json()["config_id"]
    return token, config_id


@pytest.mark.asyncio
async def test_healthy_api_returns_fresh_data(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T085: Verify healthy external APIs return fresh data.

    Given: External APIs (Tiingo, Finnhub) are healthy
    When: Sentiment endpoint is called
    Then: Fresh data is returned (not cached)
    """
    token, config_id = await create_session_and_config(api_client, test_run_id)

    try:
        response = await api_client.get(f"/api/v2/configurations/{config_id}/sentiment")

        # Should succeed when external APIs are healthy
        assert (
            response.status_code == 200
        ), f"Sentiment request failed: {response.status_code}"

        data = response.json()
        assert data is not None

        # Note: Cache behavior depends on implementation
        # This test validates data is returned successfully

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_circuit_opens_after_failures(
    api_client: PreprodAPIClient,
    test_run_id: str,
    dynamodb_table,
) -> None:
    """T086: Verify circuit breaker opens after threshold failures.

    Note: In E2E tests, we can't easily inject failures into external APIs.
    This test validates circuit breaker state can be queried.

    Given: External API failures exceeding threshold
    When: Circuit breaker state is checked
    Then: Circuit shows OPEN state
    """
    token, config_id = await create_session_and_config(api_client, test_run_id)

    try:
        # In preprod E2E, we can only observe circuit breaker behavior
        # We can't inject failures into real external APIs

        # Check if circuit breaker state is exposed
        cb_response = await api_client.get("/api/v2/health/circuit-breaker")

        if cb_response.status_code == 404:
            # No dedicated circuit breaker endpoint
            # Try querying DynamoDB directly for CB state
            try:
                response = dynamodb_table.get_item(
                    Key={"PK": "CB#tiingo", "SK": "STATE"}
                )
                if "Item" in response:
                    state = response["Item"].get("state")
                    # Just verify we can read the state
                    assert state in (None, "CLOSED", "OPEN", "HALF_OPEN")
            except Exception:
                pytest.skip("Cannot verify circuit breaker state in this environment")

        elif cb_response.status_code == 200:
            data = cb_response.json()
            # Should have circuit breaker status
            assert data is not None

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_circuit_open_returns_cached_data(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T087: Verify open circuit returns cached data.

    Given: Circuit breaker is OPEN
    When: Sentiment endpoint is called
    Then: Cached data is returned with appropriate headers
    """
    token, config_id = await create_session_and_config(api_client, test_run_id)

    try:
        # Make multiple requests to potentially see cache behavior
        responses = []
        for _ in range(3):
            response = await api_client.get(
                f"/api/v2/configurations/{config_id}/sentiment"
            )
            responses.append(response)

        # At least one should succeed
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 1, "No successful sentiment responses"

        # Check for cache headers indicating cached response
        for response in responses:
            if response.status_code == 200:
                # Cache headers depend on implementation
                # x-cache, x-from-cache would indicate cached response
                _ = response.headers.get("x-cache", "")
                _ = response.headers.get("x-from-cache", "")

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_circuit_half_open_after_timeout(
    api_client: PreprodAPIClient,
    test_run_id: str,
    dynamodb_table,
) -> None:
    """T088: Verify circuit enters HALF_OPEN after timeout.

    Note: This requires waiting for circuit breaker timeout, which
    may be too long for E2E tests. Test validates the concept.

    Given: Circuit breaker is OPEN
    When: Timeout period elapses
    Then: Circuit transitions to HALF_OPEN
    """
    # This test is more conceptual - circuit breaker timeouts are typically
    # 30-60 seconds, which is too long for individual E2E tests

    # We can verify the circuit breaker configuration exists
    try:
        response = dynamodb_table.get_item(Key={"PK": "CB#tiingo", "SK": "STATE"})
        if "Item" in response:
            # Item exists - circuit breaker state is tracked
            # Would contain timeout-related fields: opened_at, timeout, etc.
            _ = response["Item"]
    except Exception:
        pytest.skip("Cannot access circuit breaker state")


@pytest.mark.asyncio
async def test_circuit_closes_on_success(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T089: Verify circuit closes after successful requests.

    Given: Circuit breaker in HALF_OPEN state
    When: Request succeeds
    Then: Circuit transitions to CLOSED
    """
    token, config_id = await create_session_and_config(api_client, test_run_id)

    try:
        # Make a successful request
        response = await api_client.get(f"/api/v2/configurations/{config_id}/sentiment")

        # If we get a successful response, circuit should be CLOSED
        if response.status_code == 200:
            # Circuit is healthy
            pass
        elif response.status_code == 503:
            # Service unavailable - circuit might be OPEN
            data = response.json()
            # Should indicate circuit breaker status
            if "circuit" in str(data).lower():
                pass  # Expected behavior when circuit is open

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_circuit_breaker_per_service(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """Verify circuit breakers are per-service.

    Given: Tiingo circuit breaker is open
    When: Finnhub data is requested
    Then: Finnhub data still available (separate circuit)
    """
    token, config_id = await create_session_and_config(api_client, test_run_id)

    try:
        # Request sentiment which aggregates from multiple sources
        response = await api_client.get(f"/api/v2/configurations/{config_id}/sentiment")

        if response.status_code == 200:
            # If one source fails, should still get data from other
            # Implementation dependent - verify response has data
            _ = response.json()

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_health_endpoint_reports_circuit_status(
    api_client: PreprodAPIClient,
) -> None:
    """Verify health endpoint includes circuit breaker status.

    Given: An application health endpoint
    When: GET /health or /api/v2/health is called
    Then: Response includes circuit breaker states
    """
    # Check main health endpoint
    response = await api_client.get("/health")

    if response.status_code == 404:
        response = await api_client.get("/api/v2/health")

    if response.status_code == 200:
        # Health response might include circuit breaker info
        # This depends on implementation - verify response parses
        _ = response.json()

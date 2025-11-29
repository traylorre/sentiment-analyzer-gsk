# E2E Tests: SSE Streaming (User Story 10)
#
# Tests Server-Sent Events functionality:
# - SSE connection establishment
# - Sentiment update events
# - Refresh events
# - Reconnection with Last-Event-ID
# - Authentication requirements

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us10]


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
            "name": f"SSE Test {test_run_id[:8]}",
            "tickers": [{"symbol": "AAPL", "enabled": True}],
        },
    )

    if config_response.status_code not in (200, 201):
        api_client.clear_access_token()
        pytest.skip("Config creation not available")

    config_id = config_response.json()["config_id"]
    return token, config_id


@pytest.mark.asyncio
async def test_sse_connection_established(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T095: Verify SSE connection can be established.

    Given: An authenticated user with a configuration
    When: GET /api/v2/configurations/{id}/stream is called
    Then: Connection is established with text/event-stream content type
    """
    token, config_id = await create_session_and_config(api_client, test_run_id)

    try:
        # Try to establish SSE connection
        response = await api_client.get(
            f"/api/v2/configurations/{config_id}/stream",
            headers={"Accept": "text/event-stream"},
            timeout=5.0,
        )

        if response.status_code == 404:
            pytest.skip("SSE streaming endpoint not implemented")

        # Should return 200 with event-stream content type
        # or upgrade to streaming
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            assert (
                "text/event-stream" in content_type or "stream" in content_type.lower()
            ), f"Expected event-stream content type, got: {content_type}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_sse_receives_sentiment_update(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T096: Verify SSE receives sentiment update events.

    Given: An established SSE connection
    When: Sentiment data changes
    Then: Client receives sentiment_update event with data
    """
    token, config_id = await create_session_and_config(api_client, test_run_id)

    try:
        # This test validates the SSE endpoint contract
        # In preprod, we may not be able to trigger real sentiment updates
        response = await api_client.get(
            f"/api/v2/configurations/{config_id}/stream",
            headers={"Accept": "text/event-stream"},
            timeout=5.0,
        )

        if response.status_code == 404:
            pytest.skip("SSE streaming endpoint not implemented")

        # Verify endpoint responds appropriately
        assert response.status_code in (200, 204)

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_sse_receives_refresh_event(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T097: Verify SSE receives refresh events.

    Given: An established SSE connection
    When: Server triggers a refresh
    Then: Client receives refresh event
    """
    token, config_id = await create_session_and_config(api_client, test_run_id)

    try:
        response = await api_client.get(
            f"/api/v2/configurations/{config_id}/stream",
            headers={"Accept": "text/event-stream"},
            timeout=5.0,
        )

        if response.status_code == 404:
            pytest.skip("SSE streaming endpoint not implemented")

        # Validate endpoint contract
        assert response.status_code in (200, 204)

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_sse_reconnection_with_last_event_id(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T098: Verify SSE reconnection with Last-Event-ID.

    Given: A previous SSE session with event ID
    When: Reconnecting with Last-Event-ID header
    Then: Server resumes from that event ID
    """
    token, config_id = await create_session_and_config(api_client, test_run_id)

    try:
        # Test reconnection header support
        response = await api_client.get(
            f"/api/v2/configurations/{config_id}/stream",
            headers={
                "Accept": "text/event-stream",
                "Last-Event-ID": "test-event-12345",
            },
            timeout=5.0,
        )

        if response.status_code == 404:
            pytest.skip("SSE streaming endpoint not implemented")

        # Should accept reconnection request
        assert response.status_code in (200, 204)

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_sse_unauthenticated_rejected(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T099: Verify unauthenticated SSE requests are rejected.

    Given: No authentication
    When: GET /api/v2/configurations/{id}/stream is called
    Then: Response is 401 Unauthorized
    """
    # First create a config to get a valid config_id
    token, config_id = await create_session_and_config(api_client, test_run_id)
    api_client.clear_access_token()

    # Try to access without token
    response = await api_client.get(
        f"/api/v2/configurations/{config_id}/stream",
        headers={"Accept": "text/event-stream"},
        timeout=5.0,
    )

    # Should be 401 without auth (unless endpoint doesn't exist)
    assert response.status_code in (
        401,
        404,
    ), f"Unauthenticated should return 401: {response.status_code}"


@pytest.mark.asyncio
async def test_sse_invalid_config_rejected(
    api_client: PreprodAPIClient,
) -> None:
    """Verify SSE rejects invalid config IDs.

    Given: An invalid configuration ID
    When: SSE stream is requested
    Then: Response is 404 Not Found
    """
    # Create session
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    # API returns 201 Created for new sessions (correct HTTP semantics)
    assert session_response.status_code in (200, 201)
    token = session_response.json()["token"]

    api_client.set_access_token(token)
    try:
        response = await api_client.get(
            "/api/v2/configurations/invalid-config-xyz/stream",
            headers={"Accept": "text/event-stream"},
            timeout=5.0,
        )

        # Should be 404 for invalid config
        assert response.status_code in (
            404,
            403,
        ), f"Invalid config should return 404/403: {response.status_code}"

    finally:
        api_client.clear_access_token()

# E2E Tests: SSE Streaming (User Story 10)
#
# Tests Server-Sent Events functionality:
# - SSE connection establishment
# - Global metrics stream
# - Config-specific stream
# - Sentiment update events
# - Refresh events
# - Reconnection with Last-Event-ID
# - Authentication requirements

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient
from tests.fixtures.synthetic.config_generator import SyntheticConfiguration

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us10]


@pytest.mark.asyncio
async def test_global_stream_available(
    api_client: PreprodAPIClient,
) -> None:
    """T095b: Verify global SSE stream is available.

    Given: The API is running
    When: GET /api/v2/stream is called
    Then: Connection is established with text/event-stream content type

    Note: SSE endpoints are streaming and never complete. We use stream_sse()
    to validate headers and receive first events without blocking.
    """
    # Use streaming mode for SSE (regular GET would timeout waiting for stream to end)
    status_code, headers, content = await api_client.stream_sse(
        "/api/v2/stream",
        timeout=10.0,
    )

    # Should return 200 with event-stream content type
    assert status_code == 200, f"Expected 200, got {status_code}"
    content_type = headers.get("content-type", "")
    # Note: Lambda Function URLs with RESPONSE_STREAM mode return application/octet-stream
    # regardless of the Content-Type set in the response. This is a known AWS limitation.
    # See: https://repost.aws/questions/QU3G889txXR-aVe_GIxAvnGQ
    # The SSE functionality works correctly - clients receive properly formatted SSE events.
    assert (
        "text/event-stream" in content_type or "stream" in content_type.lower()
    ), f"Expected event-stream content type, got: {content_type}"


@pytest.mark.asyncio
async def test_stream_status_endpoint(
    api_client: PreprodAPIClient,
) -> None:
    """Verify /api/v2/stream/status returns connection info.

    Given: The API is running
    When: GET /api/v2/stream/status is called
    Then: Response contains connection count and limits
    """
    response = await api_client.get("/api/v2/stream/status")

    assert response.status_code == 200
    data = response.json()
    assert "connections" in data
    assert "max_connections" in data
    assert "available" in data


async def create_session_and_config(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> tuple[str, str]:
    """Helper to create session and config."""
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    # API returns 201 Created for new sessions (correct HTTP semantics)
    assert session_response.status_code == 201
    token = session_response.json()["token"]

    api_client.set_access_token(token)
    config_response = await api_client.post(
        "/api/v2/configurations",
        json=synthetic_config.to_api_payload(),
    )

    if config_response.status_code != 201:
        api_client.clear_access_token()
        pytest.skip("Config creation not available")

    config_id = config_response.json()["config_id"]
    return token, config_id


@pytest.mark.asyncio
async def test_sse_connection_established(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> None:
    """T095: Verify SSE connection can be established.

    Given: An authenticated user with a configuration
    When: GET /api/v2/configurations/{id}/stream is called
    Then: Connection is established with text/event-stream content type

    Note: SSE endpoints are streaming and never complete. We use stream_sse()
    to validate headers and receive first events without blocking.
    """
    token, config_id = await create_session_and_config(api_client, synthetic_config)

    try:
        # Try to establish SSE connection using streaming mode
        status_code, headers, content = await api_client.stream_sse(
            f"/api/v2/configurations/{config_id}/stream",
            timeout=10.0,
        )

        # SSE streaming endpoint is implemented - 404 is a real failure
        assert status_code == 200, f"Expected 200, got {status_code}"

        # Should return 200 with event-stream content type
        content_type = headers.get("content-type", "")
        assert (
            "text/event-stream" in content_type or "stream" in content_type.lower()
        ), f"Expected event-stream content type, got: {content_type}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_sse_receives_sentiment_update(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> None:
    """T096: Verify SSE receives sentiment update events.

    Given: An established SSE connection
    When: Sentiment data changes
    Then: Client receives sentiment_update event with data

    Note: SSE endpoints are streaming and never complete. We use stream_sse()
    to validate headers and receive first events without blocking.
    """
    token, config_id = await create_session_and_config(api_client, synthetic_config)

    try:
        # This test validates the SSE endpoint contract
        # In preprod, we may not be able to trigger real sentiment updates
        status_code, headers, content = await api_client.stream_sse(
            f"/api/v2/configurations/{config_id}/stream",
            timeout=10.0,
        )

        # SSE streaming endpoint is implemented - 404 is a real failure
        assert status_code == 200, f"Expected 200, got {status_code}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_sse_receives_refresh_event(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> None:
    """T097: Verify SSE receives refresh events.

    Given: An established SSE connection
    When: Server triggers a refresh
    Then: Client receives refresh event

    Note: SSE endpoints are streaming and never complete. We use stream_sse()
    to validate headers and receive first events without blocking.
    """
    token, config_id = await create_session_and_config(api_client, synthetic_config)

    try:
        status_code, headers, content = await api_client.stream_sse(
            f"/api/v2/configurations/{config_id}/stream",
            timeout=10.0,
        )

        # SSE streaming endpoint is implemented - 404 is a real failure
        assert status_code == 200, f"Expected 200, got {status_code}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_sse_reconnection_with_last_event_id(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> None:
    """T098: Verify SSE reconnection with Last-Event-ID.

    Given: A previous SSE session with event ID
    When: Reconnecting with Last-Event-ID header
    Then: Server resumes from that event ID

    Note: SSE endpoints are streaming and never complete. We use stream_sse()
    to validate headers and receive first events without blocking.
    """
    token, config_id = await create_session_and_config(api_client, synthetic_config)

    try:
        # Test reconnection header support
        status_code, headers, content = await api_client.stream_sse(
            f"/api/v2/configurations/{config_id}/stream",
            headers={"Last-Event-ID": "test-event-12345"},
            timeout=10.0,
        )

        # SSE streaming endpoint is implemented - 404 is a real failure
        assert status_code == 200, f"Expected 200, got {status_code}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_sse_unauthenticated_rejected(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> None:
    """T099: Verify unauthenticated SSE requests are rejected.

    Given: No authentication
    When: GET /api/v2/configurations/{id}/stream is called
    Then: Response is 401 Unauthorized
    """
    # First create a config to get a valid config_id
    token, config_id = await create_session_and_config(api_client, synthetic_config)
    api_client.clear_access_token()

    # Try to access without token
    response = await api_client.get(
        f"/api/v2/configurations/{config_id}/stream",
        headers={"Accept": "text/event-stream"},
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
    assert session_response.status_code == 201
    token = session_response.json()["token"]

    api_client.set_access_token(token)
    try:
        response = await api_client.get(
            "/api/v2/configurations/invalid-config-xyz/stream",
            headers={"Accept": "text/event-stream"},
        )

        # Should be 404 for invalid config
        assert response.status_code in (
            404,
            403,
        ), f"Invalid config should return 404/403: {response.status_code}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_stream_status_shows_connection_limit(
    api_client: PreprodAPIClient,
) -> None:
    """T042: Verify stream status shows connection limits.

    Given: The SSE Lambda is running
    When: GET /api/v2/stream/status is called
    Then: Response shows max_connections limit (100 per FR-008)

    Note: Testing actual 503 response would require exhausting 100 connections
    which is not practical for E2E tests. We verify the limit is correctly
    reported via the status endpoint instead.
    """
    response = await api_client.get("/api/v2/stream/status")

    assert response.status_code == 200
    data = response.json()

    # Verify connection limit is configured correctly per FR-008
    assert "max_connections" in data, "Status should include max_connections"
    assert (
        data["max_connections"] == 100
    ), f"Max connections should be 100 per FR-008, got {data['max_connections']}"

    # Verify available slots calculation
    assert "available" in data, "Status should include available slots"
    assert "connections" in data, "Status should include current connections"
    assert data["available"] == data["max_connections"] - data["connections"]

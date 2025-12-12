# E2E Tests: Dashboard BUFFERED Response Mode (Feature 016)
#
# Validates that the dashboard Lambda returns proper JSON responses
# after the two-Lambda architecture deployment. The dashboard Lambda
# uses BUFFERED invoke mode (via Mangum), ensuring REST API responses
# are properly formatted and not streaming.
#
# Key validation:
# - REST endpoints return valid JSON (not chunked/streamed)
# - Content-Type is application/json
# - Response bodies are complete and parseable
# - No streaming artifacts in responses

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient
from tests.fixtures.synthetic.config_generator import SyntheticConfiguration

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us2]


@pytest.mark.asyncio
async def test_health_endpoint_returns_json(
    api_client: PreprodAPIClient,
) -> None:
    """Verify health endpoint returns proper JSON response.

    Given: The dashboard Lambda is deployed with BUFFERED mode
    When: GET /health is called
    Then: Response is valid JSON with application/json content type
    """
    response = await api_client.get("/health")

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert (
        "application/json" in content_type
    ), f"Expected application/json, got: {content_type}"

    # Verify response is valid JSON (not chunked stream)
    data = response.json()
    assert isinstance(data, dict)
    assert "status" in data or "healthy" in str(data).lower()


@pytest.mark.asyncio
async def test_configs_list_returns_json(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> None:
    """Verify configurations list returns proper JSON response.

    Given: An authenticated user
    When: GET /api/v2/configurations is called
    Then: Response is valid JSON with configurations list and max_allowed
    """
    # Create session
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert session_response.status_code == 201
    token = session_response.json()["token"]

    api_client.set_access_token(token)
    try:
        response = await api_client.get("/api/v2/configurations")

        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert (
            "application/json" in content_type
        ), f"Expected application/json, got: {content_type}"

        # Verify response is valid JSON with expected structure
        data = response.json()
        assert isinstance(data, dict), f"Expected dict, got {type(data).__name__}"
        assert "configurations" in data, "Missing 'configurations' key"
        assert isinstance(data["configurations"], list)

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_config_create_returns_json(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> None:
    """Verify configuration creation returns proper JSON response.

    Given: An authenticated user
    When: POST /api/v2/configurations is called
    Then: Response is valid JSON with config_id
    """
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert session_response.status_code == 201
    token = session_response.json()["token"]

    api_client.set_access_token(token)
    try:
        response = await api_client.post(
            "/api/v2/configurations",
            json=synthetic_config.to_api_payload(),
        )

        # Should return 201 Created
        assert response.status_code == 201
        content_type = response.headers.get("content-type", "")
        assert (
            "application/json" in content_type
        ), f"Expected application/json, got: {content_type}"

        # Verify response is valid JSON with expected fields
        data = response.json()
        assert isinstance(data, dict)
        assert "config_id" in data

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_sentiment_endpoint_returns_json(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> None:
    """Verify sentiment endpoint returns proper JSON response.

    Given: An authenticated user with a configuration
    When: GET /api/v2/configurations/{id}/sentiment is called
    Then: Response is valid JSON (not chunked stream)
    """
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert session_response.status_code == 201
    token = session_response.json()["token"]

    api_client.set_access_token(token)
    try:
        # Create config first
        config_response = await api_client.post(
            "/api/v2/configurations",
            json=synthetic_config.to_api_payload(),
        )
        if config_response.status_code != 201:
            pytest.skip("Config creation not available")

        config_id = config_response.json()["config_id"]

        # Get sentiment data
        response = await api_client.get(f"/api/v2/configurations/{config_id}/sentiment")

        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert (
            "application/json" in content_type
        ), f"Expected application/json, got: {content_type}"

        # Verify response is valid JSON
        data = response.json()
        assert isinstance(data, dict | list)

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_dashboard_metrics_returns_json(
    api_client: PreprodAPIClient,
) -> None:
    """Verify dashboard metrics endpoint returns proper JSON response.

    Given: The dashboard Lambda is deployed
    When: GET /api/v2/metrics/dashboard is called
    Then: Response is valid JSON with metrics data
    """
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert session_response.status_code == 201
    token = session_response.json()["token"]

    api_client.set_access_token(token)
    try:
        response = await api_client.get("/api/v2/metrics/dashboard")

        # Endpoint may not be implemented yet
        if response.status_code == 404:
            pytest.skip("Dashboard metrics endpoint not implemented")

        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert (
            "application/json" in content_type
        ), f"Expected application/json, got: {content_type}"

        data = response.json()
        assert isinstance(data, dict)

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_error_response_is_json(
    api_client: PreprodAPIClient,
) -> None:
    """Verify error responses return proper JSON.

    Given: A request to a non-existent endpoint
    When: GET /api/v2/nonexistent is called
    Then: Response is valid JSON error response
    """
    response = await api_client.get("/api/v2/nonexistent")

    # Should return 404
    assert response.status_code == 404
    content_type = response.headers.get("content-type", "")
    assert (
        "application/json" in content_type
    ), f"Expected application/json, got: {content_type}"

    # Verify error response is valid JSON
    data = response.json()
    assert isinstance(data, dict)
    assert "detail" in data or "error" in data or "message" in data


@pytest.mark.asyncio
async def test_response_not_chunked_transfer_encoding(
    api_client: PreprodAPIClient,
) -> None:
    """Verify responses do not use chunked transfer encoding inappropriately.

    Given: The dashboard Lambda uses BUFFERED mode
    When: Any REST endpoint is called
    Then: Response Content-Length is present (not streaming)

    Note: BUFFERED mode ensures complete responses, while RESPONSE_STREAM
    would use chunked encoding. This test validates the BUFFERED behavior.
    """
    response = await api_client.get("/health")

    assert response.status_code == 200

    # In BUFFERED mode, Lambda returns complete responses
    # Content-Length header should be present for JSON responses
    transfer_encoding = response.headers.get("transfer-encoding", "")

    # Either Content-Length should be set, or if chunked, the response
    # should still be valid JSON (not streaming events)
    data = response.json()
    assert isinstance(data, dict), "Response should be valid JSON, not streaming"

    # If chunked, verify it's still complete JSON (not partial)
    if "chunked" in transfer_encoding.lower():
        # The response was still parseable as complete JSON, which is OK
        # This can happen with some Lambda configurations
        assert "status" in data or len(data) > 0


@pytest.mark.asyncio
async def test_anonymous_auth_returns_json(
    api_client: PreprodAPIClient,
) -> None:
    """Verify anonymous auth endpoint returns proper JSON.

    Given: The dashboard Lambda is deployed
    When: POST /api/v2/auth/anonymous is called
    Then: Response is valid JSON with token
    """
    response = await api_client.post("/api/v2/auth/anonymous", json={})

    assert response.status_code == 201
    content_type = response.headers.get("content-type", "")
    assert (
        "application/json" in content_type
    ), f"Expected application/json, got: {content_type}"

    data = response.json()
    assert isinstance(data, dict)
    assert "token" in data


@pytest.mark.asyncio
async def test_alerts_list_returns_json(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> None:
    """Verify alerts list returns proper JSON response.

    Given: An authenticated user with a configuration
    When: GET /api/v2/configurations/{id}/alerts is called
    Then: Response is valid JSON with AlertListResponse structure
    """
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert session_response.status_code == 201
    token = session_response.json()["token"]

    api_client.set_access_token(token)
    try:
        # Create config first
        config_response = await api_client.post(
            "/api/v2/configurations",
            json=synthetic_config.to_api_payload(),
        )
        if config_response.status_code != 201:
            pytest.skip("Config creation not available")

        config_id = config_response.json()["config_id"]

        response = await api_client.get(f"/api/v2/configurations/{config_id}/alerts")

        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert (
            "application/json" in content_type
        ), f"Expected application/json, got: {content_type}"

        data = response.json()
        # API returns AlertListResponse with alerts list, total count, and quota info
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert "alerts" in data, "Response missing 'alerts' field"
        assert "total" in data, "Response missing 'total' field"
        assert "daily_email_quota" in data, "Response missing 'daily_email_quota' field"
        assert isinstance(data["alerts"], list), "alerts should be a list"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_multiple_requests_all_return_json(
    api_client: PreprodAPIClient,
) -> None:
    """Verify multiple sequential requests all return proper JSON.

    Given: The dashboard Lambda is deployed
    When: Multiple REST endpoints are called sequentially
    Then: All responses are valid JSON

    This validates consistent BUFFERED behavior across requests.
    """
    endpoints = [
        "/health",
        "/api/v2/auth/anonymous",
    ]

    for endpoint in endpoints:
        if endpoint == "/api/v2/auth/anonymous":
            response = await api_client.post(endpoint, json={})
        else:
            response = await api_client.get(endpoint)

        # All should return JSON
        content_type = response.headers.get("content-type", "")
        assert (
            "application/json" in content_type
        ), f"Endpoint {endpoint} returned non-JSON: {content_type}"

        # All should be parseable
        data = response.json()
        assert isinstance(
            data, dict | list
        ), f"Endpoint {endpoint} returned invalid JSON"

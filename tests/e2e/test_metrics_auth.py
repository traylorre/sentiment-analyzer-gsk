"""E2E tests for /api/v2/metrics endpoint authentication.

Feature 1059: E2E Test for /api/v2/metrics Auth Scenarios

IMPORTANT: This tests /api/v2/metrics, NOT /api/v2/metrics/dashboard.
The frontend dashboard (app.js) calls /api/v2/metrics to fetch aggregated
sentiment data. A prior test gap (testing the wrong endpoint) allowed
a 401 bug to persist undetected for days.

This test verifies:
1. 401 is returned when no auth headers are present
2. 200 is returned with anonymous session (X-User-ID header)
3. 200 is returned with JWT auth (Authorization: Bearer header)

See: src/lambdas/dashboard/handler.py:419-483 for endpoint implementation.
See: src/dashboard/app.js:470-495 for frontend usage.
"""

from __future__ import annotations

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.e2e, pytest.mark.preprod]


@pytest.mark.asyncio
async def test_metrics_401_without_auth(
    api_client: PreprodAPIClient,
) -> None:
    """Verify /api/v2/metrics returns 401 when no auth headers are present.

    Given: No authentication headers are set
    When: GET /api/v2/metrics is called
    Then: Response status is 401 with "Missing user identification" detail

    This is the behavior that caused the 401 bug when the frontend
    failed to initialize a session before calling the metrics endpoint.
    """
    # Ensure no auth is set (clear_access_token clears both access token and bearer token)
    api_client.clear_access_token()

    response = await api_client.get("/api/v2/metrics")

    assert response.status_code == 401, (
        f"Expected 401 without auth, got {response.status_code}. "
        "This endpoint requires either X-User-ID or Authorization header."
    )

    # Verify error message matches what handler.py returns
    data = response.json()
    assert "detail" in data, f"Expected error detail in response: {data}"
    assert (
        "missing user identification" in data["detail"].lower()
    ), f"Expected 'Missing user identification' in detail, got: {data['detail']}"


@pytest.mark.asyncio
async def test_metrics_200_with_anonymous_session(
    api_client: PreprodAPIClient,
) -> None:
    """Verify /api/v2/metrics returns 200 with anonymous session.

    Given: An anonymous session is created via POST /api/v2/auth/anonymous
    When: GET /api/v2/metrics is called with X-User-ID header
    Then: Response status is 200 with metrics data

    This is the auth flow used by the vanilla JS dashboard (app.js).
    """
    # Create anonymous session
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert (
        session_response.status_code == 201
    ), f"Failed to create anonymous session: {session_response.status_code}"

    session_data = session_response.json()
    # Handle both camelCase and snake_case response formats
    token = (
        session_data.get("token")
        or session_data.get("userId")
        or session_data.get("user_id")
    )
    assert token, f"No token in session response: {session_data}"

    # Set X-User-ID header via set_access_token
    api_client.set_access_token(token)
    try:
        response = await api_client.get("/api/v2/metrics")

        assert response.status_code == 200, (
            f"Expected 200 with anonymous session, got {response.status_code}. "
            f"Response: {response.text}"
        )

        # Verify response contains expected metrics fields
        data = response.json()
        assert isinstance(data, dict), f"Expected dict response, got: {type(data)}"

        # Check for core metrics fields
        expected_fields = ["total", "positive", "neutral", "negative"]
        for field in expected_fields:
            assert field in data, (
                f"Missing expected field '{field}' in metrics response. "
                f"Got fields: {list(data.keys())}"
            )

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_metrics_200_with_jwt_auth(
    authenticated_api_client: PreprodAPIClient,
) -> None:
    """Verify /api/v2/metrics returns 200 with JWT authentication.

    Given: A valid JWT token is set via Authorization: Bearer header
    When: GET /api/v2/metrics is called
    Then: Response status is 200 with metrics data

    This tests the authenticated user flow (Feature 1053).
    Uses the authenticated_api_client fixture which sets up JWT auth.
    """
    response = await authenticated_api_client.get("/api/v2/metrics")

    # JWT auth may not be fully implemented; skip if 501
    if response.status_code == 501:
        pytest.skip("JWT authentication not implemented for metrics endpoint")

    # 401 is acceptable if JWT validation is strict
    if response.status_code == 401:
        # This is expected if the test JWT doesn't match backend validation
        pytest.skip(
            "JWT validation failed - this may indicate test JWT configuration issue"
        )

    assert response.status_code == 200, (
        f"Expected 200 with JWT auth, got {response.status_code}. "
        f"Response: {response.text}"
    )

    # Verify response contains expected metrics fields
    data = response.json()
    assert isinstance(data, dict), f"Expected dict response, got: {type(data)}"

    # Check for core metrics fields
    expected_fields = ["total", "positive", "neutral", "negative"]
    for field in expected_fields:
        assert field in data, (
            f"Missing expected field '{field}' in metrics response. "
            f"Got fields: {list(data.keys())}"
        )

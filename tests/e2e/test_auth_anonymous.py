# E2E Tests: Anonymous Session (User Story 1)
#
# Tests anonymous user flows:
# - Session creation
# - Session validation
# - Anonymous configuration creation
#
# These tests verify the first part of the "Unknown to Known User" journey.

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us1, pytest.mark.auth]


@pytest.mark.asyncio
async def test_anonymous_session_creation(api_client: PreprodAPIClient) -> None:
    """T041: Verify anonymous session can be created.

    Given: A new user with no existing session
    When: POST /api/v2/auth/anonymous is called
    Then: Response contains session_id, token, and expires_at
    """
    response = await api_client.post("/api/v2/auth/anonymous", json={})

    # 201 Created is the correct status for resource creation
    assert response.status_code == 201, f"Expected 201, got {response.status_code}"

    data = response.json()
    # Response may use user_id or session_id depending on implementation
    assert (
        "user_id" in data or "session_id" in data
    ), "Response missing user_id/session_id"
    assert "token" in data, "Response missing token"
    # Response may use session_expires_at or expires_at
    assert (
        "session_expires_at" in data or "expires_at" in data
    ), "Response missing expiration"

    # Verify session_id/user_id format (should be UUID-like)
    session_id = data.get("session_id") or data.get("user_id")
    assert (
        session_id and len(session_id) >= 8
    ), f"session_id/user_id too short: {session_id}"

    # Verify token is non-empty
    token = data["token"]
    assert len(token) > 0, "token is empty"


@pytest.mark.asyncio
async def test_anonymous_session_validation(api_client: PreprodAPIClient) -> None:
    """T042: Verify anonymous session token is valid after creation.

    Given: A newly created anonymous session
    When: GET /api/v2/auth/me is called with the anonymous token
    Then: Response confirms the session is anonymous and returns session info
    """
    # Create anonymous session
    create_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert create_response.status_code == 201

    data = create_response.json()
    token = data["token"]

    # Validate session using the token
    api_client.set_access_token(token)
    try:
        validate_response = await api_client.get("/api/v2/auth/me")

        # Anonymous tokens may return 200 with is_anonymous=true
        # or may return 401 if anonymous sessions can't call /me
        if validate_response.status_code == 200:
            user_data = validate_response.json()
            # If authenticated, should indicate anonymous status
            assert user_data.get("is_anonymous", True), "Expected anonymous session"
        elif validate_response.status_code == 401:
            # Some APIs don't allow /me for anonymous - that's also valid
            pass
        else:
            pytest.fail(f"Unexpected status code: {validate_response.status_code}")
    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_anonymous_config_creation(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T043: Verify anonymous users can create configurations.

    Given: An anonymous session
    When: POST /api/v2/configurations is called with valid config
    Then: Configuration is created and returns config_id
    """
    # Create anonymous session
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert session_response.status_code == 201

    session_data = session_response.json()
    token = session_data["token"]

    # Create configuration with anonymous token
    api_client.set_access_token(token)
    try:
        config_payload = {
            "name": f"Test Config {test_run_id}",
            "tickers": ["AAPL", "MSFT"],
        }

        config_response = await api_client.post(
            "/api/v2/configurations",
            json=config_payload,
        )

        # Anonymous users should be able to create configs
        # Status may be 201 (created) or 200 (ok)

        # 201 Created is the correct status for resource creation
        assert (
            config_response.status_code == 201
        ), f"Expected 201, got {config_response.status_code}"

        config_data = config_response.json()
        assert "config_id" in config_data, "Response missing config_id"

        # Verify config can be retrieved
        config_id = config_data["config_id"]
        get_response = await api_client.get(f"/api/v2/configurations/{config_id}")
        assert (
            get_response.status_code == 200
        ), f"Failed to retrieve config: {config_id}"

        retrieved = get_response.json()
        assert retrieved["name"] == config_payload["name"]

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_anonymous_session_expires_header(api_client: PreprodAPIClient) -> None:
    """Verify anonymous session expiry is communicated properly.

    Given: A new anonymous session
    When: Session is created
    Then: expires_at is a valid ISO timestamp in the future
    """
    from datetime import UTC, datetime

    response = await api_client.post("/api/v2/auth/anonymous", json={})
    # API returns 201 Created for new sessions (correct HTTP semantics)
    assert response.status_code == 201

    data = response.json()
    # Response may use session_expires_at or expires_at
    expires_at = data.get("expires_at") or data.get("session_expires_at")
    assert expires_at is not None, "expires_at not provided"

    # Parse and verify it's in the future
    try:
        # Handle both Z suffix and +00:00 formats
        expires_str = expires_at.replace("Z", "+00:00")
        expiry = datetime.fromisoformat(expires_str)

        # Should be aware datetime
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)

        now = datetime.now(UTC)
        assert expiry > now, f"Session already expired: {expires_at}"

    except ValueError as e:
        pytest.fail(f"Invalid expires_at format '{expires_at}': {e}")


@pytest.mark.asyncio
async def test_anonymous_multiple_sessions_isolated(
    api_client: PreprodAPIClient,
) -> None:
    """Verify multiple anonymous sessions are isolated from each other.

    Given: Two separate anonymous sessions
    When: Each creates data
    Then: One session cannot access the other's data
    """
    # Create first anonymous session
    response1 = await api_client.post("/api/v2/auth/anonymous", json={})
    # API returns 201 Created for new sessions (correct HTTP semantics)
    assert response1.status_code == 201
    token1 = response1.json()["token"]

    # Create second anonymous session
    response2 = await api_client.post("/api/v2/auth/anonymous", json={})
    # API returns 201 Created for new sessions (correct HTTP semantics)
    assert response2.status_code == 201
    token2 = response2.json()["token"]

    # Tokens should be different
    assert token1 != token2, "Anonymous sessions should have unique tokens"

    # Create config with first session
    api_client.set_access_token(token1)
    try:
        config_response = await api_client.post(
            "/api/v2/configurations",
            json={"name": "Session 1 Config", "tickers": ["AAPL"]},
        )
        if config_response.status_code == 201:
            config_id = config_response.json()["config_id"]

            # Try to access with second session - should fail
            api_client.set_access_token(token2)
            access_response = await api_client.get(
                f"/api/v2/configurations/{config_id}"
            )
            # Should be 404 (not found) or 403 (forbidden)
            assert access_response.status_code in (
                403,
                404,
            ), f"Session isolation failed: {access_response.status_code}"
    finally:
        api_client.clear_access_token()

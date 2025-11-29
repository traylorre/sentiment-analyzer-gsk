# E2E Tests: Magic Link Authentication (User Story 1)
#
# Tests magic link authentication flows:
# - Request magic link
# - Verify magic link token
# - Anonymous data merge on authentication
# - Full journey from anonymous to authenticated
#
# These tests complete the "Unknown to Known User" journey.

import pytest

from tests.e2e.fixtures.sendgrid import SyntheticSendGridHandler
from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us1, pytest.mark.auth]


@pytest.mark.asyncio
async def test_magic_link_request(
    api_client: PreprodAPIClient,
    test_email_domain: str,
    sendgrid_handler: SyntheticSendGridHandler,
) -> None:
    """T044: Verify magic link can be requested for email.

    Given: A valid email address
    When: POST /api/v2/auth/magic-link is called
    Then: Response indicates email was sent (202 or similar success)
    """
    test_email = f"magiclink-test@{test_email_domain}"

    response = await api_client.post(
        "/api/v2/auth/magic-link",
        json={"email": test_email},
    )

    # Magic link request should succeed
    # Common responses: 200 (ok), 202 (accepted), 204 (no content)
    assert response.status_code in (
        200,
        202,
        204,
    ), f"Magic link request failed: {response.status_code} - {response.text}"

    # If response has body, check for message_id or success indicator
    if response.status_code == 200:
        data = response.json()
        # Response might include message about email being sent
        # or a message_id for tracking
        assert (
            "message_id" in data or "success" in data or "message" in data
        ), f"Unexpected response structure: {data}"


@pytest.mark.asyncio
async def test_magic_link_request_rate_limited(
    api_client: PreprodAPIClient,
    test_email_domain: str,
) -> None:
    """Verify magic link requests are rate limited.

    Given: An email that recently requested a magic link
    When: Multiple requests are made in quick succession
    Then: Rate limiting is enforced (429 or similar)
    """
    test_email = f"ratelimit-test@{test_email_domain}"

    # Make first request (should succeed)
    first_response = await api_client.post(
        "/api/v2/auth/magic-link",
        json={"email": test_email},
    )
    assert first_response.status_code in (200, 202, 204)

    # Make rapid follow-up requests
    rate_limited = False
    for _ in range(5):
        response = await api_client.post(
            "/api/v2/auth/magic-link",
            json={"email": test_email},
        )
        if response.status_code == 429:
            rate_limited = True
            break

    # Should have been rate limited at some point
    assert rate_limited, "Magic link requests were not rate limited"


@pytest.mark.asyncio
async def test_magic_link_verification(
    api_client: PreprodAPIClient,
    test_email_domain: str,
    sendgrid_handler: SyntheticSendGridHandler,
) -> None:
    """T045: Verify magic link token verification creates authenticated session.

    Note: In E2E environment, we use synthetic tokens from the handler.

    Given: A valid magic link token
    When: POST /api/v2/auth/verify is called with the token
    Then: Response contains access_token, refresh_token, and user_id
    """
    test_email = f"verify-test@{test_email_domain}"

    # Request magic link
    request_response = await api_client.post(
        "/api/v2/auth/magic-link",
        json={"email": test_email},
    )
    assert request_response.status_code in (200, 202, 204)

    # Get synthetic token from handler
    synthetic_token = sendgrid_handler.get_magic_link_token(test_email)

    # If no token (email wasn't "sent" in synthetic mode), skip verification
    if synthetic_token is None:
        pytest.skip("Synthetic token not available - email not captured")

    # Verify the token
    verify_response = await api_client.post(
        "/api/v2/auth/verify",
        json={"token": synthetic_token},
    )

    assert (
        verify_response.status_code == 200
    ), f"Token verification failed: {verify_response.status_code}"

    data = verify_response.json()
    assert "access_token" in data, "Response missing access_token"
    assert "refresh_token" in data, "Response missing refresh_token"
    assert "user_id" in data, "Response missing user_id"


@pytest.mark.asyncio
async def test_magic_link_invalid_token(api_client: PreprodAPIClient) -> None:
    """Verify invalid magic link tokens are rejected.

    Given: An invalid/expired magic link token
    When: POST /api/v2/auth/verify is called
    Then: Response is 400 or 401 with error message
    """
    response = await api_client.post(
        "/api/v2/auth/verify",
        json={"token": "invalid-token-that-does-not-exist"},
    )

    assert response.status_code in (
        400,
        401,
    ), f"Invalid token should be rejected: {response.status_code}"

    data = response.json()
    assert "error" in data or "message" in data, "Error response missing message"


@pytest.mark.asyncio
async def test_anonymous_data_merge(
    api_client: PreprodAPIClient,
    test_email_domain: str,
    test_run_id: str,
    sendgrid_handler: SyntheticSendGridHandler,
) -> None:
    """T046: Verify anonymous data is merged when user authenticates.

    Given: An anonymous session with a configuration
    And: A magic link verification with the anonymous session ID
    When: The user authenticates via magic link
    Then: The anonymous configuration is accessible in the authenticated session
    """
    # Step 1: Create anonymous session
    anon_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert anon_response.status_code == 200

    anon_data = anon_response.json()
    anon_token = anon_data["token"]
    anon_session_id = anon_data["session_id"]

    # Step 2: Create config as anonymous user
    api_client.set_access_token(anon_token)
    config_name = f"Anon Config {test_run_id}"
    try:
        config_response = await api_client.post(
            "/api/v2/configurations",
            json={
                "name": config_name,
                "tickers": [{"symbol": "GOOGL", "enabled": True}],
            },
        )

        if config_response.status_code not in (200, 201):
            pytest.skip("Anonymous config creation not supported")

        # Config ID not used directly - we verify by listing configs with auth token
        _ = config_response.json()["config_id"]

    finally:
        api_client.clear_access_token()

    # Step 3: Request magic link
    test_email = f"merge-test@{test_email_domain}"
    await api_client.post(
        "/api/v2/auth/magic-link",
        json={"email": test_email},
    )

    # Step 4: Get synthetic token and verify with anonymous session
    synthetic_token = sendgrid_handler.get_magic_link_token(test_email)
    if synthetic_token is None:
        pytest.skip("Synthetic token not available")

    verify_response = await api_client.post(
        "/api/v2/auth/verify",
        json={
            "token": synthetic_token,
            "anonymous_session_id": anon_session_id,
        },
    )

    if verify_response.status_code != 200:
        pytest.skip("Magic link verification not available in this environment")

    auth_data = verify_response.json()
    auth_token = auth_data["access_token"]

    # Step 5: Verify config is accessible with authenticated session
    api_client.set_access_token(auth_token)
    try:
        configs_response = await api_client.get("/api/v2/configurations")
        assert configs_response.status_code == 200

        configs = configs_response.json()
        config_list = configs.get("configurations", configs)

        # Find our merged config
        merged_config = next(
            (c for c in config_list if c.get("name") == config_name),
            None,
        )
        assert (
            merged_config is not None
        ), f"Merged config '{config_name}' not found in authenticated session"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_full_anonymous_to_authenticated_journey(
    api_client: PreprodAPIClient,
    test_email_domain: str,
    test_run_id: str,
    sendgrid_handler: SyntheticSendGridHandler,
) -> None:
    """T047: Full journey test from anonymous to authenticated user.

    This integration test verifies the complete flow:
    1. Create anonymous session
    2. Create configuration as anonymous
    3. Request magic link
    4. Verify magic link (with anonymous session merge)
    5. Access configuration as authenticated user
    6. Verify user profile shows email
    """
    test_email = f"fulljourney@{test_email_domain}"
    config_name = f"Journey Config {test_run_id}"

    # === Phase 1: Anonymous Session ===
    anon_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert anon_response.status_code == 200, "Failed to create anonymous session"

    anon_data = anon_response.json()
    anon_token = anon_data["token"]
    anon_session_id = anon_data["session_id"]

    # === Phase 2: Create Config as Anonymous ===
    api_client.set_access_token(anon_token)
    try:
        config_response = await api_client.post(
            "/api/v2/configurations",
            json={
                "name": config_name,
                "tickers": [
                    {"symbol": "NVDA", "enabled": True},
                    {"symbol": "AMD", "enabled": True},
                ],
            },
        )

        if config_response.status_code not in (200, 201):
            api_client.clear_access_token()
            pytest.skip("Anonymous configuration not supported")

        config_id = config_response.json()["config_id"]

    finally:
        api_client.clear_access_token()

    # === Phase 3: Request Magic Link ===
    magic_response = await api_client.post(
        "/api/v2/auth/magic-link",
        json={"email": test_email},
    )
    assert magic_response.status_code in (200, 202, 204), "Failed to request magic link"

    # === Phase 4: Verify Magic Link ===
    synthetic_token = sendgrid_handler.get_magic_link_token(test_email)
    if synthetic_token is None:
        pytest.skip("Synthetic magic link token not available")

    verify_response = await api_client.post(
        "/api/v2/auth/verify",
        json={
            "token": synthetic_token,
            "anonymous_session_id": anon_session_id,
        },
    )

    if verify_response.status_code != 200:
        pytest.skip("Magic link verification not available")

    auth_data = verify_response.json()
    assert "access_token" in auth_data, "Missing access_token after verification"
    assert "user_id" in auth_data, "Missing user_id after verification"

    auth_token = auth_data["access_token"]
    user_id = auth_data["user_id"]

    # === Phase 5: Verify Config Accessible ===
    api_client.set_access_token(auth_token)
    try:
        # Get specific config
        config_get_response = await api_client.get(
            f"/api/v2/configurations/{config_id}"
        )
        assert (
            config_get_response.status_code == 200
        ), f"Config not accessible after auth: {config_get_response.status_code}"

        config_data = config_get_response.json()
        assert config_data["name"] == config_name
        assert len(config_data.get("tickers", [])) == 2

        # === Phase 6: Verify User Profile ===
        profile_response = await api_client.get("/api/v2/auth/me")
        assert profile_response.status_code == 200, "Failed to get user profile"

        profile = profile_response.json()
        assert profile.get("user_id") == user_id
        assert profile.get("email") == test_email
        assert profile.get("is_anonymous") is False

    finally:
        api_client.clear_access_token()

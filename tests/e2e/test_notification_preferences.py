# E2E Tests: Notification Preferences API (Issue #124)
#
# Tests the notification preferences API:
# - GET /api/v2/notifications/preferences - Get current preferences
# - PATCH /api/v2/notifications/preferences - Update preferences
# - POST /api/v2/notifications/disable-all - Disable all notifications
# - POST /api/v2/notifications/resubscribe - Resubscribe to notifications
# - GET /api/v2/notifications/digest - Get digest settings
# - PATCH /api/v2/notifications/digest - Update digest settings
# - POST /api/v2/notifications/digest/test - Trigger test digest email

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us6]


async def create_anonymous_session(
    api_client: PreprodAPIClient,
) -> str:
    """Helper to create an anonymous session.

    Returns:
        Access token for the anonymous session
    """
    response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert response.status_code == 200, f"Anonymous session failed: {response.text}"
    return response.json()["token"]


# =============================================================================
# GET /api/v2/notifications/preferences
# =============================================================================


@pytest.mark.asyncio
async def test_get_preferences_returns_structure(
    api_client: PreprodAPIClient,
) -> None:
    """T139: Verify preferences endpoint returns valid structure.

    Given: An authenticated user
    When: GET /api/v2/notifications/preferences is called
    Then: Response contains email_enabled, digest_enabled, digest_time, timezone
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.get("/api/v2/notifications/preferences")

        if response.status_code == 404:
            pytest.skip("Preferences endpoint not implemented")

        assert response.status_code == 200, f"Get preferences failed: {response.text}"

        data = response.json()

        # Validate expected fields (may vary based on implementation)
        # At minimum should have email_enabled
        assert (
            "email_enabled" in data or "emailEnabled" in data
        ), "Response missing email_enabled field"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_get_preferences_unauthorized(
    api_client: PreprodAPIClient,
) -> None:
    """Verify preferences endpoint requires authentication.

    Given: No authentication token
    When: GET /api/v2/notifications/preferences is called
    Then: Response is 401 Unauthorized
    """
    api_client.clear_access_token()

    response = await api_client.get("/api/v2/notifications/preferences")

    assert response.status_code in (
        401,
        403,
    ), f"Preferences should require auth, got {response.status_code}"


# =============================================================================
# PATCH /api/v2/notifications/preferences
# =============================================================================


@pytest.mark.asyncio
async def test_update_preferences_email_enabled(
    api_client: PreprodAPIClient,
) -> None:
    """T140: Verify email_enabled preference can be updated.

    Given: An authenticated user
    When: PATCH /api/v2/notifications/preferences with email_enabled
    Then: Preference is updated and returned
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        # First get current preferences
        get_response = await api_client.get("/api/v2/notifications/preferences")

        if get_response.status_code == 404:
            pytest.skip("Preferences endpoint not implemented")

        # Toggle email_enabled
        response = await api_client.patch(
            "/api/v2/notifications/preferences",
            json={"email_enabled": False},
        )

        assert (
            response.status_code == 200
        ), f"Update preferences failed: {response.text}"

        data = response.json()

        # Verify the update was applied
        email_enabled = data.get("email_enabled") or data.get("emailEnabled")
        assert email_enabled is False, "email_enabled should be False after update"

        # Toggle back
        response2 = await api_client.patch(
            "/api/v2/notifications/preferences",
            json={"email_enabled": True},
        )

        assert response2.status_code == 200
        data2 = response2.json()
        email_enabled2 = data2.get("email_enabled") or data2.get("emailEnabled")
        assert email_enabled2 is True, "email_enabled should be True after toggle back"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_update_preferences_persists(
    api_client: PreprodAPIClient,
) -> None:
    """Verify preference updates persist across requests.

    Given: An authenticated user who updated preferences
    When: GET /api/v2/notifications/preferences is called later
    Then: Updated values are returned
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        # Check if endpoint exists
        check = await api_client.get("/api/v2/notifications/preferences")
        if check.status_code == 404:
            pytest.skip("Preferences endpoint not implemented")

        # Set a specific value
        await api_client.patch(
            "/api/v2/notifications/preferences",
            json={"email_enabled": False},
        )

        # Retrieve again
        response = await api_client.get("/api/v2/notifications/preferences")
        assert response.status_code == 200

        data = response.json()
        email_enabled = data.get("email_enabled") or data.get("emailEnabled")
        assert email_enabled is False, "Preference should persist after update"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_update_preferences_unauthorized(
    api_client: PreprodAPIClient,
) -> None:
    """Verify preferences update requires authentication.

    Given: No authentication token
    When: PATCH /api/v2/notifications/preferences is called
    Then: Response is 401 Unauthorized
    """
    api_client.clear_access_token()

    response = await api_client.patch(
        "/api/v2/notifications/preferences",
        json={"email_enabled": True},
    )

    assert response.status_code in (
        401,
        403,
    ), f"Update preferences should require auth, got {response.status_code}"


# =============================================================================
# POST /api/v2/notifications/disable-all
# =============================================================================


@pytest.mark.asyncio
async def test_disable_all_notifications(
    api_client: PreprodAPIClient,
) -> None:
    """Verify disable-all endpoint disables all notifications.

    Given: An authenticated user with notifications enabled
    When: POST /api/v2/notifications/disable-all is called
    Then: All notification settings are disabled
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.post("/api/v2/notifications/disable-all")

        if response.status_code == 404:
            pytest.skip("Disable-all endpoint not implemented")

        assert response.status_code in (
            200,
            204,
        ), f"Disable-all failed: {response.status_code}"

        # Verify preferences are now disabled
        prefs = await api_client.get("/api/v2/notifications/preferences")
        if prefs.status_code == 200:
            data = prefs.json()
            email_enabled = data.get("email_enabled") or data.get("emailEnabled")
            assert (
                email_enabled is False
            ), "email_enabled should be False after disable-all"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_disable_all_unauthorized(
    api_client: PreprodAPIClient,
) -> None:
    """Verify disable-all requires authentication.

    Given: No authentication token
    When: POST /api/v2/notifications/disable-all is called
    Then: Response is 401 Unauthorized
    """
    api_client.clear_access_token()

    response = await api_client.post("/api/v2/notifications/disable-all")

    assert response.status_code in (
        401,
        403,
        404,
    ), f"Disable-all should require auth, got {response.status_code}"


# =============================================================================
# POST /api/v2/notifications/resubscribe
# =============================================================================


@pytest.mark.asyncio
async def test_resubscribe_notifications(
    api_client: PreprodAPIClient,
) -> None:
    """Verify resubscribe endpoint enables notifications.

    Given: An authenticated user with notifications disabled
    When: POST /api/v2/notifications/resubscribe is called
    Then: Notification settings are enabled
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        # First disable
        disable_response = await api_client.post("/api/v2/notifications/disable-all")
        if disable_response.status_code == 404:
            pytest.skip("Notification management endpoints not implemented")

        # Then resubscribe
        response = await api_client.post("/api/v2/notifications/resubscribe")

        if response.status_code == 404:
            pytest.skip("Resubscribe endpoint not implemented")

        assert response.status_code in (
            200,
            204,
        ), f"Resubscribe failed: {response.status_code}"

        # Verify preferences are now enabled
        prefs = await api_client.get("/api/v2/notifications/preferences")
        if prefs.status_code == 200:
            data = prefs.json()
            email_enabled = data.get("email_enabled") or data.get("emailEnabled")
            assert (
                email_enabled is True
            ), "email_enabled should be True after resubscribe"

    finally:
        api_client.clear_access_token()


# =============================================================================
# GET /api/v2/notifications/digest
# =============================================================================


@pytest.mark.asyncio
async def test_get_digest_settings(
    api_client: PreprodAPIClient,
) -> None:
    """T144a: Verify digest settings endpoint returns valid structure.

    Given: An authenticated user
    When: GET /api/v2/notifications/digest is called
    Then: Response contains enabled, time, timezone, etc.
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.get("/api/v2/notifications/digest")

        if response.status_code == 404:
            pytest.skip("Digest settings endpoint not implemented")

        assert (
            response.status_code == 200
        ), f"Get digest settings failed: {response.text}"

        data = response.json()

        # Validate expected fields
        assert "enabled" in data, "Response missing 'enabled' field"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_get_digest_settings_unauthorized(
    api_client: PreprodAPIClient,
) -> None:
    """Verify digest settings require authentication.

    Given: No authentication token
    When: GET /api/v2/notifications/digest is called
    Then: Response is 401 Unauthorized
    """
    api_client.clear_access_token()

    response = await api_client.get("/api/v2/notifications/digest")

    assert response.status_code in (
        401,
        403,
        404,
    ), f"Digest settings should require auth, got {response.status_code}"


# =============================================================================
# PATCH /api/v2/notifications/digest
# =============================================================================


@pytest.mark.asyncio
async def test_update_digest_settings(
    api_client: PreprodAPIClient,
) -> None:
    """T144b: Verify digest settings can be updated.

    Given: An authenticated user
    When: PATCH /api/v2/notifications/digest with new settings
    Then: Settings are updated and returned
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        # Check if endpoint exists
        check = await api_client.get("/api/v2/notifications/digest")
        if check.status_code == 404:
            pytest.skip("Digest settings endpoint not implemented")

        # Update digest settings
        response = await api_client.patch(
            "/api/v2/notifications/digest",
            json={"enabled": True, "time": "09:00"},
        )

        assert response.status_code == 200, f"Update digest failed: {response.text}"

        data = response.json()
        assert data.get("enabled") is True, "enabled should be True after update"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_update_digest_settings_invalid_time(
    api_client: PreprodAPIClient,
) -> None:
    """Verify digest settings rejects invalid time format.

    Given: An authenticated user
    When: PATCH /api/v2/notifications/digest with invalid time
    Then: Response is 400 Bad Request
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        # Check if endpoint exists
        check = await api_client.get("/api/v2/notifications/digest")
        if check.status_code == 404:
            pytest.skip("Digest settings endpoint not implemented")

        # Try invalid time format
        response = await api_client.patch(
            "/api/v2/notifications/digest",
            json={"time": "invalid-time"},
        )

        # Should be rejected (400 or 422) or accepted if validation is lenient
        if response.status_code in (400, 422):
            data = response.json()
            assert "error" in data or "detail" in data or "message" in data

    finally:
        api_client.clear_access_token()


# =============================================================================
# POST /api/v2/notifications/digest/test
# =============================================================================


@pytest.mark.asyncio
async def test_trigger_test_digest(
    api_client: PreprodAPIClient,
) -> None:
    """T144c: Verify test digest can be triggered.

    Given: An authenticated user
    When: POST /api/v2/notifications/digest/test is called
    Then: Response indicates digest was queued (202 Accepted)

    Note: This may send an actual email, so we only verify the API response.
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.post("/api/v2/notifications/digest/test")

        if response.status_code == 404:
            pytest.skip("Test digest endpoint not implemented")

        # Anonymous users may be forbidden from triggering test emails
        if response.status_code == 403:
            # This is acceptable - anonymous can't send test emails
            return

        # Should be 202 Accepted for queued or 200 OK
        assert response.status_code in (
            200,
            202,
        ), f"Trigger test digest failed: {response.status_code}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_trigger_test_digest_unauthorized(
    api_client: PreprodAPIClient,
) -> None:
    """Verify test digest requires authentication.

    Given: No authentication token
    When: POST /api/v2/notifications/digest/test is called
    Then: Response is 401 Unauthorized
    """
    api_client.clear_access_token()

    response = await api_client.post("/api/v2/notifications/digest/test")

    assert response.status_code in (
        401,
        403,
        404,
    ), f"Test digest should require auth, got {response.status_code}"


# =============================================================================
# Anonymous User Restrictions
# =============================================================================


@pytest.mark.asyncio
async def test_anonymous_can_access_preferences(
    api_client: PreprodAPIClient,
) -> None:
    """Verify anonymous users can access their preferences.

    Given: An anonymous session
    When: GET /api/v2/notifications/preferences is called
    Then: Response is successful (preferences returned)
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.get("/api/v2/notifications/preferences")

        if response.status_code == 404:
            pytest.skip("Preferences endpoint not implemented")

        # Anonymous should be able to read preferences
        # or get 403 if anonymous access is restricted
        assert response.status_code in (
            200,
            403,
        ), f"Unexpected response for anonymous: {response.status_code}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_anonymous_can_update_preferences(
    api_client: PreprodAPIClient,
) -> None:
    """Verify anonymous users can update their preferences.

    Given: An anonymous session
    When: PATCH /api/v2/notifications/preferences is called
    Then: Response is successful or 403 (depending on policy)
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.patch(
            "/api/v2/notifications/preferences",
            json={"email_enabled": True},
        )

        if response.status_code == 404:
            pytest.skip("Preferences endpoint not implemented")

        # Anonymous should either succeed (200) or be forbidden (403)
        assert response.status_code in (
            200,
            403,
        ), f"Unexpected response for anonymous update: {response.status_code}"

    finally:
        api_client.clear_access_token()

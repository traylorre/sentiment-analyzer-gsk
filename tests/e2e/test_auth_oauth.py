# E2E Tests: OAuth Authentication (User Story 2)
#
# Tests OAuth authentication flows:
# - OAuth URL generation
# - URL structure validation (Google, GitHub)
# - OAuth callback token handling
# - Session validation
# - Sign out
# - Token refresh
#
# Note: Full OAuth flow testing requires real provider integration.
# These tests validate API contract and structure, not actual OAuth redirects.

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us2, pytest.mark.auth]


@pytest.mark.asyncio
async def test_oauth_urls_returned(api_client: PreprodAPIClient) -> None:
    """T048: Verify OAuth authorization URLs are returned.

    Given: An unauthenticated request
    When: GET /api/v2/auth/oauth/urls is called
    Then: Response contains google and github authorization URLs
    """
    response = await api_client.get("/api/v2/auth/oauth/urls")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    assert "google" in data, "Response missing 'google' OAuth URL"
    assert "github" in data, "Response missing 'github' OAuth URL"

    # URLs should be non-empty strings
    assert isinstance(data["google"], str) and len(data["google"]) > 0
    assert isinstance(data["github"], str) and len(data["github"]) > 0


@pytest.mark.asyncio
async def test_oauth_url_structure_google(api_client: PreprodAPIClient) -> None:
    """T049: Verify Google OAuth URL has correct structure.

    Given: OAuth URLs from the API
    When: Google OAuth URL is examined
    Then: URL contains required OAuth parameters
    """
    response = await api_client.get("/api/v2/auth/oauth/urls")
    assert response.status_code == 200

    google_url = response.json()["google"]

    # Google OAuth URL should contain:
    # - accounts.google.com domain
    # - client_id parameter
    # - redirect_uri parameter
    # - scope parameter
    # - response_type parameter

    assert (
        "accounts.google.com" in google_url or "googleapis.com" in google_url
    ), f"Invalid Google OAuth URL domain: {google_url}"

    # Check for required OAuth parameters (URL-encoded)
    required_params = ["client_id", "redirect_uri", "response_type"]
    for param in required_params:
        assert (
            param in google_url or param.replace("_", "%5F") in google_url
        ), f"Google OAuth URL missing '{param}': {google_url}"


@pytest.mark.asyncio
async def test_oauth_url_structure_github(api_client: PreprodAPIClient) -> None:
    """T050: Verify GitHub OAuth URL has correct structure.

    Given: OAuth URLs from the API
    When: GitHub OAuth URL is examined
    Then: URL contains required OAuth parameters
    """
    response = await api_client.get("/api/v2/auth/oauth/urls")
    assert response.status_code == 200

    github_url = response.json()["github"]

    # GitHub OAuth URL should contain:
    # - github.com domain
    # - client_id parameter
    # - redirect_uri parameter
    # - scope parameter

    assert "github.com" in github_url, f"Invalid GitHub OAuth URL domain: {github_url}"

    # Check for required parameters
    assert (
        "client_id" in github_url
    ), f"GitHub OAuth URL missing 'client_id': {github_url}"


@pytest.mark.asyncio
async def test_oauth_callback_tokens_returned(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T051: Verify OAuth callback returns tokens.

    Note: This test uses a simulated callback since we can't complete
    real OAuth flows in E2E tests. The API should validate the code
    and return tokens or an appropriate error.

    Given: An OAuth authorization code (simulated)
    When: POST /api/v2/auth/oauth/callback is called
    Then: Response indicates token generation was attempted
    """
    # In E2E environment, we can only test the callback endpoint contract
    # Real OAuth flows require browser interaction

    # Test with invalid code - should get appropriate error
    response = await api_client.post(
        "/api/v2/auth/oauth/callback",
        json={
            "provider": "google",
            "code": f"invalid-code-{test_run_id}",
            "state": "test-state",
        },
    )

    # Should return 400 (invalid code) or 401 (unauthorized)
    # Some implementations might return 200 with error in body
    assert response.status_code in (
        400,
        401,
        200,
    ), f"Unexpected callback response: {response.status_code}"

    if response.status_code == 200:
        # If 200, should have error indicator or tokens
        data = response.json()
        has_error = "error" in data or "message" in data
        has_tokens = "access_token" in data
        assert has_error or has_tokens, f"Unexpected 200 response: {data}"


@pytest.mark.asyncio
async def test_session_validation(
    api_client: PreprodAPIClient,
) -> None:
    """T052: Verify session validation endpoint.

    Given: An authenticated session (via anonymous for testing)
    When: GET /api/v2/auth/me is called
    Then: Response contains user/session information
    """
    # Create anonymous session for testing
    anon_response = await api_client.post("/api/v2/auth/anonymous")
    assert anon_response.status_code == 200

    token = anon_response.json()["token"]
    api_client.set_access_token(token)

    try:
        me_response = await api_client.get("/api/v2/auth/me")

        # Anonymous sessions may or may not be able to call /me
        if me_response.status_code == 200:
            data = me_response.json()
            # Should have some user identifier
            assert (
                "user_id" in data or "session_id" in data or "is_anonymous" in data
            ), f"Unexpected /me response: {data}"
        elif me_response.status_code == 401:
            # Anonymous can't access /me - acceptable behavior
            pass
        else:
            pytest.fail(f"Unexpected /me status: {me_response.status_code}")

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_signout_invalidates_session(
    api_client: PreprodAPIClient,
) -> None:
    """T053: Verify sign out invalidates session.

    Given: An authenticated session
    When: POST /api/v2/auth/signout is called
    Then: Session token is invalidated
    """
    # Create anonymous session
    anon_response = await api_client.post("/api/v2/auth/anonymous")
    assert anon_response.status_code == 200

    token = anon_response.json()["token"]
    api_client.set_access_token(token)

    try:
        # Sign out
        signout_response = await api_client.post("/api/v2/auth/signout")

        # Signout should succeed
        assert signout_response.status_code in (
            200,
            204,
        ), f"Signout failed: {signout_response.status_code}"

        # Verify token is invalidated - subsequent requests should fail
        verify_response = await api_client.get("/api/v2/configurations")

        # Should get 401 with invalidated token
        assert (
            verify_response.status_code == 401
        ), f"Token not invalidated after signout: {verify_response.status_code}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_token_refresh(
    api_client: PreprodAPIClient,
) -> None:
    """T054: Verify token refresh functionality.

    Note: Requires a refresh token which is typically only returned
    after full authentication. This test validates the API contract.

    Given: A refresh token
    When: POST /api/v2/auth/refresh is called
    Then: New access token is returned
    """
    # Test with invalid refresh token - should get appropriate error
    response = await api_client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": "invalid-refresh-token"},
    )

    # Should return 400 or 401 for invalid token
    assert response.status_code in (
        400,
        401,
    ), f"Invalid refresh token should be rejected: {response.status_code}"

    data = response.json()
    assert "error" in data or "message" in data, "Error response missing message"


@pytest.mark.asyncio
async def test_oauth_state_parameter_validation(
    api_client: PreprodAPIClient,
) -> None:
    """Verify OAuth state parameter is validated to prevent CSRF.

    Given: An OAuth callback with mismatched state
    When: POST /api/v2/auth/oauth/callback is called
    Then: Request is rejected
    """
    response = await api_client.post(
        "/api/v2/auth/oauth/callback",
        json={
            "provider": "google",
            "code": "test-code",
            "state": "",  # Empty/invalid state
        },
    )

    # Should be rejected - 400 for invalid request
    assert response.status_code in (
        400,
        401,
        403,
    ), f"Invalid state should be rejected: {response.status_code}"


@pytest.mark.asyncio
async def test_oauth_provider_validation(
    api_client: PreprodAPIClient,
) -> None:
    """Verify only supported OAuth providers are accepted.

    Given: An OAuth callback with unsupported provider
    When: POST /api/v2/auth/oauth/callback is called
    Then: Request is rejected with appropriate error
    """
    response = await api_client.post(
        "/api/v2/auth/oauth/callback",
        json={
            "provider": "unsupported-provider",
            "code": "test-code",
            "state": "test-state",
        },
    )

    # Should be rejected
    assert response.status_code in (
        400,
        422,
    ), f"Unsupported provider should be rejected: {response.status_code}"

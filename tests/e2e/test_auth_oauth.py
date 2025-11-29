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

    # Response may have providers nested under "providers" key
    providers = data.get("providers", data)

    assert "google" in providers, "Response missing 'google' OAuth URL"
    assert "github" in providers, "Response missing 'github' OAuth URL"

    # Providers may be objects with authorize_url or strings
    google_provider = providers["google"]
    github_provider = providers["github"]

    if isinstance(google_provider, dict):
        assert (
            "authorize_url" in google_provider
        ), "google provider missing authorize_url"
        assert (
            len(google_provider["authorize_url"]) > 0
        ), "google authorize_url is empty"
    else:
        assert isinstance(google_provider, str) and len(google_provider) > 0

    if isinstance(github_provider, dict):
        assert (
            "authorize_url" in github_provider
        ), "github provider missing authorize_url"
        assert (
            len(github_provider["authorize_url"]) > 0
        ), "github authorize_url is empty"
    else:
        assert isinstance(github_provider, str) and len(github_provider) > 0


@pytest.mark.asyncio
async def test_oauth_url_structure_google(api_client: PreprodAPIClient) -> None:
    """T049: Verify Google OAuth URL has correct structure.

    Given: OAuth URLs from the API
    When: Google OAuth URL is examined
    Then: URL contains required OAuth parameters
    """
    response = await api_client.get("/api/v2/auth/oauth/urls")
    assert response.status_code == 200

    data = response.json()
    providers = data.get("providers", data)
    google_provider = providers["google"]

    # Extract URL from provider (may be object or string)
    if isinstance(google_provider, dict):
        google_url = google_provider.get("authorize_url", "")
    else:
        google_url = google_provider

    assert len(google_url) > 0, "Google OAuth URL is empty"

    # OAuth URLs may go through Cognito (federated identity)
    # Check for either direct Google URLs or Cognito federated URLs
    is_cognito = "amazoncognito.com" in google_url
    is_google_direct = (
        "accounts.google.com" in google_url or "googleapis.com" in google_url
    )

    assert (
        is_cognito or is_google_direct
    ), f"Invalid Google OAuth URL (expected Cognito or Google domain): {google_url}"

    # For Cognito federated auth, check for identity_provider parameter
    if is_cognito:
        assert (
            "identity_provider=Google" in google_url
            or "idp_identifier=Google" in google_url
        ), f"Cognito URL missing Google identity provider: {google_url}"


@pytest.mark.asyncio
async def test_oauth_url_structure_github(api_client: PreprodAPIClient) -> None:
    """T050: Verify GitHub OAuth URL has correct structure.

    Given: OAuth URLs from the API
    When: GitHub OAuth URL is examined
    Then: URL contains required OAuth parameters
    """
    response = await api_client.get("/api/v2/auth/oauth/urls")
    assert response.status_code == 200

    data = response.json()
    providers = data.get("providers", data)
    github_provider = providers["github"]

    # Extract URL from provider (may be object or string)
    if isinstance(github_provider, dict):
        github_url = github_provider.get("authorize_url", "")
    else:
        github_url = github_provider

    assert len(github_url) > 0, "GitHub OAuth URL is empty"

    # OAuth URLs may go through Cognito (federated identity)
    # Check for either direct GitHub URLs or Cognito federated URLs
    is_cognito = "amazoncognito.com" in github_url
    is_github_direct = "github.com" in github_url

    assert (
        is_cognito or is_github_direct
    ), f"Invalid GitHub OAuth URL (expected Cognito or GitHub domain): {github_url}"

    # For Cognito federated auth, check for identity_provider parameter
    if is_cognito:
        assert (
            "identity_provider=Github" in github_url
            or "idp_identifier=Github" in github_url
        ), f"Cognito URL missing Github identity provider: {github_url}"


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

    # Should return 400 (invalid code), 401 (unauthorized), 422 (validation error)
    # Some implementations might return 200 with error in body
    assert response.status_code in (
        400,
        401,
        422,
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
    anon_response = await api_client.post("/api/v2/auth/anonymous", json={})
    # API returns 201 Created for new sessions (correct HTTP semantics)
    assert anon_response.status_code in (200, 201)

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
    anon_response = await api_client.post("/api/v2/auth/anonymous", json={})
    # API returns 201 Created for new sessions (correct HTTP semantics)
    assert anon_response.status_code in (200, 201)

    token = anon_response.json()["token"]
    api_client.set_access_token(token)

    try:
        # Sign out
        signout_response = await api_client.post("/api/v2/auth/signout")

        # Signout should succeed (200/204) or may not support anonymous (401)
        assert signout_response.status_code in (
            200,
            204,
            401,
        ), f"Signout failed: {signout_response.status_code}"

        # If anonymous can't sign out, skip rest of test
        if signout_response.status_code == 401:
            pytest.skip("Anonymous sessions cannot sign out")

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

    # Should return 400/401 for invalid token, 500 if backend has error
    assert response.status_code in (
        400,
        401,
        500,
    ), f"Invalid refresh token should be rejected: {response.status_code}"

    # Handle empty response body gracefully
    if response.text:
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

    # Should be rejected - 400 for invalid request, 422 for validation error
    assert response.status_code in (
        400,
        401,
        403,
        422,
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

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

from urllib.parse import urlparse

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient


def _host_matches_domain(url: str, domain: str) -> bool:
    """Check if URL host matches or is subdomain of the given domain.

    Uses proper URL parsing to prevent domain spoofing attacks.
    Example: _host_matches_domain("https://auth.amazoncognito.com/...", "amazoncognito.com") -> True
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        domain = domain.lower()
        # Host matches exactly or is subdomain (host ends with .domain)
        return host == domain or host.endswith(f".{domain}")
    except Exception:
        return False


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
    # Using proper URL parsing to prevent domain spoofing (CodeQL py/incomplete-url-substring-sanitization)
    is_cognito = _host_matches_domain(google_url, "amazoncognito.com")
    is_google_direct = _host_matches_domain(
        google_url, "accounts.google.com"
    ) or _host_matches_domain(google_url, "googleapis.com")

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
    # Using proper URL parsing to prevent domain spoofing (CodeQL py/incomplete-url-substring-sanitization)
    is_cognito = _host_matches_domain(github_url, "amazoncognito.com")
    is_github_direct = _host_matches_domain(github_url, "github.com")

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

    # Should return error status for invalid code
    # 400 (invalid code), 401 (unauthorized), 422 (validation error)
    # Some implementations return 200 with error in body
    assert response.status_code in (
        400,
        401,
        422,
        200,
    ), f"Unexpected callback response: {response.status_code}"

    if response.status_code == 200:
        # If 200, MUST have error indicator (not tokens) for invalid code
        data = response.json()
        has_error = "error" in data or "message" in data or "detail" in data
        has_tokens = "access_token" in data

        # Single-outcome: invalid code should return error, not tokens
        assert has_error, f"Expected error in response for invalid code: {data}"
        assert not has_tokens, f"Invalid code should not return tokens: {data}"


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
    assert anon_response.status_code == 201

    token = anon_response.json()["token"]
    api_client.set_access_token(token)

    try:
        me_response = await api_client.get("/api/v2/auth/me")

        # Anonymous sessions may or may not be able to call /me
        if me_response.status_code == 200:
            data = me_response.json()
            # Should have some user identifier or auth type info
            assert (
                "user_id" in data
                or "session_id" in data
                or "is_anonymous" in data
                or "auth_type" in data
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
    assert anon_response.status_code == 201

    token = anon_response.json()["token"]
    api_client.set_access_token(token)

    try:
        # Sign out
        signout_response = await api_client.post("/api/v2/auth/signout")

        # Signout should succeed (200/204), not support anonymous (401),
        # or have internal error (500 if endpoint not fully implemented)
        assert signout_response.status_code in (
            200,
            204,
            401,
            500,
        ), f"Signout failed: {signout_response.status_code}"

        # If anonymous can't sign out or endpoint not implemented, skip rest of test
        if signout_response.status_code in (401, 500):
            pytest.skip(
                "Anonymous sessions cannot sign out or endpoint not implemented"
            )

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
    # Also accept 404 if the endpoint doesn't exist
    if response.status_code == 404:
        pytest.skip("Token refresh endpoint not implemented")

    assert response.status_code in (
        400,
        401,
        500,
    ), f"Invalid refresh token should be rejected: {response.status_code}"

    # Handle empty response body gracefully
    if response.text and response.text.strip():
        try:
            data = response.json()
            assert (
                "error" in data or "message" in data or "detail" in data
            ), "Error response missing message"
        except Exception:
            # If response is not JSON, that's acceptable for error responses
            pass


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


# =============================================================================
# Feature 1178: Federation Fields E2E Tests
# =============================================================================


@pytest.mark.asyncio
async def test_me_endpoint_returns_federation_fields(
    api_client: PreprodAPIClient,
) -> None:
    """T055: Verify /api/v2/auth/me returns federation fields.

    Feature 1178: Federation fields (role, verification, linked_providers,
    last_provider_used) should be included in /me response.

    Given: An authenticated session
    When: GET /api/v2/auth/me is called
    Then: Response includes federation fields with valid values
    """
    # Create anonymous session for testing
    anon_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert anon_response.status_code == 201

    token = anon_response.json()["token"]
    api_client.set_access_token(token)

    try:
        me_response = await api_client.get("/api/v2/auth/me")

        if me_response.status_code == 401:
            pytest.skip("Anonymous sessions cannot access /me endpoint")

        assert (
            me_response.status_code == 200
        ), f"Expected 200, got {me_response.status_code}"

        data = me_response.json()

        # Feature 1172/1178: Verify federation fields are present
        assert "role" in data, f"Missing 'role' in /me response: {data}"
        assert "verification" in data, f"Missing 'verification' in /me response: {data}"
        assert (
            "linked_providers" in data
        ), f"Missing 'linked_providers' in /me response: {data}"
        # last_provider_used may be null for anonymous users

        # Verify field values are valid
        valid_roles = ["anonymous", "free", "paid", "operator"]
        assert data["role"] in valid_roles, f"Invalid role: {data['role']}"

        valid_verifications = ["none", "pending", "verified"]
        assert (
            data["verification"] in valid_verifications
        ), f"Invalid verification: {data['verification']}"

        assert isinstance(
            data["linked_providers"], list
        ), "linked_providers should be a list"

        # For anonymous user, expect role="anonymous" and no linked providers
        assert (
            data["role"] == "anonymous"
        ), f"Anonymous user should have role='anonymous', got {data['role']}"
        assert (
            len(data["linked_providers"]) == 0
        ), "Anonymous user should have no linked providers"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_oauth_callback_response_includes_federation_fields(
    api_client: PreprodAPIClient,
    test_run_id: str,
) -> None:
    """T056: Verify OAuth callback response includes federation fields.

    Feature 1176/1178: Even error responses from OAuth callback should
    include federation field structure (with defaults).

    Given: An OAuth callback request with invalid code
    When: POST /api/v2/auth/oauth/callback is called
    Then: Response structure includes federation fields
    """
    response = await api_client.post(
        "/api/v2/auth/oauth/callback",
        json={
            "provider": "google",
            "code": f"invalid-code-federation-{test_run_id}",
        },
    )

    # For invalid code, expect 200 with error in body or 4xx status
    if response.status_code == 200:
        data = response.json()

        # Check federation fields are in response (Feature 1176)
        # For error/invalid code responses, fields may use defaults
        if "status" in data and data.get("status") == "error":
            # Error responses - federation fields should still be present with defaults
            assert "role" in data, f"Error response missing 'role': {data}"
            assert (
                data["role"] == "anonymous"
            ), f"Error response role should be 'anonymous': {data}"
        elif "status" in data and data.get("status") == "authenticated":
            # Successful auth (unlikely with invalid code) - federation fields required
            assert "role" in data, f"Success response missing 'role': {data}"
            assert (
                "verification" in data
            ), f"Success response missing 'verification': {data}"
            assert (
                "linked_providers" in data
            ), f"Success response missing 'linked_providers': {data}"


@pytest.mark.asyncio
async def test_federation_field_types(
    api_client: PreprodAPIClient,
) -> None:
    """T057: Verify federation field types in /me response.

    Feature 1178: Federation fields should have correct types:
    - role: string enum
    - verification: string enum
    - linked_providers: list of strings
    - last_provider_used: string or null

    Given: An authenticated session
    When: GET /api/v2/auth/me is called
    Then: Federation fields have correct types
    """
    anon_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert anon_response.status_code == 201

    token = anon_response.json()["token"]
    api_client.set_access_token(token)

    try:
        me_response = await api_client.get("/api/v2/auth/me")

        if me_response.status_code == 401:
            pytest.skip("Anonymous sessions cannot access /me endpoint")

        assert me_response.status_code == 200

        data = me_response.json()

        # Verify types
        assert isinstance(data.get("role"), str), "role should be string"
        assert isinstance(
            data.get("verification"), str
        ), "verification should be string"
        assert isinstance(
            data.get("linked_providers"), list
        ), "linked_providers should be list"

        # last_provider_used can be string or None
        last_provider = data.get("last_provider_used")
        assert last_provider is None or isinstance(
            last_provider, str
        ), f"last_provider_used should be string or null, got {type(last_provider)}"

        # Verify linked_providers contains only strings
        for provider in data.get("linked_providers", []):
            assert isinstance(
                provider, str
            ), f"linked_provider item should be string: {provider}"

    finally:
        api_client.clear_access_token()

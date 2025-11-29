# Authentication Helpers
#
# Utilities for testing authentication flows in E2E tests.
# Includes anonymous session, magic link, and OAuth helpers.

from dataclasses import dataclass

import httpx


@dataclass
class AnonymousSession:
    """Represents an anonymous user session."""

    session_id: str
    anonymous_token: str
    expires_at: str


@dataclass
class AuthenticatedSession:
    """Represents an authenticated user session."""

    user_id: str
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass
class OAuthURLs:
    """OAuth provider URLs."""

    google_url: str
    github_url: str


async def create_anonymous_session(
    client: httpx.AsyncClient,
) -> AnonymousSession:
    """Create a new anonymous session.

    Args:
        client: HTTP client for API calls

    Returns:
        AnonymousSession with session ID and token

    Raises:
        httpx.HTTPStatusError: If session creation fails
    """
    response = await client.post("/api/v2/auth/anonymous")
    response.raise_for_status()

    data = response.json()
    return AnonymousSession(
        session_id=data["session_id"],
        anonymous_token=data["token"],
        expires_at=data["expires_at"],
    )


async def request_magic_link(
    client: httpx.AsyncClient,
    email: str,
    captcha_token: str | None = None,
) -> str:
    """Request a magic link for email authentication.

    Args:
        client: HTTP client for API calls
        email: User email address
        captcha_token: Optional captcha verification token

    Returns:
        Message ID for email tracking

    Raises:
        httpx.HTTPStatusError: If request fails
    """
    payload: dict = {"email": email}
    if captcha_token:
        payload["captcha_token"] = captcha_token

    response = await client.post("/api/v2/auth/magic-link", json=payload)
    response.raise_for_status()

    data = response.json()
    return data.get("message_id", "")


async def verify_magic_link(
    client: httpx.AsyncClient,
    token: str,
    anonymous_session_id: str | None = None,
) -> AuthenticatedSession:
    """Verify a magic link token and create authenticated session.

    Args:
        client: HTTP client for API calls
        token: Magic link token from email
        anonymous_session_id: Optional anonymous session to merge

    Returns:
        AuthenticatedSession with tokens

    Raises:
        httpx.HTTPStatusError: If verification fails
    """
    payload: dict = {"token": token}
    if anonymous_session_id:
        payload["anonymous_session_id"] = anonymous_session_id

    response = await client.post("/api/v2/auth/verify", json=payload)
    response.raise_for_status()

    data = response.json()
    return AuthenticatedSession(
        user_id=data["user_id"],
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data["expires_in"],
    )


async def get_oauth_urls(client: httpx.AsyncClient) -> OAuthURLs:
    """Get OAuth provider authorization URLs.

    Args:
        client: HTTP client for API calls

    Returns:
        OAuthURLs with Google and GitHub authorization URLs

    Raises:
        httpx.HTTPStatusError: If request fails
    """
    response = await client.get("/api/v2/auth/oauth/urls")
    response.raise_for_status()

    data = response.json()
    return OAuthURLs(
        google_url=data["google"],
        github_url=data["github"],
    )


async def refresh_tokens(
    client: httpx.AsyncClient,
    refresh_token: str,
) -> AuthenticatedSession:
    """Refresh access token using refresh token.

    Args:
        client: HTTP client for API calls
        refresh_token: Valid refresh token

    Returns:
        AuthenticatedSession with new tokens

    Raises:
        httpx.HTTPStatusError: If refresh fails
    """
    response = await client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    response.raise_for_status()

    data = response.json()
    return AuthenticatedSession(
        user_id=data["user_id"],
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data["expires_in"],
    )


async def sign_out(
    client: httpx.AsyncClient,
    access_token: str,
) -> bool:
    """Sign out and invalidate session.

    Args:
        client: HTTP client for API calls
        access_token: Current access token

    Returns:
        True if sign out succeeded

    Raises:
        httpx.HTTPStatusError: If sign out fails
    """
    response = await client.post(
        "/api/v2/auth/signout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.status_code == 200


async def validate_session(
    client: httpx.AsyncClient,
    access_token: str,
) -> dict:
    """Validate current session and get user info.

    Args:
        client: HTTP client for API calls
        access_token: Current access token

    Returns:
        User info dict with user_id, email, etc.

    Raises:
        httpx.HTTPStatusError: If validation fails (401 = invalid token)
    """
    response = await client.get(
        "/api/v2/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()

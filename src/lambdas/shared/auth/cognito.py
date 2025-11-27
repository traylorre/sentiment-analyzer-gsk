"""Cognito token validation helper for Feature 006 (T101).

Handles:
- Token exchange (authorization code -> tokens)
- Token validation
- Token refresh
- Token revocation

For On-Call Engineers:
    Common issues:
    1. Invalid tokens: Check Cognito user pool configuration
    2. Token exchange fails: Verify redirect URI matches exactly
    3. Refresh fails: Check if refresh token was revoked

Security Notes:
    - Always validate tokens server-side
    - Never trust client-provided user claims
    - Use Cognito's public keys for JWT verification
"""

import base64
import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from src.lambdas.shared.logging_utils import get_safe_error_info

logger = logging.getLogger(__name__)


@dataclass
class CognitoConfig:
    """Cognito configuration from environment."""

    user_pool_id: str
    client_id: str
    client_secret: str | None
    domain: str
    region: str
    redirect_uri: str

    @classmethod
    def from_env(cls) -> "CognitoConfig":
        """Create config from environment variables."""
        return cls(
            user_pool_id=os.environ.get("COGNITO_USER_POOL_ID", ""),
            client_id=os.environ.get("COGNITO_CLIENT_ID", ""),
            client_secret=os.environ.get("COGNITO_CLIENT_SECRET"),
            domain=os.environ.get("COGNITO_DOMAIN", ""),
            region=os.environ.get("AWS_REGION", "us-east-1"),
            redirect_uri=os.environ.get("COGNITO_REDIRECT_URI", ""),
        )

    @property
    def token_url(self) -> str:
        """Cognito token endpoint URL."""
        return (
            f"https://{self.domain}.auth.{self.region}.amazoncognito.com/oauth2/token"
        )

    @property
    def revoke_url(self) -> str:
        """Cognito revoke endpoint URL."""
        return (
            f"https://{self.domain}.auth.{self.region}.amazoncognito.com/oauth2/revoke"
        )

    @property
    def jwks_url(self) -> str:
        """Cognito JWKS endpoint URL."""
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/jwks.json"

    def get_authorize_url(self, provider: str, state: str | None = None) -> str:
        """Build OAuth authorize URL for a provider."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": self.redirect_uri,
            "identity_provider": provider.capitalize(),
        }
        if state:
            params["state"] = state
        return f"https://{self.domain}.auth.{self.region}.amazoncognito.com/oauth2/authorize?{urlencode(params)}"


class CognitoTokens(BaseModel):
    """Tokens returned by Cognito."""

    id_token: str
    access_token: str
    refresh_token: str | None = None
    expires_in: int = 3600
    token_type: str = "Bearer"


class TokenError(Exception):
    """Token operation failed."""

    def __init__(self, error: str, message: str):
        self.error = error
        self.message = message
        super().__init__(message)


def exchange_code_for_tokens(
    config: CognitoConfig,
    code: str,
) -> CognitoTokens:
    """Exchange authorization code for tokens.

    Args:
        config: Cognito configuration
        code: Authorization code from OAuth callback

    Returns:
        CognitoTokens with id_token, access_token, refresh_token

    Raises:
        TokenError: If exchange fails
    """
    logger.info("Exchanging authorization code for tokens")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Add basic auth if client secret is configured
    if config.client_secret:
        auth_string = f"{config.client_id}:{config.client_secret}"
        auth_header = base64.b64encode(auth_string.encode()).decode()
        headers["Authorization"] = f"Basic {auth_header}"

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
    }

    # Include client_id in body if no secret
    if not config.client_secret:
        data["client_id"] = config.client_id

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                config.token_url,
                headers=headers,
                data=data,
            )

        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error = error_data.get("error", "token_exchange_failed")
            message = error_data.get(
                "error_description", "Failed to exchange code for tokens"
            )
            logger.warning(
                "Token exchange failed",
                extra={"error": error, "status": response.status_code},
            )
            raise TokenError(error, message)

        token_data = response.json()

        return CognitoTokens(
            id_token=token_data["id_token"],
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in", 3600),
            token_type=token_data.get("token_type", "Bearer"),
        )

    except httpx.HTTPError as e:
        logger.error(
            "HTTP error during token exchange",
            extra=get_safe_error_info(e),
        )
        raise TokenError(
            "network_error", "Failed to connect to authentication server"
        ) from e


def refresh_tokens(
    config: CognitoConfig,
    refresh_token: str,
) -> CognitoTokens:
    """Refresh access and ID tokens using refresh token.

    Args:
        config: Cognito configuration
        refresh_token: Current refresh token

    Returns:
        CognitoTokens with new id_token and access_token
        (refresh_token is not rotated)

    Raises:
        TokenError: If refresh fails
    """
    logger.debug("Refreshing tokens")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    if config.client_secret:
        auth_string = f"{config.client_id}:{config.client_secret}"
        auth_header = base64.b64encode(auth_string.encode()).decode()
        headers["Authorization"] = f"Basic {auth_header}"

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    if not config.client_secret:
        data["client_id"] = config.client_id

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                config.token_url,
                headers=headers,
                data=data,
            )

        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error = error_data.get("error", "invalid_refresh_token")

            if error == "invalid_grant":
                raise TokenError("invalid_refresh_token", "Please sign in again.")
            raise TokenError(
                error, error_data.get("error_description", "Token refresh failed")
            )

        token_data = response.json()

        # Note: refresh_token is NOT returned on refresh - it's reused
        return CognitoTokens(
            id_token=token_data["id_token"],
            access_token=token_data["access_token"],
            refresh_token=None,  # Not rotated
            expires_in=token_data.get("expires_in", 3600),
        )

    except httpx.HTTPError as e:
        logger.error(
            "HTTP error during token refresh",
            extra=get_safe_error_info(e),
        )
        raise TokenError(
            "network_error", "Failed to connect to authentication server"
        ) from e


def revoke_token(
    config: CognitoConfig,
    token: str,
) -> bool:
    """Revoke a refresh token.

    Args:
        config: Cognito configuration
        token: Refresh token to revoke

    Returns:
        True if revocation succeeded
    """
    logger.info("Revoking token")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    if config.client_secret:
        auth_string = f"{config.client_id}:{config.client_secret}"
        auth_header = base64.b64encode(auth_string.encode()).decode()
        headers["Authorization"] = f"Basic {auth_header}"

    data = {
        "token": token,
    }

    if not config.client_secret:
        data["client_id"] = config.client_id

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                config.revoke_url,
                headers=headers,
                data=data,
            )

        # Revoke returns 200 even for invalid tokens
        return response.status_code == 200

    except httpx.HTTPError as e:
        logger.error(
            "HTTP error during token revocation",
            extra=get_safe_error_info(e),
        )
        return False


def decode_id_token(token: str) -> dict[str, Any]:
    """Decode ID token without verification.

    For extracting claims after Cognito has already validated.
    DO NOT use this for authentication decisions without verification.

    Args:
        token: JWT ID token

    Returns:
        Decoded claims from token payload
    """
    try:
        # JWT is header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            return {}

        # Decode payload (middle part)
        payload = parts[1]
        # Add padding if needed
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding

        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)

    except Exception as e:
        logger.warning(
            "Failed to decode ID token",
            extra=get_safe_error_info(e),
        )
        return {}


def validate_access_token(
    config: CognitoConfig,
    access_token: str,
) -> dict[str, Any] | None:
    """Validate access token and return claims.

    Uses Cognito's userinfo endpoint to validate the token.

    Args:
        config: Cognito configuration
        access_token: JWT access token

    Returns:
        User info claims if valid, None if invalid
    """
    userinfo_url = f"https://{config.domain}.auth.{config.region}.amazoncognito.com/oauth2/userInfo"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if response.status_code == 200:
            return response.json()

        logger.debug(
            "Token validation failed",
            extra={"status": response.status_code},
        )
        return None

    except httpx.HTTPError as e:
        logger.error(
            "HTTP error during token validation",
            extra=get_safe_error_info(e),
        )
        return None


@lru_cache(maxsize=1)
def _get_jwks(config: CognitoConfig) -> dict:
    """Fetch Cognito JWKS (cached).

    Returns JSON Web Key Set for verifying token signatures.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(config.jwks_url)

        if response.status_code == 200:
            return response.json()

        return {}

    except httpx.HTTPError as e:
        logger.error(
            "Failed to fetch JWKS",
            extra=get_safe_error_info(e),
        )
        return {}


def get_user_from_token(access_token: str) -> dict[str, Any] | None:
    """Get user info from access token via userinfo endpoint.

    Args:
        access_token: Valid Cognito access token

    Returns:
        User claims (sub, email, etc.) or None if invalid
    """
    config = CognitoConfig.from_env()
    return validate_access_token(config, access_token)


def generate_secret_hash(
    client_id: str,
    client_secret: str,
    username: str,
) -> str:
    """Generate Cognito secret hash.

    Required when app client has a secret configured.

    Args:
        client_id: Cognito app client ID
        client_secret: Cognito app client secret
        username: User's username or email

    Returns:
        Base64-encoded HMAC-SHA256 hash
    """
    message = username + client_id
    dig = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(dig).decode()

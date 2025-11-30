"""
Secrets Manager Helper Module
=============================

Provides Secrets Manager integration with in-memory caching for Lambda functions.

For On-Call Engineers:
    If secrets fail to load, check:
    1. Secret exists: aws secretsmanager describe-secret --secret-id <path>
    2. Lambda IAM role has secretsmanager:GetSecretValue permission
    3. Secret path format: ${environment}/sentiment-analyzer/<name>

    Cache has 5-minute TTL. Lambda cold start refreshes cache automatically.
    See SC-03, SC-05 in ON_CALL_SOP.md for secret-related incidents.

For Developers:
    - Secrets are cached in memory to reduce API calls and latency
    - Cache TTL is 5 minutes (configurable via SECRETS_CACHE_TTL_SECONDS)
    - Use get_secret() for all secret retrieval
    - Never log secret values, only ARNs

Security Notes:
    - Secrets are never logged or exposed in error messages
    - Cache is cleared on Lambda cold start (memory isolation)
    - Use secrets.compare_digest() for timing-safe comparison
"""

import json
import logging
import os
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Structured logging for CloudWatch
logger = logging.getLogger(__name__)

# Cache configuration
# On-Call Note: Reduce TTL if secrets need faster rotation pickup
DEFAULT_CACHE_TTL_SECONDS = 300  # 5 minutes

# Retry configuration
RETRY_CONFIG = Config(
    retries={
        "max_attempts": 3,
        "mode": "adaptive",
    },
    connect_timeout=5,
    read_timeout=10,
)

# In-memory cache
# Structure: {secret_id: {"value": <parsed_value>, "expires_at": <timestamp>}}
_secrets_cache: dict[str, dict[str, Any]] = {}


def _sanitize_secret_id_for_log(secret_id: str) -> str:
    """
    Sanitize secret ID for safe logging.

    Only logs the last component of the secret path to prevent:
    - Exposing environment names (dev/prod)
    - Revealing full secret paths
    - Information disclosure for reconnaissance attacks

    Args:
        secret_id: Full secret ID (e.g., "dev/sentiment-analyzer/tiingo")

    Returns:
        Sanitized secret name (e.g., "tiingo")

    Security:
        - Prevents exposing full secret paths in logs
        - Reduces information available for attackers
        - Still provides enough context for debugging

    Example:
        >>> _sanitize_secret_id_for_log("dev/sentiment-analyzer/tiingo")
        'tiingo'
        >>> _sanitize_secret_id_for_log("arn:aws:secretsmanager:us-east-1:123:secret:api-key-abc123")
        'api-key'
    """
    # Extract just the secret name from the path
    # Handles both simple paths (dev/app/secret) and ARNs
    if secret_id.startswith("arn:"):
        # For ARNs, extract the secret name after "secret:"
        # Format: arn:aws:secretsmanager:region:account:secret:name-randomsuffix
        parts = secret_id.split(":")
        if len(parts) >= 7:
            name_with_suffix = parts[6]
            # Remove the random suffix AWS adds (last 7 chars like "-abc123")
            return (
                name_with_suffix.rsplit("-", 1)[0]
                if "-" in name_with_suffix
                else name_with_suffix
            )

    # For simple paths, just get the last component
    return secret_id.split("/")[-1]


def get_secrets_client(region_name: str | None = None) -> Any:
    """
    Get a Secrets Manager client with retry configuration.

    Args:
        region_name: Cloud region (defaults to CLOUD_REGION or AWS_REGION env var)

    Returns:
        boto3 Secrets Manager client
    """
    # Cloud-agnostic: Use CLOUD_REGION, fallback to AWS_REGION for backward compatibility
    region = (
        region_name or os.environ.get("CLOUD_REGION") or os.environ.get("AWS_REGION")
    )
    if not region:
        raise ValueError("CLOUD_REGION or AWS_REGION environment variable must be set")

    return boto3.client(
        "secretsmanager",
        region_name=region,
        config=RETRY_CONFIG,
    )


def get_secret(
    secret_id: str,
    region_name: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Retrieve a secret from Secrets Manager with caching.

    Secrets are cached in memory for 5 minutes to reduce API calls and latency.
    Cache is automatically cleared on Lambda cold start.

    Args:
        secret_id: Secret name or ARN (e.g., "dev/sentiment-analyzer/tiingo")
        region_name: AWS region
        force_refresh: If True, bypass cache and fetch from Secrets Manager

    Returns:
        Parsed secret value as dict

    Raises:
        SecretNotFoundError: If secret doesn't exist
        SecretAccessDeniedError: If Lambda role lacks permission
        SecretRetrievalError: For other Secrets Manager errors

    On-Call Note:
        If this fails, check:
        1. Secret exists: aws secretsmanager describe-secret --secret-id <id>
        2. IAM permissions: secretsmanager:GetSecretValue
        3. Secret not deleted: check recovery window
    """
    # Check cache first (unless force refresh)
    if not force_refresh:
        cached = _get_from_cache(secret_id)
        if cached is not None:
            logger.debug(
                "Secret retrieved from cache",
                extra={"secret_name": _sanitize_secret_id_for_log(secret_id)},
            )
            return cached

    # Fetch from Secrets Manager
    client = get_secrets_client(region_name)

    try:
        response = client.get_secret_value(SecretId=secret_id)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")

        if error_code == "ResourceNotFoundException":
            logger.error(
                "Secret not found",
                extra={
                    "secret_name": _sanitize_secret_id_for_log(secret_id),
                    "error_code": error_code,
                },
            )
            raise SecretNotFoundError(f"Secret not found: {secret_id}") from e

        elif error_code in ("AccessDeniedException", "UnauthorizedAccess"):
            logger.error(
                "Access denied to secret",
                extra={
                    "secret_name": _sanitize_secret_id_for_log(secret_id),
                    "error_code": error_code,
                },
            )
            raise SecretAccessDeniedError(
                f"Access denied to secret: {secret_id}"
            ) from e

        else:
            logger.error(
                "Failed to retrieve secret",
                extra={
                    "secret_name": _sanitize_secret_id_for_log(secret_id),
                    "error_code": error_code,
                },
            )
            raise SecretRetrievalError(f"Failed to retrieve secret: {secret_id}") from e

    # Parse secret value
    secret_string = response.get("SecretString")
    if not secret_string:
        # Binary secrets not supported
        raise SecretRetrievalError(f"Secret is binary, not string: {secret_id}")

    try:
        secret_value = json.loads(secret_string)
    except json.JSONDecodeError as e:
        logger.error(
            "Failed to parse secret as JSON",
            extra={"secret_name": _sanitize_secret_id_for_log(secret_id)},
        )
        raise SecretRetrievalError(f"Secret is not valid JSON: {secret_id}") from e

    # Cache the secret
    _set_in_cache(secret_id, secret_value)

    logger.info(
        "Secret retrieved from Secrets Manager",
        extra={"secret_name": _sanitize_secret_id_for_log(secret_id)},
    )

    return secret_value


def get_api_key(secret_id: str, key_field: str = "api_key") -> str:
    """
    Retrieve an API key from a secret.

    Convenience function for the common pattern of storing API keys.

    Args:
        secret_id: Secret name or ARN
        key_field: Field name in the secret JSON (default: "api_key")

    Returns:
        API key string

    Raises:
        SecretRetrievalError: If key_field not found in secret

    Example:
        >>> api_key = get_api_key("dev/sentiment-analyzer/tiingo")
        >>> # Returns value of "api_key" field from secret
    """
    secret = get_secret(secret_id)

    if key_field not in secret:
        raise SecretRetrievalError(
            f"Field '{key_field}' not found in secret: {secret_id}"
        )

    return secret[key_field]


def clear_cache() -> None:
    """
    Clear the secrets cache.

    Use this to force refresh of all secrets on next retrieval.
    Useful for testing or when secrets are rotated.
    """
    global _secrets_cache
    _secrets_cache = {}
    logger.debug("Secrets cache cleared")


def _get_from_cache(secret_id: str) -> dict[str, Any] | None:
    """
    Get a secret from cache if not expired.

    Args:
        secret_id: Secret identifier

    Returns:
        Cached secret value or None if not cached/expired
    """
    if secret_id not in _secrets_cache:
        return None

    entry = _secrets_cache[secret_id]
    if time.time() > entry["expires_at"]:
        # Cache expired
        del _secrets_cache[secret_id]
        return None

    return entry["value"]


def _set_in_cache(secret_id: str, value: dict[str, Any]) -> None:
    """
    Store a secret in cache with TTL.

    Args:
        secret_id: Secret identifier
        value: Parsed secret value
    """
    ttl = int(os.environ.get("SECRETS_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS))

    _secrets_cache[secret_id] = {
        "value": value,
        "expires_at": time.time() + ttl,
    }


def compare_digest(a: str, b: str) -> bool:
    """
    Timing-safe comparison of two strings.

    Use this for comparing API keys to prevent timing attacks.

    Args:
        a: First string
        b: Second string

    Returns:
        True if strings are equal, False otherwise

    Security Note:
        Always use this for API key validation, never use == directly.
        The == operator can leak information through timing differences.

    Example:
        >>> provided_key = request.headers.get("X-API-Key")
        >>> stored_key = get_api_key("dev/sentiment-analyzer/dashboard-api-key")
        >>> if compare_digest(provided_key, stored_key):
        ...     # Authenticated
    """
    import hmac

    # Handle None values
    if a is None or b is None:
        return False

    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# Custom exceptions for better error handling
class SecretError(Exception):
    """Base exception for secret-related errors."""

    pass


class SecretNotFoundError(SecretError):
    """Raised when a secret doesn't exist."""

    pass


class SecretAccessDeniedError(SecretError):
    """Raised when access to a secret is denied."""

    pass


class SecretRetrievalError(SecretError):
    """Raised for general secret retrieval errors."""

    pass

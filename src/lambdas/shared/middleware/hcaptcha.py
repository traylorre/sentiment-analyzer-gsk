"""hCaptcha verification middleware for Feature 006.

Implements T163: Bot protection for anonymous config creation.

For On-Call Engineers:
    hCaptcha is triggered after 3+ anonymous config creations from same IP
    in 1 hour. The frontend shows the captcha widget, user solves it, and
    sends the token with the request.

Security Notes:
    - Secret key stored in Secrets Manager: {env}/sentiment-analyzer/hcaptcha-secret-key
    - Site key is public, secret key must never be exposed
    - Tokens are single-use and expire quickly
"""

import logging
import os
from typing import Any

import httpx
from pydantic import BaseModel

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log

logger = logging.getLogger(__name__)

# hCaptcha verification endpoint
HCAPTCHA_VERIFY_URL = "https://hcaptcha.com/siteverify"

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")


class CaptchaRequired(Exception):
    """Raised when captcha verification is required."""

    def __init__(self, message: str = "Captcha verification required"):
        self.message = message
        super().__init__(self.message)


class CaptchaVerificationResult(BaseModel):
    """Result of captcha verification."""

    success: bool
    challenge_ts: str | None = None
    hostname: str | None = None
    error_codes: list[str] = []


def _get_hcaptcha_secret() -> str | None:
    """Get hCaptcha secret from Secrets Manager.

    Uses the shared secrets module which has 5-minute TTL caching built-in.

    Returns:
        Secret key or None if not configured
    """
    try:
        # Import here to avoid circular imports
        from src.lambdas.shared.secrets import get_secret

        secret_name = f"{ENVIRONMENT}/sentiment-analyzer/hcaptcha-secret-key"
        secret_data = get_secret(secret_name)
        # Return the secret key value - handle both dict and string formats
        if isinstance(secret_data, dict):
            return secret_data.get("secret_key", secret_data.get("HCAPTCHA_SECRET_KEY"))
        return str(secret_data)
    except Exception as e:
        logger.warning(
            "Failed to get hCaptcha secret",
            extra=get_safe_error_info(e),
        )
        return None


def verify_captcha(
    token: str,
    remote_ip: str | None = None,
    secret_key: str | None = None,
) -> CaptchaVerificationResult:
    """Verify hCaptcha token with server.

    Args:
        token: hCaptcha response token from frontend
        remote_ip: Optional client IP for additional verification
        secret_key: Optional secret key (uses Secrets Manager if not provided)

    Returns:
        CaptchaVerificationResult with success status

    Example:
        result = verify_captcha(request.captcha_token, client_ip)
        if not result.success:
            raise CaptchaRequired("Invalid captcha")
    """
    if not token:
        return CaptchaVerificationResult(
            success=False,
            error_codes=["missing-input-response"],
        )

    # Get secret key
    if secret_key is None:
        secret_key = _get_hcaptcha_secret()

    if not secret_key:
        # In dev/test, allow bypass if secret not configured
        if ENVIRONMENT in ("dev", "test", "local"):
            logger.warning("hCaptcha secret not configured, allowing in dev/test")
            return CaptchaVerificationResult(success=True)

        logger.error("hCaptcha secret not configured in production")
        return CaptchaVerificationResult(
            success=False,
            error_codes=["missing-input-secret"],
        )

    try:
        # Build verification request
        data: dict[str, Any] = {
            "secret": secret_key,
            "response": token,
        }

        if remote_ip:
            data["remoteip"] = remote_ip

        # Verify with hCaptcha server
        with httpx.Client(timeout=10.0) as client:
            response = client.post(HCAPTCHA_VERIFY_URL, data=data)
            response.raise_for_status()
            result = response.json()

        success = result.get("success", False)
        error_codes = result.get("error-codes", [])

        if not success:
            logger.warning(
                "Captcha verification failed",
                extra={
                    "error_codes": error_codes,
                    "remote_ip": sanitize_for_log(remote_ip[:16] if remote_ip else ""),
                },
            )

        return CaptchaVerificationResult(
            success=success,
            challenge_ts=result.get("challenge_ts"),
            hostname=result.get("hostname"),
            error_codes=error_codes,
        )

    except httpx.HTTPError as e:
        logger.error(
            "hCaptcha API request failed",
            extra=get_safe_error_info(e),
        )
        return CaptchaVerificationResult(
            success=False,
            error_codes=["http-error"],
        )

    except Exception as e:
        logger.error(
            "Unexpected error verifying captcha",
            extra=get_safe_error_info(e),
        )
        return CaptchaVerificationResult(
            success=False,
            error_codes=["internal-error"],
        )


def should_require_captcha(
    table: Any,
    client_ip: str,
    action: str = "config_create",
    threshold: int = 3,
    window_hours: int = 1,
) -> bool:
    """Check if captcha should be required based on rate limiting.

    Args:
        table: DynamoDB Table resource
        client_ip: Client IP address
        action: Action being performed
        threshold: Number of actions before requiring captcha
        window_hours: Time window in hours

    Returns:
        True if captcha should be required
    """
    from datetime import UTC, datetime, timedelta

    try:
        # Query rate limit records for this IP and action
        window_start = datetime.now(UTC) - timedelta(hours=window_hours)

        response = table.query(
            KeyConditionExpression="PK = :pk AND SK > :sk",
            ExpressionAttributeValues={
                ":pk": f"RATE#{client_ip}",
                ":sk": f"{action}#{window_start.isoformat()}",
            },
        )

        count = len(response.get("Items", []))

        if count >= threshold:
            logger.info(
                "Captcha required due to rate limit",
                extra={
                    "client_ip_prefix": sanitize_for_log(client_ip[:8]),
                    "action": action,
                    "count": count,
                    "threshold": threshold,
                },
            )
            return True

        return False

    except Exception as e:
        logger.error(
            "Error checking captcha requirement",
            extra=get_safe_error_info(e),
        )
        # Don't require captcha on error
        return False


def record_action_for_rate_limit(
    table: Any,
    client_ip: str,
    action: str = "config_create",
    ttl_hours: int = 2,
) -> None:
    """Record an action for rate limiting purposes.

    Args:
        table: DynamoDB Table resource
        client_ip: Client IP address
        action: Action being performed
        ttl_hours: TTL for the record in hours
    """
    from datetime import UTC, datetime, timedelta

    try:
        now = datetime.now(UTC)
        ttl = int((now + timedelta(hours=ttl_hours)).timestamp())

        table.put_item(
            Item={
                "PK": f"RATE#{client_ip}",
                "SK": f"{action}#{now.isoformat()}",
                "action": action,
                "client_ip": client_ip,
                "created_at": now.isoformat(),
                "ttl": ttl,
                "entity_type": "RATE_LIMIT_RECORD",
            }
        )

    except Exception as e:
        logger.error(
            "Error recording action for rate limit",
            extra=get_safe_error_info(e),
        )

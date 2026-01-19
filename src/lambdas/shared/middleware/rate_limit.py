"""IP-based rate limiting middleware for Feature 006.

Implements T164: Rate limiting to prevent abuse.

For On-Call Engineers:
    Rate limits are tracked in DynamoDB with TTL for automatic cleanup.
    Different limits apply to different actions (config creation, ticker validation, etc.)
    When rate limit is exceeded, 429 Too Many Requests is returned.

Security Notes:
    - IP address is extracted from X-Forwarded-For header (API Gateway/ALB)
    - Rate limits are per-IP, per-action
    - Anonymous users have stricter limits than authenticated users
"""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log

logger = logging.getLogger(__name__)

# Default rate limits per action
DEFAULT_RATE_LIMITS = {
    # Anonymous actions
    "config_create": {"limit": 5, "window_seconds": 3600},  # 5 per hour
    "ticker_validate": {"limit": 30, "window_seconds": 60},  # 30 per minute
    "ticker_search": {"limit": 20, "window_seconds": 60},  # 20 per minute
    "anonymous_session": {"limit": 10, "window_seconds": 3600},  # 10 per hour
    # Authenticated actions (more generous)
    "auth_config_create": {"limit": 10, "window_seconds": 3600},  # 10 per hour
    "alert_create": {"limit": 20, "window_seconds": 3600},  # 20 per hour
    "magic_link_request": {"limit": 5, "window_seconds": 300},  # 5 per 5 minutes
    # Default fallback
    "default": {"limit": 100, "window_seconds": 60},  # 100 per minute
}

# Environment
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        limit: int = 0,
        remaining: int = 0,
    ):
        self.message = message
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        super().__init__(self.message)


class RateLimitResult(BaseModel):
    """Result of rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: str
    retry_after: int | None = None


def get_client_ip(event: dict[str, Any]) -> str:
    """Extract client IP from Lambda event.

    Args:
        event: Lambda event (API Gateway or Function URL)

    Returns:
        Client IP address or "unknown"
    """
    # API Gateway v2 (HTTP API)
    request_context = event.get("requestContext", {})
    http_context = request_context.get("http", {})
    if "sourceIp" in http_context:
        return http_context["sourceIp"]

    # API Gateway v1 (REST API)
    identity = request_context.get("identity", {})
    if "sourceIp" in identity:
        return identity["sourceIp"]

    # Function URL
    if "sourceIp" in request_context:
        return request_context["sourceIp"]

    # X-Forwarded-For header (from ALB/API Gateway)
    headers = event.get("headers", {})
    forwarded_for = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (client's real IP)
        return forwarded_for.split(",")[0].strip()

    # Fallback
    return "unknown"


def check_rate_limit(
    table: Any,
    client_ip: str,
    action: str = "default",
    user_id: str | None = None,
    custom_limit: int | None = None,
    custom_window: int | None = None,
) -> RateLimitResult:
    """Check if request is within rate limit.

    Args:
        table: DynamoDB Table resource
        client_ip: Client IP address
        action: Action being performed (e.g., "config_create")
        user_id: Optional user ID for authenticated users
        custom_limit: Optional custom limit override
        custom_window: Optional custom window override (seconds)

    Returns:
        RateLimitResult with allowed status

    Example:
        result = check_rate_limit(table, client_ip, "config_create")
        if not result.allowed:
            raise RateLimitExceeded(retry_after=result.retry_after)
    """
    # Get rate limit config for action
    rate_config = DEFAULT_RATE_LIMITS.get(action, DEFAULT_RATE_LIMITS["default"])
    limit = custom_limit or rate_config["limit"]
    window_seconds = custom_window or rate_config["window_seconds"]

    # Build rate limit key
    # Use user_id if authenticated, otherwise IP
    if user_id:
        rate_key = f"USER#{user_id}"
    else:
        rate_key = f"IP#{client_ip}"

    now = datetime.now(UTC)
    window_start = now - timedelta(seconds=window_seconds)
    window_end = now + timedelta(seconds=window_seconds)

    try:
        # Query requests in current window
        response = table.query(
            KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
            ExpressionAttributeValues={
                ":pk": f"RATE#{rate_key}#{action}",
                ":start": window_start.isoformat(),
                ":end": now.isoformat(),
            },
        )

        current_count = len(response.get("Items", []))
        remaining = max(0, limit - current_count - 1)  # -1 for current request

        if current_count >= limit:
            # Rate limit exceeded
            retry_after = window_seconds

            logger.warning(
                "Rate limit exceeded",
                extra={
                    "client_ip_prefix": sanitize_for_log(client_ip[:8]),
                    "action": action,
                    "count": current_count,
                    "limit": limit,
                },
            )

            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=window_end.isoformat(),
                retry_after=retry_after,
            )

        # Record this request
        _record_request(table, rate_key, action, now, window_seconds)

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            reset_at=window_end.isoformat(),
        )

    except Exception as e:
        logger.error(
            "Error checking rate limit",
            extra={
                "action": action,
                **get_safe_error_info(e),
            },
        )
        # Allow on error (fail open)
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=limit,
            reset_at=window_end.isoformat(),
        )


def _record_request(
    table: Any,
    rate_key: str,
    action: str,
    timestamp: datetime,
    ttl_seconds: int,
) -> None:
    """Record a request for rate limiting.

    Args:
        table: DynamoDB Table resource
        rate_key: Rate limit key (IP or user)
        action: Action being performed
        timestamp: Request timestamp
        ttl_seconds: TTL for the record
    """
    try:
        ttl = int((timestamp + timedelta(seconds=ttl_seconds * 2)).timestamp())

        table.put_item(
            Item={
                "PK": f"RATE#{rate_key}#{action}",
                "SK": timestamp.isoformat(),
                "action": action,
                "rate_key": rate_key,
                "created_at": timestamp.isoformat(),
                "ttl": ttl,
                "entity_type": "RATE_LIMIT",
            }
        )

    except Exception as e:
        logger.error(
            "Error recording rate limit request",
            extra=get_safe_error_info(e),
        )


def get_rate_limit_headers(result: RateLimitResult) -> dict[str, str]:
    """Get rate limit headers for response.

    Args:
        result: Rate limit check result

    Returns:
        Dict of headers to add to response
    """
    headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": result.reset_at,
    }

    if result.retry_after:
        headers["Retry-After"] = str(result.retry_after)

    return headers

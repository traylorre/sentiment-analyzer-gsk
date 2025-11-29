"""Alert quota tracking for Feature 006.

Tracks daily email sending quota per user. Uses DynamoDB with
pattern PK=QUOTA#{user_id}, SK=DAILY#{date} for efficient
daily reset without cleanup jobs.

For On-Call Engineers:
    - Quota resets at midnight UTC automatically (new date = new SK)
    - TTL set for 30 days to auto-cleanup old quota records
    - Uses atomic counters to prevent race conditions
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from aws_xray_sdk.core import xray_recorder
from pydantic import BaseModel

from src.lambdas.shared.logging_utils import sanitize_for_log
from src.lambdas.shared.models.alert_rule import ALERT_LIMITS

logger = logging.getLogger(__name__)


class QuotaStatus(BaseModel):
    """Daily email quota status for a user."""

    used: int
    limit: int
    remaining: int
    resets_at: str  # ISO format datetime
    is_exceeded: bool


class QuotaExceededError(Exception):
    """Raised when user exceeds their daily quota."""

    def __init__(self, used: int, limit: int, resets_at: str):
        self.used = used
        self.limit = limit
        self.resets_at = resets_at
        super().__init__(f"Daily quota exceeded: {used}/{limit}")


@xray_recorder.capture("get_daily_quota")
def get_daily_quota(table: Any, user_id: str) -> QuotaStatus:
    """Get user's daily email quota status.

    Args:
        table: DynamoDB Table resource
        user_id: User ID

    Returns:
        QuotaStatus with current usage
    """
    today = datetime.now(UTC).date()
    pk = f"QUOTA#{user_id}"
    sk = f"DAILY#{today.isoformat()}"

    try:
        response = table.get_item(Key={"PK": pk, "SK": sk})
        item = response.get("Item", {})
        used = item.get("email_count", 0)
    except Exception as e:
        logger.warning(f"Failed to get quota, assuming 0: {e}")
        used = 0

    limit = ALERT_LIMITS["max_emails_per_day"]

    # Calculate when quota resets (midnight UTC next day)
    tomorrow = datetime.combine(
        today + timedelta(days=1), datetime.min.time(), tzinfo=UTC
    )

    return QuotaStatus(
        used=used,
        limit=limit,
        remaining=max(0, limit - used),
        resets_at=tomorrow.isoformat(),
        is_exceeded=used >= limit,
    )


@xray_recorder.capture("increment_email_quota")
def increment_email_quota(table: Any, user_id: str) -> QuotaStatus:
    """Increment user's daily email count atomically.

    Uses DynamoDB atomic counter to safely increment.
    Creates record if it doesn't exist.

    Args:
        table: DynamoDB Table resource
        user_id: User ID

    Returns:
        Updated QuotaStatus

    Raises:
        QuotaExceededError: If quota would be exceeded
    """
    today = datetime.now(UTC).date()
    pk = f"QUOTA#{user_id}"
    sk = f"DAILY#{today.isoformat()}"

    # Calculate TTL (30 days from now)
    ttl = int((datetime.now(UTC) + timedelta(days=30)).timestamp())

    # Calculate when quota resets
    tomorrow = datetime.combine(
        today + timedelta(days=1), datetime.min.time(), tzinfo=UTC
    )
    limit = ALERT_LIMITS["max_emails_per_day"]

    try:
        # Atomic increment with condition to prevent exceeding limit
        response = table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET email_count = if_not_exists(email_count, :zero) + :inc, "
            "entity_type = :entity, ttl = :ttl",
            ConditionExpression="attribute_not_exists(email_count) OR email_count < :limit",
            ExpressionAttributeValues={
                ":zero": 0,
                ":inc": 1,
                ":entity": "QUOTA_TRACKER",
                ":ttl": ttl,
                ":limit": limit,
            },
            ReturnValues="ALL_NEW",
        )

        new_count = response["Attributes"].get("email_count", 1)

        logger.info(
            "Incremented email quota",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "email_count": new_count,
                "limit": limit,
            },
        )

        return QuotaStatus(
            used=new_count,
            limit=limit,
            remaining=max(0, limit - new_count),
            resets_at=tomorrow.isoformat(),
            is_exceeded=new_count >= limit,
        )

    except table.meta.client.exceptions.ConditionalCheckFailedException:
        # Quota exceeded - get current count for error
        current = get_daily_quota(table, user_id)
        logger.warning(
            "Quota exceeded",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "used": current.used,
                "limit": current.limit,
            },
        )
        raise QuotaExceededError(
            used=current.used,
            limit=current.limit,
            resets_at=current.resets_at,
        ) from None


@xray_recorder.capture("check_quota_available")
def check_quota_available(table: Any, user_id: str, count: int = 1) -> bool:
    """Check if user has quota available for sending emails.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        count: Number of emails to check (default 1)

    Returns:
        True if quota available, False otherwise
    """
    status = get_daily_quota(table, user_id)
    return status.remaining >= count


@xray_recorder.capture("get_user_total_alerts")
def get_user_total_alerts(table: Any, user_id: str) -> int:
    """Get total number of alerts across all configs for a user.

    Args:
        table: DynamoDB Table resource
        user_id: User ID

    Returns:
        Total alert count
    """
    from boto3.dynamodb.conditions import Key

    try:
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
            & Key("SK").begins_with("ALERT#"),
            Select="COUNT",
        )
        return response.get("Count", 0)
    except Exception as e:
        logger.warning(f"Failed to count alerts: {e}")
        return 0

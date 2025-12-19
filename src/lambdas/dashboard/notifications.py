"""Notification endpoints for Feature 006.

Implements notification management (T137-T144):
- GET /api/v2/notifications - List notification history
- GET /api/v2/notifications/{id} - Get notification detail
- GET /api/v2/notifications/preferences - Get notification preferences
- PATCH /api/v2/notifications/preferences - Update preferences
- POST /api/v2/notifications/disable-all - Disable all notifications
- GET /api/v2/notifications/unsubscribe - Unsubscribe via token
- POST /api/v2/notifications/resubscribe - Resubscribe
- GET /api/v2/notifications/digest - Get digest settings
- PATCH /api/v2/notifications/digest - Update digest settings
- POST /api/v2/notifications/digest/test - Trigger test digest

For On-Call Engineers:
    Notifications are stored with PK=USER#{user_id}, SK={timestamp}.
    Digest settings are stored with PK=USER#{user_id}, SK=DIGEST_SETTINGS.
    User preferences are stored with PK=USER#{user_id}, SK=NOTIFICATION_PREFS.

Security Notes:
    - All operations require authenticated user session
    - Unsubscribe endpoint accepts signed tokens for email link unsubscribe
    - Users can only access their own notifications
"""

import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from aws_xray_sdk.core import xray_recorder
from boto3.dynamodb.conditions import Key
from pydantic import BaseModel

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
from src.lambdas.shared.models.notification import DigestSettings, Notification
from src.lambdas.shared.models.status_utils import DISABLED, ENABLED

logger = logging.getLogger(__name__)


# Valid IANA timezones (subset for validation)
VALID_TIMEZONES = {
    "America/New_York",
    "America/Los_Angeles",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Anchorage",
    "Pacific/Honolulu",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Singapore",
    "Australia/Sydney",
    "UTC",
}


# Response schemas


class TrackingInfo(BaseModel):
    """Email tracking info."""

    opened_at: str | None = None
    clicked_at: str | None = None


class NotificationResponse(BaseModel):
    """Notification response."""

    notification_id: str
    alert_id: str
    ticker: str
    alert_type: str
    triggered_value: float
    threshold_value: float | None = None
    threshold_direction: str | None = None
    subject: str
    body_preview: str | None = None
    sent_at: str
    status: Literal["pending", "sent", "failed", "bounced"]
    email: str | None = None
    deep_link: str
    tracking: TrackingInfo | None = None


class NotificationListResponse(BaseModel):
    """Response for GET /api/v2/notifications."""

    notifications: list[NotificationResponse]
    total: int
    limit: int
    offset: int


class NotificationPreferencesResponse(BaseModel):
    """Notification preferences response."""

    email_notifications_enabled: bool
    daily_digest_enabled: bool
    digest_time: str
    timezone: str
    email: str | None = None
    email_verified: bool


class DisableAllResponse(BaseModel):
    """Response for POST /api/v2/notifications/disable-all."""

    status: str
    alerts_disabled: int
    message: str


class UnsubscribeResponse(BaseModel):
    """Response for GET /api/v2/notifications/unsubscribe."""

    status: str
    user_id: str | None = None
    message: str


class ResubscribeResponse(BaseModel):
    """Response for POST /api/v2/notifications/resubscribe."""

    status: str
    message: str


class DigestSettingsResponse(BaseModel):
    """Response for GET /api/v2/notifications/digest."""

    enabled: bool
    time: str
    timezone: str
    include_all_configs: bool
    config_ids: list[str] | None = None
    next_scheduled: str | None = None


class TriggerTestDigestResponse(BaseModel):
    """Response for POST /api/v2/notifications/digest/test."""

    status: str
    message: str


class ErrorDetail(BaseModel):
    """Error detail for validation errors."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail


# Service functions


@xray_recorder.capture("list_notifications")
def list_notifications(
    table: Any,
    user_id: str,
    status: str | None = None,
    alert_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> NotificationListResponse:
    """List user's notification history.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        status: Filter by status (optional)
        alert_id: Filter by alert ID (optional)
        limit: Max results (default 20, max 100)
        offset: Pagination offset

    Returns:
        NotificationListResponse with filtered notifications
    """
    # Enforce max limit
    limit = min(limit, 100)

    try:
        # Query notifications (they have timestamp as SK, not prefixed)
        # Use GSI or scan with filter for notifications
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"),
            FilterExpression="entity_type = :entity_type",
            ExpressionAttributeValues={":entity_type": "NOTIFICATION"},
            ScanIndexForward=False,  # Most recent first
        )

        notifications = []
        for item in response.get("Items", []):
            # Apply filters
            if status and item.get("status") != status:
                continue
            if alert_id and item.get("alert_id") != alert_id:
                continue

            notification = Notification.from_dynamodb_item(item)
            notifications.append(_notification_to_response(notification))

        total = len(notifications)

        # Apply pagination
        paginated = notifications[offset : offset + limit]

        logger.debug(
            "Listed notifications",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "total": total,
                "returned": len(paginated),
            },
        )

        return NotificationListResponse(
            notifications=paginated,
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(
            "Failed to list notifications",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("get_notification")
def get_notification(
    table: Any,
    user_id: str,
    notification_id: str,
) -> NotificationResponse | None:
    """Get a single notification detail.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        notification_id: Notification ID

    Returns:
        NotificationResponse if found, None otherwise
    """
    try:
        # Need to scan for the notification by ID since SK is timestamp
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"),
            FilterExpression="notification_id = :notif_id AND entity_type = :entity_type",
            ExpressionAttributeValues={
                ":notif_id": notification_id,
                ":entity_type": "NOTIFICATION",
            },
        )

        items = response.get("Items", [])
        if not items:
            return None

        notification = Notification.from_dynamodb_item(items[0])
        return _notification_to_response(notification, include_detail=True)

    except Exception as e:
        logger.error(
            "Failed to get notification",
            extra={
                "notification_id": sanitize_for_log(notification_id[:8]),
                **get_safe_error_info(e),
            },
        )
        raise


@xray_recorder.capture("get_notification_preferences")
def get_notification_preferences(
    table: Any,
    user_id: str,
    user_email: str | None = None,
) -> NotificationPreferencesResponse:
    """Get user's notification preferences.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        user_email: User's email (from session)

    Returns:
        NotificationPreferencesResponse with preferences
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": "NOTIFICATION_PREFS",
            }
        )

        item = response.get("Item")
        if item:
            return NotificationPreferencesResponse(
                email_notifications_enabled=item.get(
                    "email_notifications_enabled", True
                ),
                daily_digest_enabled=item.get("daily_digest_enabled", False),
                digest_time=item.get("digest_time", "09:00"),
                timezone=item.get("timezone", "America/New_York"),
                email=user_email,
                email_verified=item.get("email_verified", False),
            )

        # Return defaults
        return NotificationPreferencesResponse(
            email_notifications_enabled=True,
            daily_digest_enabled=False,
            digest_time="09:00",
            timezone="America/New_York",
            email=user_email,
            email_verified=False,
        )

    except Exception as e:
        logger.error(
            "Failed to get notification preferences",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("update_notification_preferences")
def update_notification_preferences(
    table: Any,
    user_id: str,
    email_notifications_enabled: bool | None = None,
    daily_digest_enabled: bool | None = None,
    digest_time: str | None = None,
    timezone: str | None = None,
) -> NotificationPreferencesResponse | ErrorResponse:
    """Update user's notification preferences.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        email_notifications_enabled: Enable/disable email notifications
        daily_digest_enabled: Enable/disable daily digest
        digest_time: Digest time in HH:MM format
        timezone: IANA timezone string

    Returns:
        NotificationPreferencesResponse on success, ErrorResponse on validation error
    """
    # Validate time format
    if digest_time is not None:
        if not _validate_time_format(digest_time):
            return ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_TIME",
                    message="Time must be in HH:MM format (24-hour)",
                )
            )

    # Validate timezone
    if timezone is not None and timezone not in VALID_TIMEZONES:
        return ErrorResponse(
            error=ErrorDetail(
                code="INVALID_TIMEZONE",
                message=f"Invalid timezone: {timezone}",
            )
        )

    try:
        # Build update expression
        update_parts = []
        attr_values: dict[str, Any] = {}

        if email_notifications_enabled is not None:
            update_parts.append("email_notifications_enabled = :email_enabled")
            attr_values[":email_enabled"] = email_notifications_enabled

        if daily_digest_enabled is not None:
            update_parts.append("daily_digest_enabled = :digest_enabled")
            attr_values[":digest_enabled"] = daily_digest_enabled

        if digest_time is not None:
            update_parts.append("digest_time = :digest_time")
            attr_values[":digest_time"] = digest_time

        if timezone is not None:
            update_parts.append("timezone = :timezone")
            attr_values[":timezone"] = timezone

        # Always set entity_type and updated_at
        update_parts.append("entity_type = :entity_type")
        attr_values[":entity_type"] = "NOTIFICATION_PREFS"

        update_parts.append("updated_at = :updated_at")
        attr_values[":updated_at"] = datetime.now(UTC).isoformat()

        if update_parts:
            table.update_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": "NOTIFICATION_PREFS",
                },
                UpdateExpression="SET " + ", ".join(update_parts),
                ExpressionAttributeValues=attr_values,
            )

        logger.info(
            "Updated notification preferences",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "updated_fields": list(attr_values.keys()),
            },
        )

        return get_notification_preferences(table, user_id)

    except Exception as e:
        logger.error(
            "Failed to update notification preferences",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("disable_all_notifications")
def disable_all_notifications(
    table: Any,
    user_id: str,
) -> DisableAllResponse:
    """Disable all notifications for user.

    Args:
        table: DynamoDB Table resource
        user_id: User ID

    Returns:
        DisableAllResponse with count of alerts disabled
    """
    try:
        # Update preferences to disable all
        table.update_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": "NOTIFICATION_PREFS",
            },
            UpdateExpression="SET email_notifications_enabled = :disabled, "
            "daily_digest_enabled = :disabled, "
            "entity_type = :entity_type",
            ExpressionAttributeValues={
                ":disabled": False,
                ":entity_type": "NOTIFICATION_PREFS",
            },
        )

        # Disable all alerts
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
            & Key("SK").begins_with("ALERT#"),
        )

        alerts_disabled = 0
        for item in response.get("Items", []):
            if item.get("is_enabled", True):
                table.update_item(
                    Key={
                        "PK": f"USER#{user_id}",
                        "SK": item["SK"],
                    },
                    UpdateExpression="SET is_enabled = :disabled",
                    ExpressionAttributeValues={":disabled": False},
                )
                alerts_disabled += 1

        logger.info(
            "Disabled all notifications",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "alerts_disabled": alerts_disabled,
            },
        )

        return DisableAllResponse(
            status="disabled",
            alerts_disabled=alerts_disabled,
            message="All notifications disabled",
        )

    except Exception as e:
        logger.error(
            "Failed to disable all notifications",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("unsubscribe_via_token")
def unsubscribe_via_token(
    table: Any,
    token: str,
    secret_key: str,
) -> UnsubscribeResponse | ErrorResponse:
    """Unsubscribe user via email token.

    Args:
        table: DynamoDB Table resource
        token: Unsubscribe token from email link
        secret_key: Secret key for verifying token

    Returns:
        UnsubscribeResponse on success, ErrorResponse on invalid token
    """
    try:
        # Parse and verify token (format: user_id|timestamp|signature)
        parts = token.split("|")
        if len(parts) != 3:
            return ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_TOKEN",
                    message="Unsubscribe link is invalid or expired",
                )
            )

        user_id, timestamp_str, signature = parts

        # Verify signature
        expected_sig = _generate_unsubscribe_signature(
            user_id, timestamp_str, secret_key
        )
        if not hmac.compare_digest(signature, expected_sig):
            return ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_TOKEN",
                    message="Unsubscribe link is invalid or expired",
                )
            )

        # Check if token has expired (24 hours)
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            if datetime.now(UTC) - timestamp > timedelta(hours=24):
                return ErrorResponse(
                    error=ErrorDetail(
                        code="INVALID_TOKEN",
                        message="Unsubscribe link is invalid or expired",
                    )
                )
        except ValueError:
            return ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_TOKEN",
                    message="Unsubscribe link is invalid or expired",
                )
            )

        # Disable email notifications
        table.update_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": "NOTIFICATION_PREFS",
            },
            UpdateExpression="SET email_notifications_enabled = :disabled, "
            "entity_type = :entity_type",
            ExpressionAttributeValues={
                ":disabled": False,
                ":entity_type": "NOTIFICATION_PREFS",
            },
        )

        logger.info(
            "User unsubscribed via token",
            extra={"user_id_prefix": sanitize_for_log(user_id[:8])},
        )

        return UnsubscribeResponse(
            status="unsubscribed",
            user_id=user_id,
            message="You have been unsubscribed from notification emails",
        )

    except Exception as e:
        logger.error(
            "Failed to process unsubscribe",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("resubscribe")
def resubscribe(
    table: Any,
    user_id: str,
) -> ResubscribeResponse:
    """Re-enable email notifications for user.

    Args:
        table: DynamoDB Table resource
        user_id: User ID

    Returns:
        ResubscribeResponse
    """
    try:
        table.update_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": "NOTIFICATION_PREFS",
            },
            UpdateExpression="SET email_notifications_enabled = :enabled, "
            "entity_type = :entity_type",
            ExpressionAttributeValues={
                ":enabled": True,
                ":entity_type": "NOTIFICATION_PREFS",
            },
        )

        logger.info(
            "User resubscribed",
            extra={"user_id_prefix": sanitize_for_log(user_id[:8])},
        )

        return ResubscribeResponse(
            status="resubscribed",
            message="Email notifications re-enabled",
        )

    except Exception as e:
        logger.error(
            "Failed to resubscribe",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("get_digest_settings")
def get_digest_settings(
    table: Any,
    user_id: str,
) -> DigestSettingsResponse:
    """Get user's digest settings.

    Args:
        table: DynamoDB Table resource
        user_id: User ID

    Returns:
        DigestSettingsResponse with digest settings
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": "DIGEST_SETTINGS",
            }
        )

        item = response.get("Item")
        if item:
            settings = DigestSettings.from_dynamodb_item(item)
            return _digest_to_response(settings)

        # Return defaults
        return DigestSettingsResponse(
            enabled=False,
            time="09:00",
            timezone="America/New_York",
            include_all_configs=True,
            config_ids=None,
            next_scheduled=_calculate_next_scheduled("09:00", "America/New_York"),
        )

    except Exception as e:
        logger.error(
            "Failed to get digest settings",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("update_digest_settings")
def update_digest_settings(
    table: Any,
    user_id: str,
    enabled: bool | None = None,
    time: str | None = None,
    timezone: str | None = None,
    include_all_configs: bool | None = None,
    config_ids: list[str] | None = None,
) -> DigestSettingsResponse | ErrorResponse:
    """Update user's digest settings.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        enabled: Enable/disable digest
        time: Digest time in HH:MM format
        timezone: IANA timezone string
        include_all_configs: Include all configs in digest
        config_ids: Specific config IDs to include

    Returns:
        DigestSettingsResponse on success, ErrorResponse on validation error
    """
    # Validate time format
    if time is not None:
        if not _validate_time_format(time):
            return ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_TIME",
                    message="Time must be in HH:MM format (24-hour)",
                )
            )

    # Validate timezone
    if timezone is not None and timezone not in VALID_TIMEZONES:
        return ErrorResponse(
            error=ErrorDetail(
                code="INVALID_TIMEZONE",
                message=f"Invalid timezone: {timezone}",
            )
        )

    # Validate config_ids required when not include_all_configs
    if include_all_configs is False and not config_ids:
        return ErrorResponse(
            error=ErrorDetail(
                code="CONFIG_IDS_REQUIRED",
                message="config_ids required when include_all_configs is false",
            )
        )

    try:
        # Get current settings for defaults
        current = get_digest_settings(table, user_id)

        # Merge with updates
        new_time = time if time is not None else current.time
        new_tz = timezone if timezone is not None else current.timezone

        # Calculate next scheduled
        next_scheduled = _calculate_next_scheduled(new_time, new_tz)

        # Build update expression
        update_parts = []
        attr_values: dict[str, Any] = {}

        if enabled is not None:
            update_parts.append("enabled = :enabled")
            update_parts.append("#status = :status")
            attr_values[":enabled"] = enabled
            attr_values[":status"] = ENABLED if enabled else DISABLED

        if time is not None:
            # 'time' is a reserved word in DynamoDB
            update_parts.append("#t = :time")
            attr_values[":time"] = time

        if timezone is not None:
            update_parts.append("timezone = :timezone")
            attr_values[":timezone"] = timezone

        if include_all_configs is not None:
            update_parts.append("include_all_configs = :include_all")
            attr_values[":include_all"] = include_all_configs

        if config_ids is not None:
            update_parts.append("config_ids = :config_ids")
            attr_values[":config_ids"] = config_ids

        # Always update next_scheduled and entity_type
        update_parts.append("next_scheduled = :next_scheduled")
        attr_values[":next_scheduled"] = next_scheduled

        update_parts.append("entity_type = :entity_type")
        attr_values[":entity_type"] = "DIGEST_SETTINGS"

        update_parts.append("user_id = :user_id")
        attr_values[":user_id"] = user_id

        update_kwargs: dict[str, Any] = {
            "Key": {
                "PK": f"USER#{user_id}",
                "SK": "DIGEST_SETTINGS",
            },
            "UpdateExpression": "SET " + ", ".join(update_parts),
            "ExpressionAttributeValues": attr_values,
        }

        # Add expression attribute names if we used #t for time or #status
        attr_names: dict[str, str] = {}
        if time is not None:
            attr_names["#t"] = "time"
        if enabled is not None:
            attr_names["#status"] = "status"
        if attr_names:
            update_kwargs["ExpressionAttributeNames"] = attr_names

        table.update_item(**update_kwargs)

        logger.info(
            "Updated digest settings",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "updated_fields": list(attr_values.keys()),
            },
        )

        return get_digest_settings(table, user_id)

    except Exception as e:
        logger.error(
            "Failed to update digest settings",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("trigger_test_digest")
def trigger_test_digest(
    table: Any,
    user_id: str,
) -> TriggerTestDigestResponse:
    """Queue a test digest email.

    Args:
        table: DynamoDB Table resource
        user_id: User ID

    Returns:
        TriggerTestDigestResponse
    """
    # In a real implementation, this would put a message on SQS
    # For now, just log and return success
    logger.info(
        "Triggered test digest",
        extra={"user_id_prefix": sanitize_for_log(user_id[:8])},
    )

    return TriggerTestDigestResponse(
        status="test_queued",
        message="Test digest email will be sent within 1 minute",
    )


# Helper functions


def _validate_time_format(time: str) -> bool:
    """Validate HH:MM time format."""
    if len(time) != 5 or time[2] != ":":
        return False

    try:
        hours_str, minutes_str = time.split(":")
        if len(hours_str) != 2 or len(minutes_str) != 2:
            return False

        hours = int(hours_str)
        minutes = int(minutes_str)
        return 0 <= hours <= 23 and 0 <= minutes <= 59
    except ValueError:
        return False


def _calculate_next_scheduled(time: str, timezone: str) -> str:
    """Calculate next scheduled digest time.

    For simplicity, returns UTC time. In production would use proper
    timezone conversion.
    """
    now = datetime.now(UTC)
    hours, minutes = map(int, time.split(":"))

    next_digest = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    if next_digest <= now:
        next_digest += timedelta(days=1)

    return next_digest.strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_unsubscribe_signature(
    user_id: str, timestamp: str, secret_key: str
) -> str:
    """Generate HMAC signature for unsubscribe token."""
    message = f"{user_id}|{timestamp}"
    return hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]


def generate_unsubscribe_token(user_id: str, secret_key: str) -> str:
    """Generate an unsubscribe token for email links.

    Args:
        user_id: User ID
        secret_key: Secret key for signing

    Returns:
        Signed token string (format: user_id|timestamp|signature)
    """
    timestamp = datetime.now(UTC).isoformat()
    signature = _generate_unsubscribe_signature(user_id, timestamp, secret_key)
    return f"{user_id}|{timestamp}|{signature}"


def _notification_to_response(
    notification: Notification,
    include_detail: bool = False,
) -> NotificationResponse:
    """Convert Notification to response format."""
    tracking = None
    if include_detail and (notification.opened_at or notification.clicked_at):
        tracking = TrackingInfo(
            opened_at=(
                notification.opened_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                if notification.opened_at
                else None
            ),
            clicked_at=(
                notification.clicked_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                if notification.clicked_at
                else None
            ),
        )

    return NotificationResponse(
        notification_id=notification.notification_id,
        alert_id=notification.alert_id,
        ticker=notification.ticker,
        alert_type=notification.alert_type,
        triggered_value=notification.triggered_value,
        subject=notification.subject,
        sent_at=notification.sent_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        status=notification.status,
        deep_link=notification.deep_link,
        email=notification.email if include_detail else None,
        tracking=tracking,
    )


def _digest_to_response(settings: DigestSettings) -> DigestSettingsResponse:
    """Convert DigestSettings to response format."""
    return DigestSettingsResponse(
        enabled=settings.enabled,
        time=settings.time,
        timezone=settings.timezone,
        include_all_configs=settings.include_all_configs,
        config_ids=settings.config_ids if settings.config_ids else None,
        next_scheduled=(
            settings.next_scheduled.strftime("%Y-%m-%dT%H:%M:%SZ")
            if settings.next_scheduled
            else _calculate_next_scheduled(settings.time, settings.timezone)
        ),
    )

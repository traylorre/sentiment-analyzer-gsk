"""Alert CRUD endpoints for Feature 006.

Implements alert management (T131-T136):
- POST /api/v2/alerts - Create alert rule
- GET /api/v2/alerts - List alerts
- GET /api/v2/alerts/{id} - Get alert
- PATCH /api/v2/alerts/{id} - Update alert
- DELETE /api/v2/alerts/{id} - Delete alert
- POST /api/v2/alerts/{id}/toggle - Toggle alert status

For On-Call Engineers:
    Alerts are stored with PK=USER#{user_id}, SK=ALERT#{alert_id}.
    Users can have max 10 alerts per configuration.
    Threshold ranges: sentiment (-1.0 to 1.0), volatility (0 to 100%).

Security Notes:
    - All operations require authenticated user session (not anonymous)
    - Users can only access their own alerts
    - Anonymous users get 403 Forbidden
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from aws_xray_sdk.core import xray_recorder
from boto3.dynamodb.conditions import Key
from pydantic import BaseModel, Field

from src.lambdas.dashboard.quota import get_daily_quota
from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
from src.lambdas.shared.models.alert_rule import (
    ALERT_LIMITS,
    AlertRule,
    AlertRuleCreate,
)
from src.lambdas.shared.models.status_utils import DISABLED, ENABLED

logger = logging.getLogger(__name__)


# Response schemas


class AlertResponse(BaseModel):
    """Alert response."""

    alert_id: str
    config_id: str
    ticker: str
    alert_type: Literal["sentiment_threshold", "volatility_threshold"]
    threshold_value: float
    threshold_direction: Literal["above", "below"]
    is_enabled: bool
    last_triggered_at: str | None = None
    trigger_count: int
    created_at: str


class AlertListResponse(BaseModel):
    """Response for GET /api/v2/alerts."""

    alerts: list[AlertResponse]
    total: int
    daily_email_quota: dict[str, Any]


class AlertToggleResponse(BaseModel):
    """Response for POST /api/v2/alerts/{id}/toggle."""

    alert_id: str
    is_enabled: bool
    message: str


class AlertUpdateRequest(BaseModel):
    """Request for PATCH /api/v2/alerts/{id}.

    Accepts both internal names (is_enabled, threshold_value) and
    client-facing names (enabled, threshold) for flexibility.
    """

    threshold_value: float | None = Field(default=None, alias="threshold")
    threshold_direction: Literal["above", "below"] | None = Field(
        default=None, alias="condition"
    )
    is_enabled: bool | None = Field(default=None, alias="enabled")

    model_config = {"populate_by_name": True}


class ErrorDetail(BaseModel):
    """Error detail for validation errors."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail


# Service functions


@xray_recorder.capture("create_alert")
def create_alert(
    table: Any,
    user_id: str,
    request: AlertRuleCreate,
    is_authenticated: bool = True,
) -> AlertResponse | ErrorResponse:
    """Create a new alert rule.

    Args:
        table: DynamoDB Table resource
        user_id: User ID (from session)
        request: Alert creation request
        is_authenticated: Whether user is authenticated (not anonymous)

    Returns:
        AlertResponse on success, ErrorResponse on failure
    """
    # Anonymous users cannot create alerts
    if not is_authenticated:
        return ErrorResponse(
            error=ErrorDetail(
                code="ANONYMOUS_NOT_ALLOWED",
                message="Alerts require authentication",
            )
        )

    # Validate threshold value based on alert type
    validation_error = _validate_threshold(request.alert_type, request.threshold_value)
    if validation_error:
        return validation_error

    # Check if user has reached max alerts for this config
    existing_count = _count_config_alerts(table, user_id, request.config_id)
    if existing_count >= ALERT_LIMITS["max_alerts_per_config"]:
        return ErrorResponse(
            error=ErrorDetail(
                code="ALERT_LIMIT_EXCEEDED",
                message=f"Maximum alerts ({ALERT_LIMITS['max_alerts_per_config']}) per configuration reached",
                details={
                    "max_allowed": ALERT_LIMITS["max_alerts_per_config"],
                    "current_count": existing_count,
                },
            )
        )

    now = datetime.now(UTC)
    alert_id = str(uuid.uuid4())

    alert = AlertRule(
        alert_id=alert_id,
        user_id=user_id,
        config_id=request.config_id,
        ticker=request.ticker.upper(),
        alert_type=request.alert_type,
        threshold_value=request.threshold_value,
        threshold_direction=request.threshold_direction,
        is_enabled=True,
        status=ENABLED,
        trigger_count=0,
        created_at=now,
    )

    try:
        table.put_item(Item=alert.to_dynamodb_item())

        logger.info(
            "Created alert",
            extra={
                "alert_id": sanitize_for_log(alert_id[:8]),
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "ticker": sanitize_for_log(alert.ticker),
                "alert_type": alert.alert_type,
            },
        )

        return _alert_to_response(alert)

    except Exception as e:
        logger.error(
            "Failed to create alert",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("list_alerts")
def list_alerts(
    table: Any,
    user_id: str,
    config_id: str | None = None,
    ticker: str | None = None,
    enabled: bool | None = None,
) -> AlertListResponse:
    """List user's alerts with optional filters.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        config_id: Filter by configuration (optional)
        ticker: Filter by ticker (optional)
        enabled: Filter by enabled status (optional)

    Returns:
        AlertListResponse with filtered alerts
    """
    try:
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
            & Key("SK").begins_with("ALERT#"),
        )

        alerts = []
        for item in response.get("Items", []):
            # Skip non-alert items
            if item.get("entity_type") != "ALERT_RULE":
                continue

            # Apply filters
            if config_id and item.get("config_id") != config_id:
                continue
            if ticker and item.get("ticker") != ticker.upper():
                continue
            # Use status field with fallback to is_enabled for backward compatibility
            if enabled is not None:
                status = item.get(
                    "status", ENABLED if item.get("is_enabled", True) else DISABLED
                )
                item_enabled = status == ENABLED
                if item_enabled != enabled:
                    continue

            alert = AlertRule.from_dynamodb_item(item)
            alerts.append(_alert_to_response(alert))

        # Sort by created_at descending
        alerts.sort(key=lambda a: a.created_at, reverse=True)

        # Get daily email quota info
        quota_info = _get_daily_email_quota(table, user_id)

        logger.debug(
            "Listed alerts",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "count": len(alerts),
            },
        )

        return AlertListResponse(
            alerts=alerts,
            total=len(alerts),
            daily_email_quota=quota_info,
        )

    except Exception as e:
        logger.error(
            "Failed to list alerts",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("get_alert")
def get_alert(
    table: Any,
    user_id: str,
    alert_id: str,
) -> AlertResponse | None:
    """Get a single alert.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        alert_id: Alert ID

    Returns:
        AlertResponse if found, None otherwise
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": f"ALERT#{alert_id}",
            }
        )

        item = response.get("Item")
        if not item:
            return None

        alert = AlertRule.from_dynamodb_item(item)
        return _alert_to_response(alert)

    except Exception as e:
        logger.error(
            "Failed to get alert",
            extra={
                "alert_id": sanitize_for_log(alert_id[:8] if alert_id else ""),
                **get_safe_error_info(e),
            },
        )
        raise


@xray_recorder.capture("update_alert")
def update_alert(
    table: Any,
    user_id: str,
    alert_id: str,
    request: AlertUpdateRequest,
) -> AlertResponse | ErrorResponse | None:
    """Update an existing alert.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        alert_id: Alert ID
        request: Update request

    Returns:
        AlertResponse on success, ErrorResponse on validation error,
        None if alert not found
    """
    # Get existing alert
    existing = get_alert(table, user_id, alert_id)
    if existing is None:
        return None

    # Validate new threshold if provided
    if request.threshold_value is not None:
        validation_error = _validate_threshold(
            existing.alert_type, request.threshold_value
        )
        if validation_error:
            return validation_error

    # Build update expression
    update_parts = []
    attr_values: dict[str, Any] = {}
    attr_names: dict[str, str] = {}

    if request.threshold_value is not None:
        update_parts.append("threshold_value = :threshold")
        attr_values[":threshold"] = str(request.threshold_value)

    if request.threshold_direction is not None:
        update_parts.append("threshold_direction = :direction")
        attr_values[":direction"] = request.threshold_direction

    if request.is_enabled is not None:
        update_parts.append("is_enabled = :enabled")
        update_parts.append("#status = :status")
        attr_values[":enabled"] = request.is_enabled
        attr_values[":status"] = ENABLED if request.is_enabled else DISABLED
        attr_names["#status"] = "status"

    if not update_parts:
        # Nothing to update, return existing
        return existing

    try:
        # Use ReturnValues='ALL_NEW' to get updated item directly,
        # avoiding eventual consistency issues with a separate read
        update_kwargs: dict[str, Any] = {
            "Key": {
                "PK": f"USER#{user_id}",
                "SK": f"ALERT#{alert_id}",
            },
            "UpdateExpression": "SET " + ", ".join(update_parts),
            "ExpressionAttributeValues": attr_values,
            "ReturnValues": "ALL_NEW",
        }
        if attr_names:
            update_kwargs["ExpressionAttributeNames"] = attr_names
        response = table.update_item(**update_kwargs)

        logger.info(
            "Updated alert",
            extra={
                "alert_id": sanitize_for_log(alert_id[:8]),
                "updated_fields": list(attr_values.keys()),
            },
        )

        # Parse the updated item from response
        updated_item = response.get("Attributes", {})
        if not updated_item:
            # Fallback to get_alert if no attributes returned (shouldn't happen)
            return get_alert(table, user_id, alert_id)

        alert = AlertRule.from_dynamodb_item(updated_item)
        return _alert_to_response(alert)

    except Exception as e:
        logger.error(
            "Failed to update alert",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("delete_alert")
def delete_alert(
    table: Any,
    user_id: str,
    alert_id: str,
) -> bool:
    """Delete an alert.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        alert_id: Alert ID

    Returns:
        True if deleted, False if not found
    """
    # Verify alert exists and belongs to user
    existing = get_alert(table, user_id, alert_id)
    if existing is None:
        return False

    try:
        table.delete_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": f"ALERT#{alert_id}",
            }
        )

        logger.info(
            "Deleted alert",
            extra={
                "alert_id": sanitize_for_log(alert_id[:8]),
                "user_id_prefix": sanitize_for_log(user_id[:8]),
            },
        )

        return True

    except Exception as e:
        logger.error(
            "Failed to delete alert",
            extra=get_safe_error_info(e),
        )
        raise


@xray_recorder.capture("toggle_alert")
def toggle_alert(
    table: Any,
    user_id: str,
    alert_id: str,
) -> AlertToggleResponse | None:
    """Toggle an alert's enabled status.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        alert_id: Alert ID

    Returns:
        AlertToggleResponse if found, None otherwise
    """
    # Get existing alert
    existing = get_alert(table, user_id, alert_id)
    if existing is None:
        return None

    new_enabled = not existing.is_enabled
    new_status = ENABLED if new_enabled else DISABLED

    try:
        table.update_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": f"ALERT#{alert_id}",
            },
            UpdateExpression="SET is_enabled = :enabled, #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":enabled": new_enabled, ":status": new_status},
        )

        message = "Alert enabled" if new_enabled else "Alert disabled"

        logger.info(
            f"Toggled alert: {message}",
            extra={
                "alert_id": sanitize_for_log(alert_id[:8]),
                "is_enabled": new_enabled,
            },
        )

        return AlertToggleResponse(
            alert_id=alert_id,
            is_enabled=new_enabled,
            message=message,
        )

    except Exception as e:
        logger.error(
            "Failed to toggle alert",
            extra=get_safe_error_info(e),
        )
        raise


# Helper functions


def _count_config_alerts(table: Any, user_id: str, config_id: str) -> int:
    """Count alerts for a specific configuration."""
    try:
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
            & Key("SK").begins_with("ALERT#"),
            FilterExpression="config_id = :config_id",
            ExpressionAttributeValues={":config_id": config_id},
            Select="COUNT",
        )
        return response.get("Count", 0)
    except Exception:
        return 0


def _validate_threshold(
    alert_type: str, threshold_value: float
) -> ErrorResponse | None:
    """Validate threshold value based on alert type.

    Returns ErrorResponse if invalid, None if valid.
    """
    if alert_type == "sentiment_threshold":
        min_val, max_val = ALERT_LIMITS["sentiment_threshold_range"]
        if not (min_val <= threshold_value <= max_val):
            return ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_THRESHOLD",
                    message=f"Sentiment threshold must be between {min_val} and {max_val}",
                    details={
                        "field": "threshold_value",
                        "constraint": f"must be between {min_val} and {max_val}",
                        "received": threshold_value,
                    },
                )
            )
    elif alert_type == "volatility_threshold":
        min_val, max_val = ALERT_LIMITS["volatility_threshold_range"]
        if not (min_val <= threshold_value <= max_val):
            return ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_THRESHOLD",
                    message=f"Volatility threshold must be between {min_val}% and {max_val}%",
                    details={
                        "field": "threshold_value",
                        "constraint": f"must be between {min_val}% and {max_val}%",
                        "received": threshold_value,
                    },
                )
            )

    return None


def _get_daily_email_quota(table: Any, user_id: str) -> dict[str, Any]:
    """Get user's daily email quota status.

    Returns dict with used, limit, remaining, and resets_at.
    """
    quota = get_daily_quota(table, user_id)
    return {
        "used": quota.used,
        "limit": quota.limit,
        "remaining": quota.remaining,
        "resets_at": quota.resets_at,
        "is_exceeded": quota.is_exceeded,
    }


def _alert_to_response(alert: AlertRule) -> AlertResponse:
    """Convert AlertRule to response format."""
    return AlertResponse(
        alert_id=alert.alert_id,
        config_id=alert.config_id,
        ticker=alert.ticker,
        alert_type=alert.alert_type,
        threshold_value=alert.threshold_value,
        threshold_direction=alert.threshold_direction,
        is_enabled=alert.is_enabled,
        last_triggered_at=(
            alert.last_triggered_at.strftime("%Y-%m-%dT%H:%M:%SZ")
            if alert.last_triggered_at
            else None
        ),
        trigger_count=alert.trigger_count,
        created_at=alert.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def get_alerts_by_config(
    table: Any,
    user_id: str,
    config_id: str,
) -> AlertListResponse | ErrorResponse:
    """Get alerts for a specific configuration.

    Convenience wrapper around list_alerts with config_id filter.

    Args:
        table: DynamoDB Table resource
        user_id: User ID for access control
        config_id: Configuration ID to filter by

    Returns:
        AlertListResponse with alerts for the configuration
    """
    return list_alerts(table=table, user_id=user_id, config_id=config_id)

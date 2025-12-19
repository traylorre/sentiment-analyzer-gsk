"""Alert evaluation service for Feature 006.

Implements T145-T147:
- Alert evaluation logic comparing current values to thresholds
- Internal evaluate endpoint for analysis Lambda to call
- Email quota tracking and monitoring

For On-Call Engineers:
    Alert evaluation happens when sentiment/volatility data is updated.
    The analysis Lambda calls the internal /api/internal/alerts/evaluate endpoint.
    Alerts are only triggered if the threshold is crossed and user has email quota.

Security Notes:
    - Internal endpoints require X-Internal-Auth header
    - Email quota is tracked per user per day (max 10)
    - Alert cooldown prevents duplicate triggers
"""

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from aws_xray_sdk.core import xray_recorder
from pydantic import BaseModel

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
from src.lambdas.shared.models.alert_rule import ALERT_LIMITS, AlertRule
from src.lambdas.shared.models.status_utils import ENABLED

logger = logging.getLogger(__name__)

# Environment variables
DYNAMODB_TABLE = os.environ["DATABASE_TABLE"]
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")


# Request/Response schemas


class SentimentUpdate(BaseModel):
    """Sentiment data update."""

    score: float
    source: str
    timestamp: str


class VolatilityUpdate(BaseModel):
    """Volatility data update."""

    atr_percent: float
    timestamp: str


class AlertUpdates(BaseModel):
    """Updates to evaluate against alerts."""

    sentiment: SentimentUpdate | None = None
    volatility: VolatilityUpdate | None = None


class EvaluateAlertsRequest(BaseModel):
    """Request for POST /api/internal/alerts/evaluate."""

    ticker: str
    updates: AlertUpdates


class AlertTriggerDetail(BaseModel):
    """Detail for a single triggered alert."""

    alert_id: str
    user_id: str
    triggered: bool
    current_value: float
    threshold: float
    notification_id: str | None = None


class EvaluateAlertsResponse(BaseModel):
    """Response for POST /api/internal/alerts/evaluate."""

    evaluated: int
    triggered: int
    notifications_queued: int
    details: list[AlertTriggerDetail]


class EmailQuotaResponse(BaseModel):
    """Response for GET /api/internal/email-quota."""

    daily_limit: int
    used_today: int
    remaining: int
    percent_used: float
    reset_at: str
    alert_threshold: int
    alert_triggered: bool
    alert_triggered_at: str | None = None
    last_email_sent_at: str | None = None
    top_users: list[dict[str, Any]]


# Service functions


@xray_recorder.capture("evaluate_alerts_for_ticker")
def evaluate_alerts_for_ticker(
    table: Any,
    ticker: str,
    sentiment_score: float | None = None,
    volatility_atr: float | None = None,
) -> EvaluateAlertsResponse:
    """Evaluate all alerts for a specific ticker.

    Args:
        table: DynamoDB Table resource
        ticker: Stock symbol to evaluate
        sentiment_score: Current sentiment score (-1.0 to 1.0)
        volatility_atr: Current ATR volatility (percent)

    Returns:
        EvaluateAlertsResponse with evaluation results
    """
    ticker = ticker.upper()
    details: list[AlertTriggerDetail] = []
    triggered_count = 0
    notifications_queued = 0

    try:
        # Find all alerts for this ticker using GSI or scan
        # For simplicity, scan all alerts and filter by ticker
        # In production, use a GSI on ticker
        alerts = _find_alerts_by_ticker(table, ticker)

        logger.info(
            f"Evaluating {len(alerts)} alerts for ticker {ticker}",
            extra={
                "ticker": sanitize_for_log(ticker),
                "alert_count": len(alerts),
                "sentiment_score": sentiment_score,
                "volatility_atr": volatility_atr,
            },
        )

        for alert in alerts:
            # Skip disabled alerts - use status field (with is_enabled fallback)
            if alert.status != ENABLED:
                continue

            # Check cooldown (don't trigger same alert within 1 hour)
            if _is_in_cooldown(alert):
                continue

            # Evaluate based on alert type
            triggered = False
            current_value = 0.0

            if (
                alert.alert_type == "sentiment_threshold"
                and sentiment_score is not None
            ):
                current_value = sentiment_score
                triggered = _evaluate_threshold(
                    current_value,
                    alert.threshold_value,
                    alert.threshold_direction,
                )
            elif (
                alert.alert_type == "volatility_threshold"
                and volatility_atr is not None
            ):
                current_value = volatility_atr
                triggered = _evaluate_threshold(
                    current_value,
                    alert.threshold_value,
                    alert.threshold_direction,
                )

            notification_id = None
            if triggered:
                # Check user's email quota
                if _check_email_quota(table, alert.user_id):
                    # Queue notification
                    notification_id = _queue_notification(
                        table,
                        alert,
                        current_value,
                    )
                    if notification_id:
                        notifications_queued += 1

                        # Update alert trigger info
                        _update_alert_triggered(table, alert)

                triggered_count += 1

            details.append(
                AlertTriggerDetail(
                    alert_id=alert.alert_id,
                    user_id=alert.user_id,
                    triggered=triggered,
                    current_value=current_value,
                    threshold=alert.threshold_value,
                    notification_id=notification_id,
                )
            )

        return EvaluateAlertsResponse(
            evaluated=len(alerts),
            triggered=triggered_count,
            notifications_queued=notifications_queued,
            details=details,
        )

    except Exception as e:
        logger.error(
            "Failed to evaluate alerts",
            extra={
                "ticker": sanitize_for_log(ticker),
                **get_safe_error_info(e),
            },
        )
        raise


@xray_recorder.capture("get_email_quota_status")
def get_email_quota_status(table: Any) -> EmailQuotaResponse:
    """Get current email quota status.

    Args:
        table: DynamoDB Table resource

    Returns:
        EmailQuotaResponse with quota info
    """
    try:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        tomorrow = (datetime.now(UTC) + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Get quota tracking record
        response = table.get_item(
            Key={
                "PK": "EMAIL_QUOTA",
                "SK": today,
            }
        )

        item = response.get("Item", {})
        used_today = int(item.get("count", 0))
        daily_limit = 100  # SendGrid free tier
        alert_threshold = 50

        # Get top users
        top_users = item.get("top_users", [])

        # Check if alert was triggered
        alert_triggered = used_today >= alert_threshold
        alert_triggered_at = item.get("alert_triggered_at")

        return EmailQuotaResponse(
            daily_limit=daily_limit,
            used_today=used_today,
            remaining=max(0, daily_limit - used_today),
            percent_used=round((used_today / daily_limit) * 100, 1),
            reset_at=tomorrow.strftime("%Y-%m-%dT%H:%M:%SZ"),
            alert_threshold=alert_threshold,
            alert_triggered=alert_triggered,
            alert_triggered_at=alert_triggered_at,
            last_email_sent_at=item.get("last_sent_at"),
            top_users=top_users[:10],  # Top 10 users
        )

    except Exception as e:
        logger.error(
            "Failed to get email quota status",
            extra=get_safe_error_info(e),
        )
        raise


def verify_internal_auth(auth_header: str | None) -> bool:
    """Verify internal API authentication.

    Args:
        auth_header: X-Internal-Auth header value

    Returns:
        True if authenticated, False otherwise
    """
    if not INTERNAL_API_KEY:
        # Allow in dev/test if not configured
        return os.environ.get("ENVIRONMENT", "dev") in ("dev", "test")

    return auth_header == INTERNAL_API_KEY


# Helper functions


def _find_alerts_by_ticker(table: Any, ticker: str) -> list[AlertRule]:
    """Find all active alerts for a specific ticker.

    Uses by_entity_status GSI for O(result) query performance with FilterExpression on ticker.
    (502-gsi-query-optimization: Replaced scan with GSI query)

    Args:
        table: DynamoDB Table resource
        ticker: Ticker symbol to find alerts for

    Returns:
        List of AlertRule objects for the ticker
    """
    alerts = []

    try:
        # Query using by_entity_status GSI, filter by ticker
        # ALERT_RULE uses "enabled"/"disabled" status values (not "active"/"inactive")
        response = table.query(
            IndexName="by_entity_status",
            KeyConditionExpression="entity_type = :type AND #status = :status",
            FilterExpression="ticker = :ticker",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":type": "ALERT_RULE",
                ":status": ENABLED,
                ":ticker": ticker,
            },
        )

        for item in response.get("Items", []):
            alerts.append(AlertRule.from_dynamodb_item(item))

        # Handle pagination with LastEvaluatedKey
        while "LastEvaluatedKey" in response:
            response = table.query(
                IndexName="by_entity_status",
                KeyConditionExpression="entity_type = :type AND #status = :status",
                FilterExpression="ticker = :ticker",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":type": "ALERT_RULE",
                    ":status": ENABLED,
                    ":ticker": ticker,
                },
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            for item in response.get("Items", []):
                alerts.append(AlertRule.from_dynamodb_item(item))

    except Exception as e:
        logger.error(f"Error finding alerts for ticker: {e}")

    return alerts


def _evaluate_threshold(
    current_value: float,
    threshold_value: float,
    direction: Literal["above", "below"],
) -> bool:
    """Evaluate if threshold is crossed.

    Args:
        current_value: Current metric value
        threshold_value: Threshold to compare against
        direction: Direction of comparison

    Returns:
        True if threshold is crossed
    """
    if direction == "above":
        return current_value > threshold_value
    else:  # below
        return current_value < threshold_value


def _is_in_cooldown(alert: AlertRule, cooldown_hours: int = 1) -> bool:
    """Check if alert is in cooldown period.

    Args:
        alert: Alert rule to check
        cooldown_hours: Hours between triggers (default 1)

    Returns:
        True if in cooldown, False otherwise
    """
    if not alert.last_triggered_at:
        return False

    cooldown_end = alert.last_triggered_at + timedelta(hours=cooldown_hours)
    return datetime.now(UTC) < cooldown_end


def _check_email_quota(table: Any, user_id: str) -> bool:
    """Check if user has remaining email quota.

    Args:
        table: DynamoDB Table resource
        user_id: User to check

    Returns:
        True if user can receive email, False if quota exceeded
    """
    try:
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        response = table.get_item(
            Key={
                "PK": f"USER_QUOTA#{user_id}",
                "SK": today,
            }
        )

        item = response.get("Item", {})
        emails_today = int(item.get("count", 0))

        return emails_today < ALERT_LIMITS["max_emails_per_day"]

    except Exception:
        # Default to allowing on error
        return True


def _queue_notification(
    table: Any,
    alert: AlertRule,
    triggered_value: float,
) -> str | None:
    """Queue notification for alert.

    Args:
        table: DynamoDB Table resource
        alert: Alert that was triggered
        triggered_value: Value that triggered the alert

    Returns:
        Notification ID if queued, None otherwise
    """
    try:
        notification_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # Get user email (would query user record in real implementation)
        # For now, create placeholder notification
        notification_item = {
            "PK": f"USER#{alert.user_id}",
            "SK": f"NOTIF#{now.isoformat()}",
            "notification_id": notification_id,
            "user_id": alert.user_id,
            "alert_id": alert.alert_id,
            "ticker": alert.ticker,
            "alert_type": alert.alert_type,
            "triggered_value": str(triggered_value),
            "threshold_value": str(alert.threshold_value),
            "threshold_direction": alert.threshold_direction,
            "status": "pending",
            "created_at": now.isoformat(),
            "entity_type": "NOTIFICATION_QUEUE",
        }

        table.put_item(Item=notification_item)

        # Increment user's daily quota
        _increment_user_quota(table, alert.user_id)

        # Increment global quota
        _increment_global_quota(table)

        logger.info(
            f"Queued notification {notification_id} for alert {alert.alert_id}",
            extra={
                "notification_id": sanitize_for_log(notification_id[:8]),
                "alert_id": sanitize_for_log(alert.alert_id[:8]),
            },
        )

        return notification_id

    except Exception as e:
        logger.error(f"Failed to queue notification: {e}")
        return None


def _update_alert_triggered(table: Any, alert: AlertRule) -> None:
    """Update alert with trigger timestamp and count.

    Args:
        table: DynamoDB Table resource
        alert: Alert that was triggered
    """
    try:
        now = datetime.now(UTC)

        table.update_item(
            Key={
                "PK": f"USER#{alert.user_id}",
                "SK": f"ALERT#{alert.alert_id}",
            },
            UpdateExpression="SET last_triggered_at = :ts, trigger_count = trigger_count + :one",
            ExpressionAttributeValues={
                ":ts": now.isoformat(),
                ":one": 1,
            },
        )

    except Exception as e:
        logger.error(f"Failed to update alert trigger info: {e}")


def _increment_user_quota(table: Any, user_id: str) -> None:
    """Increment user's daily email quota usage.

    Args:
        table: DynamoDB Table resource
        user_id: User to increment
    """
    try:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        ttl = int(
            tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        )

        table.update_item(
            Key={
                "PK": f"USER_QUOTA#{user_id}",
                "SK": today,
            },
            UpdateExpression="SET #c = if_not_exists(#c, :zero) + :one, "
            "entity_type = :type, ttl = :ttl",
            ExpressionAttributeNames={"#c": "count"},
            ExpressionAttributeValues={
                ":zero": 0,
                ":one": 1,
                ":type": "USER_QUOTA",
                ":ttl": ttl,
            },
        )

    except Exception as e:
        logger.error(f"Failed to increment user quota: {e}")


def _increment_global_quota(table: Any) -> None:
    """Increment global daily email quota usage.

    Args:
        table: DynamoDB Table resource
    """
    try:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        now = datetime.now(UTC)
        tomorrow = now + timedelta(days=1)
        ttl = int(
            tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        )

        table.update_item(
            Key={
                "PK": "EMAIL_QUOTA",
                "SK": today,
            },
            UpdateExpression="SET #c = if_not_exists(#c, :zero) + :one, "
            "last_sent_at = :ts, entity_type = :type, ttl = :ttl",
            ExpressionAttributeNames={"#c": "count"},
            ExpressionAttributeValues={
                ":zero": 0,
                ":one": 1,
                ":ts": now.isoformat(),
                ":type": "EMAIL_QUOTA",
                ":ttl": ttl,
            },
        )

    except Exception as e:
        logger.error(f"Failed to increment global quota: {e}")

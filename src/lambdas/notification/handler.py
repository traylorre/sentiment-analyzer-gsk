"""Notification Lambda handler for Feature 006.

Handles:
- Alert notifications when sentiment thresholds are crossed
- Magic link authentication emails
- Daily digest emails

Triggered by:
- EventBridge scheduled events (digest)
- SNS messages (alert triggers)
- Direct invocation (magic links)
"""

import json
import logging
import os
from typing import Any

from aws_xray_sdk.core import patch_all, xray_recorder

from src.lambdas.notification.digest_service import process_daily_digests
from src.lambdas.notification.sendgrid_service import (
    EmailService,
    EmailServiceError,
    RateLimitExceededError,
)

# Patch boto3 and requests for X-Ray tracing
patch_all()

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Environment variables
SENDGRID_SECRET_ARN = os.environ.get("SENDGRID_SECRET_ARN", "")
DYNAMODB_TABLE = os.environ["DATABASE_TABLE"]
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@sentiment-analyzer.com")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://sentiment-analyzer.com")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle notification Lambda invocations.

    Args:
        event: Lambda event containing notification type and data
        context: Lambda context

    Returns:
        Response dict with statusCode and body
    """
    logger.info(f"Notification Lambda invoked: {json.dumps(event)[:500]}")

    try:
        # Determine notification type
        notification_type = _get_notification_type(event)

        if notification_type == "alert":
            return _handle_alert_notification(event)
        elif notification_type == "magic_link":
            return _handle_magic_link(event)
        elif notification_type == "digest":
            return _handle_daily_digest(event)
        else:
            logger.warning(f"Unknown notification type: {notification_type}")
            return _response(
                400, {"error": f"Unknown notification type: {notification_type}"}
            )

    except RateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded: {e}")
        return _response(
            429, {"error": "Rate limit exceeded", "retry_after": e.retry_after}
        )

    except EmailServiceError as e:
        logger.error(f"Email service error: {e}")
        return _response(500, {"error": "Failed to send email"})

    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        return _response(500, {"error": "Internal server error"})


def _get_notification_type(event: dict[str, Any]) -> str:
    """Determine the notification type from the event.

    Args:
        event: Lambda event

    Returns:
        Notification type string
    """
    # Direct invocation with type
    if "notification_type" in event:
        return event["notification_type"]

    # SNS message
    if "Records" in event:
        for record in event.get("Records", []):
            if record.get("EventSource") == "aws:sns":
                message = json.loads(record.get("Sns", {}).get("Message", "{}"))
                return message.get("notification_type", "alert")

    # EventBridge scheduled event (digest)
    if "detail-type" in event:
        if event.get("detail-type") == "Scheduled Event":
            return "digest"

    return "unknown"


@xray_recorder.capture("handle_alert_notification")
def _handle_alert_notification(event: dict[str, Any]) -> dict[str, Any]:
    """Handle alert notification when threshold is crossed.

    Args:
        event: Event containing alert data

    Returns:
        Response dict
    """
    # Extract alert data
    alert_data = event.get("alert", {})
    if "Records" in event:
        # From SNS
        for record in event.get("Records", []):
            if record.get("EventSource") == "aws:sns":
                message = json.loads(record.get("Sns", {}).get("Message", "{}"))
                alert_data = message.get("alert", {})
                break

    # Validate required fields
    email = alert_data.get("email")
    ticker = alert_data.get("ticker")
    alert_type = alert_data.get("alert_type")
    triggered_value = alert_data.get("triggered_value")
    threshold = alert_data.get("threshold")

    if not all([email, ticker, alert_type, triggered_value, threshold]):
        logger.warning(f"Missing required alert fields: {alert_data}")
        return _response(400, {"error": "Missing required alert fields"})

    # Build email content
    subject = f"Alert: {ticker} {alert_type} threshold crossed"
    html_content = _build_alert_email(ticker, alert_type, triggered_value, threshold)

    # Send email
    email_service = _get_email_service()
    success = email_service.send_email(
        to_email=email,
        subject=subject,
        html_content=html_content,
    )

    if success:
        logger.info(f"Alert email sent to {email} for {ticker}")
        return _response(200, {"message": "Alert notification sent"})
    else:
        logger.error(f"Failed to send alert email to {email}")
        return _response(500, {"error": "Failed to send email"})


@xray_recorder.capture("handle_magic_link")
def _handle_magic_link(event: dict[str, Any]) -> dict[str, Any]:
    """Handle magic link authentication email.

    Args:
        event: Event containing magic link data

    Returns:
        Response dict
    """
    email = event.get("email")
    token = event.get("token")
    expires_in_minutes = event.get("expires_in_minutes", 60)

    if not all([email, token]):
        logger.warning("Missing email or token for magic link")
        return _response(400, {"error": "Missing email or token"})

    # Build magic link URL
    magic_link = f"{DASHBOARD_URL}/auth/verify?token={token}"

    # Build email content
    subject = "Your sign-in link for Sentiment Analyzer"
    html_content = _build_magic_link_email(magic_link, expires_in_minutes)

    # Send email
    email_service = _get_email_service()
    success = email_service.send_email(
        to_email=email,
        subject=subject,
        html_content=html_content,
    )

    if success:
        logger.info(f"Magic link email sent to {email}")
        return _response(200, {"message": "Magic link sent"})
    else:
        logger.error(f"Failed to send magic link email to {email}")
        return _response(500, {"error": "Failed to send email"})


@xray_recorder.capture("handle_daily_digest")
def _handle_daily_digest(event: dict[str, Any]) -> dict[str, Any]:
    """Handle daily digest email generation.

    Processes all users due for digest based on their timezone and
    configured delivery time. Sends personalized sentiment summaries.

    Args:
        event: EventBridge scheduled event

    Returns:
        Response dict with processing stats
    """
    import boto3

    logger.info("Daily digest handler invoked")

    # Get DynamoDB table
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(DYNAMODB_TABLE)

    # Get email service
    email_service = _get_email_service()

    # Process digests
    stats = process_daily_digests(
        table=table,
        email_service=email_service,
        dashboard_url=DASHBOARD_URL,
    )

    logger.info("Daily digest processing complete", extra=stats)

    return _response(
        200,
        {
            "message": "Digest processing complete",
            "stats": stats,
        },
    )


def _get_email_service() -> EmailService:
    """Get configured email service.

    Returns:
        EmailService instance
    """
    return EmailService(
        secret_arn=SENDGRID_SECRET_ARN,
        from_email=FROM_EMAIL,
    )


def _build_alert_email(
    ticker: str,
    alert_type: str,
    triggered_value: float,
    threshold: float,
) -> str:
    """Build HTML content for alert email.

    Args:
        ticker: Stock symbol
        alert_type: Type of alert (sentiment/volatility)
        triggered_value: Value that triggered alert
        threshold: Threshold that was crossed

    Returns:
        HTML email content
    """
    direction = "exceeded" if triggered_value > threshold else "dropped below"
    color = "#22c55e" if triggered_value > threshold else "#ef4444"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #1e40af; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9fafb; }}
            .metric {{ font-size: 24px; font-weight: bold; color: {color}; }}
            .button {{ display: inline-block; padding: 12px 24px; background-color: #1e40af;
                       color: white; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Alert: {ticker}</h1>
            </div>
            <div class="content">
                <p>Your {alert_type} alert for <strong>{ticker}</strong> has been triggered.</p>
                <p>The {alert_type} value has {direction} your threshold of {threshold:.2f}.</p>
                <p>Current value: <span class="metric">{triggered_value:.2f}</span></p>
                <a href="{DASHBOARD_URL}/dashboard?ticker={ticker}" class="button">
                    View Dashboard
                </a>
            </div>
            <div class="footer">
                <p>You received this email because you set up an alert in Sentiment Analyzer.</p>
                <p><a href="{DASHBOARD_URL}/settings/alerts">Manage your alerts</a></p>
            </div>
        </div>
    </body>
    </html>
    """


def _build_magic_link_email(magic_link: str, expires_in_minutes: int) -> str:
    """Build HTML content for magic link email.

    Args:
        magic_link: The magic link URL
        expires_in_minutes: Link expiration time

    Returns:
        HTML email content
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #1e40af; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9fafb; text-align: center; }}
            .button {{ display: inline-block; padding: 16px 32px; background-color: #22c55e;
                       color: white; text-decoration: none; border-radius: 4px; font-size: 18px;
                       margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            .warning {{ color: #f59e0b; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Sign in to Sentiment Analyzer</h1>
            </div>
            <div class="content">
                <p>Click the button below to sign in to your account.</p>
                <a href="{magic_link}" class="button">Sign In</a>
                <p class="warning">This link will expire in {expires_in_minutes} minutes.</p>
                <p style="color: #666; font-size: 12px;">
                    If you didn't request this link, you can safely ignore this email.
                </p>
            </div>
            <div class="footer">
                <p>This is an automated message from Sentiment Analyzer.</p>
            </div>
        </div>
    </body>
    </html>
    """


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """Build Lambda response.

    Args:
        status_code: HTTP status code
        body: Response body

    Returns:
        Lambda response dict
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body),
    }

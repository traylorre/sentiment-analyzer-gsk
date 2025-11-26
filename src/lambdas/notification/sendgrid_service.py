"""SendGrid email service for Feature 006.

Handles transactional emails:
- Magic link authentication
- Alert notifications
- Daily digest emails

Rate limits:
- SendGrid free tier: 100 emails/day
- Application limit: 10 alerts/day/user
"""

import json
import logging
from functools import lru_cache

import boto3
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Base exception for email service errors."""

    pass


class RateLimitExceededError(EmailServiceError):
    """Raised when email rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(EmailServiceError):
    """Raised when SendGrid authentication fails."""

    pass


class EmailService:
    """SendGrid email service for transactional emails.

    Provides:
    - Magic link emails for passwordless auth
    - Alert notification emails
    - Daily digest emails
    - Rate limit tracking
    """

    def __init__(
        self,
        secret_arn: str,
        from_email: str,
        api_key: str | None = None,
    ):
        """Initialize email service.

        Args:
            secret_arn: ARN of SendGrid API key in Secrets Manager
            from_email: Sender email address
            api_key: Optional API key (overrides secret_arn for testing)
        """
        self.secret_arn = secret_arn
        self.from_email = from_email
        self._api_key = api_key
        self._client: SendGridAPIClient | None = None

    @property
    def api_key(self) -> str:
        """Get SendGrid API key from cache or Secrets Manager."""
        if self._api_key:
            return self._api_key
        return _get_sendgrid_api_key(self.secret_arn)

    @property
    def client(self) -> SendGridAPIClient:
        """Get or create SendGrid client."""
        if self._client is None:
            self._client = SendGridAPIClient(self.api_key)
        return self._client

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: str | None = None,
    ) -> bool:
        """Send a single email via SendGrid.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML email body
            plain_content: Plain text fallback (optional)

        Returns:
            True if email was sent successfully

        Raises:
            RateLimitExceededError: If SendGrid rate limit hit
            AuthenticationError: If API key invalid
            EmailServiceError: On other errors
        """
        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )

        if plain_content:
            message.plain_text_content = plain_content

        try:
            response = self.client.send(message)

            # 202 = Accepted (queued for sending)
            if response.status_code == 202:
                logger.info(f"Email sent to {to_email}, subject: {subject[:50]}")
                return True

            # Other success codes
            if 200 <= response.status_code < 300:
                logger.info(f"Email sent to {to_email}, status: {response.status_code}")
                return True

            logger.warning(
                f"Unexpected status code from SendGrid: {response.status_code}"
            )
            return False

        except Exception as e:
            error_str = str(e)

            # Handle rate limiting
            if "429" in error_str or "rate limit" in error_str.lower():
                logger.warning(f"SendGrid rate limit exceeded: {e}")
                raise RateLimitExceededError(
                    "SendGrid rate limit exceeded", retry_after=60
                ) from e

            # Handle authentication errors
            if "401" in error_str or "403" in error_str:
                logger.error(f"SendGrid authentication error: {e}")
                raise AuthenticationError("Invalid SendGrid API key") from e

            # Other errors
            logger.error(f"SendGrid error: {e}")
            raise EmailServiceError(f"Failed to send email: {e}") from e

    def send_magic_link(
        self,
        to_email: str,
        magic_link: str,
        expires_in_minutes: int = 60,
    ) -> bool:
        """Send magic link authentication email.

        Args:
            to_email: Recipient email address
            magic_link: The magic link URL
            expires_in_minutes: Link expiration time

        Returns:
            True if email was sent successfully
        """
        subject = "Your sign-in link for Sentiment Analyzer"
        html_content = self._build_magic_link_html(magic_link, expires_in_minutes)
        plain_content = f"Sign in to Sentiment Analyzer: {magic_link}\nThis link expires in {expires_in_minutes} minutes."

        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            plain_content=plain_content,
        )

    def send_alert(
        self,
        to_email: str,
        ticker: str,
        alert_type: str,
        triggered_value: float,
        threshold: float,
        dashboard_url: str,
    ) -> bool:
        """Send alert notification email.

        Args:
            to_email: Recipient email address
            ticker: Stock symbol
            alert_type: Type of alert (sentiment/volatility)
            triggered_value: Value that triggered alert
            threshold: Threshold that was crossed
            dashboard_url: URL to dashboard

        Returns:
            True if email was sent successfully
        """
        subject = f"Alert: {ticker} {alert_type} threshold crossed"
        html_content = self._build_alert_html(
            ticker, alert_type, triggered_value, threshold, dashboard_url
        )

        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
        )

    def _build_magic_link_html(self, magic_link: str, expires_in_minutes: int) -> str:
        """Build HTML for magic link email."""
        return f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #1e40af;">Sign in to Sentiment Analyzer</h2>
            <p>Click the button below to sign in to your account:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{magic_link}"
                   style="background-color: #22c55e; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    Sign In
                </a>
            </p>
            <p style="color: #f59e0b; font-size: 14px;">
                This link will expire in {expires_in_minutes} minutes.
            </p>
            <p style="color: #666; font-size: 12px;">
                If you didn't request this link, you can safely ignore this email.
            </p>
        </body>
        </html>
        """

    def _build_alert_html(
        self,
        ticker: str,
        alert_type: str,
        triggered_value: float,
        threshold: float,
        dashboard_url: str,
    ) -> str:
        """Build HTML for alert notification email."""
        direction = "exceeded" if triggered_value > threshold else "dropped below"
        color = "#22c55e" if triggered_value > threshold else "#ef4444"

        return f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #1e40af;">Alert: {ticker}</h2>
            <p>Your {alert_type} alert for <strong>{ticker}</strong> has been triggered.</p>
            <p>The {alert_type} value has {direction} your threshold of <strong>{threshold:.2f}</strong>.</p>
            <p style="font-size: 24px; font-weight: bold; color: {color};">
                Current value: {triggered_value:.2f}
            </p>
            <p style="margin-top: 20px;">
                <a href="{dashboard_url}/dashboard?ticker={ticker}"
                   style="background-color: #1e40af; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    View Dashboard
                </a>
            </p>
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                <a href="{dashboard_url}/settings/alerts">Manage your alerts</a>
            </p>
        </body>
        </html>
        """


@lru_cache(maxsize=1)
def _get_sendgrid_api_key(secret_arn: str) -> str:
    """Get SendGrid API key from Secrets Manager.

    Uses LRU cache to avoid repeated API calls.

    Args:
        secret_arn: ARN of the secret

    Returns:
        SendGrid API key string

    Raises:
        EmailServiceError: If secret cannot be retrieved
    """
    if not secret_arn:
        raise EmailServiceError("SendGrid secret ARN not configured")

    try:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_arn)
        secret = response.get("SecretString", "{}")

        # Parse as JSON if it's a JSON object
        try:
            data = json.loads(secret)
            # Support both formats: {"api_key": "..."} or raw string
            return data.get("api_key", data.get("SENDGRID_API_KEY", secret))
        except json.JSONDecodeError:
            # Raw API key string
            return secret

    except Exception as e:
        logger.error(f"Failed to get SendGrid API key: {e}")
        raise EmailServiceError(f"Failed to retrieve SendGrid API key: {e}") from e


def clear_api_key_cache() -> None:
    """Clear the API key cache (for testing)."""
    _get_sendgrid_api_key.cache_clear()

"""Unit tests for SendGrid email service."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.notification.sendgrid_service import (
    AuthenticationError,
    EmailService,
    EmailServiceError,
    RateLimitExceededError,
    _get_sendgrid_api_key,
    clear_api_key_cache,
)


class TestEmailServiceInit:
    """Test EmailService initialization."""

    def test_init_with_secret_arn(self):
        """Test initialization with secret ARN."""
        service = EmailService(
            secret_arn="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
            from_email="test@example.com",
        )
        assert (
            service.secret_arn
            == "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
        )
        assert service.from_email == "test@example.com"
        assert service._api_key is None

    def test_init_with_api_key_override(self):
        """Test initialization with API key override for testing."""
        service = EmailService(
            secret_arn="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
            from_email="test@example.com",
            api_key="SG.test_key",
        )
        assert service._api_key == "SG.test_key"
        assert service.api_key == "SG.test_key"


class TestEmailServiceApiKey:
    """Test API key retrieval."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_api_key_cache()

    def test_api_key_from_override(self):
        """Test API key from override."""
        service = EmailService(
            secret_arn="arn:test",
            from_email="test@example.com",
            api_key="SG.override_key",
        )
        assert service.api_key == "SG.override_key"

    @patch("src.lambdas.notification.sendgrid_service.boto3")
    def test_api_key_from_secrets_manager_json(self, mock_boto3):
        """Test API key retrieval from Secrets Manager (JSON format)."""
        clear_api_key_cache()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "SG.secret_key"})
        }

        service = EmailService(
            secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:test",
            from_email="test@example.com",
        )
        assert service.api_key == "SG.secret_key"

    @patch("src.lambdas.notification.sendgrid_service.boto3")
    def test_api_key_from_secrets_manager_raw_string(self, mock_boto3):
        """Test API key retrieval from Secrets Manager (raw string format)."""
        clear_api_key_cache()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": "SG.raw_string_key"
        }

        service = EmailService(
            secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:test2",
            from_email="test@example.com",
        )
        assert service.api_key == "SG.raw_string_key"

    @patch("src.lambdas.notification.sendgrid_service.boto3")
    def test_api_key_from_secrets_manager_sendgrid_key_format(self, mock_boto3):
        """Test API key with SENDGRID_API_KEY JSON field."""
        clear_api_key_cache()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"SENDGRID_API_KEY": "SG.alternate_key"})
        }

        service = EmailService(
            secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:test3",
            from_email="test@example.com",
        )
        assert service.api_key == "SG.alternate_key"


class TestEmailServiceSendEmail:
    """Test email sending functionality."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_api_key_cache()

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_email_success(self, mock_sendgrid):
        """Test successful email send."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )
        result = service.send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            html_content="<p>Test body</p>",
        )

        assert result is True
        mock_client.send.assert_called_once()

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_email_with_plain_content(self, mock_sendgrid):
        """Test email send with plain text content."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )
        result = service.send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            html_content="<p>Test body</p>",
            plain_content="Test body plain",
        )

        assert result is True

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_email_200_success(self, mock_sendgrid):
        """Test email send with 200 status code."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.send.return_value = mock_response

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )
        result = service.send_email(
            to_email="recipient@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        assert result is True

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_email_unexpected_status(self, mock_sendgrid):
        """Test email send with unexpected status code."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_client.send.return_value = mock_response

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )
        result = service.send_email(
            to_email="recipient@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        assert result is False

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_email_rate_limit_429(self, mock_sendgrid):
        """Test rate limit error handling (429)."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_client.send.side_effect = Exception("HTTP Error 429: Too Many Requests")

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )

        with pytest.raises(RateLimitExceededError) as exc_info:
            service.send_email(
                to_email="recipient@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

        assert exc_info.value.retry_after == 60

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_email_rate_limit_text(self, mock_sendgrid):
        """Test rate limit error handling (text match)."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_client.send.side_effect = Exception("Rate limit exceeded")

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )

        with pytest.raises(RateLimitExceededError):
            service.send_email(
                to_email="recipient@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_email_auth_error_401(self, mock_sendgrid):
        """Test authentication error handling (401)."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_client.send.side_effect = Exception("HTTP Error 401: Unauthorized")

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )

        with pytest.raises(AuthenticationError):
            service.send_email(
                to_email="recipient@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_email_auth_error_403(self, mock_sendgrid):
        """Test authentication error handling (403)."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_client.send.side_effect = Exception("HTTP Error 403: Forbidden")

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )

        with pytest.raises(AuthenticationError):
            service.send_email(
                to_email="recipient@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_email_generic_error(self, mock_sendgrid):
        """Test generic error handling."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_client.send.side_effect = Exception("Network error")

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )

        with pytest.raises(EmailServiceError) as exc_info:
            service.send_email(
                to_email="recipient@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

        assert "Network error" in str(exc_info.value)


class TestEmailServiceMagicLink:
    """Test magic link email functionality."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_api_key_cache()

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_magic_link_success(self, mock_sendgrid):
        """Test successful magic link email."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )
        result = service.send_magic_link(
            to_email="user@example.com",
            magic_link="https://app.example.com/auth/verify?token=abc123",
            expires_in_minutes=30,
        )

        assert result is True
        mock_client.send.assert_called_once()


class TestEmailServiceAlert:
    """Test alert email functionality."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_api_key_cache()

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_alert_success(self, mock_sendgrid):
        """Test successful alert email."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )
        result = service.send_alert(
            to_email="user@example.com",
            ticker="AAPL",
            alert_type="sentiment",
            triggered_value=0.85,
            threshold=0.75,
            dashboard_url="https://dashboard.example.com",
        )

        assert result is True
        mock_client.send.assert_called_once()

    @patch("src.lambdas.notification.sendgrid_service.SendGridAPIClient")
    def test_send_alert_below_threshold(self, mock_sendgrid):
        """Test alert email when value drops below threshold."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response

        service = EmailService(
            secret_arn="arn:test",
            from_email="sender@example.com",
            api_key="SG.test_key",
        )
        result = service.send_alert(
            to_email="user@example.com",
            ticker="TSLA",
            alert_type="volatility",
            triggered_value=0.20,
            threshold=0.30,
            dashboard_url="https://dashboard.example.com",
        )

        assert result is True


class TestGetSendgridApiKey:
    """Test the cached API key retrieval function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_api_key_cache()

    def test_empty_secret_arn_raises_error(self):
        """Test that empty secret ARN raises error."""
        clear_api_key_cache()
        with pytest.raises(EmailServiceError) as exc_info:
            _get_sendgrid_api_key("")

        assert "not configured" in str(exc_info.value)

    @patch("src.lambdas.notification.sendgrid_service.boto3")
    def test_secrets_manager_error(self, mock_boto3):
        """Test handling of Secrets Manager errors."""
        clear_api_key_cache()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_secret_value.side_effect = Exception("Access denied")

        with pytest.raises(EmailServiceError) as exc_info:
            _get_sendgrid_api_key(
                "arn:aws:secretsmanager:us-east-1:123:secret:test-error"
            )

        assert "Failed to retrieve" in str(exc_info.value)


class TestClearApiKeyCache:
    """Test cache clearing functionality."""

    def test_clear_cache(self):
        """Test that cache clearing works."""
        clear_api_key_cache()
        # Should not raise an error
        assert True

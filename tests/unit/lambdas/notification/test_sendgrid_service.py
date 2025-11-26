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


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear API key cache before each test."""
    clear_api_key_cache()
    yield
    clear_api_key_cache()


@pytest.fixture
def email_service():
    """Create email service with test API key."""
    return EmailService(
        secret_arn="test-secret-arn",
        from_email="test@example.com",
        api_key="test-api-key",
    )


class TestEmailServiceInit:
    """Tests for EmailService initialization."""

    def test_init_with_api_key(self):
        """Test init with direct API key."""
        service = EmailService(
            secret_arn="arn:test",
            from_email="test@example.com",
            api_key="direct-key",
        )
        assert service._api_key == "direct-key"
        assert service.api_key == "direct-key"

    def test_init_without_api_key(self):
        """Test init without direct API key loads from secrets."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "secret-key"}

        with patch("boto3.client", return_value=mock_client):
            service = EmailService(
                secret_arn="arn:test",
                from_email="test@example.com",
            )
            assert service.api_key == "secret-key"


class TestEmailServiceSendEmail:
    """Tests for EmailService.send_email method."""

    def test_send_email_success(self, email_service: EmailService):
        """Test successful email sending."""
        mock_response = MagicMock()
        mock_response.status_code = 202

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response

        with patch.object(email_service, "_client", mock_client):
            result = email_service.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                html_content="<p>Test content</p>",
            )

        assert result is True
        mock_client.send.assert_called_once()

    def test_send_email_with_plain_content(self, email_service: EmailService):
        """Test sending email with plain text fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 202

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response

        with patch.object(email_service, "_client", mock_client):
            result = email_service.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                html_content="<p>Test</p>",
                plain_content="Test plain text",
            )

        assert result is True

    def test_send_email_200_status(self, email_service: EmailService):
        """Test email with 200 status code."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response

        with patch.object(email_service, "_client", mock_client):
            result = email_service.send_email(
                to_email="recipient@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

        assert result is True

    def test_send_email_unexpected_status(self, email_service: EmailService):
        """Test email with unexpected status code."""
        mock_response = MagicMock()
        mock_response.status_code = 400

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response

        with patch.object(email_service, "_client", mock_client):
            result = email_service.send_email(
                to_email="recipient@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

        assert result is False

    def test_send_email_rate_limit_429(self, email_service: EmailService):
        """Test rate limit error handling for 429."""
        mock_client = MagicMock()
        mock_client.send.side_effect = Exception("429 Too Many Requests")

        with patch.object(email_service, "_client", mock_client):
            with pytest.raises(RateLimitExceededError) as exc_info:
                email_service.send_email(
                    to_email="recipient@example.com",
                    subject="Test",
                    html_content="<p>Test</p>",
                )

        assert exc_info.value.retry_after == 60

    def test_send_email_rate_limit_message(self, email_service: EmailService):
        """Test rate limit error handling for rate limit message."""
        mock_client = MagicMock()
        mock_client.send.side_effect = Exception("Rate limit exceeded")

        with patch.object(email_service, "_client", mock_client):
            with pytest.raises(RateLimitExceededError):
                email_service.send_email(
                    to_email="recipient@example.com",
                    subject="Test",
                    html_content="<p>Test</p>",
                )

    def test_send_email_auth_error_401(self, email_service: EmailService):
        """Test authentication error handling for 401."""
        mock_client = MagicMock()
        mock_client.send.side_effect = Exception("401 Unauthorized")

        with patch.object(email_service, "_client", mock_client):
            with pytest.raises(AuthenticationError):
                email_service.send_email(
                    to_email="recipient@example.com",
                    subject="Test",
                    html_content="<p>Test</p>",
                )

    def test_send_email_auth_error_403(self, email_service: EmailService):
        """Test authentication error handling for 403."""
        mock_client = MagicMock()
        mock_client.send.side_effect = Exception("403 Forbidden")

        with patch.object(email_service, "_client", mock_client):
            with pytest.raises(AuthenticationError):
                email_service.send_email(
                    to_email="recipient@example.com",
                    subject="Test",
                    html_content="<p>Test</p>",
                )

    def test_send_email_generic_error(self, email_service: EmailService):
        """Test generic error handling."""
        mock_client = MagicMock()
        mock_client.send.side_effect = Exception("Network error")

        with patch.object(email_service, "_client", mock_client):
            with pytest.raises(EmailServiceError):
                email_service.send_email(
                    to_email="recipient@example.com",
                    subject="Test",
                    html_content="<p>Test</p>",
                )


class TestEmailServiceSendMagicLink:
    """Tests for EmailService.send_magic_link method."""

    def test_send_magic_link_success(self, email_service: EmailService):
        """Test successful magic link email."""
        mock_response = MagicMock()
        mock_response.status_code = 202

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response

        with patch.object(email_service, "_client", mock_client):
            result = email_service.send_magic_link(
                to_email="user@example.com",
                magic_link="https://example.com/auth?token=abc123",
                expires_in_minutes=30,
            )

        assert result is True
        # Verify the email was sent with correct subject
        call_args = mock_client.send.call_args
        message = call_args[0][0]
        assert "sign-in link" in message.subject.subject.lower()

    def test_send_magic_link_default_expiry(self, email_service: EmailService):
        """Test magic link with default expiry."""
        mock_response = MagicMock()
        mock_response.status_code = 202

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response

        with patch.object(email_service, "_client", mock_client):
            result = email_service.send_magic_link(
                to_email="user@example.com",
                magic_link="https://example.com/auth?token=abc123",
            )

        assert result is True


class TestEmailServiceSendAlert:
    """Tests for EmailService.send_alert method."""

    def test_send_alert_threshold_exceeded(self, email_service: EmailService):
        """Test alert email when threshold exceeded."""
        mock_response = MagicMock()
        mock_response.status_code = 202

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response

        with patch.object(email_service, "_client", mock_client):
            result = email_service.send_alert(
                to_email="user@example.com",
                ticker="AAPL",
                alert_type="sentiment",
                triggered_value=0.8,
                threshold=0.5,
                dashboard_url="https://dashboard.example.com",
            )

        assert result is True
        call_args = mock_client.send.call_args
        message = call_args[0][0]
        assert "AAPL" in message.subject.subject

    def test_send_alert_threshold_dropped(self, email_service: EmailService):
        """Test alert email when value dropped below threshold."""
        mock_response = MagicMock()
        mock_response.status_code = 202

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response

        with patch.object(email_service, "_client", mock_client):
            result = email_service.send_alert(
                to_email="user@example.com",
                ticker="AAPL",
                alert_type="volatility",
                triggered_value=0.2,
                threshold=0.5,
                dashboard_url="https://dashboard.example.com",
            )

        assert result is True


class TestGetSendGridApiKey:
    """Tests for _get_sendgrid_api_key function."""

    def test_get_api_key_json_format(self):
        """Test getting API key from JSON secret."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "json-api-key"})
        }

        with patch("boto3.client", return_value=mock_client):
            key = _get_sendgrid_api_key("arn:test")

        assert key == "json-api-key"

    def test_get_api_key_sendgrid_format(self):
        """Test getting API key with SENDGRID_API_KEY format."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"SENDGRID_API_KEY": "sendgrid-key"})
        }

        with patch("boto3.client", return_value=mock_client):
            key = _get_sendgrid_api_key("arn:test2")

        assert key == "sendgrid-key"

    def test_get_api_key_raw_string(self):
        """Test getting API key from raw string secret."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "raw-api-key"}

        with patch("boto3.client", return_value=mock_client):
            key = _get_sendgrid_api_key("arn:test3")

        assert key == "raw-api-key"

    def test_get_api_key_empty_arn(self):
        """Test error when ARN is empty."""
        with pytest.raises(EmailServiceError, match="not configured"):
            _get_sendgrid_api_key("")

    def test_get_api_key_secrets_manager_error(self):
        """Test error handling for Secrets Manager failure."""
        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = Exception("Access denied")

        with patch("boto3.client", return_value=mock_client):
            with pytest.raises(EmailServiceError, match="Failed to retrieve"):
                _get_sendgrid_api_key("arn:test4")

    def test_get_api_key_caching(self):
        """Test that API key is cached."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "cached-key"}

        with patch("boto3.client", return_value=mock_client):
            key1 = _get_sendgrid_api_key("arn:cached")
            key2 = _get_sendgrid_api_key("arn:cached")

        # Should only call Secrets Manager once due to caching
        assert mock_client.get_secret_value.call_count == 1
        assert key1 == key2 == "cached-key"


class TestEmailServiceClientProperty:
    """Tests for EmailService.client property."""

    def test_client_created_lazily(self, email_service: EmailService):
        """Test that client is created lazily."""
        assert email_service._client is None
        client = email_service.client
        assert client is not None
        assert email_service._client is not None

    def test_client_reused(self, email_service: EmailService):
        """Test that client is reused."""
        client1 = email_service.client
        client2 = email_service.client
        assert client1 is client2


class TestEmailServiceHtmlBuilders:
    """Tests for HTML email builders."""

    def test_magic_link_html_contains_link(self, email_service: EmailService):
        """Test magic link HTML contains the link."""
        html = email_service._build_magic_link_html(
            magic_link="https://example.com/auth?token=test",
            expires_in_minutes=30,
        )
        assert "https://example.com/auth?token=test" in html
        assert "30 minutes" in html

    def test_alert_html_contains_ticker(self, email_service: EmailService):
        """Test alert HTML contains ticker."""
        html = email_service._build_alert_html(
            ticker="AAPL",
            alert_type="sentiment",
            triggered_value=0.75,
            threshold=0.5,
            dashboard_url="https://dashboard.example.com",
        )
        assert "AAPL" in html
        assert "sentiment" in html
        assert "0.75" in html
        assert "0.50" in html

    def test_alert_html_exceeded_color(self, email_service: EmailService):
        """Test alert HTML uses green for exceeded threshold."""
        html = email_service._build_alert_html(
            ticker="AAPL",
            alert_type="sentiment",
            triggered_value=0.8,
            threshold=0.5,
            dashboard_url="https://example.com",
        )
        assert "#22c55e" in html  # Green color
        assert "exceeded" in html

    def test_alert_html_dropped_color(self, email_service: EmailService):
        """Test alert HTML uses red for dropped below threshold."""
        html = email_service._build_alert_html(
            ticker="AAPL",
            alert_type="volatility",
            triggered_value=0.2,
            threshold=0.5,
            dashboard_url="https://example.com",
        )
        assert "#ef4444" in html  # Red color
        assert "dropped below" in html


class TestTemplateLoading:
    """Tests for email template loading (T102)."""

    def test_magic_link_uses_template_file(self, email_service: EmailService):
        """Test magic link uses the template file when available."""
        html = email_service._build_magic_link_html(
            magic_link="https://example.com/auth?token=test123",
            expires_in_minutes=60,
            dashboard_url="https://dashboard.example.com",
        )

        # Template file includes these specific elements
        assert "Sign in to your account" in html
        assert "https://example.com/auth?token=test123" in html
        assert "60 minutes" in html
        assert "Sign In Securely" in html  # Button text from template

    def test_magic_link_template_substitution(self, email_service: EmailService):
        """Test all template variables are substituted."""
        html = email_service._build_magic_link_html(
            magic_link="https://app.test.com/magic?t=abc",
            expires_in_minutes=30,
            dashboard_url="https://app.test.com",
        )

        # No unsubstituted template variables
        assert "{{magic_link}}" not in html
        assert "{{expires_in_minutes}}" not in html
        assert "{{dashboard_url}}" not in html

        # Values are properly substituted
        assert "https://app.test.com/magic?t=abc" in html
        assert "30" in html
        assert "https://app.test.com" in html

    def test_magic_link_template_fallback(self, email_service: EmailService):
        """Test fallback HTML when template not found."""
        # Patch _load_template to return None (template not found)
        with patch(
            "src.lambdas.notification.sendgrid_service._load_template",
            return_value=None,
        ):
            html = email_service._build_magic_link_html(
                magic_link="https://example.com/auth?token=test",
                expires_in_minutes=60,
            )

            # Should use fallback inline HTML
            assert "https://example.com/auth?token=test" in html
            assert "60 minutes" in html
            # Fallback has simpler styling
            assert "Sign in to Sentiment Analyzer" in html

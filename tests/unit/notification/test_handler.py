"""Unit tests for Notification Lambda handler."""

import json
from unittest.mock import MagicMock, patch

from src.lambdas.notification.handler import (
    _build_alert_email,
    _build_magic_link_email,
    _get_notification_type,
    _response,
    lambda_handler,
)
from src.lambdas.notification.sendgrid_service import (
    EmailServiceError,
    RateLimitExceededError,
)


class TestGetNotificationType:
    """Test notification type detection."""

    def test_direct_invocation_type(self):
        """Test direct invocation with notification_type."""
        event = {"notification_type": "alert"}
        assert _get_notification_type(event) == "alert"

    def test_sns_message_type(self):
        """Test SNS message notification type."""
        event = {
            "Records": [
                {
                    "EventSource": "aws:sns",
                    "Sns": {"Message": json.dumps({"notification_type": "alert"})},
                }
            ]
        }
        assert _get_notification_type(event) == "alert"

    def test_sns_message_default_to_alert(self):
        """Test SNS message defaults to alert type."""
        event = {
            "Records": [
                {
                    "EventSource": "aws:sns",
                    "Sns": {"Message": json.dumps({"data": "some data"})},
                }
            ]
        }
        assert _get_notification_type(event) == "alert"

    def test_eventbridge_scheduled_event(self):
        """Test EventBridge scheduled event detection."""
        event = {"detail-type": "Scheduled Event", "source": "aws.events"}
        assert _get_notification_type(event) == "digest"

    def test_unknown_type(self):
        """Test unknown event type."""
        event = {"some": "data"}
        assert _get_notification_type(event) == "unknown"


class TestResponse:
    """Test response building."""

    def test_response_200(self):
        """Test 200 response."""
        result = _response(200, {"message": "OK"})
        assert result["statusCode"] == 200
        assert json.loads(result["body"]) == {"message": "OK"}
        assert result["headers"]["Content-Type"] == "application/json"

    def test_response_400(self):
        """Test 400 response."""
        result = _response(400, {"error": "Bad request"})
        assert result["statusCode"] == 400
        assert json.loads(result["body"]) == {"error": "Bad request"}

    def test_response_500(self):
        """Test 500 response."""
        result = _response(500, {"error": "Internal error"})
        assert result["statusCode"] == 500


class TestBuildAlertEmail:
    """Test alert email HTML building."""

    def test_build_alert_email_above_threshold(self):
        """Test alert email when value exceeds threshold."""
        html = _build_alert_email(
            ticker="AAPL",
            alert_type="sentiment",
            triggered_value=0.85,
            threshold=0.75,
        )

        assert "AAPL" in html
        assert "sentiment" in html
        assert "exceeded" in html
        assert "0.85" in html
        assert "0.75" in html
        assert "#22c55e" in html  # Green color for exceeded

    def test_build_alert_email_below_threshold(self):
        """Test alert email when value drops below threshold."""
        html = _build_alert_email(
            ticker="TSLA",
            alert_type="volatility",
            triggered_value=0.20,
            threshold=0.30,
        )

        assert "TSLA" in html
        assert "volatility" in html
        assert "dropped below" in html
        assert "0.20" in html
        assert "0.30" in html
        assert "#ef4444" in html  # Red color for dropped


class TestBuildMagicLinkEmail:
    """Test magic link email HTML building."""

    def test_build_magic_link_email(self):
        """Test magic link email HTML."""
        html = _build_magic_link_email(
            magic_link="https://app.example.com/auth/verify?token=abc123",
            expires_in_minutes=60,
        )

        assert "https://app.example.com/auth/verify?token=abc123" in html
        assert "60 minutes" in html
        assert "Sign In" in html


class TestLambdaHandlerAlert:
    """Test Lambda handler alert notifications."""

    @patch("src.lambdas.notification.handler._get_email_service")
    def test_handle_alert_success(self, mock_get_service):
        """Test successful alert handling."""
        mock_service = MagicMock()
        mock_service.send_email.return_value = True
        mock_get_service.return_value = mock_service

        event = {
            "notification_type": "alert",
            "alert": {
                "email": "user@example.com",
                "ticker": "AAPL",
                "alert_type": "sentiment",
                "triggered_value": 0.85,
                "threshold": 0.75,
            },
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        mock_service.send_email.assert_called_once()

    @patch("src.lambdas.notification.handler._get_email_service")
    def test_handle_alert_from_sns(self, mock_get_service):
        """Test alert from SNS message."""
        mock_service = MagicMock()
        mock_service.send_email.return_value = True
        mock_get_service.return_value = mock_service

        event = {
            "Records": [
                {
                    "EventSource": "aws:sns",
                    "Sns": {
                        "Message": json.dumps(
                            {
                                "notification_type": "alert",
                                "alert": {
                                    "email": "user@example.com",
                                    "ticker": "MSFT",
                                    "alert_type": "volatility",
                                    "triggered_value": 2.5,
                                    "threshold": 2.0,
                                },
                            }
                        )
                    },
                }
            ]
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200

    @patch("src.lambdas.notification.handler._get_email_service")
    def test_handle_alert_missing_fields(self, mock_get_service):
        """Test alert with missing required fields."""
        event = {
            "notification_type": "alert",
            "alert": {
                "email": "user@example.com",
                # Missing ticker, alert_type, triggered_value, threshold
            },
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 400
        assert "Missing required" in json.loads(result["body"])["error"]

    @patch("src.lambdas.notification.handler._get_email_service")
    def test_handle_alert_email_failure(self, mock_get_service):
        """Test alert when email send fails."""
        mock_service = MagicMock()
        mock_service.send_email.return_value = False
        mock_get_service.return_value = mock_service

        event = {
            "notification_type": "alert",
            "alert": {
                "email": "user@example.com",
                "ticker": "AAPL",
                "alert_type": "sentiment",
                "triggered_value": 0.85,
                "threshold": 0.75,
            },
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 500


class TestLambdaHandlerMagicLink:
    """Test Lambda handler magic link notifications."""

    @patch("src.lambdas.notification.handler._get_email_service")
    def test_handle_magic_link_success(self, mock_get_service):
        """Test successful magic link handling."""
        mock_service = MagicMock()
        mock_service.send_email.return_value = True
        mock_get_service.return_value = mock_service

        event = {
            "notification_type": "magic_link",
            "email": "user@example.com",
            "token": "abc123def456",
            "expires_in_minutes": 30,
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        mock_service.send_email.assert_called_once()

    @patch("src.lambdas.notification.handler._get_email_service")
    def test_handle_magic_link_missing_email(self, mock_get_service):
        """Test magic link with missing email."""
        event = {
            "notification_type": "magic_link",
            "token": "abc123",
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 400
        assert "Missing email or token" in json.loads(result["body"])["error"]

    @patch("src.lambdas.notification.handler._get_email_service")
    def test_handle_magic_link_missing_token(self, mock_get_service):
        """Test magic link with missing token."""
        event = {
            "notification_type": "magic_link",
            "email": "user@example.com",
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 400


class TestLambdaHandlerDigest:
    """Test Lambda handler daily digest notifications."""

    @patch("src.lambdas.notification.handler.process_daily_digests")
    @patch("src.lambdas.notification.handler._get_email_service")
    @patch("boto3.resource")
    def test_handle_digest_processes_successfully(
        self, mock_boto3_resource, mock_get_service, mock_process_digests
    ):
        """Test digest handler processes digests and returns stats."""
        mock_process_digests.return_value = {
            "processed": 5,
            "sent": 3,
            "skipped": 1,
            "failed": 1,
        }
        mock_table = MagicMock()
        mock_boto3_resource.return_value.Table.return_value = mock_table
        mock_email_service = MagicMock()
        mock_get_service.return_value = mock_email_service

        event = {"detail-type": "Scheduled Event", "source": "aws.events"}

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Digest processing complete"
        assert body["stats"]["processed"] == 5
        assert body["stats"]["sent"] == 3
        mock_process_digests.assert_called_once()


class TestLambdaHandlerErrors:
    """Test Lambda handler error handling."""

    def test_handle_unknown_type(self):
        """Test unknown notification type."""
        event = {"some": "random", "data": "here"}

        result = lambda_handler(event, None)

        assert result["statusCode"] == 400
        assert "Unknown notification type" in json.loads(result["body"])["error"]

    @patch("src.lambdas.notification.handler._get_email_service")
    def test_handle_rate_limit_error(self, mock_get_service):
        """Test rate limit error handling."""
        mock_service = MagicMock()
        mock_service.send_email.side_effect = RateLimitExceededError(
            "Rate limit exceeded", retry_after=120
        )
        mock_get_service.return_value = mock_service

        event = {
            "notification_type": "alert",
            "alert": {
                "email": "user@example.com",
                "ticker": "AAPL",
                "alert_type": "sentiment",
                "triggered_value": 0.85,
                "threshold": 0.75,
            },
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 429
        body = json.loads(result["body"])
        assert body["retry_after"] == 120

    @patch("src.lambdas.notification.handler._get_email_service")
    def test_handle_email_service_error(self, mock_get_service):
        """Test email service error handling."""
        mock_service = MagicMock()
        mock_service.send_email.side_effect = EmailServiceError("Email failed")
        mock_get_service.return_value = mock_service

        event = {
            "notification_type": "alert",
            "alert": {
                "email": "user@example.com",
                "ticker": "AAPL",
                "alert_type": "sentiment",
                "triggered_value": 0.85,
                "threshold": 0.75,
            },
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 500

    @patch("src.lambdas.notification.handler._get_email_service")
    def test_handle_unexpected_error(self, mock_get_service):
        """Test unexpected error handling."""
        mock_service = MagicMock()
        mock_service.send_email.side_effect = RuntimeError("Unexpected error")
        mock_get_service.return_value = mock_service

        event = {
            "notification_type": "alert",
            "alert": {
                "email": "user@example.com",
                "ticker": "AAPL",
                "alert_type": "sentiment",
                "triggered_value": 0.85,
                "threshold": 0.75,
            },
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 500
        assert "Internal server error" in json.loads(result["body"])["error"]

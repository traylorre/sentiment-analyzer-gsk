"""Unit tests for hCaptcha middleware (T163)."""

from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.shared.middleware.hcaptcha import (
    CaptchaRequired,
    CaptchaVerificationResult,
    record_action_for_rate_limit,
    should_require_captcha,
    verify_captcha,
)


class TestVerifyCaptcha:
    """Tests for verify_captcha function."""

    def test_missing_token_returns_failure(self):
        """Returns failure for missing token."""
        result = verify_captcha("")

        assert result.success is False
        assert "missing-input-response" in result.error_codes

    def test_missing_token_none_returns_failure(self):
        """Returns failure for None token."""
        result = verify_captcha(None)

        assert result.success is False
        assert "missing-input-response" in result.error_codes

    @patch("src.lambdas.shared.middleware.hcaptcha._get_hcaptcha_secret")
    @patch("src.lambdas.shared.middleware.hcaptcha.ENVIRONMENT", "dev")
    def test_dev_mode_allows_without_secret(self, mock_get_secret):
        """Allows in dev mode without secret configured."""
        mock_get_secret.return_value = None

        result = verify_captcha("test-token")

        assert result.success is True

    @patch("src.lambdas.shared.middleware.hcaptcha._get_hcaptcha_secret")
    @patch("src.lambdas.shared.middleware.hcaptcha.ENVIRONMENT", "prod")
    def test_prod_mode_fails_without_secret(self, mock_get_secret):
        """Fails in prod mode without secret configured."""
        mock_get_secret.return_value = None

        result = verify_captcha("test-token")

        assert result.success is False
        assert "missing-input-secret" in result.error_codes

    @patch("src.lambdas.shared.middleware.hcaptcha.httpx.Client")
    @patch("src.lambdas.shared.middleware.hcaptcha._get_hcaptcha_secret")
    def test_successful_verification(self, mock_get_secret, mock_client_class):
        """Returns success for valid token."""
        mock_get_secret.return_value = "test-secret"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "challenge_ts": "2025-11-26T12:00:00Z",
            "hostname": "example.com",
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = verify_captcha("valid-token", remote_ip="1.2.3.4")

        assert result.success is True
        assert result.hostname == "example.com"
        mock_client.post.assert_called_once()

    @patch("src.lambdas.shared.middleware.hcaptcha.httpx.Client")
    @patch("src.lambdas.shared.middleware.hcaptcha._get_hcaptcha_secret")
    def test_failed_verification(self, mock_get_secret, mock_client_class):
        """Returns failure for invalid token."""
        mock_get_secret.return_value = "test-secret"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["invalid-input-response"],
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = verify_captcha("invalid-token")

        assert result.success is False
        assert "invalid-input-response" in result.error_codes

    @patch("src.lambdas.shared.middleware.hcaptcha.httpx.Client")
    @patch("src.lambdas.shared.middleware.hcaptcha._get_hcaptcha_secret")
    def test_http_error_returns_failure(self, mock_get_secret, mock_client_class):
        """Returns failure on HTTP error."""
        import httpx

        mock_get_secret.return_value = "test-secret"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.HTTPError("Connection failed")
        mock_client_class.return_value = mock_client

        result = verify_captcha("test-token")

        assert result.success is False
        assert "http-error" in result.error_codes

    def test_with_explicit_secret_key(self):
        """Uses explicit secret key when provided."""
        with patch("src.lambdas.shared.middleware.hcaptcha.httpx.Client") as mock_class:
            mock_response = MagicMock()
            mock_response.json.return_value = {"success": True}

            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_class.return_value = mock_client

            result = verify_captcha("token", secret_key="explicit-secret")

            assert result.success is True
            # Verify the explicit secret was used
            call_data = mock_client.post.call_args[1]["data"]
            assert call_data["secret"] == "explicit-secret"


class TestShouldRequireCaptcha:
    """Tests for should_require_captcha function."""

    @pytest.fixture
    def mock_table(self):
        """Create mock DynamoDB table."""
        return MagicMock()

    def test_below_threshold_no_captcha(self, mock_table):
        """No captcha required below threshold."""
        mock_table.query.return_value = {"Items": [{"id": "1"}, {"id": "2"}]}

        result = should_require_captcha(
            mock_table, "1.2.3.4", threshold=3, window_hours=1
        )

        assert result is False

    def test_at_threshold_requires_captcha(self, mock_table):
        """Captcha required at threshold."""
        mock_table.query.return_value = {
            "Items": [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        }

        result = should_require_captcha(
            mock_table, "1.2.3.4", threshold=3, window_hours=1
        )

        assert result is True

    def test_above_threshold_requires_captcha(self, mock_table):
        """Captcha required above threshold."""
        mock_table.query.return_value = {
            "Items": [{"id": "1"}, {"id": "2"}, {"id": "3"}, {"id": "4"}, {"id": "5"}]
        }

        result = should_require_captcha(
            mock_table, "1.2.3.4", threshold=3, window_hours=1
        )

        assert result is True

    def test_error_returns_false(self, mock_table):
        """Returns False on error (fail open)."""
        mock_table.query.side_effect = Exception("DB error")

        result = should_require_captcha(mock_table, "1.2.3.4")

        assert result is False


class TestRecordActionForRateLimit:
    """Tests for record_action_for_rate_limit function."""

    @pytest.fixture
    def mock_table(self):
        """Create mock DynamoDB table."""
        return MagicMock()

    def test_records_action(self, mock_table):
        """Records action successfully."""
        record_action_for_rate_limit(mock_table, "1.2.3.4", "config_create")

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "RATE#1.2.3.4"
        assert item["action"] == "config_create"
        assert item["entity_type"] == "RATE_LIMIT_RECORD"
        assert "ttl" in item

    def test_handles_error_gracefully(self, mock_table):
        """Handles errors gracefully."""
        mock_table.put_item.side_effect = Exception("DB error")

        # Should not raise
        record_action_for_rate_limit(mock_table, "1.2.3.4", "config_create")


class TestCaptchaRequired:
    """Tests for CaptchaRequired exception."""

    def test_default_message(self):
        """Has default message."""
        exc = CaptchaRequired()
        assert str(exc) == "Captcha verification required"

    def test_custom_message(self):
        """Accepts custom message."""
        exc = CaptchaRequired("Custom message")
        assert str(exc) == "Custom message"
        assert exc.message == "Custom message"


class TestCaptchaVerificationResult:
    """Tests for CaptchaVerificationResult model."""

    def test_minimal_result(self):
        """Creates minimal result."""
        result = CaptchaVerificationResult(success=True)
        assert result.success is True
        assert result.error_codes == []

    def test_full_result(self):
        """Creates full result."""
        result = CaptchaVerificationResult(
            success=True,
            challenge_ts="2025-11-26T12:00:00Z",
            hostname="example.com",
            error_codes=[],
        )
        assert result.success is True
        assert result.hostname == "example.com"

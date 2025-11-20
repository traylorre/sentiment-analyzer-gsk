"""
Unit Tests for Error Response Helper
=====================================

Tests for standardized error response formatting.

For On-Call Engineers:
    These tests verify error response format matches plan.md spec.
    All responses include request_id for log correlation.

For Developers:
    - Test all convenience functions
    - Verify status codes and error codes
    - Test logging behavior
"""

import json

from src.lambdas.shared.errors import (
    ErrorCode,
    database_error,
    error_response,
    internal_error,
    model_error,
    not_found_error,
    rate_limit_error,
    secret_error,
    unauthorized_error,
    validation_error,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_error_code_values(self):
        """Test that all error codes have expected values."""
        assert ErrorCode.RATE_LIMIT_EXCEEDED.value == "RATE_LIMIT_EXCEEDED"
        assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert ErrorCode.NOT_FOUND.value == "NOT_FOUND"
        assert ErrorCode.SECRET_ERROR.value == "SECRET_ERROR"
        assert ErrorCode.DATABASE_ERROR.value == "DATABASE_ERROR"
        assert ErrorCode.UNAUTHORIZED.value == "UNAUTHORIZED"
        assert ErrorCode.INTERNAL_ERROR.value == "INTERNAL_ERROR"
        assert ErrorCode.MODEL_ERROR.value == "MODEL_ERROR"

    def test_error_code_is_string(self):
        """Test that ErrorCode inherits from str."""
        # This allows using enum directly in JSON
        assert isinstance(ErrorCode.VALIDATION_ERROR, str)


class TestErrorResponse:
    """Tests for error_response function."""

    def test_basic_error_response(self):
        """Test basic error response structure."""
        response = error_response(
            400,
            "Bad request",
            ErrorCode.VALIDATION_ERROR,
            "req-123",
            log_error=False,
        )

        assert response["statusCode"] == 400
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["headers"]["X-Request-Id"] == "req-123"

        body = json.loads(response["body"])
        assert body["error"] == "Bad request"
        assert body["code"] == "VALIDATION_ERROR"
        assert body["request_id"] == "req-123"

    def test_error_response_with_details(self):
        """Test error response includes details."""
        response = error_response(
            400,
            "Invalid input",
            ErrorCode.VALIDATION_ERROR,
            "req-123",
            details={"field": "score", "value": -1},
            log_error=False,
        )

        body = json.loads(response["body"])
        assert body["details"]["field"] == "score"
        assert body["details"]["value"] == -1

    def test_error_response_without_details(self):
        """Test error response without details."""
        response = error_response(
            500,
            "Internal error",
            ErrorCode.INTERNAL_ERROR,
            "req-123",
            log_error=False,
        )

        body = json.loads(response["body"])
        assert "details" not in body

    def test_error_response_with_string_code(self):
        """Test error response with string code instead of enum."""
        response = error_response(
            400,
            "Custom error",
            "CUSTOM_CODE",
            "req-123",
            log_error=False,
        )

        body = json.loads(response["body"])
        assert body["code"] == "CUSTOM_CODE"

    def test_error_response_status_codes(self):
        """Test various status codes."""
        for status_code in [400, 401, 403, 404, 429, 500, 502, 503]:
            response = error_response(
                status_code,
                "Test",
                ErrorCode.INTERNAL_ERROR,
                "req-123",
                log_error=False,
            )
            assert response["statusCode"] == status_code


class TestValidationError:
    """Tests for validation_error convenience function."""

    def test_validation_error_basic(self):
        """Test basic validation error."""
        response = validation_error("Invalid input", "req-123")

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["code"] == "VALIDATION_ERROR"
        assert body["error"] == "Invalid input"

    def test_validation_error_with_field(self):
        """Test validation error with field name."""
        response = validation_error(
            "Invalid score",
            "req-123",
            field="score",
        )

        body = json.loads(response["body"])
        assert body["details"]["field"] == "score"

    def test_validation_error_with_details(self):
        """Test validation error with custom details."""
        response = validation_error(
            "Multiple errors",
            "req-123",
            details={"errors": ["field1", "field2"]},
        )

        body = json.loads(response["body"])
        assert body["details"]["errors"] == ["field1", "field2"]


class TestNotFoundError:
    """Tests for not_found_error convenience function."""

    def test_not_found_basic(self):
        """Test basic not found error."""
        response = not_found_error("Item not found", "req-123")

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["code"] == "NOT_FOUND"

    def test_not_found_with_resource(self):
        """Test not found with resource identifier."""
        response = not_found_error(
            "Article not found",
            "req-123",
            resource="newsapi#abc123",
        )

        body = json.loads(response["body"])
        assert body["details"]["resource"] == "newsapi#abc123"


class TestUnauthorizedError:
    """Tests for unauthorized_error convenience function."""

    def test_unauthorized_default_message(self):
        """Test unauthorized with default message."""
        response = unauthorized_error("req-123")

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["code"] == "UNAUTHORIZED"
        assert body["error"] == "Authentication required"

    def test_unauthorized_custom_message(self):
        """Test unauthorized with custom message."""
        response = unauthorized_error("req-123", message="Invalid API key")

        body = json.loads(response["body"])
        assert body["error"] == "Invalid API key"


class TestRateLimitError:
    """Tests for rate_limit_error convenience function."""

    def test_rate_limit_basic(self):
        """Test basic rate limit error."""
        response = rate_limit_error("req-123")

        assert response["statusCode"] == 429
        body = json.loads(response["body"])
        assert body["code"] == "RATE_LIMIT_EXCEEDED"
        assert "external API" in body["error"]

    def test_rate_limit_with_service(self):
        """Test rate limit with specific service."""
        response = rate_limit_error("req-123", service="NewsAPI")

        body = json.loads(response["body"])
        assert "NewsAPI" in body["error"]
        assert body["details"]["service"] == "NewsAPI"

    def test_rate_limit_with_retry_after(self):
        """Test rate limit with Retry-After header."""
        response = rate_limit_error("req-123", retry_after=3600)

        assert response["headers"]["Retry-After"] == "3600"
        body = json.loads(response["body"])
        assert body["details"]["retry_after_seconds"] == 3600


class TestInternalError:
    """Tests for internal_error convenience function."""

    def test_internal_error_default(self):
        """Test internal error with defaults."""
        response = internal_error("req-123")

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["code"] == "INTERNAL_ERROR"
        assert body["error"] == "Internal server error"

    def test_internal_error_no_details_exposed(self, caplog):
        """Test that internal error details are not exposed."""
        response = internal_error(
            "req-123",
            details={"stack_trace": "sensitive info"},
        )

        body = json.loads(response["body"])
        # Details should NOT be in response (security)
        assert "details" not in body

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Internal error details")


class TestDatabaseError:
    """Tests for database_error convenience function."""

    def test_database_error(self, caplog):
        """Test database error."""
        response = database_error("req-123", "put_item")

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["code"] == "DATABASE_ERROR"
        assert "put_item" in body["error"]

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Database operation failed")

    def test_database_error_with_details(self, caplog):
        """Test database error with details."""
        response = database_error(
            "req-123",
            "query",
            details={"table": "sentiment-items"},
        )

        body = json.loads(response["body"])
        assert body["details"]["table"] == "sentiment-items"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Database operation failed")


class TestSecretError:
    """Tests for secret_error convenience function."""

    def test_secret_error(self, caplog):
        """Test secret error."""
        response = secret_error("req-123", "dev/sentiment-analyzer/newsapi")

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["code"] == "SECRET_ERROR"
        assert body["details"]["secret_id"] == "dev/sentiment-analyzer/newsapi"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Failed to retrieve configuration")


class TestModelError:
    """Tests for model_error convenience function."""

    def test_model_error_default(self, caplog):
        """Test model error with default message."""
        response = model_error("req-123")

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["code"] == "MODEL_ERROR"
        assert body["error"] == "Sentiment analysis failed"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Sentiment analysis failed")

    def test_model_error_custom_message(self, caplog):
        """Test model error with custom message."""
        response = model_error(
            "req-123",
            message="Model loading failed",
            details={"model_path": "/opt/model"},
        )

        body = json.loads(response["body"])
        assert body["error"] == "Model loading failed"
        assert body["details"]["model_path"] == "/opt/model"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Model loading failed")


class TestResponseFormat:
    """Tests to verify response format matches plan.md spec."""

    def test_response_is_lambda_compatible(self):
        """Test response has correct Lambda API Gateway format."""
        response = error_response(
            400,
            "Test",
            ErrorCode.VALIDATION_ERROR,
            "req-123",
            log_error=False,
        )

        # Must have these keys for API Gateway/Lambda Function URL
        assert "statusCode" in response
        assert "headers" in response
        assert "body" in response

        # Body must be JSON string
        assert isinstance(response["body"], str)
        json.loads(response["body"])  # Should not raise

    def test_body_format_matches_spec(self):
        """Test body format matches plan.md specification."""
        response = error_response(
            500,
            "Test error",
            ErrorCode.INTERNAL_ERROR,
            "req-123",
            details={"key": "value"},
            log_error=False,
        )

        body = json.loads(response["body"])

        # Required fields per plan.md
        assert "error" in body
        assert "code" in body
        assert "request_id" in body

        # Optional field
        assert "details" in body

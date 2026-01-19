"""Unit tests for PreprodEnvValidator.

Tests environment validation logic including:
- Missing required environment variables
- DATABASE_TABLE vs DYNAMODB_TABLE consistency
- URL format validation
- Environment value validation
"""

import os

import pytest

from tests.fixtures.validators.preprod_env_validator import (
    EnvValidationError,
    PreprodEnvValidator,
)


@pytest.fixture
def validator():
    """Create a fresh validator instance."""
    return PreprodEnvValidator()


@pytest.fixture
def clean_env():
    """Fixture that cleans relevant env vars before and after test."""
    # Store original values
    original = {}
    env_vars = [
        "AWS_REGION",
        "ENVIRONMENT",
        "DYNAMODB_TABLE",
        "DATABASE_TABLE",
        "PREPROD_DASHBOARD_URL",
        "SSE_LAMBDA_URL",
        "DASHBOARD_FUNCTION_URL",
        "API_KEY",
    ]
    for var in env_vars:
        original[var] = os.environ.get(var)

    # Clear all
    for var in env_vars:
        os.environ.pop(var, None)

    yield

    # Restore original values
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value
        else:
            os.environ.pop(var, None)


class TestRequiredVars:
    """Tests for required environment variable validation."""

    def test_missing_aws_region(self, validator, clean_env):
        """Missing AWS_REGION should produce error."""
        os.environ["ENVIRONMENT"] = "preprod"

        errors = validator._validate_required_vars()

        assert len(errors) == 1
        assert errors[0].var == "AWS_REGION"
        assert "Missing required" in errors[0].message

    def test_missing_environment(self, validator, clean_env):
        """Missing ENVIRONMENT should produce error."""
        os.environ["AWS_REGION"] = "us-east-1"

        errors = validator._validate_required_vars()

        assert len(errors) == 1
        assert errors[0].var == "ENVIRONMENT"

    def test_all_required_present(self, validator, clean_env):
        """No errors when all required vars are present."""
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["ENVIRONMENT"] = "preprod"

        errors = validator._validate_required_vars()

        assert len(errors) == 0


class TestTableConsistency:
    """Tests for DATABASE_TABLE vs DYNAMODB_TABLE consistency."""

    def test_matching_tables_no_error(self, validator, clean_env):
        """No error when tables match."""
        os.environ["DYNAMODB_TABLE"] = "preprod-sentiment-items"
        os.environ["DATABASE_TABLE"] = "preprod-sentiment-items"

        errors = validator._validate_table_consistency()

        assert len(errors) == 0

    def test_different_tables_produces_warning(self, validator, clean_env):
        """Different tables should produce warning error."""
        os.environ["DYNAMODB_TABLE"] = "preprod-sentiment-items"
        os.environ["DATABASE_TABLE"] = "preprod-sentiment-users"

        errors = validator._validate_table_consistency()

        assert len(errors) == 1
        assert errors[0].var == "DATABASE_TABLE"
        assert "differs from DYNAMODB_TABLE" in errors[0].message
        assert "ResourceNotFoundException" in errors[0].message
        assert errors[0].value["DATABASE_TABLE"] == "preprod-sentiment-users"
        assert errors[0].value["DYNAMODB_TABLE"] == "preprod-sentiment-items"

    def test_only_dynamodb_table_no_error(self, validator, clean_env):
        """No error when only DYNAMODB_TABLE is set."""
        os.environ["DYNAMODB_TABLE"] = "preprod-sentiment-items"

        errors = validator._validate_table_consistency()

        assert len(errors) == 0

    def test_only_database_table_no_error(self, validator, clean_env):
        """No error when only DATABASE_TABLE is set."""
        os.environ["DATABASE_TABLE"] = "preprod-sentiment-users"

        errors = validator._validate_table_consistency()

        assert len(errors) == 0


class TestEnvironmentValue:
    """Tests for ENVIRONMENT value validation."""

    def test_valid_preprod(self, validator, clean_env):
        """ENVIRONMENT=preprod is valid."""
        os.environ["ENVIRONMENT"] = "preprod"

        errors = validator._validate_environment_value()

        assert len(errors) == 0

    def test_valid_dev(self, validator, clean_env):
        """ENVIRONMENT=dev is valid."""
        os.environ["ENVIRONMENT"] = "dev"

        errors = validator._validate_environment_value()

        assert len(errors) == 0

    def test_valid_test(self, validator, clean_env):
        """ENVIRONMENT=test is valid."""
        os.environ["ENVIRONMENT"] = "test"

        errors = validator._validate_environment_value()

        assert len(errors) == 0

    def test_invalid_environment(self, validator, clean_env):
        """Invalid ENVIRONMENT value should produce error."""
        os.environ["ENVIRONMENT"] = "production"

        errors = validator._validate_environment_value()

        assert len(errors) == 1
        assert errors[0].var == "ENVIRONMENT"
        assert "not a recognized value" in errors[0].message


class TestURLValidation:
    """Tests for URL format validation."""

    def test_valid_lambda_function_url(self, validator, clean_env):
        """Valid Lambda function URL should pass."""
        os.environ["PREPROD_DASHBOARD_URL"] = (
            "https://abc123def456.lambda-url.us-east-1.on.aws/"
        )

        errors = validator._validate_urls()

        assert len(errors) == 0

    def test_valid_lambda_url_no_trailing_slash(self, validator, clean_env):
        """Lambda URL without trailing slash should pass."""
        os.environ["SSE_LAMBDA_URL"] = (
            "https://xyz789ghi012.lambda-url.us-east-1.on.aws"
        )

        errors = validator._validate_urls()

        assert len(errors) == 0

    def test_valid_amplify_url(self, validator, clean_env):
        """Amplify URL should pass (Feature 1207: CloudFront removed)."""
        os.environ["PREPROD_DASHBOARD_URL"] = "https://main.d1234567890.amplifyapp.com/"

        errors = validator._validate_urls()

        assert len(errors) == 0

    def test_valid_api_gateway_url(self, validator, clean_env):
        """API Gateway URL should pass."""
        os.environ["PREPROD_DASHBOARD_URL"] = (
            "https://abc123.execute-api.us-east-1.amazonaws.com/prod/"
        )

        errors = validator._validate_urls()

        assert len(errors) == 0

    def test_valid_localhost_url(self, validator, clean_env):
        """Localhost URL should pass (for local dev)."""
        os.environ["PREPROD_DASHBOARD_URL"] = "http://localhost:8080/"

        errors = validator._validate_urls()

        assert len(errors) == 0

    def test_invalid_url_format(self, validator, clean_env):
        """Invalid URL format should produce error."""
        os.environ["PREPROD_DASHBOARD_URL"] = "not-a-valid-url"

        errors = validator._validate_urls()

        assert len(errors) == 1
        assert errors[0].var == "PREPROD_DASHBOARD_URL"
        assert "URL format may be invalid" in errors[0].message

    def test_missing_url_no_error(self, validator, clean_env):
        """Missing URL vars should not produce URL format errors."""
        # URLs are validated in _validate_e2e_vars for presence
        # _validate_urls only checks format if present
        errors = validator._validate_urls()

        assert len(errors) == 0


class TestFullValidation:
    """Tests for full validation workflow."""

    def test_validate_all_with_valid_config(self, validator, clean_env):
        """Full validation should pass with valid config."""
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["ENVIRONMENT"] = "preprod"
        os.environ["DYNAMODB_TABLE"] = "preprod-sentiment-items"
        os.environ["DATABASE_TABLE"] = "preprod-sentiment-items"
        os.environ["PREPROD_DASHBOARD_URL"] = (
            "https://abc123.lambda-url.us-east-1.on.aws/"
        )
        os.environ["SSE_LAMBDA_URL"] = "https://xyz789.lambda-url.us-east-1.on.aws/"
        os.environ["API_KEY"] = "test-api-key"

        errors = validator.validate(test_type="all")

        assert len(errors) == 0

    def test_validate_integration_only(self, validator, clean_env):
        """Integration validation should check table vars."""
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["ENVIRONMENT"] = "preprod"
        os.environ["DYNAMODB_TABLE"] = "preprod-sentiment-items"
        os.environ["DATABASE_TABLE"] = "preprod-sentiment-users"

        errors = validator.validate(test_type="integration")

        # Should have warning about different tables
        assert len(errors) == 1
        assert errors[0].var == "DATABASE_TABLE"

    def test_validate_e2e_only(self, validator, clean_env):
        """E2E validation should check URL vars."""
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["ENVIRONMENT"] = "preprod"

        errors = validator.validate(test_type="e2e")

        # Should have errors for missing E2E vars
        assert len(errors) >= 3  # PREPROD_DASHBOARD_URL, SSE_LAMBDA_URL, API_KEY

    def test_format_errors(self, validator, clean_env):
        """Error formatting should produce readable output."""
        errors = [
            EnvValidationError(
                var="DATABASE_TABLE",
                message="differs from DYNAMODB_TABLE",
                value="preprod-sentiment-users",
                suggestion="Set DATABASE_TABLE to match",
            ),
        ]

        formatted = validator.format_errors(errors)

        assert "Preprod environment validation failed" in formatted
        assert "DATABASE_TABLE" in formatted
        assert "differs from DYNAMODB_TABLE" in formatted
        assert "preprod-sentiment-users" in formatted
        assert "Set DATABASE_TABLE to match" in formatted

    def test_format_errors_empty(self, validator):
        """Empty error list should return empty string."""
        assert validator.format_errors([]) == ""

    def test_assert_valid_raises(self, validator, clean_env):
        """assert_valid should raise AssertionError on invalid config."""
        # Missing required vars
        with pytest.raises(AssertionError) as exc_info:
            validator.assert_valid()

        assert "Preprod environment validation failed" in str(exc_info.value)

    def test_assert_valid_passes(self, validator, clean_env):
        """assert_valid should not raise on valid config."""
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["ENVIRONMENT"] = "preprod"
        os.environ["DYNAMODB_TABLE"] = "preprod-sentiment-items"
        os.environ["DATABASE_TABLE"] = "preprod-sentiment-items"
        os.environ["PREPROD_DASHBOARD_URL"] = (
            "https://abc123.lambda-url.us-east-1.on.aws/"
        )
        os.environ["SSE_LAMBDA_URL"] = "https://xyz789.lambda-url.us-east-1.on.aws/"
        os.environ["API_KEY"] = "test-api-key"

        # Should not raise
        validator.assert_valid()

    def test_warn_on_issues(self, validator, clean_env):
        """warn_on_issues should return errors without raising."""
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["ENVIRONMENT"] = "preprod"
        os.environ["DYNAMODB_TABLE"] = "preprod-sentiment-items"
        os.environ["DATABASE_TABLE"] = "preprod-sentiment-users"

        errors = validator.warn_on_issues(test_type="integration")

        # Should return errors, not raise
        assert len(errors) == 1
        assert errors[0].var == "DATABASE_TABLE"

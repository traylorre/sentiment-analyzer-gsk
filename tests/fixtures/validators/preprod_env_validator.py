"""Preprod test environment validator.

Validates environment variable configuration before running preprod tests.
Detects misconfigurations that cause ResourceNotFoundException, 404s, and other
environment-related test failures.

Common issues caught:
- DATABASE_TABLE vs DYNAMODB_TABLE mismatch (Issue #13)
- Missing required env vars for preprod tests
- Invalid URL formats for Lambda function URLs
- Environment value mismatch (ENVIRONMENT != preprod for preprod tests)

Usage in conftest.py:
    from tests.fixtures.validators.preprod_env_validator import PreprodEnvValidator

    @pytest.fixture(scope="session", autouse=True)
    def validate_preprod_env():
        validator = PreprodEnvValidator()
        errors = validator.validate()
        if errors:
            pytest.fail(validator.format_errors(errors))
"""

import os
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class EnvValidationError:
    """Single environment validation error with context."""

    var: str
    message: str
    value: Any = None
    suggestion: str | None = None


class PreprodEnvValidator:
    """Validates preprod test environment configuration.

    Checks for common misconfigurations that cause test failures:
    1. Missing required environment variables
    2. DATABASE_TABLE vs DYNAMODB_TABLE conflicts
    3. Invalid URL formats
    4. Environment value consistency
    """

    # Required for all preprod tests
    REQUIRED_VARS = [
        "AWS_REGION",
        "ENVIRONMENT",
    ]

    # Required for integration/analysis tests
    INTEGRATION_VARS = [
        "DYNAMODB_TABLE",
        "DATABASE_TABLE",
    ]

    # Required for E2E tests
    E2E_VARS = [
        "PREPROD_DASHBOARD_URL",
        "SSE_LAMBDA_URL",
        "API_KEY",
    ]

    # URL pattern for Lambda function URLs
    URL_PATTERN = re.compile(r"^https://[a-z0-9]+\.lambda-url\.[a-z0-9-]+\.on\.aws/?$")

    # Alternative URL patterns (CloudFront, API Gateway)
    ALT_URL_PATTERNS = [
        re.compile(r"^https://[a-z0-9]+\.cloudfront\.net/?.*$"),
        re.compile(r"^https://[a-z0-9]+\.execute-api\.[a-z0-9-]+\.amazonaws\.com/?.*$"),
        re.compile(r"^https?://localhost(:\d+)?/?.*$"),  # Local dev
    ]

    def validate(self, test_type: str = "all") -> list[EnvValidationError]:
        """Validate environment configuration.

        Args:
            test_type: Type of tests to validate for:
                       "all" - validate all vars
                       "integration" - validate for integration tests
                       "e2e" - validate for E2E tests

        Returns:
            List of EnvValidationError objects (empty if valid)
        """
        errors: list[EnvValidationError] = []

        # Always validate required vars
        errors.extend(self._validate_required_vars())

        # Validate based on test type
        if test_type in ("all", "integration"):
            errors.extend(self._validate_integration_vars())
            errors.extend(self._validate_table_consistency())

        if test_type in ("all", "e2e"):
            errors.extend(self._validate_e2e_vars())
            errors.extend(self._validate_urls())

        # Always validate environment consistency
        errors.extend(self._validate_environment_value())

        return errors

    def _validate_required_vars(self) -> list[EnvValidationError]:
        """Check that required vars are present."""
        errors = []
        for var in self.REQUIRED_VARS:
            if var not in os.environ:
                errors.append(
                    EnvValidationError(
                        var=var,
                        message=f"Missing required environment variable: {var}",
                        suggestion=f"Set {var} in CI workflow or test setup",
                    )
                )
        return errors

    def _validate_integration_vars(self) -> list[EnvValidationError]:
        """Check that integration test vars are present."""
        errors = []
        for var in self.INTEGRATION_VARS:
            if var not in os.environ:
                errors.append(
                    EnvValidationError(
                        var=var,
                        message=f"Missing environment variable for integration tests: {var}",
                        suggestion=f"Set {var} in CI workflow env section",
                    )
                )
        return errors

    def _validate_e2e_vars(self) -> list[EnvValidationError]:
        """Check that E2E test vars are present."""
        errors = []
        for var in self.E2E_VARS:
            if var not in os.environ:
                errors.append(
                    EnvValidationError(
                        var=var,
                        message=f"Missing environment variable for E2E tests: {var}",
                        suggestion=f"Set {var} in CI workflow env section",
                    )
                )
        return errors

    def _validate_table_consistency(self) -> list[EnvValidationError]:
        """Check DATABASE_TABLE vs DYNAMODB_TABLE consistency.

        Issue #13: Analysis handler uses DATABASE_TABLE via get_table(),
        but tests often insert data using DYNAMODB_TABLE. If these point
        to different tables, tests fail with ResourceNotFoundException.

        This validator WARNS when they differ, allowing intentional
        configurations but flagging potential issues.
        """
        errors = []

        dynamodb_table = os.environ.get("DYNAMODB_TABLE")
        database_table = os.environ.get("DATABASE_TABLE")

        # Only check if both are set
        if dynamodb_table and database_table:
            if dynamodb_table != database_table:
                errors.append(
                    EnvValidationError(
                        var="DATABASE_TABLE",
                        message=(
                            f"DATABASE_TABLE ({database_table}) differs from "
                            f"DYNAMODB_TABLE ({dynamodb_table}). This may cause "
                            f"ResourceNotFoundException in analysis tests if tests "
                            f"insert data into DYNAMODB_TABLE but handler reads from "
                            f"DATABASE_TABLE."
                        ),
                        value={
                            "DATABASE_TABLE": database_table,
                            "DYNAMODB_TABLE": dynamodb_table,
                        },
                        suggestion=(
                            "If running analysis tests, ensure DATABASE_TABLE points "
                            "to the same table as DYNAMODB_TABLE, or override in test "
                            "fixture (see test_analysis_preprod.py env_vars fixture)."
                        ),
                    )
                )

        return errors

    def _validate_environment_value(self) -> list[EnvValidationError]:
        """Check ENVIRONMENT value consistency."""
        errors = []

        env_value = os.environ.get("ENVIRONMENT", "")

        # For preprod tests, ENVIRONMENT should be "preprod"
        if env_value and env_value not in ("preprod", "dev", "test"):
            errors.append(
                EnvValidationError(
                    var="ENVIRONMENT",
                    message=(
                        f"ENVIRONMENT={env_value} is not a recognized value. "
                        f"Expected: preprod, dev, or test"
                    ),
                    value=env_value,
                    suggestion="Set ENVIRONMENT=preprod for preprod tests",
                )
            )

        return errors

    def _validate_urls(self) -> list[EnvValidationError]:
        """Validate URL format for Lambda function URLs."""
        errors = []

        url_vars = ["PREPROD_DASHBOARD_URL", "SSE_LAMBDA_URL", "DASHBOARD_FUNCTION_URL"]

        for var in url_vars:
            url = os.environ.get(var)
            if not url:
                continue

            # Check if URL matches expected patterns
            is_valid = self.URL_PATTERN.match(url) or any(
                p.match(url) for p in self.ALT_URL_PATTERNS
            )

            if not is_valid:
                errors.append(
                    EnvValidationError(
                        var=var,
                        message=(
                            f"URL format may be invalid: {url}. "
                            f"Expected Lambda Function URL, CloudFront, or API Gateway URL."
                        ),
                        value=url,
                        suggestion=(
                            "Verify the URL is correct. Lambda Function URLs look like: "
                            "https://xxxxx.lambda-url.us-east-1.on.aws/"
                        ),
                    )
                )

        return errors

    def format_errors(self, errors: list[EnvValidationError]) -> str:
        """Format errors into a readable string for pytest.fail().

        Args:
            errors: List of validation errors

        Returns:
            Formatted error message
        """
        if not errors:
            return ""

        lines = ["Preprod environment validation failed:"]
        for err in errors:
            lines.append(f"\n  {err.var}:")
            lines.append(f"    Error: {err.message}")
            if err.value is not None:
                lines.append(f"    Value: {err.value}")
            if err.suggestion:
                lines.append(f"    Fix: {err.suggestion}")

        return "\n".join(lines)

    def assert_valid(self, test_type: str = "all") -> None:
        """Assert environment is valid, raise AssertionError if not.

        Args:
            test_type: Type of tests to validate for

        Raises:
            AssertionError: If validation fails
        """
        errors = self.validate(test_type)
        if errors:
            raise AssertionError(self.format_errors(errors))

    def warn_on_issues(self, test_type: str = "all") -> list[EnvValidationError]:
        """Return issues as warnings instead of hard failures.

        Useful for non-critical validations that should be logged but
        not fail the test run.

        Args:
            test_type: Type of tests to validate for

        Returns:
            List of validation errors (for logging)
        """
        return self.validate(test_type)

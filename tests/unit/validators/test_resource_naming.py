"""Tests for resource naming validation.

Feature: 075-validation-gaps
User Story 1: Resource Naming Consistency Validation
"""

from pathlib import Path

import pytest

from src.validators.resource_naming import (
    LEGACY_PATTERN,
    NAMING_PATTERN,
    TerraformResource,
    ValidationStatus,
    extract_resources,
    validate_all_resources,
    validate_naming_pattern,
)

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "terraform"


class TestNamingPatterns:
    """Test the naming pattern regex constants."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("preprod-sentiment-dashboard", True),
            ("prod-sentiment-api", True),
            ("preprod-sentiment-items", True),
            ("prod-sentiment-events-dlq", True),
            ("preprod-sentiment-123", True),
            # Invalid patterns
            ("dev-sentiment-dashboard", False),
            ("sentiment-dashboard", False),
            ("preprod-dashboard", False),
            ("PREPROD-sentiment-dashboard", False),
            ("preprod-SENTIMENT-dashboard", False),
        ],
    )
    def test_naming_pattern_matches(self, name: str, expected: bool):
        """Test NAMING_PATTERN matches valid names."""
        result = bool(NAMING_PATTERN.match(name))
        assert (
            result == expected
        ), f"Expected {name} to {'match' if expected else 'not match'}"

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("sentiment-analyzer-api", True),
            ("sentiment-analyzer-dashboard", True),
            ("sentiment-analyzer-processor", True),
            # Non-legacy patterns
            ("preprod-sentiment-api", False),
            ("sentiment-api", False),
            ("analyzer-sentiment", False),
        ],
    )
    def test_legacy_pattern_matches(self, name: str, expected: bool):
        """Test LEGACY_PATTERN detects old naming convention."""
        result = bool(LEGACY_PATTERN.match(name))
        assert (
            result == expected
        ), f"Expected {name} to {'match' if expected else 'not match'} legacy"


class TestValidateNamingPattern:
    """Test validate_naming_pattern function."""

    def test_valid_lambda_name_passes(self):
        """Valid Lambda name should pass validation."""
        resource = TerraformResource(
            name="preprod-sentiment-dashboard",
            resource_type="aws_lambda_function",
            module_path=Path("modules/lambda/main.tf"),
            line_number=10,
            terraform_id="aws_lambda_function.dashboard",
        )
        result = validate_naming_pattern(resource)
        assert result.status == ValidationStatus.PASSED
        assert "follows naming convention" in result.message

    def test_valid_dynamodb_name_passes(self):
        """Valid DynamoDB table name should pass validation."""
        resource = TerraformResource(
            name="prod-sentiment-items",
            resource_type="aws_dynamodb_table",
            module_path=Path("modules/dynamodb/main.tf"),
            line_number=5,
            terraform_id="aws_dynamodb_table.items",
        )
        result = validate_naming_pattern(resource)
        assert result.status == ValidationStatus.PASSED

    def test_valid_sqs_name_passes(self):
        """Valid SQS queue name should pass validation."""
        resource = TerraformResource(
            name="preprod-sentiment-events",
            resource_type="aws_sqs_queue",
            module_path=Path("modules/sqs/main.tf"),
            line_number=1,
            terraform_id="aws_sqs_queue.events",
        )
        result = validate_naming_pattern(resource)
        assert result.status == ValidationStatus.PASSED

    def test_valid_sns_name_passes(self):
        """Valid SNS topic name should pass validation."""
        resource = TerraformResource(
            name="prod-sentiment-alerts",
            resource_type="aws_sns_topic",
            module_path=Path("modules/sns/main.tf"),
            line_number=1,
            terraform_id="aws_sns_topic.alerts",
        )
        result = validate_naming_pattern(resource)
        assert result.status == ValidationStatus.PASSED

    def test_legacy_naming_rejected(self):
        """Legacy naming pattern should fail with specific message."""
        resource = TerraformResource(
            name="sentiment-analyzer-api",
            resource_type="aws_lambda_function",
            module_path=Path("modules/lambda/main.tf"),
            line_number=10,
            terraform_id="aws_lambda_function.api",
        )
        result = validate_naming_pattern(resource)
        assert result.status == ValidationStatus.FAIL
        assert "legacy" in result.message.lower()
        assert result.pattern_matched == LEGACY_PATTERN.pattern

    def test_missing_sentiment_segment_rejected(self):
        """Missing 'sentiment' segment should fail validation."""
        resource = TerraformResource(
            name="preprod-dashboard",
            resource_type="aws_lambda_function",
            module_path=Path("modules/lambda/main.tf"),
            line_number=10,
            terraform_id="aws_lambda_function.dashboard",
        )
        result = validate_naming_pattern(resource)
        assert result.status == ValidationStatus.FAIL
        assert "does not match" in result.message

    def test_wrong_environment_rejected(self):
        """Wrong environment prefix (not preprod/prod) should fail."""
        resource = TerraformResource(
            name="dev-sentiment-api",
            resource_type="aws_lambda_function",
            module_path=Path("modules/lambda/main.tf"),
            line_number=10,
            terraform_id="aws_lambda_function.api",
        )
        result = validate_naming_pattern(resource)
        assert result.status == ValidationStatus.FAIL


class TestExtractResources:
    """Test extract_resources function."""

    def test_extract_from_valid_fixtures(self):
        """Extract resources from valid_naming.tf fixture."""
        if not FIXTURES_DIR.exists():
            pytest.skip("Test fixtures not found")

        resources = extract_resources(FIXTURES_DIR)
        assert len(resources) > 0, "Should extract at least one resource"

        # Check we got expected resource types
        resource_types = {r.resource_type for r in resources}
        assert "aws_lambda_function" in resource_types
        assert "aws_dynamodb_table" in resource_types

    def test_nonexistent_path_raises(self):
        """Non-existent path should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            extract_resources(Path("/nonexistent/path"))

    def test_empty_directory_raises(self, tmp_path):
        """Directory with no .tf files should raise ValueError."""
        with pytest.raises(ValueError, match="No .tf files"):
            extract_resources(tmp_path)


class TestValidateAllResources:
    """Test validate_all_resources function."""

    def test_all_lambda_names_valid(self):
        """All Lambda function names must match {env}-sentiment-{name}."""
        if not (FIXTURES_DIR / "valid_naming.tf").exists():
            pytest.skip("Test fixtures not found")

        results = validate_all_resources(FIXTURES_DIR)
        lambda_results = [
            r for r in results if r.resource.resource_type == "aws_lambda_function"
        ]

        # Filter to just the valid_naming.tf file
        valid_results = [
            r
            for r in lambda_results
            if r.resource.module_path.name == "valid_naming.tf"
        ]

        for result in valid_results:
            assert (
                result.status == ValidationStatus.PASSED
            ), f"Lambda {result.resource.name} should pass: {result.message}"

    def test_all_dynamodb_names_valid(self):
        """All DynamoDB table names must match {env}-sentiment-{name}."""
        if not (FIXTURES_DIR / "valid_naming.tf").exists():
            pytest.skip("Test fixtures not found")

        results = validate_all_resources(FIXTURES_DIR)
        dynamodb_results = [
            r for r in results if r.resource.resource_type == "aws_dynamodb_table"
        ]

        valid_results = [
            r
            for r in dynamodb_results
            if r.resource.module_path.name == "valid_naming.tf"
        ]

        for result in valid_results:
            assert (
                result.status == ValidationStatus.PASSED
            ), f"DynamoDB {result.resource.name} should pass: {result.message}"

    def test_all_sqs_names_valid(self):
        """All SQS queue names must match {env}-sentiment-{name}."""
        if not (FIXTURES_DIR / "valid_naming.tf").exists():
            pytest.skip("Test fixtures not found")

        results = validate_all_resources(FIXTURES_DIR)
        sqs_results = [
            r for r in results if r.resource.resource_type == "aws_sqs_queue"
        ]

        valid_results = [
            r for r in sqs_results if r.resource.module_path.name == "valid_naming.tf"
        ]

        for result in valid_results:
            assert (
                result.status == ValidationStatus.PASSED
            ), f"SQS {result.resource.name} should pass: {result.message}"

    def test_all_sns_names_valid(self):
        """All SNS topic names must match {env}-sentiment-{name}."""
        if not (FIXTURES_DIR / "valid_naming.tf").exists():
            pytest.skip("Test fixtures not found")

        results = validate_all_resources(FIXTURES_DIR)
        sns_results = [
            r for r in results if r.resource.resource_type == "aws_sns_topic"
        ]

        valid_results = [
            r for r in sns_results if r.resource.module_path.name == "valid_naming.tf"
        ]

        for result in valid_results:
            assert (
                result.status == ValidationStatus.PASSED
            ), f"SNS {result.resource.name} should pass: {result.message}"

    def test_legacy_naming_detected(self):
        """Legacy naming fixture should have all FAIL results."""
        if not (FIXTURES_DIR / "legacy_naming.tf").exists():
            pytest.skip("Legacy naming fixture not found")

        results = validate_all_resources(FIXTURES_DIR)
        legacy_results = [
            r for r in results if r.resource.module_path.name == "legacy_naming.tf"
        ]

        assert len(legacy_results) > 0, "Should find resources in legacy fixture"
        for result in legacy_results:
            assert (
                result.status == ValidationStatus.FAIL
            ), f"Legacy resource {result.resource.name} should fail: {result.message}"

    def test_invalid_naming_detected(self):
        """Invalid naming fixture should have all FAIL results."""
        if not (FIXTURES_DIR / "invalid_naming.tf").exists():
            pytest.skip("Invalid naming fixture not found")

        results = validate_all_resources(FIXTURES_DIR)
        invalid_results = [
            r for r in results if r.resource.module_path.name == "invalid_naming.tf"
        ]

        assert len(invalid_results) > 0, "Should find resources in invalid fixture"
        for result in invalid_results:
            assert (
                result.status == ValidationStatus.FAIL
            ), f"Invalid resource {result.resource.name} should fail: {result.message}"

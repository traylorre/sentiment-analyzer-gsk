"""Tests for IAM coverage validation.

Feature: 075-validation-gaps
User Story 2: IAM Pattern Coverage Validation
"""

from pathlib import Path

import pytest

from src.validators.iam_coverage import (
    CoverageReport,
    IAMPattern,
    check_coverage,
    extract_iam_patterns,
    validate_iam_coverage,
)
from src.validators.resource_naming import TerraformResource

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "terraform"


class TestIAMPattern:
    """Test IAMPattern dataclass."""

    def test_create_iam_pattern(self):
        """IAMPattern should be immutable and store pattern info."""
        pattern = IAMPattern(
            pattern="arn:aws:lambda:*:*:function:*-sentiment-*",
            policy_source=Path("ci-user-policy.tf"),
            line_number=100,
            resource_type="aws_lambda_function",
            action="lambda:InvokeFunction",
        )
        assert pattern.pattern == "arn:aws:lambda:*:*:function:*-sentiment-*"
        assert pattern.resource_type == "aws_lambda_function"


class TestCoverageReport:
    """Test CoverageReport dataclass."""

    def test_coverage_percentage_calculation(self):
        """Coverage percentage should be calculated correctly."""
        report = CoverageReport(
            total_resources=10,
            covered_resources=8,
            uncovered_resources=[],
        )
        assert report.coverage_percentage == 80.0

    def test_coverage_percentage_zero_resources(self):
        """Zero resources should return 100% coverage."""
        report = CoverageReport(
            total_resources=0,
            covered_resources=0,
        )
        assert report.coverage_percentage == 100.0

    def test_is_fully_covered_true(self):
        """is_fully_covered should be True when no uncovered resources."""
        report = CoverageReport(
            total_resources=5,
            covered_resources=5,
            uncovered_resources=[],
        )
        assert report.is_fully_covered is True

    def test_is_fully_covered_false(self):
        """is_fully_covered should be False when uncovered resources exist."""
        resource = TerraformResource(
            name="test-resource",
            resource_type="aws_lambda_function",
            module_path=Path("test.tf"),
            line_number=1,
            terraform_id="aws_lambda_function.test",
        )
        report = CoverageReport(
            total_resources=5,
            covered_resources=4,
            uncovered_resources=[resource],
        )
        assert report.is_fully_covered is False


class TestExtractIAMPatterns:
    """Test extract_iam_patterns function."""

    def test_nonexistent_path_raises(self):
        """Non-existent path should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            extract_iam_patterns(Path("/nonexistent/policy.tf"))

    def test_extract_lambda_patterns(self, tmp_path):
        """Should extract Lambda ARN patterns from policy file."""
        policy_file = tmp_path / "test-policy.tf"
        policy_file.write_text("""
resource "aws_iam_policy" "ci_user" {
  policy = jsonencode({
    Statement = [
      {
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = "arn:aws:lambda:*:*:function:*-sentiment-*"
      }
    ]
  })
}
""")
        patterns = extract_iam_patterns(policy_file)
        assert len(patterns) >= 1
        lambda_patterns = [
            p for p in patterns if p.resource_type == "aws_lambda_function"
        ]
        assert len(lambda_patterns) >= 1


class TestCheckCoverage:
    """Test check_coverage function."""

    def test_all_resources_covered_by_iam(self):
        """Every Terraform resource must have a matching IAM ARN pattern."""
        resources = [
            TerraformResource(
                name="preprod-sentiment-dashboard",
                resource_type="aws_lambda_function",
                module_path=Path("lambda/main.tf"),
                line_number=10,
                terraform_id="aws_lambda_function.dashboard",
            ),
        ]
        patterns = [
            IAMPattern(
                pattern="arn:aws:lambda:*:*:function:*-sentiment-*",
                policy_source=Path("ci-user-policy.tf"),
                line_number=100,
                resource_type="aws_lambda_function",
                action="lambda:*",
            ),
        ]

        report = check_coverage(resources, patterns)
        assert report.is_fully_covered, f"Uncovered: {report.uncovered_resources}"

    def test_no_orphaned_iam_patterns(self):
        """IAM patterns must not reference non-existent resources."""
        resources = [
            TerraformResource(
                name="preprod-sentiment-dashboard",
                resource_type="aws_lambda_function",
                module_path=Path("lambda/main.tf"),
                line_number=10,
                terraform_id="aws_lambda_function.dashboard",
            ),
        ]
        patterns = [
            IAMPattern(
                pattern="arn:aws:lambda:*:*:function:*-sentiment-*",
                policy_source=Path("ci-user-policy.tf"),
                line_number=100,
                resource_type="aws_lambda_function",
                action="lambda:*",
            ),
            IAMPattern(
                pattern="arn:aws:dynamodb:*:*:table/unused-*",
                policy_source=Path("ci-user-policy.tf"),
                line_number=200,
                resource_type="aws_dynamodb_table",
                action="dynamodb:*",
            ),
        ]

        report = check_coverage(resources, patterns)
        # One pattern should be orphaned (dynamodb pattern with no matching resources)
        assert len(report.orphaned_patterns) >= 1

    def test_wildcard_patterns_flagged(self):
        """Wildcard patterns (*) should still provide coverage."""
        resources = [
            TerraformResource(
                name="preprod-sentiment-dashboard",
                resource_type="aws_lambda_function",
                module_path=Path("lambda/main.tf"),
                line_number=10,
                terraform_id="aws_lambda_function.dashboard",
            ),
        ]
        patterns = [
            IAMPattern(
                pattern="arn:aws:lambda:*:*:function:*",
                policy_source=Path("ci-user-policy.tf"),
                line_number=100,
                resource_type="aws_lambda_function",
                action="lambda:*",
            ),
        ]

        report = check_coverage(resources, patterns)
        assert report.is_fully_covered


class TestValidateIAMCoverage:
    """Test validate_iam_coverage convenience function."""

    def test_validates_with_fixtures(self, tmp_path):
        """Should validate coverage with Terraform files."""
        # Create minimal test files
        tf_dir = tmp_path / "terraform"
        tf_dir.mkdir()

        (tf_dir / "main.tf").write_text("""
resource "aws_lambda_function" "test" {
  function_name = "preprod-sentiment-test"
}
""")

        (tf_dir / "policy.tf").write_text("""
resource "aws_iam_policy" "ci_user" {
  policy = jsonencode({
    Statement = [
      {
        Resource = "arn:aws:lambda:*:*:function:*-sentiment-*"
      }
    ]
  })
}
""")

        report = validate_iam_coverage(tf_dir, tf_dir / "policy.tf")
        assert isinstance(report, CoverageReport)

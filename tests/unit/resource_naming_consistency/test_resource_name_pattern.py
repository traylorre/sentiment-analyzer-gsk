"""Unit tests for resource naming pattern validation.

Property: resource_name_pattern
Description: All Terraform resources must use {env}-sentiment-{service} naming
             pattern where env is preprod or prod

Concern: resource_naming_consistency
Status: documented
"""

import re

import pytest

# Pattern: {env}-sentiment-{service}
# Valid envs: preprod, prod
VALID_PATTERN = re.compile(r"^(preprod|prod)-sentiment-[a-z0-9-]+$")

# Legacy pattern that should NOT be used
LEGACY_PATTERN = re.compile(r"^sentiment-analyzer-")


class TestResourceNamePattern:
    """Tests for {env}-sentiment-{service} naming convention."""

    def test_valid_preprod_name(self):
        """Preprod resource names should match pattern."""
        valid_names = [
            "preprod-sentiment-ingestion",
            "preprod-sentiment-dashboard",
            "preprod-sentiment-streaming",
            "preprod-sentiment-analysis-dlq",
        ]
        for name in valid_names:
            assert VALID_PATTERN.match(name), f"{name} should be valid"

    def test_valid_prod_name(self):
        """Prod resource names should match pattern."""
        valid_names = [
            "prod-sentiment-ingestion",
            "prod-sentiment-dashboard",
            "prod-sentiment-streaming",
        ]
        for name in valid_names:
            assert VALID_PATTERN.match(name), f"{name} should be valid"

    def test_legacy_pattern_rejected(self):
        """Legacy sentiment-analyzer-* pattern should be rejected."""
        legacy_names = [
            "sentiment-analyzer-lambda",
            "sentiment-analyzer-table",
            "sentiment-analyzer-bucket",
        ]
        for name in legacy_names:
            assert LEGACY_PATTERN.match(name), f"{name} should match legacy"
            assert not VALID_PATTERN.match(
                name
            ), f"{name} should NOT match valid pattern"

    def test_invalid_env_rejected(self):
        """Invalid environment prefixes should be rejected."""
        invalid_names = [
            "dev-sentiment-ingestion",  # dev not allowed
            "staging-sentiment-dashboard",  # staging not allowed
            "test-sentiment-streaming",  # test not allowed
        ]
        for name in invalid_names:
            assert not VALID_PATTERN.match(name), f"{name} should be rejected"

    def test_missing_sentiment_rejected(self):
        """Names without 'sentiment' segment should be rejected."""
        invalid_names = [
            "preprod-ingestion",
            "prod-dashboard",
            "preprod-analysis-lambda",
        ]
        for name in invalid_names:
            assert not VALID_PATTERN.match(name), f"{name} should be rejected"


class TestTerraformResourceNames:
    """Validate actual Terraform resource names follow the pattern.

    TODO: Implement extraction of resource names from Terraform files.
    """

    @pytest.mark.skip(reason="Validator not yet implemented - see /add-validator")
    def test_all_lambda_names_valid(self):
        """All Lambda function names should follow pattern."""
        pass

    @pytest.mark.skip(reason="Validator not yet implemented - see /add-validator")
    def test_all_dynamodb_names_valid(self):
        """All DynamoDB table names should follow pattern."""
        pass

    @pytest.mark.skip(reason="Validator not yet implemented - see /add-validator")
    def test_all_sqs_names_valid(self):
        """All SQS queue names should follow pattern."""
        pass

    @pytest.mark.skip(reason="Validator not yet implemented - see /add-validator")
    def test_all_sns_names_valid(self):
        """All SNS topic names should follow pattern."""
        pass

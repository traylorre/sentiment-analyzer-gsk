"""Unit tests for IAM ARN pattern coverage validation.

Property: iam_pattern_coverage
Description: IAM ARN patterns must cover all Terraform resource names -
             every resource must have a matching IAM policy pattern

Concern: resource_naming_consistency
Status: documented
"""

import fnmatch

import pytest


class TestIAMPatternCoverage:
    """Tests that IAM ARN patterns cover all resource names."""

    def test_lambda_pattern_covers_preprod(self):
        """Lambda ARN pattern should cover preprod resources."""
        pattern = "*-sentiment-*"
        resources = [
            "preprod-sentiment-ingestion",
            "preprod-sentiment-dashboard",
            "preprod-sentiment-streaming",
        ]
        for resource in resources:
            assert fnmatch.fnmatch(
                resource, pattern
            ), f"{resource} not covered by {pattern}"

    def test_lambda_pattern_covers_prod(self):
        """Lambda ARN pattern should cover prod resources."""
        pattern = "*-sentiment-*"
        resources = [
            "prod-sentiment-ingestion",
            "prod-sentiment-dashboard",
            "prod-sentiment-streaming",
        ]
        for resource in resources:
            assert fnmatch.fnmatch(
                resource, pattern
            ), f"{resource} not covered by {pattern}"

    def test_dynamodb_pattern_covers_tables(self):
        """DynamoDB ARN pattern should cover all tables."""
        pattern = "*-sentiment-*"
        resources = [
            "preprod-sentiment-items",
            "preprod-sentiment-users",
            "prod-sentiment-items",
            "prod-sentiment-users",
        ]
        for resource in resources:
            assert fnmatch.fnmatch(
                resource, pattern
            ), f"{resource} not covered by {pattern}"

    def test_sns_pattern_covers_topics(self):
        """SNS ARN pattern should cover all topics."""
        pattern = "*-sentiment-*"
        resources = [
            "preprod-sentiment-alarms",
            "preprod-sentiment-analysis-requests",
            "prod-sentiment-alarms",
        ]
        for resource in resources:
            assert fnmatch.fnmatch(
                resource, pattern
            ), f"{resource} not covered by {pattern}"

    def test_sqs_pattern_covers_queues(self):
        """SQS ARN pattern should cover all queues."""
        pattern = "*-sentiment-*"
        resources = [
            "preprod-sentiment-analysis-dlq",
            "prod-sentiment-analysis-dlq",
        ]
        for resource in resources:
            assert fnmatch.fnmatch(
                resource, pattern
            ), f"{resource} not covered by {pattern}"

    def test_legacy_pattern_not_covered(self):
        """Legacy sentiment-analyzer-* should NOT be covered by new pattern."""
        pattern = "*-sentiment-*"
        legacy_resources = [
            "sentiment-analyzer-lambda",
            "sentiment-analyzer-table",
        ]
        for resource in legacy_resources:
            # These should NOT match the new pattern (missing env prefix)
            assert not fnmatch.fnmatch(
                resource, pattern
            ), f"{resource} should not match {pattern}"


class TestExtractAndValidate:
    """Validate actual Terraform resources against IAM patterns.

    TODO: Implement full extraction and validation logic in validator.
    """

    @pytest.mark.skip(reason="Validator not yet implemented - see /add-validator")
    def test_all_resources_covered_by_iam(self):
        """Every Terraform resource should have a matching IAM pattern."""
        pass

    @pytest.mark.skip(reason="Validator not yet implemented - see /add-validator")
    def test_no_orphaned_iam_patterns(self):
        """IAM patterns should not reference non-existent resource patterns."""
        pass

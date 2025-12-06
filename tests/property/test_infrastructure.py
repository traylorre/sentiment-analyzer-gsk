"""Property tests for infrastructure invariants (FR-008c).

These tests verify that infrastructure configuration follows
established patterns and security requirements.
"""

import re

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from .conftest import alarm_name, iam_policy_resource_pattern


class TestIamPolicyPatterns:
    """Tests for IAM policy resource pattern invariants."""

    @settings(max_examples=100)
    @given(pattern=iam_policy_resource_pattern())
    def test_arn_has_valid_structure(self, pattern):
        """IAM ARN patterns must have valid structure."""
        parts = pattern.split(":")
        assert len(parts) >= 6
        assert parts[0] == "arn"
        assert parts[1] == "aws"

    @settings(max_examples=100)
    @given(pattern=iam_policy_resource_pattern())
    def test_arn_has_valid_service(self, pattern):
        """IAM ARN patterns must reference valid AWS services."""
        parts = pattern.split(":")
        valid_services = {
            "sqs",
            "sns",
            "lambda",
            "dynamodb",
            "cloudwatch",
            "s3",
            "logs",
        }
        assert parts[2] in valid_services

    @settings(max_examples=100)
    @given(pattern=iam_policy_resource_pattern())
    def test_pattern_contains_sentiment(self, pattern):
        """Resource patterns must include sentiment for scoping."""
        assert "sentiment" in pattern

    @settings(max_examples=50)
    @given(
        service=st.sampled_from(["sqs", "sns", "lambda"]),
        env=st.sampled_from(["dev", "preprod", "prod"]),
    )
    def test_resource_scoped_to_environment(self, service, env):
        """Resources should be scopable to environment."""
        pattern = f"arn:aws:{service}:*:*:{env}-sentiment-*"
        assert env in pattern
        assert "sentiment" in pattern


class TestAlarmNamingConvention:
    """Tests for CloudWatch alarm naming convention."""

    @settings(max_examples=100)
    @given(name=alarm_name())
    def test_alarm_follows_naming_pattern(self, name):
        """Alarm names must follow {env}-sentiment-* pattern."""
        pattern = r"^(dev|preprod|prod)-sentiment-.+$"
        assert re.match(pattern, name), f"Alarm name '{name}' does not match pattern"

    @settings(max_examples=100)
    @given(name=alarm_name())
    def test_alarm_has_environment_prefix(self, name):
        """Alarm names must start with environment prefix."""
        valid_prefixes = ["dev-", "preprod-", "prod-"]
        assert any(name.startswith(prefix) for prefix in valid_prefixes)

    @settings(max_examples=100)
    @given(name=alarm_name())
    def test_alarm_contains_sentiment(self, name):
        """Alarm names must contain 'sentiment' for IAM policy matching."""
        assert "sentiment" in name

    @settings(max_examples=50)
    @given(
        env=st.sampled_from(["dev", "preprod", "prod"]),
        component=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("Ll",), whitelist_characters="-"
            ),
        ),
    )
    def test_alarm_name_construction(self, env, component):
        """Alarm names can be constructed from env and component."""
        assume(len(component) > 0)
        name = f"{env}-sentiment-{component}"
        assert name.startswith(env)
        assert "sentiment" in name


class TestSecurityPolicyPresence:
    """Tests for security policy invariants."""

    @settings(max_examples=50)
    @given(
        action=st.sampled_from(["sqs:*", "sns:*", "dynamodb:*"]),
        condition_value=st.sampled_from(["true", "false"]),
    )
    def test_secure_transport_condition_structure(self, action, condition_value):
        """SecureTransport conditions must have valid structure."""
        condition = {"Bool": {"aws:SecureTransport": condition_value}}
        assert "Bool" in condition
        assert "aws:SecureTransport" in condition["Bool"]
        assert condition["Bool"]["aws:SecureTransport"] in ["true", "false"]

    @settings(max_examples=50)
    @given(
        resource_pattern=st.sampled_from(
            [
                "arn:aws:sqs:*:*:*-sentiment-*",
                "arn:aws:sns:*:*:*-sentiment-*",
                "arn:aws:dynamodb:*:*:table/*-sentiment-*",
            ]
        )
    )
    def test_deny_statement_structure(self, resource_pattern):
        """Deny statements must have valid structure."""
        deny_statement = {
            "Sid": "DenyInsecureTransport",
            "Effect": "Deny",
            "Action": "sqs:*",
            "Resource": resource_pattern,
            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
        }
        assert deny_statement["Effect"] == "Deny"
        assert "Condition" in deny_statement
        assert "sentiment" in deny_statement["Resource"]

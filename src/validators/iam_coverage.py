"""IAM coverage validation for Terraform resources.

Validates that every Terraform resource has corresponding IAM ARN pattern
coverage in the CI user policy.

Feature: 075-validation-gaps
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.validators.resource_naming import TerraformResource, extract_resources


@dataclass(frozen=True)
class IAMPattern:
    """Represents an IAM ARN pattern extracted from policy files.

    Attributes:
        pattern: The ARN pattern (e.g., "arn:aws:lambda:*:*:function:*-sentiment-*")
        policy_source: Path to the policy file
        line_number: Line number in the file
        resource_type: AWS resource type this pattern covers
        action: IAM action this pattern is associated with
    """

    pattern: str
    policy_source: Path
    line_number: int
    resource_type: str
    action: str


@dataclass
class CoverageReport:
    """Report of IAM coverage for Terraform resources.

    Attributes:
        total_resources: Total number of resources checked
        covered_resources: Number of resources with IAM coverage
        uncovered_resources: Resources without IAM pattern coverage
        total_patterns: Total number of IAM patterns found
        active_patterns: Number of patterns that match at least one resource
        orphaned_patterns: Patterns that don't match any resource
        exemptions_applied: Number of exemptions from iam-allowlist.yaml
    """

    total_resources: int
    covered_resources: int
    uncovered_resources: list[TerraformResource] = field(default_factory=list)
    total_patterns: int = 0
    active_patterns: int = 0
    orphaned_patterns: list[IAMPattern] = field(default_factory=list)
    exemptions_applied: int = 0

    @property
    def coverage_percentage(self) -> float:
        """Calculate coverage percentage.

        Returns:
            Percentage of resources covered (0.0 to 100.0)
        """
        if self.total_resources == 0:
            return 100.0
        return (self.covered_resources / self.total_resources) * 100

    @property
    def is_fully_covered(self) -> bool:
        """Check if all resources have IAM coverage.

        Returns:
            True if no uncovered resources, False otherwise
        """
        return len(self.uncovered_resources) == 0


# Resource type to ARN service mapping
RESOURCE_TYPE_TO_SERVICE = {
    "aws_lambda_function": "lambda",
    "aws_dynamodb_table": "dynamodb",
    "aws_sqs_queue": "sqs",
    "aws_sns_topic": "sns",
}


def extract_iam_patterns(policy_path: Path) -> list[IAMPattern]:
    """Extract ARN patterns from IAM policy files.

    Parses Terraform .tf files or JSON policy files to extract Resource
    ARN patterns from IAM policy statements.

    Args:
        policy_path: Path to IAM policy file (.tf or .json)

    Returns:
        List of IAMPattern objects

    Raises:
        FileNotFoundError: If policy_path doesn't exist
    """
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file does not exist: {policy_path}")

    content = policy_path.read_text()
    patterns: list[IAMPattern] = []

    # Pattern to match ARN patterns in Resource blocks
    arn_pattern = re.compile(
        r'"(arn:aws:(lambda|dynamodb|sqs|sns):[^"]*)"', re.MULTILINE
    )

    for match in arn_pattern.finditer(content):
        arn = match.group(1)
        service = match.group(2)
        line_number = content[: match.start()].count("\n") + 1

        # Map service to resource type
        resource_type = (
            f"aws_{service}_function" if service == "lambda" else f"aws_{service}_table"
        )
        if service == "sqs":
            resource_type = "aws_sqs_queue"
        elif service == "sns":
            resource_type = "aws_sns_topic"
        elif service == "lambda":
            resource_type = "aws_lambda_function"
        elif service == "dynamodb":
            resource_type = "aws_dynamodb_table"

        patterns.append(
            IAMPattern(
                pattern=arn,
                policy_source=policy_path,
                line_number=line_number,
                resource_type=resource_type,
                action="*",  # Simplified - in reality would parse the Action block
            )
        )

    return patterns


def check_coverage(
    resources: list[TerraformResource],
    patterns: list[IAMPattern],
    exemptions_path: Path | None = None,
) -> CoverageReport:
    """Check IAM coverage for all resources.

    For each resource, checks if there's an IAM ARN pattern that would
    allow operations on that resource.

    Args:
        resources: List of TerraformResource to check
        patterns: List of IAMPattern to match against
        exemptions_path: Optional path to iam-allowlist.yaml

    Returns:
        CoverageReport with coverage statistics and gaps
    """
    exemptions = _load_exemptions(exemptions_path) if exemptions_path else set()

    covered_resources: list[TerraformResource] = []
    uncovered_resources: list[TerraformResource] = []
    active_patterns: set[IAMPattern] = set()
    exemptions_applied = 0

    for resource in resources:
        # Check if resource is exempted
        if resource.terraform_id in exemptions:
            covered_resources.append(resource)
            exemptions_applied += 1
            continue

        # Check if any pattern covers this resource
        is_covered = False
        for pattern in patterns:
            if _arn_pattern_matches(pattern, resource):
                is_covered = True
                active_patterns.add(pattern)
                break

        if is_covered:
            covered_resources.append(resource)
        else:
            uncovered_resources.append(resource)

    # Find orphaned patterns (don't match any resource)
    orphaned_patterns = [p for p in patterns if p not in active_patterns]

    return CoverageReport(
        total_resources=len(resources),
        covered_resources=len(covered_resources),
        uncovered_resources=uncovered_resources,
        total_patterns=len(patterns),
        active_patterns=len(active_patterns),
        orphaned_patterns=orphaned_patterns,
        exemptions_applied=exemptions_applied,
    )


def _arn_pattern_matches(pattern: IAMPattern, resource: TerraformResource) -> bool:
    """Check if an IAM ARN pattern matches a resource.

    Converts IAM wildcard patterns (* and ?) to regex and checks if
    the resource name would be covered.

    Args:
        pattern: IAMPattern to check
        resource: TerraformResource to match

    Returns:
        True if pattern covers resource, False otherwise
    """
    # Resource types must be compatible
    if pattern.resource_type != resource.resource_type:
        return False

    # Convert IAM wildcard pattern to regex
    # * matches any characters, ? matches single character
    arn = pattern.pattern

    # Extract the resource name portion from the ARN pattern
    # e.g., "arn:aws:lambda:*:*:function:*-sentiment-*" -> "*-sentiment-*"
    parts = arn.split(":")
    if len(parts) < 6:
        return False

    # Get the last part which contains the resource name pattern
    name_pattern = parts[-1]

    # Convert to regex
    regex_pattern = name_pattern.replace("*", ".*").replace("?", ".")
    regex_pattern = f"^{regex_pattern}$"

    try:
        return bool(re.match(regex_pattern, resource.name))
    except re.error:
        return False


def _load_exemptions(exemptions_path: Path) -> set[str]:
    """Load exemptions from iam-allowlist.yaml.

    Args:
        exemptions_path: Path to iam-allowlist.yaml

    Returns:
        Set of terraform_id strings that are exempted
    """
    if not exemptions_path.exists():
        return set()

    try:
        with open(exemptions_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return set()

    exemptions: set[str] = set()

    # Extract terraform_ids from suppressions
    for suppression in data.get("suppressions", []):
        terraform_id = suppression.get("terraform_id")
        if terraform_id:
            exemptions.add(terraform_id)

    return exemptions


def validate_iam_coverage(
    terraform_path: Path,
    policy_path: Path,
    exemptions_path: Path | None = None,
) -> CoverageReport:
    """Validate IAM coverage for all resources in a Terraform directory.

    Convenience function that combines extract_resources, extract_iam_patterns,
    and check_coverage.

    Args:
        terraform_path: Path to Terraform directory with resources
        policy_path: Path to IAM policy file
        exemptions_path: Optional path to iam-allowlist.yaml

    Returns:
        CoverageReport with coverage statistics
    """
    resources = extract_resources(terraform_path)
    patterns = extract_iam_patterns(policy_path)
    return check_coverage(resources, patterns, exemptions_path)

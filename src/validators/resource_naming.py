"""Resource naming validation for Terraform resources.

Validates that AWS resources follow the naming pattern:
    {env}-sentiment-{service}

Where env is 'preprod' or 'prod' and service is lowercase alphanumeric with hyphens.

Feature: 075-validation-gaps
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import hcl2


class ValidationStatus(Enum):
    """Status of a validation check."""

    PASSED = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True)
class TerraformResource:
    """Represents a Terraform resource extracted from HCL files.

    Attributes:
        name: The resource's name attribute value (e.g., "preprod-sentiment-dashboard")
        resource_type: AWS resource type (e.g., "aws_lambda_function")
        module_path: Path to the .tf file containing this resource
        line_number: Line number in the file where resource is defined
        terraform_id: Terraform resource identifier (e.g., "aws_lambda_function.dashboard")
    """

    name: str
    resource_type: str
    module_path: Path
    line_number: int
    terraform_id: str


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a single resource.

    Attributes:
        status: PASS, FAIL, or SKIP
        resource: The TerraformResource that was validated
        message: Human-readable description of the result
        pattern_matched: The regex pattern that matched (for PASS) or was expected (for FAIL)
    """

    status: ValidationStatus
    resource: TerraformResource
    message: str
    pattern_matched: str | None = None


# Pattern constants
NAMING_PATTERN = re.compile(r"^(preprod|prod)-sentiment-[a-z0-9-]+$")
LEGACY_PATTERN = re.compile(r"^sentiment-analyzer-.*$")

# AWS resource types that should be validated
VALIDATED_RESOURCE_TYPES = frozenset(
    {
        "aws_lambda_function",
        "aws_dynamodb_table",
        "aws_sqs_queue",
        "aws_sns_topic",
    }
)


def extract_resources(terraform_path: Path) -> list[TerraformResource]:
    """Extract AWS resources from Terraform HCL files.

    Parses all .tf files in the given directory and extracts Lambda, DynamoDB,
    SQS, and SNS resources.

    Args:
        terraform_path: Path to Terraform directory

    Returns:
        List of TerraformResource objects for Lambda, DynamoDB, SQS, SNS

    Raises:
        FileNotFoundError: If terraform_path doesn't exist
        ValueError: If no .tf files found
    """
    if not terraform_path.exists():
        raise FileNotFoundError(f"Terraform path does not exist: {terraform_path}")

    tf_files = list(terraform_path.glob("**/*.tf"))
    if not tf_files:
        raise ValueError(f"No .tf files found in: {terraform_path}")

    resources: list[TerraformResource] = []

    for tf_file in tf_files:
        resources.extend(_extract_from_file(tf_file))

    return resources


def _extract_from_file(tf_file: Path) -> list[TerraformResource]:
    """Extract resources from a single Terraform file.

    Args:
        tf_file: Path to a .tf file

    Returns:
        List of TerraformResource objects
    """
    resources: list[TerraformResource] = []

    try:
        with open(tf_file) as f:
            parsed = hcl2.load(f)
    except Exception:
        # Fall back to regex parsing for files hcl2 can't handle
        return _extract_with_regex(tf_file)

    # HCL2 returns a dict with 'resource' key containing list of resource blocks
    resource_blocks = parsed.get("resource", [])

    for block in resource_blocks:
        # Each block is a dict like {"aws_lambda_function": {"dashboard": {...}}}
        for resource_type, instances in block.items():
            if resource_type not in VALIDATED_RESOURCE_TYPES:
                continue

            for instance_name, config in instances.items():
                # Skip internal metadata keys
                if instance_name.startswith("__"):
                    continue

                # Extract the 'name' attribute if it exists
                name = _extract_name_attribute(config, resource_type)
                if name:
                    # Get line number from hcl2 metadata if available
                    line_number = config.get("__start_line__", 1)
                    resources.append(
                        TerraformResource(
                            name=name,
                            resource_type=resource_type,
                            module_path=tf_file,
                            line_number=line_number,
                            terraform_id=f"{resource_type}.{instance_name}",
                        )
                    )

    return resources


def _extract_name_attribute(config: dict, resource_type: str) -> str | None:
    """Extract the name attribute from a resource config.

    Different resource types use different attribute names:
    - aws_lambda_function: function_name
    - aws_dynamodb_table: name
    - aws_sqs_queue: name
    - aws_sns_topic: name

    Args:
        config: Resource configuration dict
        resource_type: AWS resource type

    Returns:
        Name value or None if not found
    """
    name_attrs = {
        "aws_lambda_function": "function_name",
        "aws_dynamodb_table": "name",
        "aws_sqs_queue": "name",
        "aws_sns_topic": "name",
    }

    attr = name_attrs.get(resource_type, "name")
    name = config.get(attr)

    # hcl2 returns values as lists - extract the first element
    if isinstance(name, list) and len(name) > 0:
        name = name[0]

    # Handle Terraform interpolations like "${var.environment}-sentiment-dashboard"
    if isinstance(name, str) and "${" in name:
        # Resolve simple var.environment references
        name = re.sub(r"\$\{var\.environment\}", "preprod", name)

    return name if isinstance(name, str) else None


def _extract_with_regex(tf_file: Path) -> list[TerraformResource]:
    """Fallback regex extraction for files hcl2 can't parse.

    Args:
        tf_file: Path to a .tf file

    Returns:
        List of TerraformResource objects
    """
    resources: list[TerraformResource] = []
    content = tf_file.read_text()

    # Pattern to match resource blocks
    resource_pattern = re.compile(
        r'resource\s+"(aws_(?:lambda_function|dynamodb_table|sqs_queue|sns_topic))"\s+"(\w+)"',
        re.MULTILINE,
    )

    # Pattern to match name attributes
    name_patterns = {
        "aws_lambda_function": re.compile(r'function_name\s*=\s*"([^"]+)"'),
        "aws_dynamodb_table": re.compile(r'name\s*=\s*"([^"]+)"'),
        "aws_sqs_queue": re.compile(r'name\s*=\s*"([^"]+)"'),
        "aws_sns_topic": re.compile(r'name\s*=\s*"([^"]+)"'),
    }

    for match in resource_pattern.finditer(content):
        resource_type = match.group(1)
        instance_name = match.group(2)
        line_number = content[: match.start()].count("\n") + 1

        # Find the name attribute after this resource declaration
        name_pattern = name_patterns.get(resource_type)
        if name_pattern:
            name_match = name_pattern.search(content, match.end())
            if name_match:
                name = name_match.group(1)
                # Resolve Terraform interpolations
                name = re.sub(r"\$\{var\.environment\}", "preprod", name)

                resources.append(
                    TerraformResource(
                        name=name,
                        resource_type=resource_type,
                        module_path=tf_file,
                        line_number=line_number,
                        terraform_id=f"{resource_type}.{instance_name}",
                    )
                )

    return resources


def validate_naming_pattern(resource: TerraformResource) -> ValidationResult:
    """Validate a single resource against naming conventions.

    Checks that the resource name matches the pattern:
        ^(preprod|prod)-sentiment-[a-z0-9-]+$

    Also detects and rejects legacy naming patterns like:
        ^sentiment-analyzer-.*$

    Args:
        resource: TerraformResource to validate

    Returns:
        ValidationResult with PASS, FAIL, or SKIP status
    """
    name = resource.name

    # Check for valid naming pattern
    if NAMING_PATTERN.match(name):
        return ValidationResult(
            status=ValidationStatus.PASSED,
            resource=resource,
            message=f"Resource '{name}' follows naming convention",
            pattern_matched=NAMING_PATTERN.pattern,
        )

    # Check for legacy naming (specific failure message)
    if LEGACY_PATTERN.match(name):
        return ValidationResult(
            status=ValidationStatus.FAIL,
            resource=resource,
            message=f"Resource '{name}' uses legacy naming pattern. "
            f"Expected: {{env}}-sentiment-{{service}}",
            pattern_matched=LEGACY_PATTERN.pattern,
        )

    # Generic failure for other non-matching patterns
    return ValidationResult(
        status=ValidationStatus.FAIL,
        resource=resource,
        message=f"Resource '{name}' does not match naming convention. "
        f"Expected pattern: (preprod|prod)-sentiment-<service>",
        pattern_matched=None,
    )


def validate_all_resources(terraform_path: Path) -> list[ValidationResult]:
    """Validate all resources in a Terraform directory.

    Extracts all Lambda, DynamoDB, SQS, and SNS resources and validates
    their names against the naming convention.

    Args:
        terraform_path: Path to Terraform directory

    Returns:
        List of ValidationResult objects, one per resource
    """
    resources = extract_resources(terraform_path)
    return [validate_naming_pattern(resource) for resource in resources]

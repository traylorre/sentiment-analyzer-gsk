"""Validation utilities for Terraform resources and IAM policies.

Feature: 075-validation-gaps
"""

from src.validators.iam_coverage import (
    CoverageReport,
    IAMPattern,
    check_coverage,
    extract_iam_patterns,
    validate_iam_coverage,
)
from src.validators.resource_naming import (
    LEGACY_PATTERN,
    NAMING_PATTERN,
    TerraformResource,
    ValidationResult,
    ValidationStatus,
    extract_resources,
    validate_all_resources,
    validate_naming_pattern,
)

__all__ = [
    # Resource naming
    "TerraformResource",
    "ValidationStatus",
    "ValidationResult",
    "NAMING_PATTERN",
    "LEGACY_PATTERN",
    "extract_resources",
    "validate_naming_pattern",
    "validate_all_resources",
    # IAM coverage
    "IAMPattern",
    "CoverageReport",
    "extract_iam_patterns",
    "check_coverage",
    "validate_iam_coverage",
]

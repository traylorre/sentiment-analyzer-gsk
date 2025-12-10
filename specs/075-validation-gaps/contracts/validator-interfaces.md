# Validator Interfaces Contract

**Feature**: 075-validation-gaps
**Date**: 2025-12-09

## Resource Naming Validator Interface

### Module: `src/validators/resource_naming.py`

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

class ValidationStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"

@dataclass(frozen=True)
class TerraformResource:
    name: str
    resource_type: str
    module_path: Path
    line_number: int
    terraform_id: str

@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    resource: TerraformResource
    message: str
    pattern_matched: str | None = None

def extract_resources(terraform_path: Path) -> list[TerraformResource]:
    """Extract AWS resources from Terraform HCL files.

    Args:
        terraform_path: Path to Terraform directory

    Returns:
        List of TerraformResource objects for Lambda, DynamoDB, SQS, SNS

    Raises:
        FileNotFoundError: If terraform_path doesn't exist
        ValueError: If no .tf files found
    """
    ...

def validate_naming_pattern(resource: TerraformResource) -> ValidationResult:
    """Validate a single resource against naming conventions.

    Args:
        resource: TerraformResource to validate

    Returns:
        ValidationResult with PASS, FAIL, or SKIP status

    Pattern: ^(preprod|prod)-sentiment-[a-z0-9-]+$
    """
    ...

def validate_all_resources(terraform_path: Path) -> list[ValidationResult]:
    """Validate all resources in a Terraform directory.

    Args:
        terraform_path: Path to Terraform directory

    Returns:
        List of ValidationResult objects, one per resource
    """
    ...
```

## IAM Coverage Validator Interface

### Module: `src/validators/iam_coverage.py`

```python
from dataclasses import dataclass
from pathlib import Path
from src.validators.resource_naming import TerraformResource

@dataclass(frozen=True)
class IAMPattern:
    pattern: str
    policy_source: Path
    line_number: int
    resource_type: str
    action: str

@dataclass
class CoverageReport:
    total_resources: int
    covered_resources: int
    uncovered_resources: list[TerraformResource]
    total_patterns: int
    active_patterns: int
    orphaned_patterns: list[IAMPattern]
    exemptions_applied: int

    @property
    def coverage_percentage(self) -> float: ...

    @property
    def is_fully_covered(self) -> bool: ...

def extract_iam_patterns(policy_path: Path) -> list[IAMPattern]:
    """Extract ARN patterns from IAM policy files.

    Args:
        policy_path: Path to IAM policy file (.tf or .json)

    Returns:
        List of IAMPattern objects

    Raises:
        FileNotFoundError: If policy_path doesn't exist
    """
    ...

def check_coverage(
    resources: list[TerraformResource],
    patterns: list[IAMPattern],
    exemptions_path: Path | None = None
) -> CoverageReport:
    """Check IAM coverage for all resources.

    Args:
        resources: List of TerraformResource to check
        patterns: List of IAMPattern to match against
        exemptions_path: Optional path to iam-allowlist.yaml

    Returns:
        CoverageReport with coverage statistics and gaps
    """
    ...
```

## JWT Validation Interface

### Module: `src/lambdas/shared/middleware/auth_middleware.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class JWTClaim:
    subject: str
    expiration: datetime
    issued_at: datetime
    issuer: str | None = None

@dataclass(frozen=True)
class JWTConfig:
    secret: str
    algorithm: str = "HS256"
    issuer: str | None = "sentiment-analyzer"
    leeway_seconds: int = 60
    access_token_lifetime_seconds: int = 900

def validate_jwt(token: str, config: JWTConfig | None = None) -> JWTClaim | None:
    """Validate a JWT token and extract claims.

    Args:
        token: JWT token string (without "Bearer " prefix)
        config: Optional JWTConfig, uses environment if not provided

    Returns:
        JWTClaim if valid, None if invalid

    Environment:
        JWT_SECRET: Required secret key for validation
    """
    ...

def extract_user_id(event: dict[str, Any]) -> str | None:
    """Extract user ID from Lambda event headers.

    Supports:
    1. UUID tokens (anonymous sessions)
    2. JWT tokens (authenticated sessions)
    3. X-User-ID header (legacy)

    Args:
        event: Lambda event dict with headers

    Returns:
        User ID string if found and valid, None otherwise
    """
    ...
```

## Test Contracts

### Resource Naming Tests

```python
# tests/unit/validators/test_resource_naming.py

def test_all_lambda_names_valid():
    """All Lambda function names must match {env}-sentiment-{name}."""
    ...

def test_all_dynamodb_names_valid():
    """All DynamoDB table names must match {env}-sentiment-{name}."""
    ...

def test_all_sqs_names_valid():
    """All SQS queue names must match {env}-sentiment-{name}."""
    ...

def test_all_sns_names_valid():
    """All SNS topic names must match {env}-sentiment-{name}."""
    ...
```

### IAM Coverage Tests

```python
# tests/unit/validators/test_iam_coverage.py

def test_all_resources_covered_by_iam():
    """Every Terraform resource must have a matching IAM ARN pattern."""
    ...

def test_no_orphaned_iam_patterns():
    """IAM patterns must not reference non-existent resources."""
    ...
```

### JWT Validation Tests

```python
# tests/unit/middleware/test_jwt_validation.py

def test_valid_jwt_token():
    """Valid JWT tokens should return JWTClaim with correct subject."""
    ...

def test_expired_jwt_token():
    """Expired JWT tokens should return None."""
    ...

def test_malformed_jwt_token():
    """Malformed JWT tokens should return None."""
    ...

def test_invalid_signature():
    """JWT tokens with invalid signatures should return None."""
    ...

def test_missing_required_claims():
    """JWT tokens missing sub/exp/iat should return None."""
    ...

def test_jwt_performance_benchmark():
    """1000 JWT validations should complete in <1 second."""
    ...
```

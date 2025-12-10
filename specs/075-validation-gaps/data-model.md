# Data Model: Close Validation Gaps

**Feature**: 075-validation-gaps
**Date**: 2025-12-09
**Status**: Complete

## Overview

This feature introduces internal data structures for validators and extends the auth middleware. No persistent storage changes required.

## Part A: Resource Naming Validator Entities

### TerraformResource

Represents an infrastructure resource extracted from Terraform HCL files.

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class TerraformResource:
    """A resource extracted from Terraform configuration."""

    name: str
    """Resource name (e.g., 'preprod-sentiment-items')"""

    resource_type: str
    """AWS resource type (e.g., 'aws_dynamodb_table', 'aws_lambda_function')"""

    module_path: Path
    """Path to the Terraform file containing this resource"""

    line_number: int
    """Line number where the resource is defined"""

    terraform_id: str
    """Full Terraform resource identifier (e.g., 'aws_dynamodb_table.sentiment_items')"""
```

### ValidationResult

Result of validating a single resource against naming conventions.

```python
from dataclasses import dataclass
from enum import Enum

class ValidationStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"  # For exempted resources

@dataclass(frozen=True)
class ValidationResult:
    """Result of naming pattern validation."""

    status: ValidationStatus
    resource: TerraformResource
    message: str
    pattern_matched: str | None = None  # Which pattern matched (if PASS)
```

## Part B: IAM Coverage Validator Entities

### IAMPattern

Represents an ARN pattern extracted from IAM policy documents.

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class IAMPattern:
    """An ARN pattern from an IAM policy."""

    pattern: str
    """ARN pattern string (e.g., 'arn:aws:lambda:*:*:function:*-sentiment-*')"""

    policy_source: Path
    """Path to the policy file"""

    line_number: int
    """Line number where the pattern appears"""

    resource_type: str
    """Inferred resource type (lambda, dynamodb, sqs, sns, etc.)"""

    action: str
    """IAM action this pattern applies to (e.g., 'lambda:InvokeFunction')"""
```

### CoverageReport

Aggregated result of IAM coverage analysis.

```python
from dataclasses import dataclass

@dataclass
class CoverageReport:
    """Result of IAM coverage analysis."""

    total_resources: int
    covered_resources: int
    uncovered_resources: list[TerraformResource]

    total_patterns: int
    active_patterns: int
    orphaned_patterns: list[IAMPattern]

    exemptions_applied: int

    @property
    def coverage_percentage(self) -> float:
        if self.total_resources == 0:
            return 100.0
        return (self.covered_resources / self.total_resources) * 100

    @property
    def is_fully_covered(self) -> bool:
        return len(self.uncovered_resources) == 0
```

## Part C: JWT Authentication Entities

### JWTClaim

Validated claims extracted from a JWT token.

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class JWTClaim:
    """Validated claims from a JWT token."""

    subject: str
    """User ID (from 'sub' claim)"""

    expiration: datetime
    """Token expiration time (from 'exp' claim)"""

    issued_at: datetime
    """Token issue time (from 'iat' claim)"""

    issuer: str | None = None
    """Token issuer (from 'iss' claim, optional)"""
```

### JWTConfig

Configuration for JWT validation (loaded at startup).

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class JWTConfig:
    """JWT validation configuration."""

    secret: str
    """Secret key for HS256 validation"""

    algorithm: str = "HS256"
    """JWT algorithm (only HS256 supported)"""

    issuer: str | None = "sentiment-analyzer"
    """Expected issuer (None to skip issuer validation)"""

    leeway_seconds: int = 60
    """Clock skew tolerance for exp/iat validation"""

    access_token_lifetime_seconds: int = 900
    """Access token lifetime (15 minutes)"""
```

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                    Validation Flow                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Terraform Files                                                 │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────┐     ┌───────────────────┐                 │
│  │ TerraformResource │────▶│ ValidationResult  │                 │
│  └──────────────────┘     └───────────────────┘                 │
│       │                          │                               │
│       │                          │                               │
│       ▼                          ▼                               │
│  ┌──────────────────┐     ┌───────────────────┐                 │
│  │   IAMPattern     │────▶│  CoverageReport   │                 │
│  └──────────────────┘     └───────────────────┘                 │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                    Auth Flow                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Authorization Header                                            │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────┐     ┌───────────────────┐                 │
│  │   JWT Token      │────▶│    JWTClaim       │                 │
│  └──────────────────┘     └───────────────────┘                 │
│       │                          │                               │
│       │ (if UUID)                │ (if JWT)                      │
│       ▼                          ▼                               │
│  ┌──────────────────────────────────────────┐                   │
│  │              user_id: str                 │                   │
│  └──────────────────────────────────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Validation Rules

### Resource Naming Rules

| Rule ID | Description | Regex Pattern |
|---------|-------------|---------------|
| RN-001 | Standard naming | `^(preprod\|prod)-sentiment-[a-z0-9-]+$` |
| RN-002 | Legacy naming (reject) | `^sentiment-analyzer-.*$` |
| RN-003 | Missing env prefix (reject) | `^sentiment-[a-z0-9-]+$` |

### JWT Validation Rules

| Rule ID | Description | Implementation |
|---------|-------------|----------------|
| JWT-001 | Valid signature | PyJWT decode with secret |
| JWT-002 | Not expired | exp > current_time - leeway |
| JWT-003 | Valid structure | Contains sub, exp, iat |
| JWT-004 | Algorithm whitelist | Only HS256 accepted |

## No Database Changes

This feature does not modify any database schemas:
- Validators operate on files only
- JWT validation is stateless (no token storage)
- All data structures are in-memory during validation

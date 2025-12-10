# Implementation Plan: Close Validation Gaps - Resource Naming Validators & JWT Auth

**Branch**: `075-validation-gaps` | **Date**: 2025-12-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/075-validation-gaps/spec.md`

## Summary

Close 7 easily-closeable validation gaps: 6 skipped resource naming validator tests and 1 JWT authentication TODO. This involves implementing Terraform resource extraction and IAM pattern cross-referencing validators, plus adding PyJWT-based token validation to the existing auth middleware.

## Technical Context

**Language/Version**: Python 3.13 (Lambda runtime)
**Primary Dependencies**: pytest, python-hcl2 (Terraform parsing), PyJWT
**Storage**: N/A (validation operates on files)
**Testing**: pytest with moto, hypothesis for property testing
**Target Platform**: Linux (CI/CD pipeline)
**Project Type**: Single project
**Performance Goals**: Validators complete in <5 seconds, JWT validation 1000+ tokens/sec
**Constraints**: No new nosec/noqa suppressions
**Scale/Scope**: ~50 Terraform files, ~20 IAM policy files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Unit tests accompany all implementation (Section 7: Testing & Validation)
- [x] No pipeline bypasses - all changes must pass CI/CD (Section 8: Git Workflow)
- [x] Security: JWT secret from environment/secrets manager, not source control (Section 3)
- [x] GPG-signed commits required (Section 8)
- [x] No direct pushes to main - feature branch workflow (Section 8)
- [x] 80% coverage minimum for new code (Section 7)

## Project Structure

### Documentation (this feature)

```text
specs/075-validation-gaps/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── lambdas/
│   └── shared/
│       └── middleware/
│           └── auth_middleware.py  # JWT validation (FR-007 to FR-012)
└── validators/
    ├── resource_naming.py          # FR-001 to FR-003 (new)
    └── iam_coverage.py             # FR-004 to FR-006 (new)

tests/
├── unit/
│   ├── resource_naming_consistency/
│   │   ├── test_resource_name_pattern.py  # Unskip 4 tests
│   │   └── test_iam_pattern_coverage.py   # Unskip 2 tests
│   └── middleware/
│       └── test_jwt_validation.py         # New JWT tests
└── fixtures/
    └── terraform/                         # Test Terraform files
```

**Structure Decision**: Single project structure - validators are internal tools for CI validation, not a separate package.

## Phase 0: Research

### Part A: Resource Naming Validators

**Current State Analysis**:
- Terraform modules use `${var.environment}-sentiment-{service}` naming pattern
- DynamoDB: `preprod-sentiment-items`, `preprod-sentiment-users`, `preprod-chaos-experiments`
- Lambda: Names passed via `function_name` variable from root module
- IAM policies in `ci-user-policy.tf` use ARN patterns like `arn:aws:lambda:*:*:function:*-sentiment-*`

**Terraform Parsing Options**:
1. **python-hcl2** (recommended): Parse HCL2 syntax natively, extract resource blocks
2. **regex parsing**: Brittle, doesn't handle nested blocks
3. **terraform show -json**: Requires Terraform init, slow for validation

**Decision**: Use python-hcl2 for static parsing - no Terraform state required, fast execution.

**Resource Name Extraction Strategy**:
```python
# Pattern: Extract from resource "aws_xxx" blocks
# Lambda: aws_lambda_function.this.function_name → var.function_name → resolve
# DynamoDB: aws_dynamodb_table.xxx.name → "${var.environment}-sentiment-xxx"
# SQS: aws_sqs_queue.xxx.name
# SNS: aws_sns_topic.xxx.name
```

### Part B: IAM Coverage Validation

**IAM Pattern Sources**:
- `infrastructure/terraform/ci-user-policy.tf` - Main CI/CD permissions
- `infrastructure/terraform/modules/iam/main.tf` - Lambda execution roles
- `iam-allowlist.yaml` - Exempted patterns (already documented)

**Cross-Reference Algorithm**:
1. Extract all resource names from Terraform (Lambda, DynamoDB, SQS, SNS)
2. Extract all ARN patterns from IAM policies
3. For each resource: verify at least one IAM pattern matches
4. For each IAM pattern: verify at least one resource matches (detect orphans)

### Part C: JWT Authentication

**Current Implementation** (`auth_middleware.py:57-80`):
- Accepts UUID tokens as user IDs directly
- TODO at line 75: "Add JWT validation for authenticated sessions"

**JWT Library Options**:
1. **PyJWT** (recommended): Standard library, minimal dependencies, fast
2. **python-jose**: More features (JWE), heavier
3. **authlib**: Full OAuth, overkill for this use case

**Decision**: Use PyJWT - simple, well-maintained, Lambda-compatible size.

**JWT Structure (per clarification)**:
- Access token: 15-minute expiration
- Refresh token: Longer expiration (handled separately)
- Claims: `sub` (user_id), `exp`, `iat`, `iss`

**Secret Management**:
- Environment variable: `JWT_SECRET` (from AWS Secrets Manager via Lambda config)
- Algorithm: HS256 (symmetric, simple) or RS256 (asymmetric, for JWKS)

## Phase 1: Design

### Part A: Resource Naming Validator (`src/validators/resource_naming.py`)

```python
# Key entities
@dataclass
class TerraformResource:
    name: str           # e.g., "preprod-sentiment-items"
    type: str           # e.g., "aws_dynamodb_table"
    module_path: str    # e.g., "modules/dynamodb/main.tf"
    line_number: int

@dataclass
class ValidationResult:
    passed: bool
    resource: TerraformResource
    message: str

# Main interface
def extract_resources(terraform_path: Path) -> list[TerraformResource]:
    """Extract Lambda, DynamoDB, SQS, SNS resources from Terraform files."""

def validate_naming_pattern(resource: TerraformResource) -> ValidationResult:
    """Validate resource name matches {env}-sentiment-{service} pattern."""

def validate_all_resources(terraform_path: Path) -> list[ValidationResult]:
    """Run naming validation on all resources."""
```

**Naming Pattern Regex**: `^(preprod|prod)-sentiment-[a-z0-9-]+$`
**Legacy Pattern (reject)**: `^sentiment-analyzer-.*$`

### Part B: IAM Coverage Validator (`src/validators/iam_coverage.py`)

```python
@dataclass
class IAMPattern:
    pattern: str        # ARN pattern string
    policy_source: str  # e.g., "ci-user-policy.tf:123"
    resource_type: str  # e.g., "lambda", "dynamodb"

def extract_iam_patterns(policy_path: Path) -> list[IAMPattern]:
    """Extract ARN patterns from IAM policy files."""

def check_coverage(
    resources: list[TerraformResource],
    patterns: list[IAMPattern]
) -> tuple[list[TerraformResource], list[IAMPattern]]:
    """Return (uncovered_resources, orphaned_patterns)."""
```

### Part C: JWT Validator (`auth_middleware.py` update)

```python
# New imports
import jwt  # PyJWT
from datetime import datetime, timezone

@dataclass
class JWTClaim:
    subject: str        # User ID
    expiration: datetime
    issued_at: datetime
    issuer: str | None

def validate_jwt(token: str) -> JWTClaim | None:
    """Validate JWT token and extract claims.

    Returns None if:
    - Token is malformed
    - Token is expired
    - Signature is invalid
    - Required claims missing
    """

def _extract_user_id_from_token(token: str) -> str | None:
    # Existing: UUID check
    if _is_valid_uuid(token):
        return token

    # New: JWT validation
    claims = validate_jwt(token)
    if claims:
        return claims.subject

    return None
```

**Error Handling**:
- Expired: Return None, log "JWT expired" (debug level)
- Malformed: Return None, log "Invalid JWT format" (warning level)
- Invalid signature: Return None, log "JWT signature invalid" (warning level)
- Missing secret: Raise configuration error at startup (fail-fast)

## Complexity Tracking

No constitution violations requiring justification.

## Decision Records

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| TF parsing | python-hcl2, regex, terraform show | python-hcl2 | Native HCL2 parsing, no TF init required |
| JWT library | PyJWT, python-jose, authlib | PyJWT | Minimal deps, Lambda-compatible, simple API |
| JWT algorithm | HS256, RS256 | HS256 | Symmetric, simple setup, adequate security |

## Implementation Order

1. **Resource Naming Validator** (Part A)
   - Implement `extract_resources()` and `validate_naming_pattern()`
   - Unskip 4 tests in `test_resource_name_pattern.py`
   - Add fixtures for valid/invalid resource names

2. **IAM Coverage Validator** (Part B)
   - Implement `extract_iam_patterns()` and `check_coverage()`
   - Unskip 2 tests in `test_iam_pattern_coverage.py`
   - Verify against existing resources and patterns

3. **JWT Authentication** (Part C)
   - Add PyJWT to requirements.txt
   - Implement `validate_jwt()` in auth_middleware.py
   - Remove TODO comment
   - Add unit tests for all JWT scenarios

## Success Criteria Verification

| SC | Verification Method |
|----|---------------------|
| SC-001 | Run pytest, verify 6 tests not skipped, all pass |
| SC-002 | Coverage report shows 100% for JWT validation path |
| SC-003 | grep for nosec/noqa/type:ignore shows no additions |
| SC-004 | `make validate` passes in target repo |
| SC-005 | Add intentionally misnamed fixtures, verify detection |
| SC-006 | Benchmark test: 1000 JWT validations <1 second |

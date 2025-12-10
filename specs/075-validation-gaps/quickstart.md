# Quickstart: Close Validation Gaps

**Feature**: 075-validation-gaps
**Date**: 2025-12-09

## Overview

This guide helps developers quickly understand and work with the validation gap closures implemented in this feature.

## Part A: Resource Naming Validator

### Running the Validator

```bash
# Run all resource naming tests
pytest tests/unit/validators/test_resource_naming.py -v

# Run specific test
pytest tests/unit/validators/test_resource_naming.py::test_all_lambda_names_valid -v

# Run with coverage
pytest tests/unit/validators/test_resource_naming.py --cov=src/validators/resource_naming
```

### Using the Validator Programmatically

```python
from pathlib import Path
from src.validators.resource_naming import (
    extract_resources,
    validate_naming_pattern,
    validate_all_resources
)

# Extract resources from Terraform
terraform_path = Path("infrastructure/terraform")
resources = extract_resources(terraform_path)

# Validate a single resource
result = validate_naming_pattern(resources[0])
print(f"{result.resource.name}: {result.status.value}")

# Validate all resources
results = validate_all_resources(terraform_path)
failures = [r for r in results if r.status == ValidationStatus.FAIL]
print(f"Found {len(failures)} naming violations")
```

### Valid Naming Patterns

| Pattern | Example | Valid? |
|---------|---------|--------|
| `{env}-sentiment-{name}` | `preprod-sentiment-dashboard` | ✓ |
| `{env}-sentiment-{name}` | `prod-sentiment-items` | ✓ |
| `sentiment-analyzer-*` | `sentiment-analyzer-api` | ✗ (legacy) |
| `sentiment-{name}` | `sentiment-items` | ✗ (missing env) |

## Part B: IAM Coverage Validator

### Running the Validator

```bash
# Run all IAM coverage tests
pytest tests/unit/validators/test_iam_coverage.py -v

# Run specific test
pytest tests/unit/validators/test_iam_coverage.py::test_all_resources_covered_by_iam -v
```

### Using the Validator Programmatically

```python
from pathlib import Path
from src.validators.iam_coverage import (
    extract_iam_patterns,
    check_coverage
)
from src.validators.resource_naming import extract_resources

# Extract resources and patterns
resources = extract_resources(Path("infrastructure/terraform"))
patterns = extract_iam_patterns(Path("infrastructure/terraform/ci-user-policy.tf"))

# Check coverage
report = check_coverage(resources, patterns)

print(f"Coverage: {report.coverage_percentage:.1f}%")
print(f"Uncovered resources: {len(report.uncovered_resources)}")
print(f"Orphaned patterns: {len(report.orphaned_patterns)}")
```

## Part C: JWT Authentication

### Configuration

Set the JWT secret as an environment variable:

```bash
# For local development (use a test secret)
export JWT_SECRET="dev-test-only"  # pragma: allowlist secret

# For production (loaded from Secrets Manager by Lambda)
# Configured via Terraform environment_variables
```

### Testing JWT Validation

```bash
# Run all JWT tests
pytest tests/unit/middleware/test_jwt_validation.py -v

# Run with coverage
pytest tests/unit/middleware/test_jwt_validation.py --cov=src/lambdas/shared/middleware/auth_middleware
```

### Using JWT in API Requests

```python
import jwt
from datetime import datetime, timezone, timedelta

# Create a test token
secret = "your-jwt-secret"  # pragma: allowlist secret
payload = {
    "sub": "user-uuid-here",
    "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    "iat": datetime.now(timezone.utc),
    "iss": "sentiment-analyzer"
}
token = jwt.encode(payload, secret, algorithm="HS256")

# Use in API request
import httpx
response = httpx.get(
    "https://api.example.com/v2/sentiment",
    headers={"Authorization": f"Bearer {token}"}
)
```

### JWT Token Structure

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "exp": 1733760000,
  "iat": 1733759100,
  "iss": "sentiment-analyzer"
}
```

| Claim | Description | Required |
|-------|-------------|----------|
| `sub` | User ID (UUID) | Yes |
| `exp` | Expiration timestamp | Yes |
| `iat` | Issued-at timestamp | Yes |
| `iss` | Issuer identifier | No |

### Error Handling

The auth middleware returns `None` for invalid tokens (no exception thrown):

```python
from src.lambdas.shared.middleware.auth_middleware import extract_user_id

# Returns None for:
# - Expired tokens
# - Invalid signatures
# - Malformed tokens
# - Missing required claims

user_id = extract_user_id(event)
if user_id is None:
    # Handle unauthenticated request
    return {"statusCode": 401, "body": "Unauthorized"}
```

## Running All Tests

```bash
# Run all validation gap tests
pytest tests/unit/validators/ tests/unit/middleware/test_jwt_validation.py -v

# Verify no tests are skipped
pytest tests/unit/validators/ -v --collect-only | grep -c "skipped"
# Should output: 0

# Full validation suite
make validate
```

## Troubleshooting

### JWT_SECRET Not Set

```
ValueError: JWT_SECRET environment variable not configured
```

**Fix**: Set the `JWT_SECRET` environment variable before running the application.

### python-hcl2 Parse Error

```
hcl2.exceptions.HclParseException: Unable to parse ...
```

**Fix**: Ensure Terraform files use valid HCL2 syntax. The validator falls back to regex for edge cases.

### Resource Naming Validation Fails

Check if the resource is in the allowlist:

```python
# Check iam-allowlist.yaml for exemptions
# Some resources (like chaos module) have documented deviations
```

# Tech Debt Registry

> **Purpose**: Track all technical debt, shortcuts, and loose ends discovered during the CI/CD stabilization phase (commits 5ea852b to HEAD). This is a prioritized, actionable list for cleanup.

---

## Critical Priority (Security/Production Risk)

### TD-001: CORS allow_methods Wildcard [EXISTING]
**Location**: `infrastructure/terraform/main.tf:230`
```hcl
allow_methods = ["*"]  # Should be ["GET", "OPTIONS"]
```
**Risk**: Allows all HTTP methods (POST, PUT, DELETE) when only GET/OPTIONS needed
**Root Cause**: AWS validation error with specific methods list
**Fix**: Investigate AWS provider version or API limitation
**Commit**: 108a34f

### TD-002: CORS allow_origins Wildcard
**Location**:
- `infrastructure/terraform/main.tf:231`
- `src/lambdas/dashboard/handler.py:105`
```python
allow_origins=["*"],  # Demo configuration - restrict in production
```
**Risk**: Any domain can make requests to dashboard API
**Root Cause**: Demo configuration left as placeholder
**Fix**: Restrict to specific origins before production deployment
**Priority**: HIGH for production, acceptable for demo

### TD-003: CloudWatch Metrics IAM Resource Wildcard
**Location**: `infrastructure/terraform/modules/iam/main.tf` (lines 107, 184, 304, 380)
```hcl
Resource = "*"
Condition = {
  StringEquals = {
    "cloudwatch:namespace" = "SentimentAnalyzer"
  }
}
```
**Status**: ACCEPTABLE - Has namespace condition constraint
**Note**: CloudWatch PutMetricData requires `*` resource, condition provides security

---

## High Priority (Code Quality/Maintainability)

### TD-004: noqa Comments for E402 Lint Errors
**Location**:
- `tests/integration/test_dashboard_e2e.py:29-34`
- `tests/unit/test_dashboard_handler.py:29-34`
```python
os.environ["API_KEY"] = "test-api-key-12345"  # Before imports
import boto3  # noqa: E402
```
**Root Cause**: Dashboard handler reads API_KEY at module import time
**Why It's Debt**: Working around a design flaw instead of fixing it
**Better Fix**: Make handler read env vars lazily, not at import time
**Commits**: 0b27743, 007cc16

### TD-005: Integration Test Cleanup Not Implemented
**Location**: `.github/workflows/integration.yml:117-123`
```yaml
- name: Cleanup test data
  run: |
    echo "Cleaning up test data..."
    # Cleanup logic will be implemented in test fixtures
```
**Risk**: Test data accumulates in dev DynamoDB over time
**Root Cause**: Rushed to fix integration tests, deferred cleanup
**Fix**: Implement cleanup in test fixtures or add explicit delete commands
**Commit**: Part of integration.yml creation

### TD-006: Test Expectation Changes Without Root Cause Fix
**Location**: `tests/unit/test_ingestion_handler.py`
**Commit**: 0062d8d
```python
# Was: 4 new, 0 duplicates
# Now: 2 new, 2 duplicates
# Comment: "Same articles returned for both tags"
```
**Issue**: Changed test expectations to match observed behavior, not fixed root cause
**Questions to Answer**:
1. Is the deduplication behavior correct or a bug?
2. Should the mock return different articles per tag?
3. Is the "duplicates_skipped" count accurate?

### TD-007: secret_not_found Test Returns 401 Instead of 500
**Location**: `tests/unit/test_ingestion_handler.py:864`
**Commit**: 0062d8d
```python
# Changed from 500 to 401
assert result["statusCode"] == 401
# Comment: "Missing secret results in authentication failure"
```
**Issue**: Changed expectation to match behavior without verifying it's correct
**Question**: Should missing NewsAPI secret return 401 (unauthorized) or 500 (server error)?

---

## Medium Priority (Cleanup/Polish)

### TD-008: Unused F841 Variables Ignored in Tests
**Location**: `pyproject.toml:102`
```toml
"F841",  # unused variables - often used for side effects in tests
```
**Risk**: Masks legitimate unused variable bugs
**Better Fix**: Use explicit `_` prefix for intentionally unused variables
**Why Ignored**: Quick fix to pass linting

### TD-009: Deprecation Warnings Filtered
**Location**: `pyproject.toml:134-137`
```toml
filterwarnings = [
    "ignore::DeprecationWarning:moto.*:",
    "ignore::DeprecationWarning:boto.*:",
]
```
**Risk**: Won't be warned when moto/boto deprecate APIs we use
**Root Cause**: moto 5.0 upgrade caused warning spam
**Better Fix**: Address specific deprecations, not blanket ignore

### TD-010: Protected Namespace Workaround
**Location**: `src/lambdas/shared/schemas.py`
**Commit**: b90bc06
```python
class ConfigDict:
    protected_namespaces = ()  # Suppress warning for model_version field
```
**Why**: Pydantic complains about `model_*` field names
**Better Fix**: Rename `model_version` to `ml_model_version` or `version`

### TD-011: Metrics Lambda Not Implemented
**Location**: `infrastructure/terraform/main.tf:308`
```hcl
# Metrics Lambda not implemented in Demo 1
create_metrics_schedule = false
```
**Status**: Intentional for demo scope
**Risk**: Operational monitoring for stuck items not active
**Note**: Dashboard handles metrics via /api/metrics endpoint instead

### TD-012: S3 Archival Lambda Specified But Not Implemented
**Location**: Referenced in `docs/INTERFACE-ANALYSIS-SUMMARY.md:58`
**Status**: Spec says archival Lambda exists, but it doesn't
**Risk**: Documentation mismatch with reality

---

## Low Priority (Nice to Have)

### TD-013: Multiple Import Fix Approaches
**Location**: `.github/workflows/test.yml`
**Commits**: 59dbbb1, f9a00c4
**History**:
1. First tried: `PYTHONPATH=. pytest`
2. Then changed to: `pip install -e .`
**Note**: Editable install is correct, but shows trial-and-error

### TD-014: moto Version Jump
**Location**: `requirements-dev.txt`
**Commit**: 1f2c1ae
```text
moto>=5.0.0  # Upgraded from 4.2.0 for mock_aws decorator
```
**Note**: Major version jump, may have other API changes we haven't tested

### TD-015: pytest-env Dependency Added
**Location**: `requirements-dev.txt`
**Commit**: b90bc06
**Note**: Added but seems unused in pyproject.toml. Verify if actually needed.

---

## Commit-by-Commit Lessons

### Commits That Were Shortcuts

| Commit | Description | Problem |
|--------|-------------|---------|
| 5ea852b | Align code formatting | Removed blank lines from tests - not a fix, cosmetic |
| 007cc16 | Resolve ruff linting | 71 auto-fixes in one commit - should have been reviewed |
| 0b27743 | Add noqa comments | Workaround instead of fixing root cause |
| e2cb2fa | Resolve test failures | Multiple unrelated fixes in one commit |
| 0062d8d | Update test expectations | Changed tests to match behavior, not fixed behavior |
| 108a34f | CORS wildcard | Acknowledged hack, good that it's tracked |
| bc44128 | Access keys for integration | Removed OIDC attempt without understanding why it failed |

### Pattern of Problems

1. **Hole-by-hole fixing**: Each CI failure fixed one thing, pushed, hit next error
2. **Test adjustment over code fixing**: When tests failed, adjusted expectations
3. **Lint suppression over lint fixing**: noqa instead of restructuring
4. **Major dependency jumps**: moto 4.2→5.0 without incremental testing

---

## Action Items for Cleanup Sprint

### Must Fix Before Demo
- [ ] TD-001: Investigate CORS allow_methods validation error
- [ ] TD-002: Document which origins should be allowed (or keep * for demo)
- [ ] TD-005: Implement test data cleanup

### Should Fix for Code Quality
- [ ] TD-004: Refactor dashboard handler to not read env at import time
- [ ] TD-006: Verify deduplication behavior is correct
- [ ] TD-007: Verify secret_not_found should return 401
- [ ] TD-008: Replace blanket F841 ignore with explicit `_` variables

### Can Defer
- [ ] TD-009: Address specific deprecation warnings
- [ ] TD-010: Rename model_version field
- [ ] TD-012: Remove or implement S3 archival Lambda
- [ ] TD-014: Review moto 5.0 changelog for breaking changes
- [ ] TD-015: Remove pytest-env if unused

---

## Tracking Metrics

| Metric | Value |
|--------|-------|
| Total Tech Debt Items | 15 |
| Critical (Security) | 3 |
| High (Quality) | 4 |
| Medium (Cleanup) | 5 |
| Low (Nice to Have) | 3 |
| Items from shortcuts | 7 |
| Items acceptable for demo | 4 |

---

*This registry should be reviewed before any production deployment. Items marked as "acceptable for demo" must be addressed for production.*

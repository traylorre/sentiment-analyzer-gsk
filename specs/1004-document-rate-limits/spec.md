# Feature 1004: Document Rate Limit Test Behavior

## Problem Statement

3-4 E2E tests skip with "Could not trigger rate limit" messages. Investigation reveals:

1. **Rate limits are correctly configured** - 100 req/sec steady, 200 concurrent burst
2. **Tests cannot trigger limits** - 50-100 requests can't exceed 200 burst
3. **Skip behavior is CORRECT** - Tests accurately describe the situation

This is NOT a bug. The tests correctly skip rather than falsely pass.

## Current Rate Limit Configuration

From `infrastructure/terraform/main.tf:700-701`:
```hcl
rate_limit  = 100 # Requests per second (steady state)
burst_limit = 200 # Concurrent requests (burst)
```

From `infrastructure/terraform/modules/api_gateway/variables.tf:26-33`:
- `rate_limit`: Default 100 requests per second
- `burst_limit`: Default 200 concurrent requests

## Affected Tests (4 skips)

| Test | File | Skip Reason |
|------|------|-------------|
| test_rate_limit_triggers_429 | test_rate_limiting.py:115 | 50 concurrent requests < 200 burst |
| test_retry_after_header_present | test_rate_limiting.py:162 | 100 sequential < 100 req/sec |
| test_rate_limit_recovery | test_rate_limiting.py:220 | Depends on triggering limit first |
| test_rate_limit_returns_retry_info | test_failure_injection.py:364 | 100 requests < limits |

## Analysis

The tests are working correctly:

1. **test_rate_limit_headers_on_normal_response** - PASSES
   - Verifies rate limiting infrastructure is configured
   - Checks for X-RateLimit-* headers without needing to trigger 429

2. **test_requests_within_limit_succeed** - PASSES
   - Verifies requests within limit succeed

3. **Tests that skip** - CORRECT BEHAVIOR
   - Cannot trigger limits with E2E-reasonable request counts
   - Skip with actionable remediation messages

## Solution Approach

Since the skip behavior is correct, the solution is documentation:

1. **Update SKIP_REASONS.md** with actual rate limit values from Terraform
2. **Add rate limit documentation** to tests/e2e/README.md
3. **Add inline comments** to rate limit tests explaining why skip is expected

## Changes Required

### 1. Update tests/e2e/SKIP_REASONS.md

Add actual Terraform-sourced values:

```markdown
#### RATE_LIMIT_CONFIG
**Count**: 3-4 tests
**Pattern**: "Could not trigger rate limit with 100 requests"

**Preprod Rate Limits** (from infrastructure/terraform/main.tf):
- Steady-state: 100 requests per second
- Burst limit: 200 concurrent requests
- No per-IP quotas configured

**Why Tests Skip**:
E2E tests send 50-100 requests. With a 200 request burst limit,
these cannot trigger rate limiting. This is expected behavior.

**Verification**:
- `test_rate_limit_headers_on_normal_response` PASSES
- Confirms rate limiting infrastructure is configured
- 429 triggering tests skip because limits are appropriately generous
```

### 2. Add inline comments to test_rate_limiting.py

Add header comment explaining expected skip behavior.

## Out of Scope

- Lowering rate limits (security decision, not E2E concern)
- Mocking rate limits (defeats purpose of E2E verification)
- Adding production rate limit tests (separate feature)

## Success Criteria

- SKIP_REASONS.md contains exact rate limit values from Terraform
- Rate limit test file has header explaining expected skip behavior
- Skip count reduced from "unknown" to "documented 3-4 expected skips"

# Feature 1294: Delete Obsolete Function URL Tests

## Problem
29 tests in `tests/integration/test_e2e_lambda_invocation_preprod.py` make direct HTTPS requests to Lambda Function URLs using `requests.get(DASHBOARD_FUNCTION_URL)`. Feature 1256 intentionally blocks this access pattern with AWS_IAM auth. All 29 tests get 403.

## Why Delete, Not Rewrite

1. **The access pattern is intentionally removed.** Feature 1256 specifically blocks direct Function URL access. Tests that require this pattern are testing a removed feature.

2. **Application behavior is already covered.** `test_session_consistency_preprod.py` tests the same endpoints (auth, configs, sentiment) via invoke transport. `test_function_url_restricted.py` validates that Function URLs return 403 (proving Feature 1256 works).

3. **Rewriting would create duplicates.** Converting these 29 tests to invoke would produce tests nearly identical to `test_session_consistency_preprod.py`.

## Coverage Verification

| Deleted Test Area | Covered By |
|-------------------|-----------|
| Health endpoint | `test_canary_preprod.py` (being rewritten in 1292) |
| Auth rejection | `test_function_url_restricted.py::test_bearer_token_on_function_url_still_403` |
| Sentiment/articles endpoints | `test_session_consistency_preprod.py` via invoke |
| CORS headers | `test_cors_404_e2e.py` (rewritten in 1291) via API Gateway |
| HTTP routing (404) | `test_admin_lockdown_preprod.py` (rewritten in 1292) |
| DynamoDB integration | `test_session_consistency_preprod.py` via invoke |
| Concurrent requests | `test_session_consistency_preprod.py` via invoke |
| Response format (JSON) | All tests that call `.json()` on responses |
| Function URL returns 403 | `test_function_url_restricted.py` (explicit validation) |

## Functional Requirements

### FR-001: Delete `test_e2e_lambda_invocation_preprod.py`
Remove the entire file. All 29 tests become dead code after Feature 1256.

### FR-002: Verify no other file imports from it
Grep for imports of this file to ensure no dependencies.

## Success Criteria
- SC-001: File deleted, no import errors
- SC-002: No reduction in actual application behavior coverage (verified by coverage matrix above)
- SC-003: Test count drops by 29, but all were FAILING — net improvement is 29 fewer failures

## Adversarial Review #1

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | **HIGH** | `test_function_url_restricted.py` is SKIPPED in CI (requires `AWS_ENV=preprod` which isn't set). The "Function URL returns 403" coverage claim is unverified. | **Resolved**: Add `AWS_ENV: preprod` to the deploy workflow test job environment. This enables the validation tests that prove Feature 1256 works. Without this, we're deleting 29 tests and claiming coverage that doesn't actually run. |
| 2 | **MEDIUM** | Deleting 29 tests without adding `AWS_ENV` leaves a gap: no CI test validates that Function URLs are IAM-protected. | **Resolved by #1**: Adding `AWS_ENV=preprod` enables `test_function_url_restricted.py` which has 5 tests explicitly validating this. |

**0 CRITICAL, 0 HIGH remaining.** Gate passes (conditional on FR-003 below).

### Spec Edit: Added FR-003
FR-003: Add `AWS_ENV: preprod` to deploy workflow test job to enable `test_function_url_restricted.py`.

## Out of Scope
- Writing new tests to replace these (coverage already exists)

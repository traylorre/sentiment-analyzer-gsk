# E2E Test Skip Reason Taxonomy

This document categorizes expected skip reasons for E2E tests running in preprod.
Skips are categorized to distinguish between expected behavior and actionable issues.

## Skip Categories

### LEGITIMATE - No Action Required

#### AUTH_REQUIRED
**Count**: ~13 tests
**Pattern**: "requires full authentication (not anonymous)"

Tests require OAuth or magic-link authentication, not anonymous sessions.
The E2E suite runs with anonymous sessions by default.

**Examples**:
- `test_notification_preferences.py`: Preferences/digest endpoints
- `test_quota.py`: Quota endpoint

**Resolution**: These endpoints correctly enforce authentication. To test them:
1. Use authenticated session fixture (when implemented)
2. Mark as `@pytest.mark.authenticated` for separate test run

#### CLEANUP_UTILITY
**Count**: 6 tests
**Pattern**: "Use --run-cleanup to execute cleanup utilities"

Utility tests for cleaning up test data. Skipped by default to prevent accidental data deletion.

**To run**: `pytest --run-cleanup tests/e2e/test_cleanup.py`

#### ENVIRONMENT
**Count**: ~6 tests
**Patterns**:
- "X-Ray trace not found (may not be sampled)"
- "No notifications available"
- "Circuit breaker state not available"
- "Cold start benchmark requires Lambda config update"
- "Test only runs in production environment"

Transient conditions that vary by environment/timing. Not bugs.

#### RATE_LIMIT_CONFIG
**Count**: 3 tests
**Pattern**: "Could not trigger rate limit with 100 requests"

Preprod has higher rate limits than test expects. Document actual limits.

**Preprod Rate Limits** (as of 2025-12):
- API Gateway: 100 requests/second burst, 50 sustained
- Magic link: 10/hour per IP
- E2E tests send 100 requests, may not trigger limits

---

### ACTIONABLE - Requires Fix

#### NOT_IMPLEMENTED
**Count**: 4 tests
**Pattern**: "[endpoint] not implemented"

Truly missing endpoints that need to be built:

| Endpoint | File | Ticket |
|----------|------|--------|
| Pre-market redirect | test_market_status.py:196 | TBD |
| Market schedule | test_market_status.py:225 | TBD |
| Dashboard metrics | test_dashboard_buffered.py:184 | TBD |
| Magic link verification | test_session_consistency_preprod.py | TBD |

#### AUTH_FORMAT
**Count**: 13 tests
**Pattern**: "Auth format incompatible - API v2 uses X-User-ID header"

Tests in `test_e2e_lambda_invocation_preprod.py` use wrong auth format.

**Fix**: Update tests to use X-User-ID header instead of Authorization bearer.

---

### RESOLVED

#### CONFIG_UNAVAILABLE (Fixed in PR #435)
**Previous Count**: 4-19 tests
**Pattern**: "Config creation not available"

**Root Cause**: Tests sent `tickers: [{"symbol": "AAPL"}]` but API expects `["AAPL"]`.
**Fix**: PR #435 corrected payload format in `test_anonymous_restrictions.py`.

---

## Monitoring Skip Rate

Target: <15% skip rate (currently ~25%)

```bash
# Check skip rate from CI logs
gh run view <run_id> --log | grep -c SKIPPED
```

Future: Feature 1005 will add a validator to fail CI if skip rate exceeds 15%.

## Adding New Skip Reasons

When adding a new `pytest.skip()`:
1. Use descriptive message explaining WHY, not just WHAT
2. Categorize using this taxonomy
3. Update counts in this document

**Good**: `pytest.skip("Preferences endpoint requires OAuth authentication (Feature 012)")`
**Bad**: `pytest.skip("Preferences endpoint not implemented")`

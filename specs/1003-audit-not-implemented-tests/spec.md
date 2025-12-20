# Feature 1003: Audit NOT_IMPLEMENTED E2E Test Skips

## Problem Statement

Static code analysis found 70 E2E tests with "endpoint not implemented" skip messages, but **runtime analysis reveals these are mostly mis-categorized**:

- Most endpoints ARE implemented in `router_v2.py`
- Skip messages in code are generic (e.g., "not implemented")
- Actual runtime skip reasons are more specific (e.g., "requires full authentication")

## Runtime Skip Analysis (from deploy run 20388319599)

### Category 1: Authentication Required (13 occurrences) - LEGITIMATE

These endpoints exist but require authenticated (non-anonymous) sessions:

| File | Count | Skip Reason |
|------|-------|-------------|
| test_notification_preferences.py | 7 | Preferences endpoint requires full authentication |
| test_quota.py | 6 | Quota endpoint requires full authentication |

**Action**: These are correct behavior. Update skip message to be clearer:
```python
pytest.skip("Requires authenticated session (OAuth/magic-link), not anonymous")
```

### Category 2: Auth Format Incompatible (13 occurrences) - TEST INFRASTRUCTURE

`test_e2e_lambda_invocation_preprod.py` uses wrong auth format:

```
Auth format incompatible - API v2 uses X-User-ID header
```

**Action**: Update tests to use correct X-User-ID header format.

### Category 3: Actually Not Implemented (4 occurrences) - TRUE GAPS

| Endpoint | File | Line |
|----------|------|------|
| Pre-market | test_market_status.py | 196 |
| Market schedule | test_market_status.py | 225 |
| Dashboard metrics | test_dashboard_buffered.py | 184 |
| Magic link | test_session_consistency_preprod.py | 157, 223 |

**Action**: Document as future features, update skip reason to include ticket reference.

### Category 4: Rate Limit (3 occurrences) - ENVIRONMENT

```
Could not trigger rate limit with 100 requests
preprod may have higher rate limits configured
```

**Action**: Document preprod rate limits, adjust test thresholds (Feature 1004).

### Category 5: Config Creation (4 occurrences) - FIXED in PR #435

```
Config creation not available
```

Root cause was payload format bug. Fixed in PR #435.

### Category 6: Test Utilities (6 occurrences) - INTENTIONAL

```
Use --run-cleanup to execute cleanup utilities
```

**Action**: No change needed. These are utility tests.

### Category 7: Environment/State (6+ occurrences) - TRANSIENT

- X-Ray trace not sampled
- No notifications available
- Circuit breaker state issues
- Cold start benchmark

**Action**: No change needed. These are legitimate conditional skips.

## Solution Approach

### Phase 1: Documentation (This PR)

1. Create skip reason taxonomy in `tests/e2e/SKIP_REASONS.md`
2. Document each skip category with expected count and rationale
3. Update misleading "not implemented" messages to accurate descriptions

### Phase 2: Test Infrastructure Fixes (Separate PR)

1. Fix `test_e2e_lambda_invocation_preprod.py` auth format (13 tests)
2. Add authenticated session fixture for preference/quota tests (13 tests)

### Phase 3: Feature Gaps (Future Specs)

Create specs for truly missing endpoints:
- Pre-market endpoint
- Market schedule endpoint
- Dashboard metrics endpoint

## Skip Reason Taxonomy

```markdown
# E2E Test Skip Reason Taxonomy

## Legitimate Skips (No Action)
- `AUTH_REQUIRED`: Endpoint requires OAuth/magic-link authentication
- `CLEANUP_UTILITY`: Test utility, run with --run-cleanup
- `ENVIRONMENT`: Transient state (X-Ray sampling, no data, cold start)
- `RATE_LIMIT_CONFIG`: Preprod rate limits differ from expectations

## Actionable Skips
- `NOT_IMPLEMENTED`: Endpoint not yet built (reference ticket)
- `AUTH_FORMAT`: Test uses wrong auth format (fix test)
- `PAYLOAD_FORMAT`: Test sends wrong payload (fix test)

## Resolved
- `CONFIG_UNAVAILABLE` → Fixed in PR #435 (payload format)
```

## Implementation Tasks

1. [x] Analyze runtime skip reasons from deploy logs
2. [ ] Create `tests/e2e/SKIP_REASONS.md` taxonomy document
3. [ ] Update 4 "not implemented" messages to reference feature tickets
4. [ ] Create stubs for truly missing endpoints (return 501) with ticket refs
5. [ ] Document preprod rate limits in `tests/e2e/README.md`

## Out of Scope

- Implementing missing endpoints (separate specs per Amendment 1.6)
- Fixing auth format issues (separate PR for test infrastructure)
- Adding authenticated session support (separate PR)

## Metrics

| Category | Count | Action |
|----------|-------|--------|
| Auth Required | 13 | Document as legitimate |
| Auth Format | 13 | Separate PR for fix |
| Not Implemented | 4 | Create feature tickets |
| Rate Limit | 3 | Feature 1004 |
| Config Creation | 4 | Fixed in PR #435 |
| Cleanup Utility | 6 | No action |
| Environment | 6+ | No action |

**Total Runtime Skips**: ~61
**Actionable Skips**: 4 (truly not implemented)
**Test Infrastructure Fixes Needed**: 26 (auth format + auth required)

## Success Criteria

- All skip reasons documented in taxonomy
- No misleading "not implemented" messages for implemented endpoints
- Feature tickets created for 4 truly missing endpoints

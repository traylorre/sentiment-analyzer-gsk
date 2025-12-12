# 093: E2E False-Pass Remediation - Tasks

## Phase 1: Critical - Remove 500 Error Masking [COMPLETE]

| Task | File | Status |
|------|------|--------|
| T001 | Remove 500 skip in test_magic_link_request | DONE |
| T002 | Remove 500 skip in test_magic_link_request_rate_limited | DONE |
| T003 | Remove 500 skip in test_magic_link_verification | DONE |
| T004 | Remove 500 skip in test_anonymous_data_merge | DONE |
| T005 | Remove 500 skip in test_full_anonymous_to_authenticated_journey | DONE |
| T006 | Remove 500 skip in test_rate_limiting.py | DONE |

## Phase 2: Prevention - Pre-commit Hook [COMPLETE]

| Task | File | Status |
|------|------|--------|
| T007 | Create check-false-pass-patterns.sh | DONE |
| T008 | Add to .pre-commit-config.yaml | DONE |
| T009 | Create audit-e2e-skips.py | DONE |

## Phase 3: HIGH Risk - "Not Implemented" Skips [FUTURE]

These 70 skips are for endpoints that may not exist. Each needs:
1. Investigation: Does the endpoint exist?
2. Decision: xfail with issue, or delete test

**Files affected**:
- test_notifications.py (9 skips)
- test_market_status.py (6 skips)
- test_anonymous_restrictions.py (5 skips)
- test_auth_oauth.py (2 skips)
- test_dashboard_buffered.py (2 skips)
- test_rate_limiting.py (1 skip)
- test_session_consistency_preprod.py (4 skips)
- Other files (41 skips)

**Recommended approach**: Create GitHub issue to track each missing endpoint, then mark tests with `@pytest.mark.xfail(reason="Issue #XXX")`.

## Phase 4: HIGH Risk - "Config Unavailable" Skips [FUTURE]

These 19 skips indicate infrastructure issues. Options:
1. Fix the infrastructure so config creation works
2. Mark as xfail with tracking issue
3. Delete if functionality is deprecated

## Phase 5: Medium Risk - Rate Limit Skips [FUTURE]

4 skips for rate limits that differ between environments. These may be legitimate - convert to environment-specific skipif.

## Verification

Run the audit script to confirm no critical issues:

```bash
python3 scripts/audit-e2e-skips.py --critical-only
```

Expected output: `Critical (500 masking): 0`

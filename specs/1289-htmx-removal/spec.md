# Feature 1289: HTMX Dashboard Removal

> Supersedes: Feature 1286 (chaos-html-removal)
> Gated on: Feature 1288 deployed + 7-day soak period with no regressions

## Summary

Remove the legacy HTMX/Alpine.js chaos dashboard (`src/dashboard/chaos.html`) and its serving route after the React replacement (Feature 1288) has been validated in production for 7 days.

**Key constraint:** This is a cleanup feature. It ONLY removes dead code. No functional changes.

## Soak Period Gate

This feature MUST NOT be implemented until:
1. Feature 1288 (chaos admin pages) is deployed to preprod
2. Operators have used the React chaos dashboard for ≥7 days
3. No regressions reported in chaos experiment lifecycle
4. Gameday dry-run completed using React dashboard (if Feature 1243 is ready)

## User Stories

### US-001: Remove dead code
As a maintainer, I want the legacy HTMX chaos dashboard removed so that there is only one chaos UI to maintain.

**Acceptance criteria:**
- `src/dashboard/chaos.html` deleted
- `GET /chaos` route removed from handler.py
- `TestChaosUIEndpoint` test class removed
- No runtime errors after removal
- Existing chaos API endpoints unaffected

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | Delete `src/dashboard/chaos.html` | MUST |
| FR-002 | Remove `serve_chaos()` function from `handler.py` | MUST |
| FR-003 | Remove `TestChaosUIEndpoint` test class from `test_dashboard_handler.py` | MUST |
| FR-004 | Do NOT remove `_is_dev_environment()` — used by 16+ other functions | MUST |
| FR-005 | Do NOT remove any chaos API endpoints (`/chaos/experiments/*`, `/chaos/reports/*`, etc.) | MUST |
| FR-006 | Remove vendor files if they exist (`static/vendor/htmx.min.js`, `static/vendor/alpine.min.js`) | SHOULD |
| FR-007 | Update or remove `playwright-chaos` CI job if it tests the old HTML dashboard | SHOULD |

## Files to Modify

### Delete
- `src/dashboard/chaos.html` (1,634 lines)
- `src/dashboard/static/vendor/htmx.min.js` (if exists)
- `src/dashboard/static/vendor/alpine.min.js` (if exists)

### Modify
- `src/lambdas/dashboard/handler.py` — Remove `serve_chaos()` function (lines ~331-349)
- `tests/unit/test_dashboard_handler.py` — Remove `TestChaosUIEndpoint` class (lines ~703-735)
- `.github/workflows/pr-checks.yml` — Review `playwright-chaos` job (lines ~283-339), update if it tests old HTML

### Do NOT Touch
- `src/lambdas/dashboard/chaos.py` — Backend chaos logic (stays)
- `_is_dev_environment()` — Used by 16+ functions (stays)
- All `/chaos/experiments/*` and `/chaos/reports/*` routes (stay)
- All chaos DynamoDB tables (stay)
- All Terraform chaos module (stays)

## Edge Cases

1. **Vendor files don't exist**: The HTML references `/static/vendor/htmx.min.js` and `/static/vendor/alpine.min.js` but they may not be deployed. Check before attempting deletion.
2. **Playwright chaos tests**: The CI job runs `tests/e2e/chaos-*.spec.ts`. If these test the old HTML dashboard, they need updating or removal. If they test the API, they stay.

## Success Criteria

| ID | Criterion |
|----|-----------|
| SC-001 | `chaos.html` no longer exists in the repo |
| SC-002 | `GET /chaos` returns 404 (route removed) |
| SC-003 | All chaos API endpoints still work (18 endpoints) |
| SC-004 | `_is_dev_environment()` still exists and functions |
| SC-005 | CI passes with no failures |
| SC-006 | React chaos dashboard at `/admin/chaos` unaffected |

## Adversarial Review #1

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | HIGH | Playwright chaos tests may navigate to old /chaos URL | Tests rewritten to target /admin/chaos before this feature ships (FR-007) |
| 2 | MEDIUM | Line count discrepancy (1634 vs 1613) | Use actual count at deletion time |
| 3 | LOW | Minimal feature may not need full plan/tasks | Create minimal artifacts for process compliance |

**Gate: 0 CRITICAL, 0 HIGH remaining.**

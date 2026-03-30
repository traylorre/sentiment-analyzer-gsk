# Feature 1289: HTMX Removal — Tasks

## Gate Check
- [ ] Feature 1288 deployed to preprod
- [ ] 7-day soak period elapsed
- [ ] No regressions reported
- [ ] Gameday dry-run completed (if ready)

## Tasks

### Task 1: Delete chaos.html
- **Action**: `rm src/dashboard/chaos.html`
- **Requirement mapping**: FR-001

### Task 2: Delete vendor files (if they exist)
- **Action**: `rm -f src/dashboard/static/vendor/htmx.min.js src/dashboard/static/vendor/alpine.min.js`
- **Requirement mapping**: FR-006

### Task 3: Remove serve_chaos() route
- **File**: `src/lambdas/dashboard/handler.py`
- **Action**: Delete the `@app.get("/chaos")` decorated `serve_chaos()` function (~18 lines)
- **IMPORTANT**: Do NOT remove `_is_dev_environment()` or any chaos API routes
- **Requirement mapping**: FR-002, FR-004, FR-005

### Task 4: Remove TestChaosUIEndpoint tests
- **File**: `tests/unit/test_dashboard_handler.py`
- **Action**: Delete `TestChaosUIEndpoint` class (~32 lines)
- **Requirement mapping**: FR-003

### Task 5: Update CI chaos job
- **File**: `.github/workflows/pr-checks.yml`
- **Action**: Review `playwright-chaos` job. If it tests old HTML, update to test `/admin/chaos`. If it already tests React version, no changes needed.
- **Requirement mapping**: FR-007

### Task 6: Verify
- **Action**: Run `make test-local` and verify all chaos API endpoints still respond
- **Requirement mapping**: SC-003, SC-004, SC-005

## Adversarial Review #3

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | Accidentally deleting _is_dev_environment() | HIGH (if it happened) | Task 3 explicitly warns against this. Code review will catch. |

**Highest-risk task:** Task 3 (route removal) — must surgically remove only serve_chaos()
**Most likely rework:** Task 5 (CI update) — depends on what Playwright tests actually test

**READY FOR IMPLEMENTATION** — gated on 7-day soak after Feature 1288.

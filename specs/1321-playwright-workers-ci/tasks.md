# Tasks: Feature 1321 — Playwright Workers CI

## Task 1: Update Playwright Config Workers

- **File**: `frontend/playwright.config.ts`
- **Line**: 15
- **Action**: Change `workers: process.env.CI ? 1 : undefined` to `workers: process.env.CI ? 4 : 4`
- **Depends on**: nothing
- **Verification**: Read line 15, confirm `workers: process.env.CI ? 4 : 4`

## Task 2: Add --workers=4 to CI Workflow

- **File**: `.github/workflows/pr-checks.yml`
- **Lines**: 318-324 (Playwright test step)
- **Action**: Add `--workers=4` to the `npx playwright test` command, after `--retries=0`
- **Depends on**: nothing
- **Verification**: `grep "workers=4" .github/workflows/pr-checks.yml` returns match

## Task 3: Push and Verify CI Pipeline

- **Action**: Push changes, observe CI run, confirm E2E job completes within 900s timeout
- **Depends on**: Task 1, Task 2
- **Verification**: CI job passes; wall-clock time for E2E step is under 900s
- **Note**: Full benefit requires Feature 1319 to be merged (API thread safety). Without
  it, tests will still fail but will fail faster (4 workers hit the broken API in
  parallel instead of serially).

## Execution Order

```
T1 ──┐
     ├──> T3 (push and verify)
T2 ──┘
```

Tasks 1 and 2 are independent and can be done in either order (or in a single commit).
Task 3 is the verification gate.

## Requirement Coverage

| Requirement | Task(s) | Covered |
|-------------|---------|---------|
| R1: Set --workers=4 in CI | T1 (config), T2 (CLI) | YES |
| R2: Keep retries=0 | T2 (no change to retries flag) | YES |
| R3: Maintain timeout | T2 (no change to timeout) | YES |

## Edge Case Coverage

| Edge Case | Mitigation | Task |
|-----------|-----------|------|
| EC1: Memory pressure (4 Chromium) | 3.2GB / 16GB = 20% utilization | N/A (within limits) |
| EC2: API concurrency | Feature 1319 dependency | N/A (external) |
| EC3: Browser context isolation | Playwright default behavior | N/A (built-in) |
| EC4: Test data races | Global setup runs before workers | N/A (Playwright guarantee) |

---

## Adversarial Review #3: Final Review

### Completeness Check

| Artifact | Exists | Consistent |
|----------|--------|------------|
| spec.md | YES | -- |
| plan.md | YES | Covers all spec requirements |
| tasks.md | YES | 3 tasks, correct dependencies |

### Scope Creep Check

- 2 files changed, 2 lines modified
- No new files created
- No new dependencies
- No test file changes (this is infrastructure config, not test code)
- **Verdict**: Scope is minimal. No creep.

### Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Shared test data between workers causing flaky tests | MEDIUM | MEDIUM | Playwright isolates browser contexts per worker; global setup handles cleanup |
| Timeout adjustment needed after observing real runtime | LOW | LOW | 305s projected vs 900s limit = 3x headroom |
| Feature 1319 not merged, tests still fail | HIGH | NONE | Tests fail faster, not differently. Workers change is safe regardless. |
| Runner vCPU count changes | LOW | LOW | Hardcoded 4 means we notice and adjust deliberately |

### Highest Risk

Shared test data between workers causing flaky tests. If tests implicitly depend on
execution order or shared mutable state beyond browser context, parallel execution will
surface these as intermittent failures. This is a test quality issue, not a config issue,
and is ultimately beneficial (surfaces hidden bugs).

### Most Likely Rework

Timeout adjustment. If real-world runtime with 4 workers is higher than projected (due
to resource contention or test data setup overhead), the 900s timeout may need to be
reduced or the worker count tuned. However, 3x headroom makes this unlikely.

### Implementation Readiness

**READY FOR IMPLEMENTATION**

- 2 files, 2 line changes
- No new dependencies
- No test changes required
- Can be implemented in a single commit
- Verification is observational (CI run)

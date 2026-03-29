# Feature 1271: Accessibility Timing Audit — Tasks

## Scope

Fix ARIA assertion race conditions in 4 files + replace `waitForTimeout` blind waits in those same files with event-based waiting.

## Task Dependency Graph

```
T1 (chaos-degradation.spec.ts)     ──┐
T2 (error-visibility-banner.spec.ts) ├──→ T6 (verify all pass)
T3 (chaos-cross-browser.spec.ts)   ──┤
T4 (sanity.spec.ts)                ──┤
T5 (chaos-helpers.ts blind waits)  ──┘
```

All tasks are parallelizable (different files, no dependencies except T6).

## Tasks

### T1: Fix chaos-degradation.spec.ts

**File**: `frontend/tests/e2e/chaos-degradation.spec.ts`
**Fixes**:
- Line 42: Add `{ timeout: 3000 }` to `toHaveAttribute('aria-live', 'assertive')`
- Replace `waitForTimeout()` calls in this file with `waitForResponse()` or `waitForLoadState()` where applicable

### T2: Fix error-visibility-banner.spec.ts

**File**: `frontend/tests/e2e/error-visibility-banner.spec.ts`
**Fixes**:
- Line 222: Add `{ timeout: 3000 }` to `toHaveAttribute('aria-live', 'assertive')`
- Replace blind waits with proper event-based waits where applicable

### T3: Fix chaos-cross-browser.spec.ts

**File**: `frontend/tests/e2e/chaos-cross-browser.spec.ts`
**Fixes**:
- Line 30: Add `{ timeout: 3000 }` to `toHaveAttribute('aria-live', 'assertive')`

### T4: Fix sanity.spec.ts

**File**: `frontend/tests/e2e/sanity.spec.ts`
**Fixes**:
- Lines 175-176: Add `{ timeout: 3000 }` to `toHaveAttribute('aria-pressed', 'true')`
- Lines 184-185: Same
- Lines 789-790: Same

### T5: Replace blind waits in chaos-helpers.ts

**File**: `frontend/tests/e2e/helpers/chaos-helpers.ts`
**Fixes**:
- Replace `waitForTimeout()` in `triggerHealthBanner()` and other shared helpers with `waitForResponse()` or `expect.poll()`
- Only fix waits in helpers used by files T1-T4

### T6: Verify deterministic pass

Run all affected test files with `--retries=0`:
```bash
cd frontend && npx playwright test chaos-degradation chaos-cross-browser sanity error-visibility-banner --retries=0
```

## Adversarial Review #3

**Highest-risk task**: T5 — replacing blind waits in shared helpers affects all tests that use those helpers, not just the ones we're fixing. Must verify no regressions.

**Most likely rework**: T4 (sanity.spec.ts) — `aria-pressed` timing may differ from `aria-live` because it's state-driven (user interaction) vs event-driven (failure count). May need `waitForFunction` instead of just timeout.

**Gate**: READY FOR IMPLEMENTATION

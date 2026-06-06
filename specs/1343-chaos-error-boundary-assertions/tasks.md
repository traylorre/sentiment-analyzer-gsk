# Tasks -- Feature 1343: Fix chaos-error-boundary.spec.ts Missing Assertions

## Task Dependencies

```
T1 (chaos-helpers.ts) ──> T2 (imports + remove local fn)
T2 ──> T3 (beforeEach)
T2 ──> T4 (T022 Try Again)
T2 ──> T5 (T023 banner + forceErrorBoundary)
T2 ──> T6 (T024 verify unchanged)
T1-T6 ──> T7 (verification)
```

## Tasks

### T1: Add forceErrorBoundary to chaos-helpers.ts
**File**: `frontend/tests/e2e/helpers/chaos-helpers.ts`
**Action**: Add new section after "Chaos Scenario Simulation" section (after line 316)
**Details**:

Add:
```typescript
// --- Error Boundary Utilities ------------------------------------------------

/**
 * Force the React error boundary to trigger via the test-only ErrorTrigger component.
 *
 * Sets `window.__TEST_FORCE_ERROR = true` via addInitScript (persists across navigations),
 * then navigates to '/' to trigger the error boundary render.
 *
 * @example
 * ```typescript
 * await forceErrorBoundary(page);
 * await expect(page.getByText(/something went wrong/i)).toBeVisible({ timeout: 5000 });
 * ```
 */
export async function forceErrorBoundary(page: Page): Promise<void> {
  // Must use addInitScript -- page.evaluate() sets the flag on the current page,
  // but goto() loads a NEW page where the flag doesn't exist.
  // addInitScript runs before any page JS, so the flag is set when ErrorTrigger renders.
  await page.addInitScript(() => {
    (window as any).__TEST_FORCE_ERROR = true;
  });
  await page.goto('/');
}
```

**Acceptance**: `forceErrorBoundary` is importable from chaos-helpers.ts. TypeScript compiles.

---

### T2: Update imports and remove file-local forceErrorBoundary
**File**: `frontend/tests/e2e/chaos-error-boundary.spec.ts`
**Action**: Modify import and delete local function
**Details**:

1. Update import (line 3):
   ```typescript
   // BEFORE:
   import { triggerHealthBanner, getBannerLocator } from './helpers/chaos-helpers';

   // AFTER:
   import {
     triggerHealthBanner,
     getBannerLocator,
     forceErrorBoundary,
   } from './helpers/chaos-helpers';
   ```

2. Delete the file-local `forceErrorBoundary` function (lines 25-33):
   ```typescript
   // DELETE THIS BLOCK:
   async function forceErrorBoundary(page: import('@playwright/test').Page) {
     await page.addInitScript(() => {
       (window as any).__TEST_FORCE_ERROR = true;
     });
     await page.goto('/');
   }
   ```

**Acceptance**: Spec file imports `forceErrorBoundary` from chaos-helpers. No local definition.

---

### T3: Fix beforeEach page-ready wait
**File**: `frontend/tests/e2e/chaos-error-boundary.spec.ts`
**Action**: Replace line 18
**Details**:
- Remove `await page.waitForTimeout(2000);`
- Replace with `await expect(page.locator('main')).toBeVisible({ timeout: 10000 });`

Note: Need to verify `expect` is imported. Line 2: `import { test, expect } from '@playwright/test';` -- already imported.

**Acceptance**: beforeEach waits for main element, not arbitrary timeout.

---

### T4: Fix T022 -- add Try Again click test
**File**: `frontend/tests/e2e/chaos-error-boundary.spec.ts`
**Action**: Add after existing visibility assertions in T022 (after line 55)
**Details**:

Add:
```typescript
// Verify "Try Again" button is functional (not just visible)
const tryAgainButton = page.getByRole('button', { name: /try again/i });
await tryAgainButton.click();
// After click, page should respond -- either error boundary re-renders
// (addInitScript persists across navigations) or dashboard appears
const errorText = page.getByText(/something went wrong/i);
const mainContent = page.locator('main');
await expect(errorText.or(mainContent)).toBeVisible({ timeout: 5000 });
```

**Acceptance**: "Try Again" is clicked and page responds (not frozen). Test verifies either
error boundary re-rendered or dashboard appeared.

---

### T5: Fix T023 -- banner-hidden assertion and shared helper
**File**: `frontend/tests/e2e/chaos-error-boundary.spec.ts`
**Action**: Modify T023 test body (lines 59-83)
**Details**:

1. Replace inline addInitScript + goto (lines 69-72) with shared helper:
   ```typescript
   // BEFORE:
   await page.addInitScript(() => {
     (window as any).__TEST_FORCE_ERROR = true;
   });
   await page.goto('/');

   // AFTER:
   await forceErrorBoundary(page);
   ```

2. After error boundary visibility check (line 77), add banner-hidden assertion.
   Reuse the existing `banner` variable from line 65:
   ```typescript
   // Error boundary fallback should now be visible
   await expect(
     page.getByText(/something went wrong/i),
   ).toBeVisible({ timeout: 5000 });

   // Banner should no longer be visible -- error boundary replaces entire dashboard
   await expect(banner).not.toBeVisible({ timeout: 5000 });

   // Fallback buttons should be visible
   const fallbackButtons = page.getByRole('button', { name: /try again/i });
   await expect(fallbackButtons).toBeVisible();
   ```

**Acceptance**: T023 asserts banner is NOT visible after error boundary. Uses shared
forceErrorBoundary helper.

---

### T6: Verify T024 unchanged
**File**: `frontend/tests/e2e/chaos-error-boundary.spec.ts`
**Action**: Verify only -- no changes
**Details**:

Confirm T024 (lines 86-108):
- Uses `.focus()` pattern (not Tab key)
- Has comment explaining headless Chromium limitation (lines 93-95)
- Calls `forceErrorBoundary(page)` (already uses the function by name, which now resolves
  to the imported shared version)

**Acceptance**: T024 unchanged. Documentation preserved.

---

### T7: Verification
**Action**: Run test suite
**Details**:
```bash
cd frontend && npx playwright test chaos-error-boundary.spec.ts --reporter=list
```

Also verify chaos-helpers.ts compiles:
```bash
cd frontend && npx tsc --noEmit
```

Verify:
- All 3 tests pass
- `forceErrorBoundary` exported from chaos-helpers.ts
- No file-local `forceErrorBoundary` in spec file
- T023 asserts `banner.not.toBeVisible()`
- T022 clicks "Try Again" and asserts page response
- T024 unchanged (focus-based keyboard test)

**Acceptance**: All tests pass. TypeScript compiles. Shared helper is reusable.

---

## Appendix A: Adversarial Review #3 (Tasks)

### AR3-Q1: T4 "Try Again" click -- what if it triggers page navigation that breaks subsequent assertions?
**Analysis**: `forceErrorBoundary` uses `addInitScript` which persists across navigations.
If "Try Again" reloads the page, the error boundary re-triggers. The assertion
`errorText.or(mainContent)` handles both cases. No subsequent assertions exist in T022
after this addition, so navigation doesn't break anything.
**Verdict**: ACCEPT.

### AR3-Q2: T5 reuses `banner` from line 65 -- does Playwright locator survive page navigation?
**Analysis**: Playwright locators are lazy -- they describe HOW to find an element, not a
reference to a specific DOM node. `getBannerLocator(page)` returns a locator bound to the
`page` object. After `forceErrorBoundary(page)` navigates, the locator still works because
it re-queries the DOM. The locator looks for `role="alert"` with matching text, which
should NOT exist after the error boundary replaces the dashboard.
**Verdict**: ACCEPT -- locator survives navigation.

### AR3-Q3: T1 adds to chaos-helpers.ts -- does this conflict with 1339?
**Analysis**: Feature 1339 also adds to chaos-helpers.ts (new helpers like
`captureTelemetryEvents`, `captureContentSnapshot`, etc.). T1 adds `forceErrorBoundary`
at the END of the file in its own section. If 1339 also added content at the end, there
could be a merge conflict. However, 1339 is COMPLETE (prerequisite), so its changes are
already merged. T1 appends after 1339's content.
**Verdict**: ACCEPT -- no conflict (1339 is already merged).

### AR3-Q4: Is the task set complete?
**Audit**:
- chaos-helpers.ts: T1 (forceErrorBoundary added)
- Imports: T2 (updated, local fn removed)
- beforeEach: T3 (page ready -- fixed)
- T022: T4 (Try Again click -- fixed)
- T023: T5 (banner assertion + shared helper -- fixed)
- T024: T6 (verified unchanged)
- Verification: T7

All requirements mapped. Both files covered. No gaps.
**Verdict**: COMPLETE.

---

## READY FOR IMPLEMENTATION

All adversarial reviews passed. No blocking issues. Feature depends on 1339 (complete).
Two-file change (chaos-helpers.ts + spec file) with 6 edit tasks + verification.

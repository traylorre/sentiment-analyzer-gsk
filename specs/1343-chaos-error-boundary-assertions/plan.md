# Implementation Plan -- Feature 1343: Fix chaos-error-boundary.spec.ts Missing Assertions

## Files to Modify

### 1. `frontend/tests/e2e/helpers/chaos-helpers.ts` (SECONDARY)

Add `forceErrorBoundary()` helper function.

### 2. `frontend/tests/e2e/chaos-error-boundary.spec.ts` (PRIMARY)

Remove file-local `forceErrorBoundary()`, import from chaos-helpers.ts, fix assertions.

## Technical Context

### Current State -- chaos-error-boundary.spec.ts

| Line | Current Code | Problem |
|------|-------------|---------|
| 18 | `await page.waitForTimeout(2000)` | Arbitrary wait in beforeEach |
| 25-33 | `async function forceErrorBoundary(page)` | File-local, should be shared |
| 68-72 | Inline `addInitScript` + `goto` (duplicate of forceErrorBoundary) | Should call shared helper |
| 79-80 | Comment "Banner should no longer be visible" with no assertion | Missing assertion |
| 81-82 | `fallbackButtons` visibility check but no banner hidden check | Incomplete |
| 36-56 | T022 checks button visibility but not functionality | No click test |

### Current State -- chaos-helpers.ts

File ends at line 317. New function will be added in a new section after the
"Chaos Scenario Simulation" section.

### forceErrorBoundary Implementation

```typescript
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
  await page.addInitScript(() => {
    (window as any).__TEST_FORCE_ERROR = true;
  });
  await page.goto('/');
}
```

## Implementation Plan

### Step 1: Add forceErrorBoundary to chaos-helpers.ts (FR-003)

Add the function at the end of chaos-helpers.ts, in a new section:

```typescript
// --- Error Boundary Utilities ------------------------------------------------

/**
 * Force the React error boundary ... (full JSDoc above)
 */
export async function forceErrorBoundary(page: Page): Promise<void> {
  await page.addInitScript(() => {
    (window as any).__TEST_FORCE_ERROR = true;
  });
  await page.goto('/');
}
```

### Step 2: Update chaos-error-boundary.spec.ts imports

Update import to include `forceErrorBoundary`:
```typescript
import {
  triggerHealthBanner,
  getBannerLocator,
  forceErrorBoundary,
} from './helpers/chaos-helpers';
```

### Step 3: Remove file-local forceErrorBoundary (FR-003)

Delete lines 25-33 (the `async function forceErrorBoundary` declaration inside the
describe block).

### Step 4: Fix beforeEach (FR-004)

Replace:
```typescript
await page.waitForTimeout(2000);
```
With:
```typescript
await expect(page.locator('main')).toBeVisible({ timeout: 10000 });
```

### Step 5: Fix T022 -- add Try Again click test (FR-002)

After the existing visibility assertions (line 55), add:
```typescript
// Verify "Try Again" button is functional (not just visible)
const tryAgainButton = page.getByRole('button', { name: /try again/i });
await tryAgainButton.click();
// After click, page should still be functional (not frozen).
// The error may re-trigger (addInitScript persists) or boundary may reset.
// Either way, something should be visible within 5s.
await expect(page.locator('body')).toBeVisible({ timeout: 5000 });
```

### Step 6: Fix T023 -- add banner-hidden assertion (FR-001)

After line 77 (`page.getByText(/something went wrong/i)`), replace lines 79-82:
```typescript
// BEFORE:
// Banner should no longer be visible (error boundary replaces entire dashboard content)
// The banner is inside the dashboard layout which is now showing the fallback
const fallbackButtons = page.getByRole('button', { name: /try again/i });
await expect(fallbackButtons).toBeVisible();

// AFTER:
// Banner should no longer be visible -- error boundary replaces entire dashboard content
const banner = getBannerLocator(page);
await expect(banner).not.toBeVisible({ timeout: 5000 });

// Fallback buttons should be visible
const fallbackButtons = page.getByRole('button', { name: /try again/i });
await expect(fallbackButtons).toBeVisible();
```

Also update T023 to use the shared forceErrorBoundary (replacing inline addInitScript):
```typescript
// BEFORE (lines 68-72):
await page.addInitScript(() => {
  (window as any).__TEST_FORCE_ERROR = true;
});
await page.goto('/');

// AFTER:
await forceErrorBoundary(page);
```

### Step 7: Verify T024 is unchanged (FR-005)

Confirm T024 still uses `.focus()` pattern. No changes to this test. The existing
comment (lines 93-95) documents why Tab key is not used.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| "Try Again" click reloads page and re-triggers error | Expected | None | Test checks `body` is visible, not specific content |
| Banner locator mismatch in T023 | Very Low | Medium | Same `getBannerLocator` used in all other chaos tests |
| forceErrorBoundary export breaks other tests | Very Low | Low | New export only; no existing exports modified |
| T023 inline code pattern differs from forceErrorBoundary | Very Low | Low | Functionally identical: addInitScript + goto |

---

## Appendix A: Adversarial Review #2 (Plan)

### AR2-Q1: Step 5 "Try Again" test -- is checking `body` visible sufficient?
**Challenge**: `body` is always visible even on a blank/crashed page. Is this assertion
meaningful?
**Analysis**: Good catch. A frozen page (JS infinite loop) would still have a visible
`body`. A better assertion: after clicking "Try Again", check that EITHER (a) the error
boundary text is still visible (re-triggered) OR (b) the main content area is visible
(boundary cleared). Both prove the page responded to the click.
**Revised approach**:
```typescript
await tryAgainButton.click();
// Page should respond -- either error boundary re-renders or dashboard appears
const errorText = page.getByText(/something went wrong/i);
const mainContent = page.locator('main');
await expect(errorText.or(mainContent)).toBeVisible({ timeout: 5000 });
```
**Verdict**: REVISE Step 5 to use `errorText.or(mainContent)` pattern.

### AR2-Q2: Moving forceErrorBoundary -- should other tests also be updated?
**Challenge**: Are there other spec files that use the addInitScript + goto pattern for
error boundary?
**Analysis**: Only `chaos-error-boundary.spec.ts` tests the error boundary. No other
chaos spec files trigger it. The move benefits future tests but only requires updating
this one file now.
**Verdict**: ACCEPT -- only this spec needs updating.

### AR2-Q3: T023 -- is `getBannerLocator(page)` available without importing it?
**Challenge**: Current T023 imports only `triggerHealthBanner` and `getBannerLocator` from
chaos-helpers (line 3). Need to verify `getBannerLocator` is already imported.
**Analysis**: Line 3-4:
```typescript
import { triggerHealthBanner, getBannerLocator } from './helpers/chaos-helpers';
```
Yes, `getBannerLocator` is already imported. No import change needed for this.
**Verdict**: ACCEPT.

### AR2-Q4: Step 6 creates a new `banner` variable -- is there a naming conflict?
**Challenge**: T023 already has `const banner = getBannerLocator(page)` on line 65.
After the error boundary triggers (page navigates), the old locator should still work
since Playwright locators are lazy.
**Analysis**: The existing `banner` on line 65 is from BEFORE `forceErrorBoundary`. After
`forceErrorBoundary` navigates to `/`, we need to get the banner locator again. But
Playwright locators are lazy -- they re-query the DOM on each use. So the line 65
`banner` variable works fine even after navigation.

Option: Reuse the existing `banner` variable instead of creating a new one.
**Verdict**: REVISE -- reuse existing `banner` from line 65 instead of creating new const.

# Implementation Plan -- Feature 1344: Clean Up chaos-cross-browser.spec.ts

## Files to Modify

### 1. `frontend/tests/e2e/chaos-cross-browser.spec.ts` (ONLY FILE)

This is the only file that changes. No other spec files are modified.

## Current State (106 lines)

```
Lines 1-8:    Imports
Lines 10-19:  File-level JSDoc
Lines 20-24:  test.describe + beforeEach (waitForTimeout 2000)
Lines 26-32:  T042 banner test (5 lines, good)
Lines 34-66:  T042 cached data test (32 lines, Green Dashboard Syndrome)
Lines 68-104: T043 SSE fixme test (DEAD CODE -- entire block)
Line 105:     Close describe
Line 106:     Empty
```

## Planned State (~75 lines)

```
Lines 1-7:    Imports (mockTickerDataApis retained, remove nothing -- all still used)
Lines 9-24:   Updated file-level JSDoc with cross-browser rationale
Lines 25-30:  test.describe + beforeEach (DOM-ready wait replacing waitForTimeout)
Lines 32-39:  T042 banner test (unchanged logic, added smoke test comment)
Lines 41-72:  T042 cached data test (content comparison fix, smoke test comment)
Lines 73-74:  Close describe + empty
```

## Change Details

### Change 1: Update File-Level JSDoc (lines 10-19)

**Before**:
```typescript
/**
 * Chaos: Cross-Browser Validation (Feature 1265, US5)
 *
 * Validates that degradation behavior is consistent across browser engines.
 * Runs selected chaos tests across Mobile Chrome and Mobile Safari projects.
 *
 * Caveat: Playwright's WebKit is not identical to Safari's production
 * network stack. These tests validate WebKit compatibility, not Safari-specific
 * production behavior.
 */
```

**After**:
```typescript
/**
 * Chaos: Cross-Browser Validation (Feature 1265, US5)
 *
 * CROSS-BROWSER SMOKE TESTS: These tests deliberately duplicate primary tests
 * from chaos-degradation.spec.ts (banner) and chaos-cached-data.spec.ts (cached
 * data). The duplication is intentional -- Playwright's project config runs THIS
 * file on Mobile Chrome and Mobile Safari, providing cross-browser validation
 * that the primary single-browser tests do not cover.
 *
 * Caveat: Playwright's WebKit is not identical to Safari's production
 * network stack. These tests validate WebKit compatibility, not Safari-specific
 * production behavior.
 *
 * See also: Feature 1344 (cleanup rationale)
 */
```

### Change 2: Replace beforeEach waitForTimeout (line 23)

**Before**:
```typescript
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.waitForTimeout(2000);
});
```

**After**:
```typescript
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  // Wait for dashboard to be interactive (search input rendered)
  const searchInput = page.getByPlaceholder(/search tickers/i);
  await expect(searchInput).toBeVisible({ timeout: 5000 });
});
```

Note: Requires adding `expect` to the existing import from `@playwright/test` (already
imported on line 2).

### Change 3: Add Smoke Test Comment to Banner Test (line 26)

**Before**:
```typescript
// T042: Banner lifecycle works across browsers
test('health banner appears after 3 failures', async ({ page }) => {
```

**After**:
```typescript
// T042: Cross-browser smoke test (primary: chaos-degradation.spec.ts T007)
test('health banner appears after 3 failures', async ({ page }) => {
```

No logic changes to this test. The test body remains identical.

### Change 4: Fix Cached Data Test (lines 34-66)

**Before** (Green Dashboard Syndrome):
```typescript
// T042: Cached data persists across browsers
test('cached data persists during API outage', async ({ page }) => {
  // ...loads data, captures textBefore...
  await blockAllApi(page, 503);
  await page.waitForTimeout(500);

  const textDuring = await mainContent.textContent();
  expect(textDuring).toBeTruthy();
  expect(textDuring!.length).toBeGreaterThan(10);
});
```

**After** (content comparison):
```typescript
// T042: Cross-browser smoke test (primary: chaos-cached-data.spec.ts T013)
test('cached data persists during API outage', async ({ page }) => {
  // ...loads data, captures textBefore...
  await blockAllApi(page, 503);
  // Brief settle for in-flight React Query refetch requests to hit the route block.
  // Cannot use response-based wait here because requests may already be in-flight
  // before blockAllApi() installs the route handlers.
  await page.waitForTimeout(500);

  const textDuring = await mainContent.textContent();
  expect(textDuring).toBeTruthy();
  expect(textDuring!.length).toBeGreaterThan(10);

  // Content comparison: verify cached data persists (not replaced by error page)
  // Uses substring check rather than exact match to tolerate dynamic timestamps
  expect(textDuring).toContain('AAPL');
});
```

### Change 5: Delete SSE Test (lines 68-104)

Remove the entire block:
```typescript
// T043: SSE reconnection on WebKit
// FIXME(1280): ...
test.fixme('SSE reconnection issues new fetch after connection drop', async ({
  page,
}) => {
  // ... 30 lines of dead code ...
});
```

This is a clean deletion -- no code references this test externally.

## Import Verification

After deletion of the SSE test, verify all imports are still used:

| Import | Used by |
|--------|---------|
| `test, expect` | Both remaining tests |
| `blockAllApi` | Cached data test |
| `triggerHealthBanner` | Banner test |
| `getBannerLocator` | Banner test |
| `mockTickerDataApis` | Cached data test |

All imports remain in use. No cleanup needed.

## Files NOT Modified

- `chaos-degradation.spec.ts` -- primary banner test, unchanged
- `chaos-cached-data.spec.ts` -- primary cached data test, unchanged
- `chaos-helpers.ts` -- no helper changes needed
- `mock-api-data.ts` -- no changes

---

## Appendix: Adversarial Review #2

### Completeness Check
- All 5 FRs are covered by the 5 changes above
- FR-001 (delete SSE) -> Change 5
- FR-002 (documentation) -> Changes 1, 3
- FR-003 (beforeEach) -> Change 2
- FR-004 (content comparison) -> Change 4
- FR-005 (settle wait) -> Change 4 (kept 500ms with documentation)

### Risk Assessment
- **Change 2** (beforeEach): The search input may not render if the app crashes on load.
  This is acceptable -- if the app crashes, the test SHOULD fail at this point rather
  than proceeding with a blind 2s wait.
- **Change 4** (AAPL check): The `toContain('AAPL')` assertion depends on the mock data
  setup earlier in the test. If `mockTickerDataApis` or the search/select flow changes,
  this assertion must be updated. This coupling is acceptable because the test already
  hard-codes 'AAPL' in the search flow (line 41).
- **Change 5** (SSE deletion): Zero risk. `test.fixme()` tests never execute.

### Ordering Constraint
Changes 1-4 can be applied in any order. Change 5 is independent. No ordering dependencies.

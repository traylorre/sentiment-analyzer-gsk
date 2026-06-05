# Tasks -- Feature 1340: Fix Green Dashboard Syndrome in chaos-scenarios.spec.ts

## Task Dependencies

```
T1 (beforeEach) ──> T2 (T016 ingestion)
                ──> T3 (T017 throttle)
                ──> T4 (T018 cold start)
                ──> T5 (T019 trigger)
                ──> T6 (T020 timeout)
                ──> T7 (T021 recovery)
T1-T7 ──────────> T8 (verification)
```

## Tasks

### T1: Fix beforeEach page-ready wait
**File**: `frontend/tests/e2e/chaos-scenarios.spec.ts`
**Action**: Replace line 24
**Details**:
- Remove `await page.waitForTimeout(3000);`
- Replace with `await expect(page.locator('main')).toBeVisible({ timeout: 10000 });`
- Add `import { expect } from '@playwright/test';` if not already imported (it is -- line 2)

**Acceptance**: beforeEach waits for main element, not arbitrary timeout.

---

### T2: Fix T016 -- content comparison and mandatory freshness
**File**: `frontend/tests/e2e/chaos-scenarios.spec.ts`
**Action**: Modify T016 test body (lines 28-72)
**Details**:

1. After `expect(textDuring!.length).toBeGreaterThan(10);` (line 61), add:
   ```typescript
   // Verify content identity -- not just "something is visible"
   const fragment = textBefore!.substring(0, 20);
   expect(textDuring).toContain(fragment);
   ```

2. Replace lines 65-68 (optional freshness check):
   ```typescript
   // BEFORE (optional):
   if (await freshnessIndicator.isVisible({ timeout: 3000 }).catch(() => false)) {
     const freshnessState = await freshnessIndicator.getAttribute('data-freshness-state');
     expect(['stale', 'critical']).toContain(freshnessState);
   }

   // AFTER (mandatory):
   await expect(freshnessIndicator).toBeVisible({ timeout: 5000 });
   const freshnessState = await freshnessIndicator.getAttribute('data-freshness-state');
   expect(['stale', 'critical']).toContain(freshnessState);
   ```

**Acceptance**: Test fails if (a) textDuring doesn't contain textBefore fragment, or (b) freshness indicator is not visible.

---

### T3: Fix T017 -- response-driven waits
**File**: `frontend/tests/e2e/chaos-scenarios.spec.ts`
**Action**: Modify T017 test body (lines 75-107)
**Details**:

Replace each `waitForTimeout(1500)` after search fill:
```typescript
// BEFORE:
await searchInput.fill('AAPL');
await page.waitForTimeout(1500);

// AFTER:
await searchInput.fill('AAPL');
await page.waitForResponse((r) => r.url().includes('/api/') && r.status() === 503);
```

Apply the same pattern for GOOG and MSFT fills (3 total replacements).

**Acceptance**: No `waitForTimeout` remains in T017 body (exclude beforeEach).

---

### T4: Fix T018 -- mandatory skeleton assertion
**File**: `frontend/tests/e2e/chaos-scenarios.spec.ts`
**Action**: Modify T018 test body (lines 110-133)
**Details**:

1. Remove `.catch(() => {...})` from skeleton assertion (lines 122-124):
   ```typescript
   // BEFORE:
   await expect(skeletons.first()).toBeVisible({ timeout: 2000 }).catch(() => {
     // If no skeletons visible, the page may have cached data -- still valid
   });

   // AFTER:
   await expect(skeletons.first()).toBeVisible({ timeout: 2000 });
   ```

2. Replace `await page.waitForTimeout(5000);` (line 127) with:
   ```typescript
   await page.waitForResponse(
     (r) => r.url().includes('/api/') && r.ok(),
     { timeout: 10000 },
   );
   ```

**Acceptance**: Test fails if no skeleton is visible during cold start delay. Post-load wait is response-driven.

---

### T5: Fix T019 -- content comparison and mandatory freshness
**File**: `frontend/tests/e2e/chaos-scenarios.spec.ts`
**Action**: Modify T019 test body (lines 136-179)
**Details**:

1. Replace `await page.waitForTimeout(2000);` (line 163) with:
   ```typescript
   await page.waitForTimeout(2000);
   ```
   Note: This wait is for chaos to "take effect" (SSE route handlers to start catching
   requests). There's no specific response to wait for since the chaos scenario fulfills
   with empty data. Keep this one.

2. After `expect(textDuring!.length).toBeGreaterThan(10);` (line 168), add:
   ```typescript
   const fragment = textBefore!.substring(0, 20);
   expect(textDuring).toContain(fragment);
   ```

3. Replace lines 172-175 (optional freshness check):
   ```typescript
   // BEFORE (optional):
   if (await freshnessIndicator.isVisible({ timeout: 3000 }).catch(() => false)) {
     const freshnessState = await freshnessIndicator.getAttribute('data-freshness-state');
     expect(freshnessState).toBe('critical');
   }

   // AFTER (mandatory):
   await expect(freshnessIndicator).toBeVisible({ timeout: 5000 });
   const freshnessState = await freshnessIndicator.getAttribute('data-freshness-state');
   expect(freshnessState).toBe('critical');
   ```

**Acceptance**: Test fails if (a) content fragment mismatch, or (b) freshness indicator absent/wrong state.

---

### T6: Fix T020 -- AND-logic and response-driven waits
**File**: `frontend/tests/e2e/chaos-scenarios.spec.ts`
**Action**: Modify T020 test body (lines 182-211)
**Details**:

1. Replace each `waitForTimeout(1500)` with `waitForResponse` (same pattern as T3):
   ```typescript
   await searchInput.fill('AAPL');
   await page.waitForResponse((r) => r.url().includes('/api/'));
   ```
   Note: For api_timeout scenario, routes are aborted (not 503), so match any response
   or use a timeout-safe pattern. Since `route.abort('timedout')` doesn't produce a
   response, keep `waitForTimeout(1500)` for T020 specifically OR use
   `page.waitForEvent('requestfailed')`.

   Revised approach -- use `waitForEvent('requestfailed')`:
   ```typescript
   await searchInput.fill('AAPL');
   await page.waitForEvent('requestfailed', { timeout: 5000 });
   ```

2. Replace OR logic (lines 205-208):
   ```typescript
   // BEFORE:
   expect(bannerVisible || hasContent).toBeTruthy();

   // AFTER:
   expect(bannerVisible).toBeTruthy();
   expect(hasContent).toBeTruthy();
   ```

**Acceptance**: Test asserts BOTH banner AND content. Waits are event-driven.

---

### T7: Fix T021 -- strict recovery assertion
**File**: `frontend/tests/e2e/chaos-scenarios.spec.ts`
**Action**: Modify T021 test body (lines 214-240)
**Details**:

Replace lines 235-239:
```typescript
// BEFORE:
const response = await responsePromise.catch(() => null);
expect(response === null || response.ok()).toBeTruthy();

// AFTER:
const response = await responsePromise;
expect(response.ok()).toBeTruthy();
```

**Acceptance**: Test fails if no successful API response is received within 10s timeout.

---

### T8: Verification
**Action**: Run test suite
**Details**:
```bash
cd frontend && npx playwright test chaos-scenarios.spec.ts --reporter=list
```

Verify:
- All 6 tests pass
- No `waitForTimeout` remains in test bodies (only in T016/T019 chaos settle wait -- documented exception)
- No `.catch(() => false)` or `.catch(() => null)` remains
- No OR-logic in assertions

**Acceptance**: All tests pass. Grep confirms no suppressed assertions remain.

---

## Appendix A: Adversarial Review #3 (Tasks)

### AR3-Q1: T6 uses `waitForEvent('requestfailed')` -- is this reliable?
**Challenge**: `requestfailed` fires for any request failure. Multiple in-flight requests
could race. The event might fire for a different request than the search.
**Analysis**: That's acceptable -- we need confirmation that the chaos route handler fired
for ANY request triggered by the search interaction. The specific request doesn't matter;
the assertion is on the banner visibility afterward.
**Verdict**: ACCEPT.

### AR3-Q2: T4 skeleton assertion -- will 2s timeout be enough?
**Challenge**: The cold start scenario adds a 3s delay. Skeletons should appear in <100ms
after reload. 2s is generous.
**Analysis**: Correct. The skeleton renders immediately on page load (React renders the
loading state). The 3s delay is on the API response, not on the skeleton. 2s is more
than enough.
**Verdict**: ACCEPT.

### AR3-Q3: T5 keeps `waitForTimeout(2000)` -- inconsistent with other tasks?
**Challenge**: Other tasks replace `waitForTimeout` with response-driven waits. T5 keeps it.
**Analysis**: T016/T019 simulate ingestion/trigger failure which fulfill SSE/articles with
empty arrays. There's no specific response to "wait for" because the chaos scenario
responds instantly with empty data. The 2s wait allows the dashboard to attempt refetches
that hit the mock. This is a legitimate case where no single response signals "chaos is
active." Documented as exception.
**Verdict**: ACCEPT with documentation note in code comment.

### AR3-Q4: Is the task set complete? Any missed assertions?
**Audit**:
- beforeEach: T1 (fixed)
- T016: T2 (content + freshness -- fixed)
- T017: T3 (response waits -- fixed)
- T018: T4 (skeleton + post-load -- fixed)
- T019: T5 (content + freshness -- fixed)
- T020: T6 (AND + waits -- fixed)
- T021: T7 (recovery -- fixed)
- Verification: T8

All 6 tests covered. No gaps.
**Verdict**: COMPLETE.

---

## READY FOR IMPLEMENTATION

All adversarial reviews passed. No blocking issues. Feature depends on 1339 (complete).
Single-file change with 7 surgical edits + verification.

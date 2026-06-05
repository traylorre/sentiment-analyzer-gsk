# Feature 1329: Tasks

## Task Dependency Graph

```
T1 (auth-helper.ts)
 ├─> T2 (sanity.spec.ts)
 ├─> T3 (dashboard-interactions.spec.ts)
 ├─> T4 (sentiment-visibility.spec.ts)
 ├─> T5 (chart-edge-cases.spec.ts)
 └─> T6 (chart-zoom-data.spec.ts)
      └─> T7 (verification)
```

T2-T6 are independent and can be done in any order. T1 must be first. T7 must be last.

---

## T1: Add `mockAnonymousAuth()` to auth-helper.ts

**File**: `frontend/tests/e2e/helpers/auth-helper.ts`
**Depends on**: Nothing
**Spec ref**: FR-001, NFR-002

### Actions
1. Add the following function after the existing `mockOAuthRedirect` function (after line 123):

```typescript
/**
 * Mock anonymous auth endpoint via Playwright route interception.
 *
 * Intercepts POST /api/v2/auth/anonymous and returns a mock token response.
 * Must be called BEFORE page.goto('/') to ensure the route is registered
 * before the app's useSessionInit() fires on load.
 *
 * @param page - Playwright page instance
 */
export async function mockAnonymousAuth(page: Page): Promise<void> {
  await page.route('**/api/v2/auth/anonymous', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'mock-test-token',
        token_type: 'bearer',
        auth_type: 'anonymous',
        user_id: 'anon-test-user',
        session_expires_in_seconds: 3600,
      }),
    });
  });
}
```

### Verification
- File compiles (TypeScript): `npx tsc --noEmit frontend/tests/e2e/helpers/auth-helper.ts` or rely on IDE
- `Page` type is already imported on line 10

---

## T2: Add auth mock to sanity.spec.ts

**File**: `frontend/tests/e2e/sanity.spec.ts`
**Depends on**: T1
**Spec ref**: FR-002, NFR-003
**Fixes**: 16 auth-race failures

### Actions
1. Add import after line 2:
   ```typescript
   import { mockAnonymousAuth } from './helpers/auth-helper';
   ```

2. Modify `beforeEach` (lines 5-7) from:
   ```typescript
   test.beforeEach(async ({ page }) => {
     await page.goto('/');
   });
   ```
   To:
   ```typescript
   test.beforeEach(async ({ page }) => {
     await mockAnonymousAuth(page);
     await page.goto('/');
   });
   ```

### Critical constraint
`mockAnonymousAuth(page)` MUST be before `page.goto('/')` (AR1-003).

### Verification
```bash
npx playwright test sanity.spec.ts --project="Desktop Chrome"
```
Expected: 16 tests pass (0 auth-race failures).

---

## T3: Add auth mock to dashboard-interactions.spec.ts

**File**: `frontend/tests/e2e/dashboard-interactions.spec.ts`
**Depends on**: T1
**Spec ref**: FR-003, NFR-003
**Fixes**: 4 auth-race failures

### Actions
1. Add import after line 3 (after existing `assertCleanState` import):
   ```typescript
   import { mockAnonymousAuth } from './helpers/auth-helper';
   ```

2. Add `test.beforeEach` immediately after `test.setTimeout(30_000);` (after line 6):
   ```typescript
   test.beforeEach(async ({ page }) => {
     await mockAnonymousAuth(page);
   });
   ```

### Why no `page.goto('/')` in beforeEach
Each test already calls `page.goto('/')` as its first action. The `beforeEach` only sets up the route mock. Playwright runs `beforeEach` before the test body, so the mock is active when `goto` fires.

### test.fixme handling
The `test.fixme('chart hover shows tooltip')` test is skipped entirely by Playwright. The `beforeEach` does not run for it. No impact.

### Verification
```bash
npx playwright test dashboard-interactions.spec.ts --project="Desktop Chrome"
```
Expected: 7 active tests pass (1 fixme skipped), 0 auth-race failures.

---

## T4: Add auth mock to sentiment-visibility.spec.ts

**File**: `frontend/tests/e2e/sentiment-visibility.spec.ts`
**Depends on**: T1
**Spec ref**: FR-004, NFR-003
**Fixes**: 1 auth-race failure

### Actions
1. Add import after line 2:
   ```typescript
   import { mockAnonymousAuth } from './helpers/auth-helper';
   ```

2. Add `test.beforeEach` after `test.setTimeout(30000);` (after line 5, before the `searchAndSelectTicker` function):
   ```typescript
   test.beforeEach(async ({ page }) => {
     await mockAnonymousAuth(page);
   });
   ```

### Note
The existing `searchAndSelectTicker()` helper and rate-limit retry logic are unaffected. The auth mock eliminates the auth race; the rate-limit handling addresses a separate concern (search API 429s).

### Verification
```bash
npx playwright test sentiment-visibility.spec.ts --project="Desktop Chrome"
```
Expected: 3 tests pass, 0 auth-race failures.

---

## T5: Deduplicate chart-edge-cases.spec.ts

**File**: `frontend/tests/e2e/chart-edge-cases.spec.ts`
**Depends on**: T1
**Spec ref**: FR-005
**Fixes**: 0 (deduplication only, this file already mocks auth)

### Actions
1. Add import after line 5 (after existing `mock-api-data` import):
   ```typescript
   import { mockAnonymousAuth } from './helpers/auth-helper';
   ```

2. Replace inline auth mock in `beforeEach` (lines 17-29):

   **Remove** (lines 16-29):
   ```typescript
     // Mock anonymous auth so the dashboard loads
     await page.route('**/api/v2/auth/anonymous', async (route) => {
       await route.fulfill({
         status: 201,
         contentType: 'application/json',
         body: JSON.stringify({
           access_token: 'mock-test-token',
           token_type: 'bearer',
           auth_type: 'anonymous',
           user_id: 'anon-test-user',
           session_expires_in_seconds: 3600,
         }),
       });
     });
   ```

   **Replace with**:
   ```typescript
     // Mock anonymous auth so the dashboard loads
     await mockAnonymousAuth(page);
   ```

3. Keep the ticker search mock (lines 32-40) unchanged.

### Verification
```bash
npx playwright test chart-edge-cases.spec.ts --project="Desktop Chrome"
```
Expected: Same pass/fail results as before (no behavioral change).

---

## T6: Deduplicate chart-zoom-data.spec.ts

**File**: `frontend/tests/e2e/chart-zoom-data.spec.ts`
**Depends on**: T1
**Spec ref**: FR-006
**Fixes**: 0 (deduplication only, this file already mocks auth)

### Actions
1. Add import after line 2:
   ```typescript
   import { mockAnonymousAuth } from './helpers/auth-helper';
   ```

2. Replace inline auth mock in `beforeEach` (lines 19-32):

   **Remove** (lines 19-32):
   ```typescript
     // Mock anonymous auth so the dashboard loads without real backend
     await page.route('**/api/v2/auth/anonymous', async (route) => {
       await route.fulfill({
         status: 201,
         contentType: 'application/json',
         body: JSON.stringify({
           access_token: 'mock-test-token',
           token_type: 'bearer',
           auth_type: 'anonymous',
           user_id: 'anon-test-user',
           session_expires_in_seconds: 3600,
         }),
       });
     });
   ```

   **Replace with**:
   ```typescript
     // Mock anonymous auth so the dashboard loads without real backend
     await mockAnonymousAuth(page);
   ```

### Verification
```bash
npx playwright test chart-zoom-data.spec.ts --project="Desktop Chrome"
```
Expected: Same pass/fail results as before (no behavioral change).

---

## T7: Full verification

**Depends on**: T2, T3, T4, T5, T6
**Spec ref**: NFR-004

### Actions
1. Run all 5 affected test files together:
   ```bash
   cd frontend
   npx playwright test sanity.spec.ts dashboard-interactions.spec.ts chart-zoom-data.spec.ts chart-edge-cases.spec.ts sentiment-visibility.spec.ts --project="Desktop Chrome"
   ```

2. Verify:
   - 0 auth-race failures (timeout waiting for chart data, "0 price candles" assertions)
   - All previously passing tests still pass
   - chart-edge-cases.spec.ts and chart-zoom-data.spec.ts may still have their pre-existing non-auth failures

3. Grep for any remaining inline auth mock patterns to ensure deduplication is complete:
   ```bash
   grep -rn "api/v2/auth/anonymous" frontend/tests/e2e/*.spec.ts
   ```
   Expected: 0 results (all moved to auth-helper.ts). The only remaining inline mock is in `mock-api-data.ts` (FR-007 option b).

### Success criteria
- [ ] 21 auth-race failures resolved
- [ ] No regressions in previously passing tests
- [ ] Auth mock defined in exactly one place (auth-helper.ts)
- [ ] All 5 test files import from shared helper
- [ ] `mockTickerDataApis()` in mock-api-data.ts unchanged

---

## Estimated Effort

| Task | Lines Changed | Complexity | Time |
|------|--------------|------------|------|
| T1 | +20 | Trivial | 2 min |
| T2 | +3, ~1 | Trivial | 2 min |
| T3 | +5 | Trivial | 2 min |
| T4 | +5 | Trivial | 2 min |
| T5 | +2, -13 | Trivial | 2 min |
| T6 | +2, -13 | Trivial | 2 min |
| T7 | 0 | Low | 5 min |
| **Total** | **+37, -26** | **Trivial** | **~17 min** |

---

## Adversarial Review #3: Final Readiness Check

### AR3-001: T2 line numbers may be off after import addition (NO ISSUE)
Adding an import line after line 2 shifts all subsequent line numbers by 1. The `beforeEach` at "lines 5-7" becomes lines 6-8. However, the task uses the code pattern (not line numbers) for the edit target, so this is a non-issue for implementation.

**Status**: No action needed.

### AR3-002: T3 inserts `beforeEach` inside `test.describe` but after `test.setTimeout` (VERIFIED)
Checked: `test.setTimeout(30_000)` is on line 6 inside the `test.describe` block. The first test starts on line 8. Inserting `test.beforeEach` between them is syntactically valid and follows Playwright convention (configuration before tests).

**Status**: Verified correct.

### AR3-003: T4 inserts `beforeEach` before `searchAndSelectTicker` function definition (VERIFIED)
Checked: The function definition is inside the `test.describe` block (line 7). Inserting `test.beforeEach` before a function definition is valid TypeScript — function declarations are hoisted. However, this is a function expression assigned to a const, which is NOT hoisted. The `beforeEach` does not reference `searchAndSelectTicker`, so ordering doesn't matter.

**Status**: Verified correct.

### AR3-004: T5 import placement after existing mock-api-data import (VERIFIED)
Checked: chart-edge-cases.spec.ts has imports on lines 3-6 (mock-api-data). Adding the auth-helper import on line 7 is correct and follows the existing grouping pattern (test helpers together).

**Status**: Verified correct.

### AR3-005: T7 grep verification command correctness (MINOR)
The grep command `grep -rn "api/v2/auth/anonymous" frontend/tests/e2e/*.spec.ts` uses shell globbing which only matches files in the immediate directory (not subdirectories). Since all spec files are in `frontend/tests/e2e/` directly (no subdirectories), this is correct.

**Status**: Verified correct.

### AR3-006: No task for updating mock-api-data.ts (CORRECT PER SPEC)
FR-007 option (b) explicitly says leave `mockTickerDataApis()` unchanged. No task needed. The duplicate mock in mock-api-data.ts is intentional per the plan's design decision.

**Status**: Correct by design.

### AR3-007: Task count alignment with feature description (VERIFIED)
Feature description says 27 failures across 5 files. Tasks address all 5 files. Clarification Q5 noted that 21 are auth-race (T2: 16, T3: 4, T4: 1) and 6 are pre-existing (T5: 3 chart-edge-cases, T6: 3 chart-zoom-data). Total coverage is complete.

**Status**: Verified correct.

### Summary
| ID | Severity | Status |
|----|----------|--------|
| AR3-001 | NONE | Non-issue |
| AR3-002 | NONE | Verified |
| AR3-003 | NONE | Verified |
| AR3-004 | NONE | Verified |
| AR3-005 | MINOR | Verified |
| AR3-006 | NONE | Correct by design |
| AR3-007 | NONE | Verified |

**READY FOR IMPLEMENTATION.** Zero blocking issues. All tasks are well-specified with exact code changes and verification commands.

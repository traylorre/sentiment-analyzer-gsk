# Feature 1329: Implementation Plan

## Approach: Shared Helper + Per-File beforeEach

### Design Decision: Shared helper vs. per-file inline mock

**Options considered:**

1. **Per-file inline mock** — Copy the 12-line route intercept into each file's `beforeEach`
2. **Shared helper function** — Extract `mockAnonymousAuth(page)` to `auth-helper.ts`, import in each file
3. **Playwright fixture** — Create a custom fixture that auto-mocks auth for all tests
4. **Global setup** — Mock auth in `global-setup.ts` for all tests

**Chosen: Option 2 (Shared helper function)**

Rationale:
- Option 1 violates DRY — 5 copies of the same mock to maintain
- Option 3 is over-engineered — a fixture changes the test authoring pattern and affects ALL tests, not just the ones that need mocking. Some tests may intentionally want to test without auth mocking.
- Option 4 is too broad — global setup runs once per worker, not per test. Route interception is per-page and must be set up fresh for each test's page instance.
- Option 2 is minimal, explicit, and composable. Each test file opts-in by importing and calling the helper.

### Design Decision: Where to put the helper

**Chosen: `frontend/tests/e2e/helpers/auth-helper.ts`**

This file already exists and contains auth-related utilities (`createAnonymousSession`, `setupAuthSession`, `mockOAuthRedirect`). Adding `mockAnonymousAuth` here is a natural extension. The function name follows the existing pattern (`mockOAuthRedirect` -> `mockAnonymousAuth`).

### Design Decision: Handle mock-api-data.ts duplication

**Chosen: Leave `mockTickerDataApis()` unchanged (FR-007 option b)**

The chaos test helper mocks 4 endpoints together (auth + search + OHLC + sentiment). Refactoring it to call `mockAnonymousAuth()` internally would:
- Create a coupling between chaos test helpers and auth test helpers
- Require changing the cleanup function's `unroute` logic
- Risk breaking the chaos tests for zero user benefit

The auth mock code is 12 lines — the cost of duplication is far lower than the risk of coupling.

## Implementation Steps

### Step 1: Add `mockAnonymousAuth()` to auth-helper.ts

Add to `frontend/tests/e2e/helpers/auth-helper.ts`:

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

**Why `Page` import is already available**: The file already imports `type Page` from `@playwright/test`.

### Step 2: Update sanity.spec.ts

Current `beforeEach` (line 5-7):
```typescript
test.beforeEach(async ({ page }) => {
  await page.goto('/');
});
```

Change to:
```typescript
test.beforeEach(async ({ page }) => {
  await mockAnonymousAuth(page);
  await page.goto('/');
});
```

Add import at top:
```typescript
import { mockAnonymousAuth } from './helpers/auth-helper';
```

**Critical**: `mockAnonymousAuth` MUST come before `page.goto('/')` (AR1-003).

### Step 3: Update dashboard-interactions.spec.ts

Add a top-level `beforeEach` that only mocks auth:
```typescript
test.describe('Dashboard Interactions (Feature 1247)', () => {
  test.setTimeout(30_000);

  test.beforeEach(async ({ page }) => {
    await mockAnonymousAuth(page);
  });

  // ... existing tests unchanged (each still has its own page.goto('/'))
```

Add import at top:
```typescript
import { mockAnonymousAuth } from './helpers/auth-helper';
```

**Why this works**: Each test already calls `page.goto('/')` as its first action. The `beforeEach` runs before each test, setting up the route mock. By the time `goto` fires, the mock is already active.

### Step 4: Update sentiment-visibility.spec.ts

Add a top-level `beforeEach`:
```typescript
test.describe('Sentiment Data Visibility', () => {
  test.setTimeout(30000);

  test.beforeEach(async ({ page }) => {
    await mockAnonymousAuth(page);
  });

  // ... existing code unchanged
```

Add import at top:
```typescript
import { mockAnonymousAuth } from './helpers/auth-helper';
```

**Note**: The existing `searchAndSelectTicker()` helper function and rate-limit retry logic are unaffected.

### Step 5: Deduplicate chart-edge-cases.spec.ts

Replace the inline auth mock in `beforeEach` (lines 17-29) with the shared helper:

Current:
```typescript
test.beforeEach(async ({ page }) => {
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

  // Mock ticker search to return AAPL
  await page.route('**/api/v2/tickers/search**', ...
```

Change to:
```typescript
test.beforeEach(async ({ page }) => {
  // Mock anonymous auth so the dashboard loads
  await mockAnonymousAuth(page);

  // Mock ticker search to return AAPL
  await page.route('**/api/v2/tickers/search**', ...
```

Add import at top:
```typescript
import { mockAnonymousAuth } from './helpers/auth-helper';
```

### Step 6: Deduplicate chart-zoom-data.spec.ts

Replace the inline auth mock in `beforeEach` (lines 20-31) with the shared helper:

Current:
```typescript
test.beforeEach(async ({ page }) => {
  // Mock anonymous auth so the dashboard loads without real backend
  await page.route('**/api/v2/auth/anonymous', async (route) => {
    await route.fulfill({
      ...
    });
  });
});
```

Change to:
```typescript
test.beforeEach(async ({ page }) => {
  // Mock anonymous auth so the dashboard loads without real backend
  await mockAnonymousAuth(page);
});
```

Add import at top:
```typescript
import { mockAnonymousAuth } from './helpers/auth-helper';
```

### Step 7: Verification

Run the full affected test suite:
```bash
cd frontend
npx playwright test sanity.spec.ts dashboard-interactions.spec.ts chart-zoom-data.spec.ts chart-edge-cases.spec.ts sentiment-visibility.spec.ts --project="Desktop Chrome"
```

Expected: 0 auth-related failures. (chart-edge-cases.spec.ts may still have its 3 non-auth failures.)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Mock response format drift | Low | Medium | Single source of truth in auth-helper.ts |
| Route not registered in time | Low | High | NFR-003 enforces mock-before-goto ordering |
| Breaks existing passing tests | Very Low | High | Only adding route intercepts, not changing test logic |
| chart-edge-cases behavioral change | Very Low | Medium | Same mock response, just different source |

## Dependency Order

```
Step 1 (auth-helper.ts) 
  -> Steps 2-6 (all test files, independent of each other)
    -> Step 7 (verification)
```

Steps 2-6 can be done in any order or in parallel. Step 1 must be done first. Step 7 must be done last.

---

## Adversarial Review #2: Spec-Plan Drift Check

### AR2-001: Spec says "1 failure" for sentiment-visibility but file has 3 tests (NO DRIFT)
The spec table says sentiment-visibility.spec.ts has "1 failure". The file has 3 tests. The feature description says 1 failure — this is the observed failure count from CI, not the test count. All 3 tests could have the race condition, but only 1 was caught. After the fix, all 3 get the mock, which is defensive and correct. The plan correctly adds a `beforeEach` that covers all 3 tests.

**Status**: No action needed.

### AR2-002: Plan Step 3 says "4 active tests" but spec says "4 failures" (NO DRIFT)
dashboard-interactions.spec.ts has 7 active tests + 1 `test.fixme` = 8 total. The spec says 4 failures. The plan adds `beforeEach` to all tests. The discrepancy between "4 failures" and "8 tests" is fine — some tests may pass intermittently without the mock (e.g., if auth completes fast enough). Adding the mock to all tests is the correct defensive approach.

**Status**: No action needed.

### AR2-003: Plan doesn't mention `clean-state.ts` import in dashboard-interactions.spec.ts (NO DRIFT)
dashboard-interactions.spec.ts already imports `assertCleanState` from `./helpers/clean-state`. The plan adds a new import for `mockAnonymousAuth` from `./helpers/auth-helper`. Both imports coexist. No conflict.

**Status**: No action needed.

### AR2-004: Spec FR-007 says option (b) but plan could conflict if future dev calls both (LOW)
The plan explicitly states "Leave `mockTickerDataApis()` unchanged" and provides rationale. This matches spec FR-007 option (b). No drift.

**Status**: No action needed.

### AR2-005: Clarification Q5 says actual auth-race count is 21, not 27. Success criteria says 27. (MINOR DRIFT)
The spec's success criteria say "All 27 previously failing tests pass" but Q5 clarified that only 21 are auth-race failures. The plan's Step 7 correctly says "0 auth-related failures" with a note about chart-edge-cases having other failures.

**Resolution**: This is a documentation inconsistency, not an implementation issue. The spec success criteria should be updated to say "All 21 auth-race failures resolved; 6 pre-existing failures in chart-edge-cases and chart-zoom-data unaffected." However, since the spec is already sealed after AR1, this note serves as the correction.

**Status**: Documented, no plan change needed.

### Summary
No CRITICAL or HIGH drift found. One MINOR documentation inconsistency (AR2-005) documented but not actionable. Plan is consistent with spec.

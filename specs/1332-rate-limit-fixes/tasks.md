# Tasks: 1332-rate-limit-fixes

## Phase 1: createTestConfig Mock (config-crud -- 4 failures)

### Task 1.1: Add auth mock to createTestConfig
- **File**: `frontend/tests/e2e/helpers/clean-state.ts`
- **Action**: At the start of `createTestConfig()` (after line 37), add:
  ```typescript
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
- **Why**: SessionProvider blocks page rendering until anonymous auth completes. Under parallel load, real auth API is throttled.
- **Status**: pending

### Task 1.2: Add ticker search mock to createTestConfig
- **File**: `frontend/tests/e2e/helpers/clean-state.ts`
- **Action**: After the auth mock (Task 1.1), add:
  ```typescript
  await page.route('**/api/v2/tickers/search**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        results: [{ symbol: 'AAPL', name: 'Apple Inc', exchange: 'NASDAQ' }],
      }),
    });
  });
  ```
- **Why**: Eliminates DynamoDB throughput dependency. 20 parallel tests no longer hit real search API.
- **Status**: pending

### Task 1.3: Remove retry loop from createTestConfig
- **File**: `frontend/tests/e2e/helpers/clean-state.ts`
- **Action**: Replace the retry loop (lines 65-78) with a simple fill + click:
  ```typescript
  await tickerInput.first().fill('AAPL');
  const option = page.getByRole('option', { name: /AAPL/i });
  await expect(option).toBeVisible({ timeout: 5000 });
  await option.click();
  await page.waitForTimeout(500);
  ```
- **Why**: Retry loop was a workaround for real API failures. With mocked API, first attempt always succeeds.
- **Depends on**: Task 1.2
- **Status**: pending

### Task 1.4: Add route cleanup to createTestConfig
- **File**: `frontend/tests/e2e/helpers/clean-state.ts`
- **Action**: Before the function returns (after line 86), add:
  ```typescript
  // Clean up mocks to avoid leaking into subsequent test actions
  await page.unroute('**/api/v2/auth/anonymous');
  await page.unroute('**/api/v2/tickers/search**');
  ```
- **Why**: Prevents mock routes from interfering with other tests in the same page context.
- **Depends on**: Task 1.1, Task 1.2
- **Status**: pending

## Phase 2: ticker-search-gaps Timing Fix (2 failures)

### Task 2.1: Add visibility wait in "no tickers found" test
- **File**: `frontend/tests/e2e/ticker-search-gaps.spec.ts`
- **Action**: After line 45 (`const searchInput = page.getByPlaceholder(...)`), add:
  ```typescript
  await expect(searchInput).toBeVisible({ timeout: 5000 });
  ```
- **Why**: AnimatedContainer in dashboard page delays component mounting. `fill()` on non-visible element fails silently.
- **Status**: pending

### Task 2.2: Add visibility wait in "results replace no-results" test
- **File**: `frontend/tests/e2e/ticker-search-gaps.spec.ts`
- **Action**: After line 84 (`const searchInput = page.getByPlaceholder(...)`), add:
  ```typescript
  await expect(searchInput).toBeVisible({ timeout: 5000 });
  ```
- **Why**: Same as Task 2.1. Both tests in the No-Results State describe block have this issue.
- **Status**: pending

## Phase 3: error-visibility Retry Fix (1 failure)

### Task 3.1: Add auth mock to error-visibility-search describe block
- **File**: `frontend/tests/e2e/error-visibility-search.spec.ts`
- **Action**: Add a `test.beforeEach` at the top of the describe block (after line 13):
  ```typescript
  test.beforeEach(async ({ page }) => {
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
  });
  ```
- **Why**: SessionProvider blocks ALL rendering until auth completes (layout.tsx:54-58). Without this mock, the search input never appears under parallel load.
- **Status**: pending

### Task 3.2: Add searchInput visibility waits in error-visibility tests
- **File**: `frontend/tests/e2e/error-visibility-search.spec.ts`
- **Action**: In each test that uses `searchInput.fill()`, add `await expect(searchInput).toBeVisible({ timeout: 5000 })` before the fill. Applies to tests at lines: 29, 75, 98, 134, 165, 205.
- **Why**: Consistent with Phase 2 fix. Ensures element is interactive before filling.
- **Status**: pending

### Task 3.3: Replace waitForTimeout with waitForResponse in retry test
- **File**: `frontend/tests/e2e/error-visibility-search.spec.ts`
- **Action**: In "retry button triggers a new search" (line 111):
  - Line 136: Replace `await page.waitForTimeout(1500)` with `await page.waitForResponse('**/api/v2/tickers/search**')`
  - Line 145: Replace `await page.waitForTimeout(1500)` with `await page.waitForResponse('**/api/v2/tickers/search**')`
- **Why**: `waitForTimeout` is non-deterministic. `waitForResponse` waits for the actual network response, matching the pattern in ticker-search-gaps (FR-008).
- **Depends on**: Task 3.1 (auth mock must be in place for page to render)
- **Status**: pending

### Task 3.4: Replace waitForTimeout in other error-visibility tests
- **File**: `frontend/tests/e2e/error-visibility-search.spec.ts`
- **Action**: Replace all other `waitForTimeout(1500)` calls (lines 38, 76, 100, 188) with:
  ```typescript
  await page.waitForResponse('**/api/v2/tickers/search**');
  ```
- **Why**: Consistency. All these waits are after filling search input, waiting for API response.
- **Status**: pending

## Phase 4: Verification

### Task 4.1: Run config-crud tests with parallelism
- **Action**: `cd frontend && npx playwright test config-crud.spec.ts --workers=4 --repeat-each=3`
- **Expected**: All 5 tests pass, 0 failures, 0 flakes across 15 runs (5 tests x 3 repeats)
- **Status**: pending

### Task 4.2: Run ticker-search-gaps tests
- **Action**: `cd frontend && npx playwright test ticker-search-gaps.spec.ts --workers=4 --repeat-each=3`
- **Expected**: All 8 tests pass, 0 failures, 0 flakes
- **Status**: pending

### Task 4.3: Run error-visibility-search tests
- **Action**: `cd frontend && npx playwright test error-visibility-search.spec.ts --workers=4 --repeat-each=3`
- **Expected**: All 6 tests pass, 0 failures, 0 flakes
- **Status**: pending

### Task 4.4: Run full E2E suite
- **Action**: `cd frontend && npx playwright test --workers=4`
- **Expected**: No regressions in other test files. All tests pass.
- **Status**: pending

## Summary

| Phase | Tasks | Files | Failures Fixed |
|-------|-------|-------|---------------|
| 1 | 4 | clean-state.ts | 4 (config-crud) |
| 2 | 2 | ticker-search-gaps.spec.ts | 2 |
| 3 | 4 | error-visibility-search.spec.ts | 1 |
| 4 | 4 | (verification only) | -- |
| **Total** | **14** | **3 files** | **7 failures** |

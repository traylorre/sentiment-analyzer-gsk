# Implementation Plan: Fix 7 Rate Limiting and Misc E2E Test Failures

**Feature**: 1332-rate-limit-fixes
**Created**: 2026-04-05
**Approach**: Test-only changes -- mock APIs in helpers, fix timing in assertions

## Design Decisions

### D1: Mock Location -- Inside createTestConfig vs Separate Helper

**Options**:
- A) Add `page.route()` directly inside `createTestConfig()`
- B) Create a new shared helper `mockTickerSearchForSetup(page)`
- C) Reuse `mockTickerDataApis()` from `mock-api-data.ts`

**Decision**: **A** -- Inline in `createTestConfig()`. Reasoning:
- The mock is specific to the helper's needs (just ticker search, not OHLC/sentiment)
- Keeps the helper self-contained -- callers don't need to remember to set up mocks
- `mockTickerDataApis()` mocks too much (auth, OHLC, sentiment) which could mask bugs in config-crud tests
- Mock is set up at start of function and cleaned up at end -- no leakage

### D2: Auth Mock in ticker-search-gaps -- Add waitForResponse or Not

**Options**:
- A) Just add `await page.waitForResponse('**/api/v2/auth/anonymous')` after goto
- B) Add `await expect(searchInput).toBeVisible()` with timeout
- C) Both A and B

**Decision**: **B** -- Just wait for the search input. Reasoning:
- The auth mock is already set up before `page.goto()` (confirmed in code)
- `networkidle` should be sufficient for auth to complete
- The real issue is likely that the test immediately fills the input without waiting for it to be visible
- Adding a visibility wait is the minimal reliable fix
- If this doesn't fix it, escalate to option C in a follow-up

### D3: error-visibility retry -- waitForResponse vs waitForTimeout

**Options**:
- A) Replace `waitForTimeout(1500)` with `waitForResponse`
- B) Keep timeout but increase it
- C) Use both waitForResponse + short timeout

**Decision**: **A** -- Replace with `waitForResponse`. Reasoning:
- `waitForTimeout` is non-deterministic (CI machines are slower than dev laptops)
- The test already uses `waitForResponse` in ticker-search-gaps for the same pattern
- React Query's `refetch()` fires a new request immediately, so `waitForResponse` will resolve promptly
- This is the established pattern in this codebase (see FR-008 comment in ticker-search-gaps)

### D4: Auth Mock in error-visibility-search -- Add or Not

**Options**:
- A) Add auth mock to error-visibility-search tests (like ticker-search-gaps has)
- B) Leave as-is (no auth mock)

**Decision**: **A** -- Add auth mock. Reasoning:
- error-visibility-search.spec.ts currently has NO auth mock
- Without it, the anonymous session init hits the real API
- If the local API server is slow (under parallel load), session init may fail/timeout
- This explains why the retry test fails: the page may be in a degraded state
- ticker-search-gaps already has this mock and it's the correct pattern

## Implementation Order

### Phase 1: createTestConfig Mock (Fixes 4 config-crud failures)

1. In `clean-state.ts`, modify `createTestConfig()`:
   - Add `page.route('**/api/v2/tickers/search**')` at start of function, returning mock AAPL result
   - Also add `page.route('**/api/v2/auth/anonymous')` to mock auth (needed for config form rendering)
   - Remove the 3-attempt retry loop (lines 65-78) -- no longer needed with mocked API
   - Add cleanup `page.unroute()` calls before function returns
   - Keep the existing flow: fill name -> fill ticker -> click option -> submit

### Phase 2: ticker-search-gaps Timing Fix (Fixes 2 failures)

2. In `ticker-search-gaps.spec.ts`:
   - In each failing test ("no tickers found", "results replace no-results message"):
     - Add `await expect(searchInput).toBeVisible({ timeout: 5000 })` before filling
   - The auth mock is already present in `beforeEach` (lines 14-26) -- keep as-is
   - Root cause: `AnimatedContainer delay={0.1}` in dashboard page means components mount
     with a small animation delay. After `networkidle`, the input may not be interactive yet.

### Phase 3: error-visibility Retry Fix (Fixes 1 failure)

3. In `error-visibility-search.spec.ts`:
   - Add auth mock in a `test.beforeEach` for the entire describe block (CRITICAL: SessionProvider
     blocks ALL page rendering until auth completes -- confirmed in layout.tsx:54-58)
   - In "retry button triggers a new search" test:
     - Replace `await page.waitForTimeout(1500)` (line 136) with `await page.waitForResponse('**/api/v2/tickers/search**')` after filling AAPL
     - Replace `await page.waitForTimeout(1500)` (line 145) after retry click with `await page.waitForResponse('**/api/v2/tickers/search**')`
   - Also replace `waitForTimeout` in other tests in this file for consistency
   - Add `await expect(searchInput).toBeVisible({ timeout: 5000 })` before filling in all tests

## Verification Plan

### Local Verification

```bash
cd frontend
npx playwright test config-crud.spec.ts --workers=4 --repeat-each=3
npx playwright test ticker-search-gaps.spec.ts --workers=4 --repeat-each=3
npx playwright test error-visibility-search.spec.ts --workers=4 --repeat-each=3
```

`--repeat-each=3` runs each test 3 times to catch flaky behavior.

### CI Verification

PR CI will run full E2E suite with `workers: 4` and 5 browser projects. All 7 previously-failing tests must pass.

## Files Modified

| File | Lines Changed | Change Description |
|------|--------------|-------------------|
| `frontend/tests/e2e/helpers/clean-state.ts` | ~30 | Add mock routes, remove retry loop, add cleanup |
| `frontend/tests/e2e/ticker-search-gaps.spec.ts` | ~4 | Add searchInput visibility waits |
| `frontend/tests/e2e/error-visibility-search.spec.ts` | ~20 | Add auth mock, replace waitForTimeout with waitForResponse |

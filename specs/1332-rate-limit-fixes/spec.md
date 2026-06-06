# Feature Specification: Fix 7 Rate Limiting and Misc E2E Test Failures

**Feature Branch**: `1332-rate-limit-fixes`
**Created**: 2026-04-05
**Status**: Draft
**Input**: 7 Playwright E2E tests fail due to ticker search rate limiting under parallel load and misc issues across 3 test files.

## Root Cause Analysis

Three distinct failure categories across 3 test files:

| File | Failures | Root Cause | Fix Strategy |
|------|----------|------------|-------------|
| `config-crud.spec.ts` | 4 | `createTestConfig()` helper searches AAPL via real API. 4 workers x 5 browser projects = 20 parallel tests hitting DynamoDB. Throughput throttling returns 429. Retry logic (3 attempts, 2s backoff, 8s timeout) insufficient. | Mock ticker search API in `createTestConfig()` via `page.route()` |
| `ticker-search-gaps.spec.ts` | 2 | Tests already mock search API correctly. Missing auth mock -- anonymous session init fails/races, blocking search input rendering. ticker-search-gaps mocks auth in `beforeEach` but only for the describe block; need to verify the mock fires before `networkidle`. | Verify auth mock timing, add `waitForResponse` for auth if needed |
| `error-visibility-search.spec.ts` | 1 | "retry button triggers a new search" -- test clicks retry button which calls `refetch()`. The retry button is an `<a>`-styled `<button>` element (underlined text "Retry"), not a standard Button component. Selector `getByRole('button', { name: /retry/i })` should match since it IS a `<button>` element. Likely timing: `refetch()` doesn't re-trigger the route handler because React Query cache. | Verify `refetch()` behavior; may need to invalidate query cache or adjust route handler timing |

**Core Technical Insight**: The config-crud failures are the most impactful (4 of 7). The `createTestConfig()` helper is shared by multiple test files. Mocking the ticker search API there makes all dependent tests deterministic regardless of DynamoDB capacity.

## Fix 1: Mock Ticker Search in createTestConfig (config-crud.spec.ts -- 4 failures)

### Problem

`createTestConfig()` in `clean-state.ts` (lines 37-87) performs a real ticker search for AAPL. With `workers: 4` and 5 browser projects in `playwright.config.ts`, up to 20 tests run in parallel. The local API server's mock DynamoDB cannot handle this throughput.

The retry logic (lines 66-78) is:
- 3 attempts
- 2s backoff between retries
- 8s timeout per attempt

This is insufficient under 20x parallel load because the DynamoDB throttling doesn't clear within the retry window.

### Solution

Add `page.route()` mock for ticker search inside `createTestConfig()` before filling the ticker input. This mirrors the pattern already used in `ticker-search-gaps.spec.ts` and `mock-api-data.ts`.

**Why this is safe**: `createTestConfig()` is a test helper for setting up state. Its job is to create a config, not to test ticker search. Ticker search behavior is independently tested by `ticker-search-gaps.spec.ts` and `error-visibility-search.spec.ts`.

### Acceptance Criteria

1. **Given** 4 workers running 5 browser projects, **When** config-crud tests execute, **Then** all 4 tests pass without 429 errors
2. **Given** `createTestConfig()` is called, **When** ticker search is performed, **Then** it uses mocked response (no real API call)
3. **Given** mock is applied inside `createTestConfig()`, **When** test completes, **Then** mock is cleaned up (no route leak to other tests)
4. **Given** config-crud tests pass, **When** ticker-search-gaps tests run, **Then** ticker-search-gaps still independently tests search behavior

## Fix 2: Auth Mock in ticker-search-gaps.spec.ts (2 failures)

### Problem

The "no tickers found" and "results replace no-results message" tests fail intermittently. These tests already mock the search API via `page.route('**/api/v2/tickers/search**')` and mock anonymous auth in `beforeEach`.

The auth mock is set up correctly (lines 14-26). The pattern matches `mock-api-data.ts`'s `mockTickerDataApis()` helper.

Likely failure mode: the search input (`getByPlaceholder(/search tickers/i)`) is on the main dashboard page (`page.tsx` line 96), which uses `TickerInput` with `placeholder="Search tickers (e.g., AAPL, MSFT, GOOGL)"`. The auth initialization via `useSessionInit` must complete before the dashboard renders the search input.

If the anonymous auth response is slow or the mock route hasn't been registered before `page.goto('/')`, the session init times out and the page may render in a degraded state without the search input visible.

### Solution

1. Verify the auth mock is registered BEFORE `page.goto('/')` (it currently is -- lines 14-28)
2. After `page.goto('/')` + `networkidle`, explicitly wait for the search input to be visible before interacting
3. If tests still fail: add `waitForResponse('**/api/v2/auth/anonymous')` after `page.goto()` to ensure auth completes

### Acceptance Criteria

1. **Given** auth is mocked, **When** page loads, **Then** search input is visible within 5s
2. **Given** search returns empty results, **When** "ZZZZZ" is typed, **Then** "no tickers found" message appears
3. **Given** search returns empty then results, **When** query changes from "ZZZZZ" to "AAPL", **Then** results replace no-results message

## Fix 3: Retry Button in error-visibility-search.spec.ts (1 failure)

### Problem

The "retry button triggers a new search" test (lines 111-151):
1. Mocks search API to return 500 on first request, 200 on subsequent
2. Types "AAPL" and waits for error state
3. Clicks retry button
4. Expects results to appear

The retry button (ticker-input.tsx lines 183-190) is:
```tsx
<button type="button" onClick={() => refetch()} className="...">Retry</button>
```

This calls `refetch()` from React Query's `useQuery`. The issue: `refetch()` re-executes the query function `tickersApi.search(query, 5)`, which makes a new API call. The `page.route()` handler tracks `requestCount` and serves 200 on `requestCount > 1`.

Potential issue: After the error, the component may need the dropdown to remain open for the retry to trigger properly. Or the `waitForTimeout(1500)` after clicking retry may not be sufficient for React Query's error->success state transition.

### Solution

1. Replace `waitForTimeout(1500)` with `waitForResponse('**/api/v2/tickers/search**')` for deterministic timing
2. Verify the retry button click triggers a new network request (check `requestCount` increments)
3. Add explicit wait for error state to clear before asserting results

### Acceptance Criteria

1. **Given** first search returns 500, **When** error is displayed, **Then** retry button is visible
2. **Given** retry button clicked, **When** second request succeeds (200), **Then** results replace error state
3. **Given** retry succeeds, **When** results are shown, **Then** AAPL option is visible

## Non-Goals

- **Do NOT change DynamoDB capacity** -- tests should be deterministic via mocks, not dependent on infrastructure capacity
- **Do NOT change playwright.config.ts workers** -- reducing parallelism masks the underlying issue
- **Do NOT modify the TickerInput component** -- the retry button markup and React Query integration are correct
- **Do NOT add retry logic to error-visibility-search** -- the test is correct in concept, just needs timing fixes

## User Preference: DELETE Bad Tests

Per user instruction: if a test is fundamentally testing the wrong thing or is too fragile to fix cleanly, DELETE it rather than applying a weak fix. Apply this judgment during implementation.

## Files To Modify

| File | Change |
|------|--------|
| `frontend/tests/e2e/helpers/clean-state.ts` | Add `page.route()` mock for ticker search inside `createTestConfig()`, remove retry loop |
| `frontend/tests/e2e/ticker-search-gaps.spec.ts` | Add explicit search input wait; potentially add auth response wait |
| `frontend/tests/e2e/error-visibility-search.spec.ts` | Replace `waitForTimeout` with `waitForResponse` in retry test |

## Dependencies

- `mockTickerDataApis()` in `helpers/mock-api-data.ts` already provides the mock pattern -- reuse its data shapes
- `TickerInput` component (ticker-input.tsx) confirmed to have correct retry button markup at line 183-190
- Auth mock pattern confirmed working in `ticker-search-gaps.spec.ts` lines 14-26

## Risk Assessment

**Low risk**: All changes are in test files only. No production code changes. Mocking patterns are already established in the codebase. The fixes make tests more deterministic, not less thorough.

# Feature 1329: chart-auth-mock — Fix 27 chart data auth race E2E failures

## Status: DRAFT

## Problem Statement

27 Playwright E2E tests fail because the chart component fetches data before the anonymous auth session completes. The `useChartData()` hook gates React Query with `enabled: !!ticker && hasAccessToken`. The `useSessionInit()` hook calls `signInAnonymous()` on app load (~100-500ms). Tests that don't mock the auth endpoint hit a race condition: the chart renders before the token is available, resulting in "0 price candles and 0 sentiment points".

Two files already mock auth correctly:
- `chart-edge-cases.spec.ts` — inline mock in `beforeEach`
- `chart-zoom-data.spec.ts` — inline mock in `beforeEach`

Additionally, `mock-api-data.ts` exports a `mockTickerDataApis()` helper that includes auth mocking (used by chaos tests).

## User Stories

### US1: Auth mock in sanity tests
**As a** CI pipeline operator
**I want** the 16 sanity.spec.ts tests to pass reliably
**So that** the critical user path E2E suite is green

### US2: Auth mock in dashboard interaction tests
**As a** CI pipeline operator
**I want** the 4 dashboard-interactions.spec.ts tests to pass reliably
**So that** dashboard feature regression tests are green

### US3: Auth mock in sentiment visibility tests
**As a** CI pipeline operator
**I want** the 1 sentiment-visibility.spec.ts test to pass reliably
**So that** sentiment data display regression tests are green

### US4: Shared auth mock helper
**As a** test author
**I want** a single reusable auth mock function extracted to helpers/
**So that** I don't copy the same 12-line mock into every test file

### US5: Chart-edge-cases deduplication
**As a** test author
**I want** chart-edge-cases.spec.ts to use the shared helper instead of inline mock
**So that** mock response format changes only need updating in one place

## Requirements

### FR-001: Shared auth mock helper
Create or extend `frontend/tests/e2e/helpers/auth-helper.ts` with a `mockAnonymousAuth(page: Page)` function that intercepts `**/api/v2/auth/anonymous` and fulfills with the standard mock response (access_token, token_type, auth_type, user_id, session_expires_in_seconds).

### FR-002: Auth mock in sanity.spec.ts
Add `await mockAnonymousAuth(page)` to the top-level `beforeEach` in `sanity.spec.ts` (line 5-7 area). All 16 tests must receive the mock before `page.goto('/')`.

### FR-003: Auth mock in dashboard-interactions.spec.ts
Add `await mockAnonymousAuth(page)` before `page.goto('/')` in each test (or add a top-level `beforeEach` that runs before the per-test `goto`). All 4 active tests (plus the `test.fixme`) must receive the mock.

### FR-004: Auth mock in sentiment-visibility.spec.ts
Add `await mockAnonymousAuth(page)` before `page.goto('/')` in each test. All 3 tests must receive the mock.

### FR-005: Deduplicate chart-edge-cases.spec.ts
Replace the inline auth mock (lines 17-29) with `await mockAnonymousAuth(page)`. Verify no behavioral change.

### FR-006: Deduplicate chart-zoom-data.spec.ts
Replace the inline auth mock (lines 20-31) with `await mockAnonymousAuth(page)`. Verify no behavioral change.

### FR-007: mock-api-data.ts alignment
The `mockTickerDataApis()` function in `helpers/mock-api-data.ts` already mocks auth. After creating `mockAnonymousAuth()`, either:
- (a) Have `mockTickerDataApis()` call `mockAnonymousAuth()` internally, or
- (b) Leave `mockTickerDataApis()` as-is since it serves a different purpose (full API mocking for chaos tests)

Option (b) is safer — avoid coupling chaos test helpers to this change.

### NFR-001: No production code changes
This is a test-only change. Zero modifications to `src/` directory.

### NFR-002: Mock response format
The mock response must match the actual `POST /api/v2/auth/anonymous` response shape:
```json
{
  "access_token": "mock-test-token",
  "token_type": "bearer",
  "auth_type": "anonymous",
  "user_id": "anon-test-user",
  "session_expires_in_seconds": 3600
}
```

### NFR-003: Route setup before navigation
`mockAnonymousAuth(page)` must be called BEFORE `page.goto('/')` to ensure the route intercept is registered before the app makes the auth request on load.

### NFR-004: Zero test failures on Desktop Chrome
After the fix, `npx playwright test --project=Desktop\ Chrome` must report 0 failures for the 5 affected test files.

## Success Criteria

1. All 27 previously failing tests pass on Desktop Chrome
2. No regressions in already-passing tests
3. Auth mock is defined in exactly one place (the shared helper)
4. All 5 test files import from the shared helper
5. `mockTickerDataApis()` in mock-api-data.ts is unchanged (no coupling)

## Affected Files

| File | Change | Failure Count |
|------|--------|---------------|
| `frontend/tests/e2e/helpers/auth-helper.ts` | Add `mockAnonymousAuth()` function | N/A |
| `frontend/tests/e2e/sanity.spec.ts` | Add auth mock to `beforeEach` | 16 |
| `frontend/tests/e2e/dashboard-interactions.spec.ts` | Add auth mock before each `goto` | 4 |
| `frontend/tests/e2e/sentiment-visibility.spec.ts` | Add auth mock before each `goto` | 1 |
| `frontend/tests/e2e/chart-edge-cases.spec.ts` | Replace inline mock with shared helper | 3 (other issues) |
| `frontend/tests/e2e/chart-zoom-data.spec.ts` | Replace inline mock with shared helper | 3 |

## Out of Scope

- Fixing the underlying auth race condition in production code (would require `useChartData` to wait for auth)
- Mocking other API endpoints (search, OHLC, sentiment) in files that currently hit real APIs
- Adding new tests
- Changing Playwright configuration

---

## Adversarial Review #1

### AR1-001: Mocking auth hides real auth bugs (MEDIUM)
**Attack**: By mocking `**/api/v2/auth/anonymous` in all E2E tests, we lose end-to-end coverage of the actual auth flow. If the auth endpoint breaks (wrong response shape, 500 errors, slow response), no E2E test will catch it.

**Resolution**: ACCEPTED RISK. The tests affected here are chart-focused tests, not auth tests. The auth flow has its own test coverage via `auth-helper.ts`'s `createAnonymousSession()` and `setupAuthSession()` which hit the real endpoint. Additionally, sanity.spec.ts, dashboard-interactions.spec.ts, and sentiment-visibility.spec.ts currently hit real APIs for search/OHLC/sentiment data — only the auth endpoint is being mocked. The E2E suite still exercises real auth in any test that doesn't explicitly mock it. If full auth E2E coverage is needed, a dedicated auth flow test should be added separately (out of scope for this feature).

### AR1-002: Mock response format drift (MEDIUM)
**Attack**: If the real `POST /api/v2/auth/anonymous` response schema changes (e.g., renames `access_token` to `token`, adds required fields), the mock will return stale data. Tests pass but the app would break in production.

**Resolution**: MITIGATED. The mock response shape is already used in 3 places (chart-edge-cases.spec.ts, chart-zoom-data.spec.ts, mock-api-data.ts). Extracting to a shared helper actually IMPROVES this — updating the shape in one place fixes all consumers. To further mitigate, NFR-002 documents the canonical response format. If schema drift is a concern, a future feature could add contract test validation against the actual endpoint.

### AR1-003: sanity.spec.ts beforeEach ordering (HIGH)
**Attack**: In `sanity.spec.ts`, the top-level `beforeEach` (line 5-7) calls `page.goto('/')`. If `mockAnonymousAuth(page)` is added AFTER `goto`, the route won't be registered in time. The auth request fires on page load, before the mock is active.

**Resolution**: SELF-RESOLVED. FR-002 and NFR-003 both explicitly require the mock to be called BEFORE `page.goto('/')`. Implementation must restructure the `beforeEach` to: (1) `mockAnonymousAuth(page)`, (2) `page.goto('/')`. This ordering is critical and will be verified in the plan.

### AR1-004: dashboard-interactions.spec.ts has no shared beforeEach (MEDIUM)
**Attack**: Unlike sanity.spec.ts, dashboard-interactions.spec.ts has no top-level `beforeEach`. Each test calls `page.goto('/')` individually on its first line. Adding a shared `beforeEach` could conflict with `test.fixme` which has special handling. Adding the mock in each test individually defeats the DRY purpose.

**Resolution**: SELF-RESOLVED. Add a top-level `test.beforeEach` that only calls `mockAnonymousAuth(page)` (no `goto`). Each test retains its own `page.goto('/')` call. The `test.fixme` test still works because Playwright runs `beforeEach` even for fixme tests (the fixme only affects whether the test body executes). Route interception before `goto` is the correct Playwright pattern.

### AR1-005: sentiment-visibility.spec.ts uses rate-limit retry logic (LOW)
**Attack**: `sentiment-visibility.spec.ts` has a `searchAndSelectTicker()` helper with rate-limit retry logic for the search endpoint (429 handling). If we mock auth but not search, the test still hits the real search API and could be rate-limited. This feature doesn't fix all failure modes.

**Resolution**: ACCEPTED. This feature specifically addresses the 27 auth race failures. Rate-limit failures on the search endpoint are a separate concern with existing mitigation (retry logic + `test.skip`). The spec title is "chart-auth-mock", not "mock all APIs".

### AR1-006: Duplicate mock in mock-api-data.ts creates maintenance burden (LOW)
**Attack**: After this feature, auth mocking exists in two places: `mockAnonymousAuth()` in auth-helper.ts AND inline in `mockTickerDataApis()` in mock-api-data.ts. If the mock response format changes, both must be updated.

**Resolution**: ACCEPTED per FR-007 option (b). The `mockTickerDataApis()` function serves a fundamentally different purpose (full API mocking for chaos tests) and is maintained by a different feature's ownership. Coupling it to auth-helper.ts adds a transitive dependency that could break chaos tests if the auth helper changes. The duplication is intentional and documented.

### AR1-007: chart-edge-cases.spec.ts "3 failures — other issues" (LOW)
**Attack**: The spec claims chart-edge-cases.spec.ts has "3 failures — other issues". If those failures are also auth-related, this feature should fix them. If they're truly other issues, the spec should clarify what those issues are to avoid confusion.

**Resolution**: CLARIFIED. chart-edge-cases.spec.ts already mocks auth in its `beforeEach`. The 3 failures in this file are NOT auth-related — they're from the edge case assertions themselves (empty data rendering, resolution fallback banner, error state handling). This feature's deduplication (FR-005) replaces the inline mock with the shared helper but does not change test behavior or fix those 3 failures. The failure count in the table should read "0 auth failures" for this file. Updated understanding: this file contributes 0 to the 27 auth race failures; its 3 failures are from other causes.

### Summary
| ID | Severity | Status |
|----|----------|--------|
| AR1-001 | MEDIUM | ACCEPTED RISK |
| AR1-002 | MEDIUM | MITIGATED |
| AR1-003 | HIGH | SELF-RESOLVED |
| AR1-004 | MEDIUM | SELF-RESOLVED |
| AR1-005 | LOW | ACCEPTED |
| AR1-006 | LOW | ACCEPTED |
| AR1-007 | LOW | CLARIFIED |

No CRITICAL issues found. All HIGH issues self-resolved. Spec is viable.

---

## Stage 4: Clarifications

### Q1: Does `test.fixme()` in dashboard-interactions.spec.ts execute `beforeEach`?

**Answer (from Playwright docs)**: `test.fixme()` marks a test as expected-to-fail and skips execution entirely. Playwright does NOT run `beforeEach` for `test.fixme` tests. This means adding a top-level `beforeEach` with `mockAnonymousAuth(page)` will NOT affect the `test.fixme('chart hover shows tooltip')` test. This is fine — the test is already skipped, so it doesn't contribute to the 27 failures.

**Impact on plan**: None. The `beforeEach` approach for dashboard-interactions.spec.ts is safe.

### Q2: Are there other test files with the same auth race condition that aren't in the 27-failure list?

**Answer (from codebase search)**: Examined all `.spec.ts` files that import from helpers. Files that already mock auth: `chart-edge-cases.spec.ts`, `chart-zoom-data.spec.ts`, `chaos-cached-data.spec.ts` (via `mockTickerDataApis`), `ticker-search-gaps.spec.ts` (via `mockTickerDataApis`), `chaos-cross-browser.spec.ts` (via `mockTickerDataApis`). Files that use `setupAuthSession` (real auth, not mock): `alert-crud.spec.ts`, `alerts-crud.spec.ts`, `dialog-dismissal.spec.ts`, `settings-interactions.spec.ts`, `navigation.spec.ts`. Files with neither: `sanity.spec.ts`, `dashboard-interactions.spec.ts`, `sentiment-visibility.spec.ts`, `auth-menu-items.spec.ts`, `chaos-accessibility.spec.ts`, `chaos-error-boundary.spec.ts`.

The `auth-menu-items.spec.ts`, `chaos-accessibility.spec.ts`, and `chaos-error-boundary.spec.ts` files don't mock auth but may not hit the chart data race because they test non-chart functionality. This feature targets the 5 files specified in the feature description.

**Impact on plan**: None. The 5 affected files are correct.

### Q3: Does the Playwright project name need quoting? Is it "Desktop Chrome" exactly?

**Answer (from `playwright.config.ts` line 31)**: The project name is exactly `'Desktop Chrome'` (with space). The verification command should be: `npx playwright test --project="Desktop Chrome"`.

**Impact on plan**: Step 7 verification command is correct.

### Q4: Should `mockAnonymousAuth` return a cleanup function (like `mockTickerDataApis` does)?

**Answer**: `mockTickerDataApis` returns a cleanup function because chaos tests need to remove mocks mid-test (to simulate API outage after initial data load). The auth mock for our use case is set up in `beforeEach` and should persist for the entire test. Playwright automatically cleans up routes when the page is disposed between tests. No cleanup function is needed.

**Impact on plan**: `mockAnonymousAuth` returns `Promise<void>`, not a cleanup function. Simpler API.

### Q5: What is the exact failure count breakdown across the 27 failures?

**Answer (from feature description)**: sanity.spec.ts (16) + dashboard-interactions.spec.ts (4) + chart-zoom-data.spec.ts (3) + chart-edge-cases.spec.ts (3) + sentiment-visibility.spec.ts (1) = 27. However, per AR1-007, chart-edge-cases.spec.ts already mocks auth, so its 3 failures are NOT auth-related. Similarly, chart-zoom-data.spec.ts already mocks auth, so its 3 failures may also not be auth-related. The actual auth-race failure count is: 16 + 4 + 1 = 21 confirmed auth-race failures. The other 6 failures (chart-edge-cases + chart-zoom-data) exist for other reasons but benefit from deduplication.

**Impact on plan**: Success criteria adjusted — 21 auth-race failures should be fixed. The remaining 6 failures in chart-edge-cases and chart-zoom-data are pre-existing and out of scope. NFR-004 should say "0 auth-race failures" not "0 total failures".

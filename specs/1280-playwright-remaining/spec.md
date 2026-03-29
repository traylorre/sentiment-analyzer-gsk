# Spec: 1280-playwright-remaining

## Problem Statement

6 of 31 Playwright Chaos Tests consistently fail in CI (verified in Feature 1279 run). These
fall into 3 categories with distinct root causes. Additionally, the PR Merge workflow
auto-enables auto-merge on ALL PRs, causing Playwright to be cancelled before completion
every time (~3min required checks vs ~5min Playwright).

## Root Cause Analysis

### Category 1: Error Boundary A11y Tests (2 failures)

**Tests**:
- `chaos-accessibility.spec.ts:68` — error boundary fallback axe-core scan
- `chaos-accessibility.spec.ts:109` — error boundary buttons keyboard-focusable

**Root cause**: The `ErrorFallback` component in `error-boundary.tsx` has genuine WCAG 2.1 AA
violations detected by axe-core:

1. **Decorative SVGs missing `aria-hidden`**: The `<AlertTriangle>`, `<RefreshCw>`, and `<Home>`
   lucide icons render as `<svg>` elements without `aria-hidden="true"`. axe-core flags these
   as "image-alt" violations (serious) because SVGs without `aria-hidden` are treated as
   meaningful images requiring alt text.

2. **Heading hierarchy**: The ErrorFallback uses `<h2>Something went wrong</h2>`. When the
   error boundary fires in the test, the page structure is:
   - `<html>` > `<body>` > `<main>` > `<div>` (dashboard layout)
   - DesktopNav contains `<h1>` (outside ErrorBoundary) — visible on Desktop Chrome project
   - ErrorBoundary replaces children with ErrorFallback containing `<h2>`
   - This SHOULD be valid (h1 exists in DesktopNav). However, if the Desktop Chrome viewport
     triggers the mobile layout (the DesktopNav is `hidden md:flex`), the h1 may be hidden.
     The Desktop Chrome Playwright device has viewport 1280x720, which IS desktop (md breakpoint
     is 768px), so h1 should be visible. This is likely NOT the issue.

3. **Color contrast**: `text-muted-foreground` (typically `hsl(240 5% 64.9%)` = ~#9ca3af) on
   dark background (`hsl(240 10% 3.9%)` = ~#0a0a0a). Contrast ratio ~4.1:1, which passes AA
   for normal text (4.5:1 required) but is borderline. `text-red-500` (#ef4444) on dark
   background has contrast ~4.63:1 which passes.

**Most likely violation**: SVG icons without `aria-hidden="true"` (serious impact).

**For test at line 109 (keyboard focus)**: This test does NOT use axe-core. It checks button
visibility and keyboard focus. Page snapshot confirms all 3 buttons render. The test SHOULD pass
unless there's a timing issue. The failure may be because the test at line 68 fails first and
test isolation is incomplete. BUT Playwright tests are independent — a failure in one test should
not affect another. So this test has its own root cause. Looking at the test: it uses
`page.getByRole('link', { name: /go home/i }).or(page.getByRole('button', { name: /go home/i }))`.
The "Go Home" button is a `<Button>` component. The button contains `<Home>` icon + "Go Home" text.
If the `<Home>` SVG has an accessible name, the button's accessible name computation might include
it, producing something like "home icon Go Home" which still matches `/go home/i`. This should work.

More likely: the `waitForAccessibilityTree` call waits for `button` with `type` attribute. The
`<Button>` shadcn component may not set `type="button"` explicitly — HTML `<button>` elements
default to `type="submit"`, and the shadcn Button component forwards props. Without explicit
`type`, `getAttribute('type')` returns `null` (the DOM attribute is absent even though the
effective type is "submit"). The `waitForAccessibilityTree` checks `val !== null` — so it would
fail waiting for `type` attribute. But looking at `a11y-helpers.ts:35`: it checks
`el.getAttribute(attr)` returns non-null and non-empty. If `type` is not set as an HTML attribute,
this returns `null`, and the function keeps waiting until timeout.

**Fix for line 109**: The `Button` component needs explicit `type="button"` OR the test should
wait for a different attribute.

### Category 2: Cached Data Tests (3 failures)

**Tests**:
- `chaos-cached-data.spec.ts:39` — data visible during API outage
- `chaos-cached-data.spec.ts:69` — data survives API timeout
- `chaos-cross-browser.spec.ts:35` — cached data persists during outage

**Root cause**: The `useChartData` hook requires `hasAccessToken === true` to enable OHLC and
sentiment queries (`enabled: enabled && !!ticker && hasAccessToken`). In CI, the anonymous
session creation (`POST /api/v2/auth/anonymous`) may fail because:

1. The local API server uses moto for DynamoDB, which may not be fully initialized
2. The auth endpoint requires DynamoDB table access that may error under moto
3. Even if session creation succeeds, the `isInitialized` flag requires async state updates

When auth fails: search still works (no auth required for TickerInput's useQuery), the user
can search and select AAPL, the chart component mounts, but `useChartData` never fires queries
because `hasAccessToken` is false. The chart shows "Loading..." indefinitely or "No price data".
The `beforeEach` times out waiting for `aria-label` with "price candles".

The page snapshot confirms this: "Track Price & Sentiment" empty state means either the search
interaction failed OR (more likely) the `beforeEach` timed out during `expect(suggestion).toBeVisible()`
because the search API mock wasn't intercepted.

**Alternative root cause**: The `page.route()` pattern `**/api/v2/tickers/search**` may not match
cross-origin requests in Playwright. When the frontend (localhost:3000) calls
`fetch('http://localhost:8000/api/v2/tickers/search')`, this is a cross-origin request. Playwright's
`page.route()` DOES intercept cross-origin requests — the `**` prefix handles any URL scheme/host.
This should work.

**Most likely fix**: The `mockTickerDataApis()` helper must ALSO mock the auth endpoint to ensure
`hasAccessToken` is true. Alternatively, use `page.addInitScript()` to directly set auth state
in the Zustand store before the page loads.

### Category 3: SSE Reconnection (1 failure)

**Test**: `chaos-cross-browser.spec.ts:69` — SSE reconnection after connection drop

**Root cause**: The test intercepts `**/api/v2/stream**` but SSE uses a same-origin proxy at
`/api/sse/stream` (per `use-sse.ts:123`). The route pattern doesn't match the actual SSE URL.

Additionally, SSE requires:
1. Authentication (`configId` + `userToken`) — no session exists in the test
2. A selected ticker with an active config — the `beforeEach` only navigates to `/`
3. Runtime config to be loaded (SSE URL from runtime store)

Without authentication and a selected ticker, SSE never connects. No requests match
`**/api/v2/stream**`, so the test waits 15s and times out.

**Fix**: Either (a) mock the auth + config + SSE setup to actually trigger SSE connections, or
(b) rewrite the test to directly intercept the correct URL pattern and stimulate SSE requests.

### Category 4: Auto-Merge Cancellation

**Root cause**: `pr-merge.yml` Job 3 (`enable-auto-merge`) runs on `pull_request_target: [opened]`
for all non-Dependabot PRs. It calls `peter-evans/enable-pull-request-automerge@v3` which enables
auto-merge. When the 3 required checks pass (~3min), the PR auto-merges and cancels the still-running
Playwright job (~5min with retries).

**Fix**: Add `Playwright Chaos Tests` to branch protection required checks. This ensures auto-merge
waits for Playwright to complete. Since the tests must be green before this feature merges, the
tests will be stable enough for required status.

## Requirements

### Functional

#### FR-001: Fix ErrorFallback a11y violations
1. Add `aria-hidden="true"` to all decorative SVG icons in ErrorFallback (`AlertTriangle`,
   `RefreshCw`, `Home`)
2. Add explicit `role="alert"` to the error fallback container div for landmark recognition
3. Add explicit `type="button"` to all three buttons in ErrorFallback to ensure the
   `waitForAccessibilityTree` helper finds the `type` attribute
4. Ensure heading hierarchy is valid (h2 is acceptable when h1 exists in parent layout)

#### FR-002: Fix cached data test auth dependency
1. Create a `mockAuthSession(page)` helper that intercepts `POST **/api/v2/auth/anonymous` and
   returns a valid session response with an access token
2. Also inject auth state into the frontend's Zustand auth store via `page.addInitScript()`
   to set `isInitialized = true` and `hasAccessToken = true`
3. Call `mockAuthSession(page)` in `mockTickerDataApis()` or in the test `beforeEach` BEFORE
   `page.goto('/')`

#### FR-003: Fix SSE reconnection test
1. Update the route interception pattern from `**/api/v2/stream**` to also match
   `**/api/sse/stream**` (the same-origin proxy path)
2. Mock the auth session AND runtime config to enable SSE connection
3. OR rewrite the test to be less dependent on SSE actually connecting — intercept both
   possible SSE URL patterns and stimulate reconnection

#### FR-004: Add Playwright to required checks
1. Update `scripts/setup-branch-protection.sh` to include `Playwright Chaos Tests` in the
   default required checks list
2. Run the setup script to update branch protection on the repo
3. Verify that auto-merge now waits for Playwright to complete

### Non-Functional

#### NFR-001: No test infrastructure regressions
- Passing tests (9 of 31) must continue to pass
- No changes to test timeout configuration
- Mock helpers must be composable (can be used independently)

#### NFR-002: CI performance
- Auth mock must not add latency (instant response)
- Total Playwright run time must not increase significantly (target: <5min for all 31 tests)

## Acceptance Criteria

- [ ] `chaos-accessibility.spec.ts:68` passes (error boundary a11y scan)
- [ ] `chaos-accessibility.spec.ts:109` passes (error boundary keyboard focus)
- [ ] `chaos-cached-data.spec.ts:39` passes (data visible during outage)
- [ ] `chaos-cached-data.spec.ts:69` passes (data survives timeout)
- [ ] `chaos-cross-browser.spec.ts:35` passes (cached data cross-browser)
- [ ] `chaos-cross-browser.spec.ts:69` passes OR is skipped with documented reason (SSE)
- [ ] Playwright job runs to completion (not cancelled by auto-merge)
- [ ] All 9 previously passing tests continue to pass
- [ ] Branch protection updated with `Playwright Chaos Tests` required check

## Scope

### In Scope
- `frontend/src/components/ui/error-boundary.tsx` — a11y fixes
- `frontend/tests/e2e/helpers/mock-api-data.ts` — auth mock helper
- `frontend/tests/e2e/chaos-cached-data.spec.ts` — use auth mock
- `frontend/tests/e2e/chaos-cross-browser.spec.ts` — fix SSE test + auth mock
- `scripts/setup-branch-protection.sh` — add Playwright to required checks

### Out of Scope
- Fixing tests that were not reached due to cancellation (chaos-scenarios, chaos-sse-*)
- Refactoring existing passing tests
- Adding new chaos test scenarios
- Modifying the auto-merge workflow behavior (only branch protection change)

## Risk Assessment

- **Risk**: LOW. Changes are to test infrastructure and one UI component's ARIA attributes.
- **A11y fix blast radius**: ErrorFallback component only renders during errors. Adding
  `aria-hidden` to icons and `type="button"` to buttons are purely additive, non-breaking.
- **Mock auth risk**: Mocking auth in tests is standard practice. The mock is test-only code.
- **Branch protection risk**: Adding Playwright as required check means Playwright failures
  block ALL merges. Mitigated by: (a) fixing all 6 failures in this feature, (b) Playwright
  has 2 retries configured in CI.
- **Rollback**: Revert the branch protection change via API if Playwright becomes flaky.

## Dependencies

- Feature 1279 (playwright-verify) — MERGED. Provided CI evidence and artifacts.
- Feature 1275 (error-boundary-ssr) — MERGED. The `useEffect` fix for error boundary.
- Feature 1276 (mock-api-data) — MERGED. The `mockTickerDataApis` helper.

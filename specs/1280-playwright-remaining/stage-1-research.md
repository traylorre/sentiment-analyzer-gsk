# Stage 1: Research — 1280-playwright-remaining

## Problem Summary

6 Playwright Chaos Tests fail in CI across 3 categories. Feature 1279 provided the first real CI
run, producing page snapshots and error output. This feature fixes the root causes.

Additionally, the PR Merge workflow auto-enables auto-merge on ALL PRs, which cancels Playwright
before it completes (Playwright ~5min vs required checks ~3min).

## Category Analysis

### Category 1: Error Boundary A11y (2 failures)

**Files**: `chaos-accessibility.spec.ts:68`, `chaos-accessibility.spec.ts:109`

**Root cause**: The `ErrorFallback` component in `error-boundary.tsx` has genuine WCAG 2.1 AA
violations that axe-core detects:

1. **Heading hierarchy (h2 without h1)**: The error boundary renders `<h2>Something went wrong</h2>`
   but when the error boundary fires, the page content is replaced. The dashboard layout has an
   `<h1>` in the `DesktopHeader`/`DesktopNav` component, but these may not be rendered when the
   error boundary replaces all content within the `<main>` element. The ErrorBoundary wraps
   `{children}` inside `<main>` in `(dashboard)/layout.tsx:36-41`. When error fires, ErrorFallback
   replaces children — the DesktopNav (which has the h1) is OUTSIDE the ErrorBoundary, so h1
   exists. However, the test navigates to `/` which uses the dashboard layout. The `DesktopHeader`
   renders `<h1>` at desktop viewport. But the Playwright config uses `Desktop Chrome` project
   which is desktop-sized. So h1 should be visible. BUT — the error boundary test uses
   `addInitScript` to set `__TEST_FORCE_ERROR = true` then `page.goto('/')`. The page loads the
   dashboard layout which includes DesktopNav (with h1) + ErrorBoundary > ErrorTrigger > children.
   The ErrorTrigger fires useEffect after mount, sets shouldError=true, re-renders, throws. The
   ErrorBoundary catches and renders ErrorFallback. The h1 in DesktopNav/DesktopHeader IS still
   in the DOM because it's OUTSIDE the ErrorBoundary.

   So heading hierarchy is likely NOT the issue. The real a11y violations are likely:

2. **Missing landmark role on error fallback**: The ErrorFallback renders a bare `<div>` with no
   role. It replaces the main page content. axe-core may flag that content outside landmarks exists.

3. **Icon accessibility**: `<AlertTriangle>` SVG icon has no `aria-hidden` attribute. axe-core
   flags decorative SVGs without `aria-hidden="true"` as violations.

4. **Button icon accessibility**: The buttons contain SVG icons (`<RefreshCw>`, `<Home>`) alongside
   text. These icons should have `aria-hidden="true"` to prevent screen readers from announcing
   them as separate elements.

5. **Color contrast**: `text-muted-foreground` and `text-red-500` against dark backgrounds may
   fail WCAG AA contrast ratios depending on the exact theme values.

**For the keyboard-focusable test (line 109)**: This test verifies buttons have accessible names
and are focusable. The test itself looks correct. The failure is likely cascade — if the a11y test
at line 68 fails because ErrorFallback doesn't render (but page snapshot shows it DOES render),
then the actual failure in the keyboard test may be from axe-core detecting something that causes
the test assertion to fail. Actually, re-reading the test at line 109 — it doesn't use axe-core.
It manually checks button visibility and focus. If the page snapshot shows "Something went wrong"
with all 3 buttons visible, this test SHOULD pass. The failure may be in the "Go Home" button
locator: `page.getByRole('link', { name: /go home/i }).or(page.getByRole('button', { name: /go home/i }))`.
The "Go Home" button is a `<Button>` (renders as `<button>`) not a link. The `.or()` should
handle this. Need to verify the Playwright `.or()` behavior — it tries first locator, then second.
This should work. The failure may be timeout-related or the error boundary not rendering
consistently.

### Category 2: Cached Data (3 failures)

**Files**: `chaos-cached-data.spec.ts:39`, `chaos-cached-data.spec.ts:69`, `chaos-cross-browser.spec.ts:35`

**Root cause analysis**: The `mockTickerDataApis()` sets up route interceptions correctly. The
`beforeEach` in `chaos-cached-data.spec.ts` then:
1. Calls `mockTickerDataApis(page)` — sets up route mocks
2. `page.goto('/')` — navigates to dashboard
3. Fills search input with 'AAPL'
4. Waits for `option` with name 'AAPL' to be visible
5. Clicks the suggestion
6. Waits for chart container with `aria-label` matching `/[1-9]\d* price candles/`

The page snapshot shows "Track Price & Sentiment" empty state, meaning step 4 (suggestion visible)
or step 5 (click) or step 6 (chart render) failed or never happened.

**Key insight**: The `TickerInput` component uses `role="option"` for suggestions. The mock
returns `{ results: [{ symbol: 'AAPL', name: 'Apple Inc', exchange: 'NASDAQ' }] }`. The
ticker search API is intercepted at `**/api/v2/tickers/search**`. But the TickerInput component
may use a different API path or format.

The dashboard page uses `TickerInput` which calls the search API. Let me check the API path used
by the frontend. The mock intercepts `**/api/v2/tickers/search**`. If the frontend calls a
different path (e.g., `/api/tickers/search` without `v2`, or uses a proxy route), the mock
won't intercept.

The frontend may use a Next.js API route proxy (e.g., `/api/tickers/search` which proxies to
the backend `/api/v2/tickers/search`). If so, the `**/api/v2/**` pattern won't match
`/api/tickers/search`.

This is the most likely root cause: **API path mismatch between mock routes and actual frontend
API calls**.

### Category 3: SSE Reconnection (1 failure)

**File**: `chaos-cross-browser.spec.ts:69`

**Root cause**: The test intercepts `**/api/v2/stream**` and aborts with `connectionreset`. It
then waits for 2+ SSE reconnection attempts. But:

1. SSE may use a proxy route (e.g., `/api/sse/stream` per `use-sse.ts:123`)
2. SSE only connects when there's a `configId` — which requires a user to be authenticated
   and have an active config
3. The `beforeEach` in cross-browser tests just navigates to `/` and waits 2s — no ticker
   selection, no authentication

The test will never see SSE requests because:
- SSE requires authentication (configId + userToken)
- The route pattern may not match the proxy path
- No data is loaded to trigger SSE connection

### Category 4: Auto-Merge Cancellation

**File**: `.github/workflows/pr-merge.yml` (Job 3: enable-auto-merge)

The `enable-auto-merge` job runs on `pull_request_target: [opened]` for ALL non-Dependabot PRs.
It uses `peter-evans/enable-pull-request-automerge@v3` to enable auto-merge with squash strategy.

When the 3 required checks (Secrets Scan, Lint, Run Tests) pass in ~3min, auto-merge triggers
and cancels the running Playwright job (~5min).

**Fix options**:
1. Add condition to skip auto-merge for PRs that include Playwright-affecting files
2. Disable auto-merge via `gh pr merge --disable-auto` after PR creation
3. Add `Playwright Chaos Tests` to branch protection required checks
4. Add a `wait-for-playwright` job that the auto-merge depends on

Option 3 is cleanest but means Playwright failures block ALL merges. Option 2 is surgical but
requires manual intervention on each PR. Option 1 is fragile. Option 4 adds complexity.

**Recommended**: Option 3 (add to required checks) + make Playwright `continue-on-error: true`
so it reports status but doesn't block. Actually, if Playwright is a required check, it MUST pass
to merge — that defeats the purpose if tests are still flaky.

**Better approach**: Add a `playwright-gate` job that always succeeds but waits for the playwright
job. Make `playwright-gate` a required check. Auto-merge waits for it. Playwright failures are
reported but don't block.

Actually the simplest fix: the `enable-auto-merge` job should NOT run when Playwright tests
are configured. Or: the Playwright job timeout is 5min. Required checks are ~3min. Just increase
the Playwright job's priority or make auto-merge wait.

**Simplest correct fix**: After creating a PR with Playwright changes, run
`gh pr merge --disable-auto <PR>`. This is already documented in pr-merge.yml line 15. But it
requires manual action.

**Correct systematic fix**: The PR creation script (push skill) should detect if Playwright
tests exist and disable auto-merge. OR: add `Playwright Chaos Tests` as a required check in
branch protection — this is the RIGHT answer because Playwright tests SHOULD pass before merge.

## Files That Need Changes

1. `frontend/src/components/ui/error-boundary.tsx` — Fix a11y violations in ErrorFallback
2. `frontend/tests/e2e/chaos-cached-data.spec.ts` — Fix API path matching for mocked routes
3. `frontend/tests/e2e/chaos-cross-browser.spec.ts` — Fix SSE test + fix cached data test
4. `frontend/tests/e2e/helpers/mock-api-data.ts` — Fix API route patterns to match frontend paths
5. `scripts/setup-branch-protection.sh` or CI config — Add Playwright to required checks

## Files That Need Reading (for implementation)

1. `frontend/src/lib/api/tickers.ts` — Verify actual API path used by frontend
2. `frontend/src/hooks/use-chart-data.ts` — Verify OHLC/sentiment API paths
3. `scripts/setup-branch-protection.sh` — Current required checks list

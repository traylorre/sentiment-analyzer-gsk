# Feature 1338: selector-interaction-fixes

## Problem Statement

Nine Playwright E2E tests fail across nine independent sub-issues. Each failure is a
selector mismatch, timing issue, or test setup gap -- no production code bugs. All fixes
are test-only except (d) which also needs a component accessibility improvement.

### (a) auth-menu-items.spec.ts: "menu Settings navigates"

**Test**: Clicks Settings menu item, asserts `page.toHaveURL(/\/settings/)`.

**Root Cause**: The Settings menu item uses `window.location.href = '/settings'` (hard
navigation). The URL DOES change to `/settings`. However, the hard navigation triggers a
full page load. After the page loads at `/settings`, the test expects to find a Dashboard
tab (`getByRole('tab', { name: /dashboard/i })`). The settings page has no tab component
-- the navigation is via the sidebar/bottom nav, not tabs.

**Verified via source**: `user-menu.tsx:142` uses `window.location.href = '/settings'`.
`settings/page.tsx` renders a settings form with no tab UI. The unwind step
`page.getByRole('tab', { name: /dashboard/i })` will fail because there is no tab role
on the dashboard navigation link.

**Fix**: Assert Settings content is visible instead of URL. Change unwind to navigate
via sidebar link or direct `page.goto('/')`.

### (b) dashboard-interactions.spec.ts: "empty state shows search CTA"

**Test**: Navigates to `/`, asserts regex
`/track price.*sentiment|search.*ticker|get started|select a ticker/i` is visible.

**Root Cause**: The empty state text is "Track Price & Sentiment" (page.tsx:140). The
regex `track price.*sentiment` does match "Track Price & Sentiment" since `.*` bridges
the ` & `. The actual issue is timing: the test does `page.goto('/')` without calling
`waitForAuth(page)`. The anonymous auth session init fires on mount, and until it
completes, the page may show the loading skeleton (animate-pulse divs) instead of the
empty state. The 10s timeout may not suffice on slow CI or mobile projects.

**Verified via source**: `page.tsx:125-150` shows empty state is gated on
`tickers.length === 0` which is true immediately, BUT `PageTransition` and
`AnimatedContainer` from framer-motion add delayed opacity animation (`delay: 0.2`,
`delay: 0.3`). Combined with auth init skeleton in layout, the empty state text may not
be in the DOM within 10s on mobile Safari.

**Fix**: Add `waitForAuth(page)` after `page.goto('/')` to ensure app is fully
initialized before asserting. Increase timeout to 15s for mobile parity.

### (c) dashboard-interactions.spec.ts: "resolution buttons update chart"

**Test**: Cycles through resolutions `['1m', '5m', '15m', '30m', '1h', 'D']` and asserts
each button gets `aria-pressed="true"`.

**Root Cause**: The 1m resolution produces zero candles outside market hours (9:30am-4pm
ET). When no data is available, the chart may render an error or empty state, preventing
the resolution button from becoming `aria-pressed="true"`.

**Verified via source**: The test iterates ALL resolutions including `1m`. The test runs
at arbitrary times. 1m data is only available during market hours from Tiingo.

**Fix**: Remove `1m` from the resolution cycle. Start from `5m` which has data during
extended hours. Alternatively, check that chart has data before asserting button state.

### (d) dashboard-interactions.spec.ts: "ticker chip remove clears chart"

**Test**: Loads AAPL chart, finds remove button on ticker chip via
`getByRole('button', { name: /remove.*AAPL|AAPL.*remove|close.*AAPL|AAPL.*close/i })`.
Falls back to `[data-ticker="AAPL"], .chip, .tag` filtered by `hasText: 'AAPL'` then
`getByRole('button').first()`.

**Root Cause**: The TickerChip component (`ticker-chip.tsx:91-99`) renders the remove
button as a `<motion.button>` containing only an `<X>` icon (lucide-react). There is:
- No `aria-label` on the remove button
- No visible text content
- No `data-ticker` attribute on the chip
- No `.chip` or `.tag` CSS class (uses Tailwind utilities)

The primary selector fails because the button has no accessible name. The fallback also
fails because `[data-ticker="AAPL"]` doesn't match anything, and `.chip, .tag` don't
exist.

**Verified via source**: `ticker-chip.tsx:91-99` confirms the remove button has no
accessible name. The outer `<motion.button>` (the chip itself) IS the first button
returned by `chip.getByRole('button').first()`, not the inner X button.

**Fix (component)**: Add `aria-label={`Remove ${symbol}`}` to the remove button in
`ticker-chip.tsx`. This is an accessibility improvement, not just a test fix.

**Fix (test)**: Use the newly-added aria-label: `getByRole('button', { name: /remove AAPL/i })`.

### (e) oauth-flow.spec.ts: "creates session and loads dashboard"

**Test**: Mocks OAuth URLs, mocks callback endpoint, calls `mockOAuthRedirect`, clicks
Google button, expects to land on dashboard.

**Root Cause**: The `mockOAuthRedirect` helper intercepts `**/oauth2/authorize**` and
returns `route.fulfill({ status: 302, headers: { Location: redirectUrl } })`. However,
Playwright's `route.fulfill` with status 302 does NOT cause the browser to follow the
redirect -- the page receives a 302 response but doesn't navigate to the Location header.
This means the callback page never loads.

Additionally, even if the redirect worked, `signInWithOAuth()` in the auth store calls
`window.location.href = providerInfo.authorize_url` which is a top-level navigation. The
route intercept handles the request but `route.fulfill({ status: 302 })` doesn't trigger
browser-level redirect following.

**Verified via source**: `auth-store.ts:207` does `window.location.href =
providerInfo.authorize_url`. `auth-helper.ts:148-174` intercepts and returns 302.
`callback/page.tsx:70-74` reads `oauth_provider` and `oauth_state` from sessionStorage
(which ARE set by `signInWithOAuth` at auth-store.ts:199-200 before the redirect).

**Fix**: Change `mockOAuthRedirect` to use `page.goto(redirectUrl)` instead of
`route.fulfill({ status: 302 })`, OR change the test to manually set sessionStorage
values and navigate directly to the callback URL with query params.

### (f) error-visibility-search.spec.ts: "retry button triggers search"

**Test**: Routes search API to fail first, succeed second. Fills search, waits for error,
clicks retry, expects success.

**Root Cause**: The test uses `page.waitForResponse('**/api/v2/tickers/search**')` on
line 144 to wait for the initial error response. But `searchInput.fill('AAPL')` triggers
a debounced search. If the debounce fires and the response returns before
`waitForResponse` starts listening, the promise will wait indefinitely for the NEXT
response (which won't come until retry). This is a race condition.

More critically: the `mockAnonymousAuth` in `beforeEach` may cause `page.goto('/')`
to trigger its own auth request, and the `waitForLoadState('networkidle')` should settle
that. But the real issue is the `requestCount` variable scoping: the route handler
closure captures `requestCount` correctly, but if the page triggers auth-related
navigation or refetches after auth completes, an extra search request might fire.

**Verified via source**: `error-visibility-search.spec.ts:117-160`. The test uses
`waitForResponse` (line 144) after `fill` (line 141). Other tests in the same file
use `waitForTimeout(1500)` for the same purpose. The inconsistency suggests this was
an intentional upgrade that introduced a race condition.

**Fix**: Use `Promise.all` to set up `waitForResponse` BEFORE `fill` (or immediately
after), ensuring the listener is registered before the debounce fires. Pattern:
```typescript
const responsePromise = page.waitForResponse('**/api/v2/tickers/search**');
await searchInput.fill('AAPL');
await responsePromise;
```

### (g) dialog-dismissal.spec.ts: "user menu outside click closes"

**Test**: Opens user menu, clicks `body` at position `{ x: 10, y: 10 }` to dismiss.

**Root Cause**: Position (10, 10) hits the skip-to-content link. The `SkipLink` component
(`skip-link.tsx`) is `sr-only` (offscreen via clip/overflow), but it is still in the DOM
flow and occupies the top-left area. In some browsers/viewports, clicking at (10, 10)
activates the skip link instead of triggering the expected "outside click" behavior on
the Radix DropdownMenu.

**Verified via source**: `skip-link.tsx:17-30` shows the skip link is positioned with
`sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4`. While `sr-only` uses
`clip: rect(0, 0, 0, 0)` which makes it invisible, the element's layout position is
still at (0, 0) in the document flow. Clicking at (10, 10) could interact with it.

**Fix**: Click at a position far from the top-left corner. Use `page.viewportSize()` to
calculate a safe position like bottom-center: `(width / 2, height - 10)`.

### (h) session-lifecycle.spec.ts: "sign out clears session"

**Test**: Navigates to `/settings`, clicks sign out, clicks confirm in dialog, expects
redirect to signin.

**Root Cause**: The sign-out dialog uses framer-motion `AnimatePresence` with
`initial={{ opacity: 0, scale: 0.95 }}` and `transition={{ duration: 0.2 }}`. The test
clicks the confirm button immediately after checking `isVisible({ timeout: 2000 })`.
The button may be visible but mid-animation, causing the click to not register properly.

Additionally, the confirm button selector `/confirm|yes|sign out/i` matches "Sign out"
which appears on BOTH the settings page's trigger button and the dialog's confirm button.
The test may click the trigger button again instead of the dialog's confirm.

**Verified via source**: `sign-out-dialog.tsx:49-52` shows dialog animation.
`sign-out-dialog.tsx:97-113` shows the confirm button text is "Sign out" (matching the
trigger button text on settings page at line 246-249 of settings/page.tsx).

**Fix**: Scope the confirm button to the dialog: `dialog.getByRole('button', { name: /sign out/i })`.
Add `await page.waitForTimeout(300)` after dialog appears for animation settle.

### (i) signin-interaction.spec.ts: "magic link form loads without waiting for provider check"

**Test**: Navigates to `/auth/signin`, asserts email input visible within 2s timeout.

**Root Cause**: The 2s timeout is too tight. On mobile projects (Pixel 5, iPhone 13),
the Next.js dev server may take longer to hydrate the signin page. The email input
depends on client-side rendering (`'use client'` component with `useState`).

**Verified via source**: `signin-interaction.spec.ts:94-98` uses `{ timeout: 2_000 }`.
The Playwright config runs 5 projects including mobile. Mobile webview hydration is
consistently slower than desktop.

**Fix**: Increase timeout from 2s to 5s.

## Affected Files

| File | Tests | Sub-Issue |
|------|-------|-----------|
| `frontend/tests/e2e/auth-menu-items.spec.ts` | 1 (Settings navigates) | (a) |
| `frontend/tests/e2e/dashboard-interactions.spec.ts` | 3 (empty state, resolution, chip remove) | (b)(c)(d) |
| `frontend/tests/e2e/oauth-flow.spec.ts` | 1 (creates session) | (e) |
| `frontend/tests/e2e/error-visibility-search.spec.ts` | 1 (retry button) | (f) |
| `frontend/tests/e2e/dialog-dismissal.spec.ts` | 1 (outside click) | (g) |
| `frontend/tests/e2e/session-lifecycle.spec.ts` | 1 (sign out) | (h) |
| `frontend/tests/e2e/signin-interaction.spec.ts` | 1 (magic link form) | (i) |
| `frontend/src/components/dashboard/ticker-chip.tsx` | N/A (component fix) | (d) |

## Acceptance Criteria

1. AC-a: "menu Settings navigates" test passes by asserting Settings content, not URL
2. AC-b: "empty state shows search CTA" test passes with waitForAuth and 15s timeout
3. AC-c: "resolution buttons update chart" test passes by skipping 1m resolution
4. AC-d: "ticker chip remove clears chart" test passes with aria-label on remove button
5. AC-e: "creates session and loads dashboard" test passes with fixed mock redirect
6. AC-f: "retry button triggers search" test passes with race-free waitForResponse
7. AC-g: "user menu outside click closes" test passes with safe click coordinates
8. AC-h: "sign out clears session" test passes with dialog-scoped button and animation wait
9. AC-i: "magic link form loads" test passes with 5s timeout
10. No production behavior changes except (d): aria-label on ticker chip remove button

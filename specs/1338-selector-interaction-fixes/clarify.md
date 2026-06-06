# Feature 1338: Clarification Record

## Pre-Clarification Analysis

All ambiguities were resolved through source code inspection. No user interaction
required. Each diagnosis from the feature description was verified against the actual
source and corrected where needed.

## Q1: Does (a) fail because of client-side view switching?

**Feature description claim**: "app uses client-side view switching. Page shows Settings
content but URL stays `/`."

**Actual finding**: INCORRECT. The Settings menu item uses `window.location.href =
'/settings'` (hard navigation in user-menu.tsx:142). The `/settings` route exists as a
real Next.js page at `app/(dashboard)/settings/page.tsx`. The URL DOES change.

**The real problem**: The test's UNWIND step fails, not the assertion. After navigating
to `/settings`, the test tries `page.getByRole('tab', { name: /dashboard/i })` to
navigate back. There is no tab role in the settings page or layout. The sidebar uses
links, not tabs.

**Resolution**: Fix the unwind step. The URL assertion is correct; the unwind is wrong.

## Q2: Is the empty state (b) a regex mismatch or a timing issue?

**Feature description claim**: "Fix: increase timeout or fix regex to match actual empty
state text."

**Actual finding**: The regex DOES match. "Track Price & Sentiment" matches
`track price.*sentiment`. The issue is timing -- no `waitForAuth(page)` call means the
page may not have finished auth initialization, and the empty state may not be rendered
yet within 10s on mobile projects.

**Resolution**: Add `waitForAuth` for reliable timing. Timeout increase is secondary.

## Q3: Is (c) about 1m having no data, or about button state?

**Feature description claim**: "1m resolution has no data outside market hours."

**Actual finding**: CONFIRMED. 1m intraday data from Tiingo is only available during
market hours. Outside market hours, selecting 1m may return zero candles, and the chart
may show an empty state or error instead of updating normally. The `aria-pressed="true"`
assertion may fail because the button click triggers an error state.

**Resolution**: Remove `1m` from the resolution list in the test. `5m` and higher always
have data.

## Q4: Does the mockOAuthRedirect (e) actually fail at the 302 level?

**Feature description claim**: "sessionStorage missing `oauth_state` and
`oauth_provider` before callback."

**Actual finding**: PARTIALLY CORRECT but for different reasons. `signInWithOAuth()`
DOES set sessionStorage values (auth-store.ts:199-200) before the redirect. The real
issue is that `route.fulfill({ status: 302, headers: { Location: url } })` in
Playwright does NOT cause the browser to follow the 302. The page receives the 302
response but stays on the Cognito URL (which was intercepted). The callback page never
loads.

Additionally, even if it did redirect, there's a sequence concern: `window.location.href`
triggers navigation, which Playwright intercepts. The 302 response would need to trigger
another navigation, which may not happen with `route.fulfill`.

**Resolution**: Replace the 302 approach. Either navigate directly to the callback URL
after setting sessionStorage, or use `page.route` to redirect at the request level (not
response level).

## Q5: Is (f) an auth mock ordering issue or a race condition?

**Feature description claim**: "Auth mock may intercept before error mock on same origin.
Fix: ensure route ordering is correct."

**Actual finding**: INCORRECT. The auth mock (`**/api/v2/auth/anonymous`) and search
mock (`**/api/v2/tickers/search**`) match different URL patterns and don't conflict.
The real issue is a race condition: `fill('AAPL')` triggers a debounced search that may
complete before `waitForResponse` starts listening. Other tests in the same file use
`waitForTimeout(1500)` instead, which doesn't have this race.

**Resolution**: Set up `waitForResponse` promise before `fill`, using `Promise.all` or
sequential setup.

## Q6: Does the skip link at (10,10) actually intercept clicks?

**Feature description claim**: "Click at (10,10) hits skip-link instead of blank area."

**Actual finding**: PLAUSIBLE. The SkipLink component uses `sr-only` which applies
`clip: rect(0, 0, 0, 0)` and `overflow: hidden`, effectively making it zero-sized.
However, the element is still in the DOM at position (0,0) in the document flow. Whether
clicking at (10,10) activates it depends on the browser -- some may still register click
events on clipped elements. The more likely scenario is that (10,10) hits some other
element like a header or sidebar edge.

Regardless of what exactly is at (10,10), the fix is the same: use coordinates far from
interactive elements.

**Resolution**: Click at viewport bottom-center instead of top-left.

## Q7: Does (h) fail due to animation or button selector ambiguity?

**Feature description claim**: "Sign-out dialog button click doesn't complete due to
animation."

**Actual finding**: BOTH issues. The dialog uses framer-motion with 200ms entry
animation. The confirm button selector `/confirm|yes|sign out/i` matches "Sign out"
text which appears on both the settings page trigger button and the dialog confirm
button. The test in `dialog-dismissal.spec.ts:88-94` already handles this correctly
by scoping to the dialog: `dialog.getByRole('button', { name: /sign out/i })` and
adding `waitForTimeout(500)` before clicking.

But `session-lifecycle.spec.ts:38` uses `page.getByRole('button', { name: /confirm|yes|sign out/i })`
which is page-scoped, not dialog-scoped.

**Resolution**: Scope to dialog + add animation settle wait.

## Summary: 4/9 Original Diagnoses Were Correct

| Sub-Issue | Original Diagnosis Correct? | Actual Root Cause |
|-----------|---------------------------|-------------------|
| (a) | No — URL does change | Unwind step uses nonexistent tab role |
| (b) | Partially — regex is fine | Missing waitForAuth causes timing failure |
| (c) | Yes | 1m has no data outside market hours |
| (d) | Yes | Remove button has no accessible name |
| (e) | Partially — sessionStorage IS set | route.fulfill 302 doesn't redirect browser |
| (f) | No — not auth mock ordering | Race condition with waitForResponse |
| (g) | Yes | (10,10) hits skip-link or other element |
| (h) | Partially — animation is factor | Button selector also ambiguous (page-scoped) |
| (i) | Yes | 2s too tight for mobile hydration |

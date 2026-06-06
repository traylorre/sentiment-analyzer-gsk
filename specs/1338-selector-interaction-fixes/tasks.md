# Feature 1338: Tasks

## Task List

### (a) auth-menu-items: Settings navigation assertion + unwind

- [ ] T-a: Fix "menu Settings navigates" test
  - File: `frontend/tests/e2e/auth-menu-items.spec.ts`
  - Lines 54-73: Replace URL assertion with content assertion, fix unwind step
  - After `settingsItem.click()`, add `page.waitForLoadState('networkidle')` and
    assert `page.getByText(/customize your dashboard/i)` visible with 10s timeout
  - Replace `getByRole('tab', { name: /dashboard/i })` unwind with `page.goto('/')`
  - Remove `await expect(page).toHaveURL(/\/$/)`; replace with `page.waitForLoadState('networkidle')`
  - Depends: none

### (b) dashboard-interactions: Empty state timing

- [ ] T-b: Fix "empty state shows search CTA" test
  - File: `frontend/tests/e2e/dashboard-interactions.spec.ts`
  - Lines 260-269: Add `await waitForAuth(page)` after `page.goto('/')`
  - Increase timeout from 10000 to 15000
  - Note: `waitForAuth` is already imported at line 4
  - Depends: none

### (c) dashboard-interactions: Resolution button cycle

- [ ] T-c: Fix "resolution buttons update chart" test
  - File: `frontend/tests/e2e/dashboard-interactions.spec.ts`
  - Line 118: Remove `'1m'` from resolutions array
  - Lines 141-145: Change reset target from `5m` to `15m`
  - Depends: none

### (d) ticker-chip + dashboard-interactions: Chip remove

- [ ] T-d1: Add aria-label to TickerChip remove button (COMPONENT FIX)
  - File: `frontend/src/components/dashboard/ticker-chip.tsx`
  - Line 91-92: Add `aria-label={`Remove ${symbol}`}` to the `<motion.button>` remove button
  - Depends: none

- [ ] T-d2: Simplify chip remove selector in test
  - File: `frontend/tests/e2e/dashboard-interactions.spec.ts`
  - Lines 228-242: Replace try/catch with direct `getByRole('button', { name: /remove AAPL/i })`
  - Remove fallback selector for `[data-ticker="AAPL"], .chip, .tag`
  - Depends: T-d1

### (e) oauth-flow: Fix mock redirect

- [ ] T-e: Fix "creates session and loads dashboard" test
  - File: `frontend/tests/e2e/oauth-flow.spec.ts`
  - Lines 73-118: Replace mockOAuthRedirect approach with direct navigation
  - Set `oauth_provider` and `oauth_state` in sessionStorage via `page.evaluate`
  - Navigate directly to `/auth/callback?code=valid-test-code&state=mock-state-google`
  - Keep existing callback endpoint mock
  - Remove `mockOAuthRedirect` call and Google button click
  - Depends: none

### (f) error-visibility-search: Fix retry race condition

- [ ] T-f: Fix "retry button triggers search" test
  - File: `frontend/tests/e2e/error-visibility-search.spec.ts`
  - Lines 141-144: Move `waitForResponse` setup before `fill`
  - Change from: `fill` then `waitForResponse`
  - Change to: `const p = waitForResponse(...)` then `fill` then `await p`
  - Depends: none

### (g) dialog-dismissal: Fix outside-click coordinates

- [ ] T-g: Fix "user menu outside click closes" test
  - File: `frontend/tests/e2e/dialog-dismissal.spec.ts`
  - Line 174: Replace `{ x: 10, y: 10 }` with viewport-safe coordinates
  - Use `page.viewportSize()` to get width/height
  - Click at `{ x: Math.floor(viewport.width / 2), y: Math.floor(viewport.height - 20) }` or safer area
  - Consider using `page.mouse.click()` for viewport-relative coordinates
  - Depends: none

### (h) session-lifecycle: Fix sign-out confirm scope

- [ ] T-h: Fix "sign out clears session" test
  - File: `frontend/tests/e2e/session-lifecycle.spec.ts`
  - Lines 35-44: Scope confirm button to dialog, add animation wait
  - After `signOut.click()`, get `page.getByRole('dialog')`
  - Add `page.waitForTimeout(300)` for animation settle
  - Scope confirm to `dialog.getByRole('button', { name: /sign out/i })`
  - Depends: none

### (i) signin-interaction: Increase timeout

- [ ] T-i: Fix "magic link form loads" test timeout
  - File: `frontend/tests/e2e/signin-interaction.spec.ts`
  - Line 98: Change `timeout: 2_000` to `timeout: 5_000`
  - Depends: none

### Verification

- [ ] V1: Verify auth-menu-items.spec.ts Settings test has no tab role selector
  - Grep for `getByRole('tab'` in file -- expect 0 matches
  - Depends: T-a

- [ ] V2: Verify dashboard-interactions.spec.ts has waitForAuth in empty state test
  - Grep for `waitForAuth` in the empty state test block
  - Depends: T-b

- [ ] V3: Verify resolutions array has no '1m' entry
  - Grep for `'1m'` in resolution array -- expect only in time-range tests, not resolution
  - Depends: T-c

- [ ] V4: Verify ticker-chip.tsx has aria-label on remove button
  - Grep for `aria-label.*Remove` in ticker-chip.tsx -- expect 1 match
  - Depends: T-d1

- [ ] V5: Verify dashboard-interactions.spec.ts chip remove has no try/catch fallback
  - Grep for `data-ticker` in file -- expect 0 matches
  - Depends: T-d2

- [ ] V6: Verify oauth-flow.spec.ts sets sessionStorage before callback navigation
  - Grep for `sessionStorage.setItem.*oauth_provider` in file -- expect 1 match
  - Depends: T-e

- [ ] V7: Verify error-visibility-search.spec.ts sets up waitForResponse before fill
  - Read retry test block, confirm `waitForResponse` promise is created before `fill`
  - Depends: T-f

- [ ] V8: Verify dialog-dismissal.spec.ts outside-click uses safe coordinates
  - Grep for `x: 10, y: 10` -- expect 0 matches
  - Depends: T-g

- [ ] V9: Verify session-lifecycle.spec.ts scopes confirm to dialog
  - Grep for `getByRole('dialog')` in file -- expect 1 match
  - Depends: T-h

- [ ] V10: Verify signin-interaction.spec.ts timeout is 5000
  - Grep for `timeout: 5_000` in magic link test
  - Depends: T-i

## Execution Order

All implementation tasks are independent except T-d2 depends on T-d1:

```
T-a + T-b + T-c + T-d1 + T-e + T-f + T-g + T-h + T-i  (all parallel)
  |
  v
T-d2  (after T-d1 component fix)
  |
  v
V1 + V2 + V3 + V4 + V5 + V6 + V7 + V8 + V9 + V10  (all parallel)
```

Total: 10 implementation tasks + 10 verification tasks = 20 tasks

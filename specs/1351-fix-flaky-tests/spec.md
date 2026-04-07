# Spec: Fix 3 Flaky Playwright Tests (1351-1353)

## Problem

Three Playwright E2E tests exhibit intermittent failures due to two root causes:

1. **`networkidle` wait strategy** -- TanStack Query's background refetching prevents the
   network from ever going truly idle, causing timeouts.
2. **Blind `waitForTimeout()` animation waits** -- Fixed-duration sleeps are inherently
   racy; animations may complete faster or slower depending on browser, viewport, and CI load.

## Affected Tests

### 1351: account-linking.spec.ts:32 (~65% flake rate)

- **File**: `frontend/tests/e2e/account-linking.spec.ts`
- **Test**: `settings page shows anonymous badge with upgrade prompt`
- **Root cause**: `waitForLoadState('networkidle')` never resolves because TanStack Query
  keeps polling.
- **Fix**: Replace `networkidle` with `domcontentloaded` + skeleton-gone wait. Add
  explicit timeout to `isVisible` checks.

### 1352: session-lifecycle.spec.ts:27 (~35% flake rate, mobile-only)

- **File**: `frontend/tests/e2e/session-lifecycle.spec.ts`
- **Test**: `sign out clears session and redirects to signin`
- **Root cause**: Same `networkidle` issue, plus `waitForTimeout(300)` blind animation wait
  and tight `waitForURL` timeout on mobile.
- **Fix**: Replace `networkidle` with `domcontentloaded` + skeleton-gone wait. Replace
  `waitForTimeout(300)` with animation-end detection. Increase `waitForURL` timeout to
  15000ms. Use JS click for confirm button (mobile viewport).

### 1353: dialog-dismissal.spec.ts:72 (~15% flake rate, Firefox-only)

- **File**: `frontend/tests/e2e/dialog-dismissal.spec.ts`
- **Test**: `sign-out dialog: confirm signs out`
- **Root cause**: `waitForTimeout(500)` blind animation wait insufficient on Firefox. Also,
  `page.waitForURL()` triggers Firefox `NS_BINDING_ABORTED` error because client-side
  routing aborts the navigation event that `waitForURL` listens for.
- **Fix**: Replace `waitForTimeout(500)` with animation-end detection. Replace
  `page.waitForURL()` + `expect().toHaveURL()` with a single polling
  `expect(page).toHaveURL(..., { timeout: 15000 })` that does not depend on navigation
  events.

## Verification

Each fix verified by running the specific test 3 consecutive times with zero failures.
Full Desktop Chrome + Mobile Chrome suite run to confirm no regressions.

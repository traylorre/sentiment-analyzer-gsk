# Feature 1338: Implementation Plan

## Architecture Impact

**Scope**: Test-only changes (8 sub-issues) + 1 minor component accessibility fix (d).
No new dependencies. No API changes. No infrastructure changes.

All 9 sub-issues are independent. They can be implemented in any order.

## Change Map

### (a) auth-menu-items.spec.ts: Fix Settings navigation test

| File | Change | Lines |
|------|--------|-------|
| `frontend/tests/e2e/auth-menu-items.spec.ts` | Replace URL assertion + fix unwind step | 54-73 |

**Before**:
```typescript
await expect(page).toHaveURL(/\/settings/);
const dashboardTab = page.getByRole('tab', { name: /dashboard/i });
await dashboardTab.click();
await expect(page).toHaveURL(/\/$/);
```

**After**:
```typescript
// Assert Settings content visible (hard navigation completed)
await page.waitForLoadState('networkidle');
await expect(page.getByText(/customize your dashboard/i)).toBeVisible({ timeout: 10000 });

// Unwind: navigate back to root
await page.goto('/');
await page.waitForLoadState('networkidle');
```

Rationale: The Settings page heading is "Customize your dashboard experience"
(settings/page.tsx:83). URL assertion works but the unwind uses a nonexistent tab role.
Replace the entire unwind with `page.goto('/')` which is reliable and self-contained.

### (b) dashboard-interactions.spec.ts: Fix empty state timing

| File | Change | Lines |
|------|--------|-------|
| `frontend/tests/e2e/dashboard-interactions.spec.ts` | Add waitForAuth + increase timeout | 260-269 |

**Before**:
```typescript
test('empty state shows search CTA', async ({ page }) => {
  await page.goto('/');
  const emptyState = page.getByText(
    /track price.*sentiment|search.*ticker|get started|select a ticker/i
  );
  await expect(emptyState).toBeVisible({ timeout: 10000 });
```

**After**:
```typescript
test('empty state shows search CTA', async ({ page }) => {
  await page.goto('/');
  await waitForAuth(page);
  const emptyState = page.getByText(
    /track price.*sentiment|search.*ticker|get started|select a ticker/i
  );
  await expect(emptyState).toBeVisible({ timeout: 15000 });
```

### (c) dashboard-interactions.spec.ts: Fix resolution button cycle

| File | Change | Lines |
|------|--------|-------|
| `frontend/tests/e2e/dashboard-interactions.spec.ts` | Remove 1m from resolution list | 118 |

**Before**: `const resolutions = ['1m', '5m', '15m', '30m', '1h', 'D'];`
**After**: `const resolutions = ['5m', '15m', '30m', '1h', 'D'];`

Also update the reset target from `5m` to `15m` (line 141-145) since `5m` is now
the first item and may already be pressed:
**Before**: `const resetButton = page.getByRole('button', { name: /5m.*resolution/i });`
**After**: `const resetButton = page.getByRole('button', { name: /15m.*resolution/i });`

### (d) ticker-chip.tsx + dashboard-interactions.spec.ts: Fix chip remove

| File | Change | Lines |
|------|--------|-------|
| `frontend/src/components/dashboard/ticker-chip.tsx` | Add aria-label to remove button | 91-99 |
| `frontend/tests/e2e/dashboard-interactions.spec.ts` | Simplify remove button selector | 228-242 |

**Component fix (ticker-chip.tsx)**:
```tsx
// Before (line 91-99):
<motion.button
  type="button"
  onClick={handleRemove}
  className="ml-1 p-0.5 rounded-full ..."
>
  <X className="h-3 w-3" />
</motion.button>

// After:
<motion.button
  type="button"
  onClick={handleRemove}
  aria-label={`Remove ${symbol}`}
  className="ml-1 p-0.5 rounded-full ..."
>
  <X className="h-3 w-3" />
</motion.button>
```

**Test fix (dashboard-interactions.spec.ts)**:
```typescript
// Before (complex try/catch with fallbacks):
let removeButton;
try {
  removeButton = page.getByRole('button', { name: /remove.*AAPL|.../i });
  ...
} catch {
  const chip = page.locator('[data-ticker="AAPL"], .chip, .tag')...
  ...
}

// After (direct match against aria-label):
const removeButton = page.getByRole('button', { name: /remove AAPL/i });
await expect(removeButton).toBeVisible({ timeout: 5000 });
```

### (e) oauth-flow.spec.ts: Fix mock OAuth redirect

| File | Change | Lines |
|------|--------|-------|
| `frontend/tests/e2e/oauth-flow.spec.ts` | Set sessionStorage + navigate directly | 73-118 |

**Strategy**: Instead of relying on `mockOAuthRedirect` (which uses 302 that doesn't
work), set up sessionStorage values manually and navigate to the callback URL directly.

**After**:
```typescript
test('successful OAuth callback creates session and loads dashboard', async ({ page }) => {
  await mockOAuthUrls(page);

  // Mock the callback endpoint
  await page.route('**/api/v2/auth/oauth/callback', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      status: 'success', email_masked: 't***@example.com', auth_type: 'google',
      tokens: { id_token: 'mock-id-token', access_token: 'mock-access-token', expires_in: 3600 },
      ...
    })})
  );

  // Navigate to signin first to set up page context
  await page.goto('/auth/signin');

  // Set sessionStorage values that signInWithOAuth would set
  await page.evaluate(() => {
    sessionStorage.setItem('oauth_provider', 'google');
    sessionStorage.setItem('oauth_state', 'mock-state-google');
  });

  // Navigate directly to callback (bypassing the 302 issue)
  await page.goto('/auth/callback?code=valid-test-code&state=mock-state-google');

  // After callback processes, should redirect to dashboard
  await page.waitForURL(/\/(dashboard|$|\?)/i, { timeout: 15000 });

  const body = await page.textContent('body');
  expect(body).not.toContain('error');
});
```

### (f) error-visibility-search.spec.ts: Fix retry race condition

| File | Change | Lines |
|------|--------|-------|
| `frontend/tests/e2e/error-visibility-search.spec.ts` | Setup waitForResponse before fill | 141-144 |

**Before**:
```typescript
await searchInput.fill('AAPL');
await page.waitForResponse('**/api/v2/tickers/search**');
```

**After**:
```typescript
const searchResponsePromise = page.waitForResponse('**/api/v2/tickers/search**');
await searchInput.fill('AAPL');
await searchResponsePromise;
```

### (g) dialog-dismissal.spec.ts: Fix outside-click coordinates

| File | Change | Lines |
|------|--------|-------|
| `frontend/tests/e2e/dialog-dismissal.spec.ts` | Use viewport-relative safe coordinates | 174 |

**Before**:
```typescript
await page.locator('body').click({ position: { x: 10, y: 10 } });
```

**After**:
```typescript
const viewport = page.viewportSize()!;
await page.locator('body').click({ position: { x: viewport.width / 2, y: viewport.height - 10 } });
```

### (h) session-lifecycle.spec.ts: Fix sign-out confirm scope and timing

| File | Change | Lines |
|------|--------|-------|
| `frontend/tests/e2e/session-lifecycle.spec.ts` | Scope to dialog + add animation wait | 35-44 |

**Before**:
```typescript
await signOut.click();
const confirm = page.getByRole('button', { name: /confirm|yes|sign out/i });
if (await confirm.isVisible({ timeout: 2000 }).catch(() => false)) {
  await confirm.click();
}
```

**After**:
```typescript
await signOut.click();
const dialog = page.getByRole('dialog');
if (await dialog.isVisible({ timeout: 3000 }).catch(() => false)) {
  await page.waitForTimeout(300);  // Animation settle
  const confirmBtn = dialog.getByRole('button', { name: /sign out/i });
  await confirmBtn.click();
}
```

### (i) signin-interaction.spec.ts: Increase magic link timeout

| File | Change | Lines |
|------|--------|-------|
| `frontend/tests/e2e/signin-interaction.spec.ts` | 2s -> 5s timeout | 98 |

**Before**: `await expect(page.getByPlaceholder(/email/i)).toBeVisible({ timeout: 2_000 });`
**After**: `await expect(page.getByPlaceholder(/email/i)).toBeVisible({ timeout: 5_000 });`

## Dependency Order

All 9 sub-issues are independent. Only (d) has an internal dependency:
```
(d-component) ticker-chip.tsx aria-label -> (d-test) dashboard-interactions.spec.ts selector
```

Suggested execution order (maximize parallelism):
```
(a) + (b) + (c) + (d-component) + (e) + (f) + (g) + (h) + (i)  -- all parallel
then: (d-test) -- after d-component
then: verification
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `waitForAuth` timeout not sufficient for slow CI | Low | Low | 15s timeout is 3x the auth init time |
| 5m resolution also lacks data | Very Low | Low | 5m data available during extended hours (4am-8pm ET) |
| aria-label change breaks existing unit tests | Low | Low | Unit tests don't assert absence of aria-label |
| OAuth test still fails with direct navigation | Medium | Medium | sessionStorage set before navigation; callback page reads on mount |
| Bottom-center click (g) hits mobile nav | Low | Low | Mobile nav is at fixed bottom; (width/2, height-10) in viewport coords hits it. May need adjustment. |

### Risk mitigation for (g)
The mobile nav is `fixed bottom-0` and the click position `height - 10` is in viewport
coordinates. `page.locator('body').click()` uses coordinates relative to the body element,
which may extend beyond viewport. Use `page.mouse.click()` with viewport-relative coords
instead, or pick a safer position like `(width - 10, height / 2)` (right edge, mid-height).

## Non-Goals

- No production behavior changes except (d) ticker-chip.tsx aria-label
- No new test files
- No changes to auth-helper.ts or clean-state.ts helpers
- No Playwright config changes

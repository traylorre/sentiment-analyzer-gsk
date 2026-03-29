# Feature 1273: Cached Data Empty — Tasks

## Scope

Fix 3 failing cached-data E2E tests by adding proper data loading before chaos injection, replacing blind waits with event-based waiting, and improving global-setup error messaging.

## Task Dependency Graph

```
T1 (chaos-cached-data.spec.ts beforeEach) ──┐
T2 (chaos-cached-data.spec.ts test bodies)  ├──→ T5 (verify all pass)
T3 (chaos-cross-browser.spec.ts cached test)┤
T4 (global-setup.ts error messaging)        ┘
```

T1-T4 are parallelizable (different files/sections). T5 depends on all.

## Tasks

### T1: Rewrite chaos-cached-data.spec.ts beforeEach with data loading

**File**: `frontend/tests/e2e/chaos-cached-data.spec.ts`
**Lines**: 13-17 (beforeEach block)

**Before**:
```typescript
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.waitForTimeout(3000);
});
```

**After**:
```typescript
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  // Load actual data — search for and select a ticker
  const searchInput = page.getByPlaceholder(/search tickers/i);
  await searchInput.fill('AAPL');
  const suggestion = page.getByRole('option', { name: /AAPL/i });
  await expect(suggestion).toBeVisible({ timeout: 10000 });
  await suggestion.click();
  // Wait for chart data to fully render (proven pattern from sanity.spec.ts)
  const chartContainer = page.locator(
    '[role="img"][aria-label*="Price and sentiment chart"]'
  );
  await expect(chartContainer).toHaveAttribute(
    'aria-label',
    /[1-9]\d* price candles/,
    { timeout: 15000 }
  );
});
```

**Rationale**: Tests assert "previously loaded data remains visible" but never load data. The empty dashboard has no data to persist through an API outage.

---

### T2: Replace blind waits in chaos-cached-data.spec.ts test bodies

**File**: `frontend/tests/e2e/chaos-cached-data.spec.ts`

**T013 test** (line 37): Replace `await page.waitForTimeout(2000)` after `blockAllApi()`:
```typescript
// BEFORE
await blockAllApi(page, 503);
await page.waitForTimeout(2000);

// AFTER
await blockAllApi(page, 503);
// Brief settle time for in-flight requests to hit the route block
await page.waitForTimeout(500);
```

**T014 test** (line 57-58): Replace `await page.waitForTimeout(2000)` after route abort:
```typescript
// BEFORE
await page.route('**/api/**', (route) => route.abort('timedout'));
await page.waitForTimeout(2000);

// AFTER
await page.route('**/api/**', (route) => route.abort('timedout'));
// Brief settle time for in-flight requests to hit the route block
await page.waitForTimeout(500);
```

**Rationale**: Post-chaos wait reduced from 2000ms to 500ms. Cannot be fully eliminated because in-flight React Query refetch requests need time to hit the route block before assertions run. The 500ms is sufficient for a single refetch cycle.

---

### T3: Fix chaos-cross-browser.spec.ts cached data test

**File**: `frontend/tests/e2e/chaos-cross-browser.spec.ts`
**Lines**: 34-45 ("cached data persists during API outage" test)

Add data loading at the start of the test body (NOT in beforeEach, to avoid slowing down banner/SSE tests):

```typescript
test('cached data persists during API outage', async ({ page }) => {
  // Load actual data first — the beforeEach only navigates
  const searchInput = page.getByPlaceholder(/search tickers/i);
  await searchInput.fill('AAPL');
  const suggestion = page.getByRole('option', { name: /AAPL/i });
  await expect(suggestion).toBeVisible({ timeout: 10000 });
  await suggestion.click();
  // Wait for chart data to render
  const chartContainer = page.locator(
    '[role="img"][aria-label*="Price and sentiment chart"]'
  );
  await expect(chartContainer).toHaveAttribute(
    'aria-label',
    /[1-9]\d* price candles/,
    { timeout: 15000 }
  );

  const mainContent = page.locator('main');
  const textBefore = await mainContent.textContent();
  expect(textBefore).toBeTruthy();

  await blockAllApi(page, 503);
  // Brief settle time for in-flight requests to hit the route block
  await page.waitForTimeout(500);

  const textDuring = await mainContent.textContent();
  expect(textDuring).toBeTruthy();
  expect(textDuring!.length).toBeGreaterThan(10);
});
```

**Rationale**: Data loading is in the test body (not beforeEach) because the other two tests in this describe block don't need pre-loaded data. The banner test triggers failures via search; the SSE test monitors reconnection timing.

---

### T4: Improve global-setup.ts error messaging

**File**: `frontend/tests/e2e/global-setup.ts`
**Lines**: 48-50 (catch block)

**Before**:
```typescript
} catch (error) {
  // Non-fatal — cleanup is best-effort
  console.log(`[global-setup] Cleanup skipped: ${error}`);
}
```

**After**:
```typescript
} catch (error) {
  // Non-fatal — cleanup is best-effort.
  // TypeError: fetch failed = API server not reachable yet (expected during startup)
  const message = error instanceof TypeError
    ? 'API not reachable yet (server may still be starting)'
    : String(error);
  console.log(`[global-setup] Cleanup skipped: ${message}`);
}
```

**Rationale**: The raw `TypeError: fetch failed` message is confusing during debugging. A clear message indicating the server isn't ready yet prevents wasted investigation time.

---

### T5: Verify all tests pass deterministically

Run all affected tests:
```bash
cd frontend && npx playwright test chaos-cached-data chaos-cross-browser --retries=0 --project="Desktop Chrome"
```

**Verification checklist**:
- [ ] `chaos-cached-data.spec.ts` "previously loaded data remains visible" — PASS
- [ ] `chaos-cached-data.spec.ts` "cached data survives API timeout" — PASS
- [ ] `chaos-cross-browser.spec.ts` "cached data persists during API outage" — PASS
- [ ] `chaos-cross-browser.spec.ts` "health banner appears after 3 failures" — PASS (no regression)
- [ ] `chaos-cross-browser.spec.ts` "SSE reconnection issues new fetch" — PASS (no regression)
- [ ] No `waitForTimeout(2000)` or `waitForTimeout(3000)` in modified files
- [ ] `global-setup.ts` logs clear message when API is unreachable

## Adversarial Review

**Highest-risk task**: T1 — rewriting the `beforeEach` affects both tests in the file. If the data loading pattern fails (e.g., AAPL not available in mock), both tests fail with a new error rather than the original.

**Most likely rework**: T2 — the 500ms settle time may need tuning. If React Query refetch interval is > 500ms, no in-flight request will be intercepted and the wait is unnecessary. If < 500ms, the wait is sufficient. Monitor in CI.

**Gate**: READY FOR IMPLEMENTATION

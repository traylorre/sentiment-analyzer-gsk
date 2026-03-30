# Research: Feature 1273 — Cached Data Empty

**Date**: 2026-03-28
**Status**: Complete

## Problem Statement

Three Playwright E2E tests fail because they assert dashboard content exists after a blind `waitForTimeout()`, but the dashboard is empty when the assertion runs. These tests validate cached data resilience during API outages -- a critical chaos engineering property.

## Failing Tests

| Test File | Test Name | Duration | Failure |
|-----------|-----------|----------|---------|
| `chaos-cached-data.spec.ts` | previously loaded data remains visible during API outage | 3.7s | `expect(initialChildCount).toBeGreaterThan(0)` fails |
| `chaos-cached-data.spec.ts` | cached data survives API timeout | 3.7s | `expect(textBefore).toBeTruthy()` fails |
| `chaos-cross-browser.spec.ts` | cached data persists during API outage | 2.6s | `expect(textBefore).toBeTruthy()` fails |

## Root Cause Analysis

### Cause 1: global-setup.ts fires fetch before webServer is ready

`global-setup.ts` calls `fetch('/api/v2/auth/anonymous')` using `API_URL` (default `http://localhost:8000`). This runs BEFORE Playwright's webServer readiness check, so the server may not be listening yet. The `TypeError: fetch failed` is caught and silently swallowed via the catch block ("Cleanup skipped: ..."). This is not the direct failure cause (global-setup is cleanup, not data loading), but it contributes to confusing diagnostic output.

### Cause 2: Tests rely on blind waitForTimeout for initial data load

All three failing tests share this pattern in `beforeEach`:

```typescript
await page.goto('/');
await page.waitForTimeout(2000-3000);
```

This assumes data renders within 2-3 seconds. On the fresh dashboard with no ticker selected, the page shows an **empty state** ("Track sentiment", "Search for a ticker"). There is no pre-loaded data to persist through an API outage because:

1. The dashboard starts with no ticker selected
2. No API call fetches data until the user searches/selects a ticker
3. The "empty state" text does exist in `<main>`, but the tests check for data content (> 10 chars, > 0 children) -- which passes for the empty state message but fails when the dashboard renders nothing due to hydration timing

### Cause 3: No initial data load step before API blocking

The tests block all API calls AFTER the `beforeEach`, then assert "previously loaded data" remains. But the tests never load any data in the first place. The test logic should:

1. Navigate to dashboard
2. **Search for and select a ticker** (load actual data)
3. **Wait for data to render** (verify content exists)
4. Block API
5. Assert content persists

Currently steps 2 and 3 are missing entirely.

## Codebase Analysis

### Dashboard Empty State

From `first-impression.spec.ts`, the dashboard shows:
- Heading: "Sentiment" (or similar)
- Search input: "Search tickers"
- Empty state: "Track sentiment" / "Search for a ticker"

This means `mainContent.textContent()` on a fresh dashboard returns the empty state text -- which IS truthy and IS > 10 chars. But the tests intermittently fail because:
- Hydration hasn't completed within the timeout
- The `<main>` element has no children yet during SSR/hydration

### Working Pattern (from sanity.spec.ts and error-visibility-banner.spec.ts)

Tests that successfully load data always:
1. Fill search input: `await searchInput.fill('AAPL')`
2. Wait for suggestion: `await expect(suggestion).toBeVisible({ timeout: 10000 })`
3. Click suggestion: `await suggestion.click()`
4. Wait for chart: `await expect(chartContainer).toHaveAttribute('aria-label', /price candles/, { timeout: 15000 })`

This is the proven pattern for loading data into the dashboard.

### chaos-helpers.ts triggerHealthBanner() Pattern

The `triggerHealthBanner()` helper (already fixed in Feature 1271) uses `waitForResponse()` instead of blind waits. This is the established pattern for chaos test setup.

## Fix Strategy

### Fix 1: Add data loading step to cached-data tests

Replace the blind `waitForTimeout` in `beforeEach` with actual data loading:

```typescript
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  // Load actual data by searching and selecting a ticker
  const searchInput = page.getByPlaceholder(/search tickers/i);
  await searchInput.fill('AAPL');
  const suggestion = page.getByRole('option', { name: /AAPL/i });
  await expect(suggestion).toBeVisible({ timeout: 10000 });
  await suggestion.click();
  // Wait for chart data to render
  const chartContainer = page.locator('[role="img"][aria-label*="Price and sentiment chart"]');
  await expect(chartContainer).toHaveAttribute('aria-label', /[1-9]\d* price candles/, { timeout: 15000 });
});
```

### Fix 2: Fix chaos-cross-browser.spec.ts similarly

Same pattern -- load data before asserting it persists.

### Fix 3: Harden global-setup.ts

Add retry logic or move cleanup to after webServer readiness, or document that cleanup is best-effort and not critical for test correctness.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Data load adds 10-15s to each test | High | Low | Necessary cost; tests currently don't work at all |
| AAPL ticker not available in mock API | Low | High | Verify run-local-api.py serves ticker search |
| Chart doesn't render in CI | Low | Medium | Use generous timeout (15s), CI has retries |
| Other tests affected by global-setup change | Low | Low | global-setup cleanup is best-effort already |

## References

- Feature 1265: Original chaos test spec (US1/FR-015)
- Feature 1270: ARIA race condition fix pattern
- Feature 1271: waitForTimeout elimination pattern
- `sanity.spec.ts`: Proven data loading pattern
- `error-visibility-banner.spec.ts`: Proven API blocking pattern

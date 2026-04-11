// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import {
  blockAllApi,
  triggerHealthBanner,
  getBannerLocator,
} from './helpers/chaos-helpers';
import { mockTickerDataApis } from './helpers/mock-api-data';

/**
 * Chaos: Cross-Browser Smoke Tests (Feature 1265, US5)
 *
 * PURPOSE: These are intentional DUPLICATES of tests in chaos-degradation.spec.ts
 * and chaos-cached-data.spec.ts. They exist because Playwright runs them against
 * Mobile Chrome and Mobile Safari projects (configured in playwright.config.ts),
 * validating that degradation behavior works across browser engines.
 *
 * If you're looking for the authoritative version of these tests, see:
 * - chaos-degradation.spec.ts (health banner lifecycle)
 * - chaos-cached-data.spec.ts (cached data resilience)
 *
 * Caveat: Playwright's WebKit is not identical to Safari's production
 * network stack. These tests validate WebKit compatibility, not Safari-specific
 * production behavior.
 */
test.describe('Chaos: Cross-Browser Validation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for page content to render instead of blind timeout
    await expect(page.locator('main')).toBeVisible({ timeout: 10000 });
  });

  // T042: Banner lifecycle works across browsers
  test('health banner appears after 3 failures', async ({ page }) => {
    await triggerHealthBanner(page);
    const banner = getBannerLocator(page);
    await expect(banner).toBeVisible();
    await expect(banner).toHaveAttribute('aria-live', 'assertive', { timeout: 3000 });
  });

  // T042: Cached data persists across browsers
  test('cached data persists during API outage', async ({ page }) => {
    // Feature 1276: Mock data APIs for instant loading (was ~17s with real APIs)
    await mockTickerDataApis(page);

    // Load data — the beforeEach only navigates, so we must search + select here.
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    const suggestion = page.getByRole('option', { name: /AAPL/i });
    await expect(suggestion).toBeVisible({ timeout: 5000 });
    await suggestion.click();
    // Wait for chart data to render (instant with mocks, 5s safety margin)
    const chartContainer = page.locator(
      '[role="img"][aria-label*="Price and sentiment chart"]',
    );
    await expect(chartContainer).toHaveAttribute(
      'aria-label',
      /[1-9]\d* price candles/,
      { timeout: 5000 },
    );

    const mainContent = page.locator('main');
    const textBefore = await mainContent.textContent();
    expect(textBefore).toBeTruthy();

    await blockAllApi(page, 503);
    // Brief settle for in-flight React Query refetch requests to hit the route block
    // 500ms is conservative — routes take effect immediately, but in-flight requests
    // may still return before the block applies. This is a known timing tradeoff.
    await page.waitForTimeout(500);

    const textDuring = await mainContent.textContent();
    expect(textDuring).toBeTruthy();
    expect(textDuring!.length).toBeGreaterThan(10);

    // Content comparison: verify SAME content persists (not replaced by error page)
    const contentFragment = textBefore!.substring(0, 20);
    expect(textDuring).toContain(contentFragment);
  });

  // T043 (SSE reconnection) DELETED — Feature 1344.
  // Mock API (run-local-api.py) doesn't implement SSE endpoints.
  // SSE test infrastructure tracked in Feature 1280.
});

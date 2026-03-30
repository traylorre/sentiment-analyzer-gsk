// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import {
  blockAllApi,
  triggerHealthBanner,
  getBannerLocator,
} from './helpers/chaos-helpers';
import { mockTickerDataApis } from './helpers/mock-api-data';

/**
 * Chaos: Cross-Browser Validation (Feature 1265, US5)
 *
 * Validates that degradation behavior is consistent across browser engines.
 * Runs selected chaos tests across Mobile Chrome and Mobile Safari projects.
 *
 * Caveat: Playwright's WebKit is not identical to Safari's production
 * network stack. These tests validate WebKit compatibility, not Safari-specific
 * production behavior.
 */
test.describe('Chaos: Cross-Browser Validation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
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
    await page.waitForTimeout(500);

    const textDuring = await mainContent.textContent();
    expect(textDuring).toBeTruthy();
    expect(textDuring!.length).toBeGreaterThan(10);
  });

  // T043: SSE reconnection on WebKit
  // FIXME(1280): SSE reconnection requires a streaming server that doesn't exist
  // in the Playwright test environment. The mock API (run-local-api.py) doesn't
  // implement SSE endpoints. This test needs SSE mock infrastructure to be viable.
  // Tracked for future: add SSE mock to run-local-api.py or use page.route() to
  // simulate EventSource streams.
  test.fixme('SSE reconnection issues new fetch after connection drop', async ({
    page,
  }) => {
    const sseRequests: number[] = [];
    page.on('request', (req) => {
      if (req.url().includes('/stream') || req.url().includes('/sse')) {
        sseRequests.push(Date.now());
      }
    });

    // Abort SSE to trigger reconnection
    await page.route('**/api/v2/stream**', (route) =>
      route.abort('connectionreset'),
    );

    // Wait for at least 2 reconnection attempts (poll instead of blind wait
    // to avoid racing against exponential backoff timing — see Feature 1274)
    await expect
      .poll(() => sseRequests.length, {
        message: 'Expected 2+ SSE reconnection attempts',
        timeout: 15000,
        intervals: [500],
      })
      .toBeGreaterThanOrEqual(2);

    if (sseRequests.length >= 2) {
      // Intervals should be > 0 (backoff is working, within 2x tolerance)
      const interval = sseRequests[1] - sseRequests[0];
      expect(interval).toBeGreaterThan(100);
    }
  });
});

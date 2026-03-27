// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import {
  blockAllApi,
  triggerHealthBanner,
  getBannerLocator,
} from './helpers/chaos-helpers';

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
    await expect(banner).toHaveAttribute('aria-live', 'assertive');
  });

  // T042: Cached data persists across browsers
  test('cached data persists during API outage', async ({ page }) => {
    const mainContent = page.locator('main');
    const textBefore = await mainContent.textContent();
    expect(textBefore).toBeTruthy();

    await blockAllApi(page, 503);
    await page.waitForTimeout(2000);

    const textDuring = await mainContent.textContent();
    expect(textDuring).toBeTruthy();
    expect(textDuring!.length).toBeGreaterThan(10);
  });

  // T043: SSE reconnection on WebKit
  test('SSE reconnection issues new fetch after connection drop', async ({
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

    // Wait for at least 2 reconnection attempts
    await page.waitForTimeout(5000);

    // Should have multiple SSE requests (reconnection behavior works)
    expect(sseRequests.length).toBeGreaterThanOrEqual(2);

    if (sseRequests.length >= 2) {
      // Intervals should be > 0 (backoff is working, within 2x tolerance)
      const interval = sseRequests[1] - sseRequests[0];
      expect(interval).toBeGreaterThan(100);
    }
  });
});

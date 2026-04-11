// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import {
  blockAllApi,
  unblockAllApi,
  triggerHealthBanner,
  waitForRecovery,
  captureConsoleEvents,
  captureTelemetryEvents,
  getBannerLocator,
  getDismissButton,
} from './helpers/chaos-helpers';

/**
 * Chaos: API Degradation — Health Banner Lifecycle (Feature 1265, US1)
 *
 * Validates the customer experience when the backend API becomes unreachable:
 * - Banner appears after 3 consecutive failures within 60s (FR-002)
 * - Banner can be dismissed (FR-016)
 * - Banner auto-clears on recovery (FR-003)
 * - Single failures are tolerated without banner (isolation)
 * - Cross-endpoint success resets failure counter (EC-001)
 * - Dismissed banner reappears on new degradation cycle (FR-016)
 */
test.describe('Chaos: API Degradation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 10000 });
  });

  // T007: Health banner appears after 3 consecutive API failures
  test('health banner appears after 3 consecutive API failures', async ({
    page,
  }) => {
    const telemetry = captureTelemetryEvents(page);

    await triggerHealthBanner(page);

    const banner = getBannerLocator(page);
    await expect(banner).toBeVisible();

    // Verify accessibility attributes
    await expect(banner).toHaveAttribute('aria-live', 'assertive', { timeout: 3000 });

    // Verify structured telemetry event (JSON-parsed, not substring match)
    const bannerEvent = telemetry.findEvent('api_health_banner_shown');
    expect(bannerEvent).toBeTruthy();
  });

  // T008: Health banner dismissal emits console event
  test('health banner dismissal emits console event', async ({ page }) => {
    const telemetry = captureTelemetryEvents(page);

    await triggerHealthBanner(page);

    const banner = getBannerLocator(page);
    await expect(banner).toBeVisible();

    // Click dismiss button
    const dismissButton = getDismissButton(page);
    await expect(dismissButton).toBeVisible();
    await dismissButton.click();

    // Banner should disappear
    await expect(banner).not.toBeVisible({ timeout: 3000 });

    // Verify structured dismiss event (JSON-parsed, not substring match)
    const dismissEvent = telemetry.findEvent('api_health_banner_dismissed');
    expect(dismissEvent).toBeTruthy();
  });

  // T009: Health banner auto-clears on recovery
  // Uses legacy captureConsoleEvents — see Feature 1339 for structured migration
  // (waitForRecovery() expects string[], so captureTelemetryEvents cannot be used here)
  test('health banner auto-clears on recovery', async ({ page }) => {
    const consoleMessages = captureConsoleEvents(page);

    await triggerHealthBanner(page);

    const banner = getBannerLocator(page);
    await expect(banner).toBeVisible();

    // Restore connectivity
    await unblockAllApi(page);

    // Mock a successful ticker search response
    await page.route('**/api/v2/tickers/search**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [
            { symbol: 'TSLA', name: 'Tesla Inc.', exchange: 'NASDAQ' },
          ],
        }),
      }),
    );

    // Trigger a successful interaction — this calls recordSuccess()
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('');
    await searchInput.fill('TSLA');

    // Verify all three recovery signals
    await waitForRecovery(page, consoleMessages);
  });

  // T010: Single failure does not trigger banner (isolation)
  test('single failure does not trigger banner', async ({ page }) => {
    let requestCount = 0;
    await page.route('**/api/v2/tickers/search**', (route) => {
      requestCount++;
      if (requestCount === 1) {
        return route.fulfill({ status: 500, body: 'error' });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [
            { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
          ],
        }),
      });
    });

    const searchInput = page.getByPlaceholder(/search tickers/i);

    // First search fails (requestCount === 1 -> 500)
    await searchInput.fill('AAPL');
    await page.waitForResponse(
      (r) => r.url().includes('/tickers/search') && r.status() === 500,
    );

    // Second search succeeds (requestCount > 1 -> 200) — resets failure counter
    await searchInput.fill('');
    await searchInput.fill('GOOG');
    await page.waitForResponse(
      (r) => r.url().includes('/tickers/search') && r.status() === 200,
    );

    // Banner should NOT appear (only 1 failure, then recovery)
    const banner = getBannerLocator(page);
    await expect(banner).not.toBeVisible();
  });

  // T011: Cross-endpoint failure interaction (EC-001)
  test('cross-endpoint success prevents banner despite other endpoint failures', async ({
    page,
  }) => {
    // Block sentiment endpoint — returns 503
    await page.route('**/api/v2/sentiment**', (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ code: 'SERVICE_UNAVAILABLE' }),
      }),
    );

    // Allow ticker search — returns success
    await page.route('**/api/v2/tickers/search**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [
            { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
          ],
        }),
      }),
    );

    const searchInput = page.getByPlaceholder(/search tickers/i);

    // Interaction 1: search triggers both sentiment (fail) and ticker (success)
    // The success on ticker calls recordSuccess() which resets the counter
    await searchInput.fill('AAPL');
    await page.waitForResponse((r) => r.url().includes('/tickers/search'));

    // Interaction 2: same pattern — sentiment fails, ticker succeeds
    await searchInput.fill('');
    await searchInput.fill('GOOG');
    await page.waitForResponse((r) => r.url().includes('/tickers/search'));

    // Interaction 3: same pattern
    await searchInput.fill('');
    await searchInput.fill('MSFT');
    await page.waitForResponse((r) => r.url().includes('/tickers/search'));

    // Banner should NOT appear — each successful ticker response resets the counter
    const banner = getBannerLocator(page);
    await expect(banner).not.toBeVisible();
  });

  // T012: Banner dismissal resets on new degradation cycle (FR-016)
  test('dismissed banner reappears on new degradation cycle', async ({
    page,
  }) => {
    // First degradation cycle
    await triggerHealthBanner(page);

    const banner = getBannerLocator(page);
    await expect(banner).toBeVisible();

    // Dismiss the banner
    const dismissButton = getDismissButton(page);
    await dismissButton.click();
    await expect(banner).not.toBeVisible({ timeout: 3000 });

    // Recover — remove blocks
    await unblockAllApi(page);

    // Mock a successful response to trigger recordSuccess()
    await page.route('**/api/v2/tickers/search**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [
            { symbol: 'TSLA', name: 'Tesla Inc.', exchange: 'NASDAQ' },
          ],
        }),
      }),
    );

    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('');
    await searchInput.fill('TSLA');
    await page.waitForResponse(
      (r) => r.url().includes('/tickers/search') && r.ok(),
      { timeout: 5000 },
    );

    // Remove the success mock
    await page.unroute('**/api/v2/tickers/search**');
    // Settle: ensure route deregistration completes and any in-flight requests
    // resolve before re-blocking. Without this, triggerHealthBanner may still
    // match the now-removed success mock for requests already in the pipeline.
    await page.waitForTimeout(500);

    // Second degradation cycle — banner should reappear (not stay dismissed)
    await triggerHealthBanner(page);
    await expect(banner).toBeVisible({ timeout: 5000 });
  });
});

// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { blockAllApi } from './helpers/chaos-helpers';
import { mockTickerDataApis } from './helpers/mock-api-data';

/**
 * Chaos: Cached Data Resilience (Feature 1265, US1/FR-015)
 *
 * Validates that previously loaded data remains visible during API outages.
 * The dashboard should never show a blank screen when the API goes down —
 * existing rendered content must persist.
 */
test.describe('Chaos: Cached Data Resilience', () => {
  let cleanupMocks: (() => Promise<void>) | undefined;

  test.beforeEach(async ({ page }) => {
    // Feature 1276: Mock search/OHLC/sentiment APIs with pre-canned data.
    // Chaos tests verify cache resilience, not data fetching. Mocking
    // eliminates Tiingo/Finnhub latency that caused 17s timeouts.
    cleanupMocks = await mockTickerDataApis(page);

    // Navigate and load data — mocked APIs respond instantly
    await page.goto('/');
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
  });

  test.afterEach(async () => {
    if (cleanupMocks) {
      try {
        await cleanupMocks();
      } catch {
        // Cleanup may fail if page already closed — don't re-throw
      }
      cleanupMocks = undefined;
    }
  });

  // T013: Previously loaded data remains visible during API outage
  test('previously loaded data remains visible during API outage', async ({
    page,
  }) => {
    // Verify initial data is rendered (dashboard is not empty)
    const mainContent = page.locator('main');
    const initialChildCount = await mainContent.locator('> *').count();
    expect(initialChildCount).toBeGreaterThan(0);

    // Capture a snapshot of visible text before chaos
    const textBefore = await mainContent.textContent();
    expect(textBefore).toBeTruthy();
    expect(textBefore!.length).toBeGreaterThan(10);

    // Now block all API calls — simulate complete outage
    await blockAllApi(page, 503);

    // Brief settle for in-flight React Query refetch requests to hit the route block
    await page.waitForTimeout(500);

    // Dashboard should still have rendered content — NOT empty/blank
    const childCountDuringChaos = await mainContent.locator('> *').count();
    expect(childCountDuringChaos).toBeGreaterThan(0);

    // Text content should still be present
    const textDuring = await mainContent.textContent();
    expect(textDuring).toBeTruthy();
    expect(textDuring!.length).toBeGreaterThan(10);

    // Verify content identity — same data, not just "some content"
    const fragment = textBefore!.substring(0, 20);
    expect(textDuring).toContain(fragment);

    // Verify chart persists through outage
    const chartContainer = page.locator(
      '[role="img"][aria-label*="Price and sentiment chart"]',
    );
    await expect(chartContainer).toBeVisible({ timeout: 3000 });
  });

  // T014: Cached data survives API timeout
  test('cached data survives API timeout', async ({ page }) => {
    // Verify initial render
    const mainContent = page.locator('main');
    const textBefore = await mainContent.textContent();
    expect(textBefore).toBeTruthy();

    // Block with timeout error
    await page.route('**/api/**', (route) => route.abort('timedout'));

    // Brief settle for in-flight React Query refetch requests to hit the route block
    await page.waitForTimeout(500);

    // Dashboard should still have content
    const textDuring = await mainContent.textContent();
    expect(textDuring).toBeTruthy();
    expect(textDuring!.length).toBeGreaterThan(10);

    // Verify content identity — same data, not just "some content"
    const fragment = textBefore!.substring(0, 20);
    expect(textDuring).toContain(fragment);

    // Content should still be interactive (clicking doesn't crash).
    // Use visible() filter — on mobile viewports some elements in main are hidden.
    const clickableElements = mainContent.locator(
      'button, a, [role="button"]',
    ).locator('visible=true');
    const clickableCount = await clickableElements.count();
    if (clickableCount > 0) {
      // Assert element is still interactive during outage
      await expect(clickableElements.first()).toBeVisible({ timeout: 3000 });
      await clickableElements.first().click({ timeout: 3000 });
    }
  });
});

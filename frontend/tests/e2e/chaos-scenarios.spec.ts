// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import {
  simulateChaosScenario,
  blockAllApi,
  unblockAllApi,
  getBannerLocator,
  type ChaosScenarioType,
} from './helpers/chaos-helpers';

/**
 * Chaos: Scenario Customer Outcomes (Feature 1265, US3/FR-008)
 *
 * Validates that each of the 5 chaos injection types produces a predictable,
 * non-crashing customer experience. Each scenario maps to specific UI outcomes:
 * - Dashboard never shows blank/empty screens
 * - Appropriate degradation indicators appear
 * - Recovery is verifiable via API 200 response
 */
test.describe('Chaos: Scenario Customer Outcomes', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for main content to render before applying chaos (response-driven, not arbitrary timeout)
    await expect(page.locator('main')).toBeVisible({ timeout: 10000 });
  });

  // T016: Ingestion failure — dashboard persists with no new data
  test('ingestion failure — dashboard persists, no blank screen', async ({
    page,
  }) => {
    // Verify initial render
    const mainContent = page.locator('main');
    const textBefore = await mainContent.textContent();
    expect(textBefore).toBeTruthy();

    // Apply ingestion failure: SSE/articles return empty new-items
    const restore = await simulateChaosScenario(page, 'ingestion_failure');

    // Also intercept sentiment API with aged timestamp to simulate stale data
    const fifteenMinutesAgo = new Date(Date.now() - 15 * 60 * 1000).toISOString();
    await page.route('**/api/v2/configurations/*/sentiment', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          config_id: 'test',
          tickers: [],
          last_updated: fifteenMinutesAgo,
          next_refresh_at: new Date().toISOString(),
          cache_status: 'stale',
        }),
      }),
    );

    // Seed activeConfigId so useSentiment query is enabled on reload
    await page.evaluate(() => {
      localStorage.setItem(
        'sentiment-configs',
        JSON.stringify({ state: { activeConfigId: 'test' }, version: 0 }),
      );
    });

    // Reload to trigger refetch against the mocked stale sentiment endpoint
    await page.reload();
    await expect(page.locator('main')).toBeVisible({ timeout: 10000 });

    // Dashboard should still have rendered content — NOT empty
    const textDuring = await mainContent.textContent();
    expect(textDuring).toBeTruthy();
    expect(textDuring!.length).toBeGreaterThan(10);

    // Verify content identity — not just "something is visible"
    const fragment = textBefore!.substring(0, 20);
    expect(textDuring).toContain(fragment);

    // Stale data indicator MUST be visible and in warning/stale state (Feature 1266)
    // Desktop header indicator (mobile header is hidden at md+ breakpoint)
    const freshnessIndicator = page.locator('[data-testid="data-freshness-indicator"]').last();
    await expect(freshnessIndicator).toBeVisible({ timeout: 5000 });
    const freshnessState = await freshnessIndicator.getAttribute('data-freshness-state');
    expect(['stale', 'critical']).toContain(freshnessState);

    await page.unroute('**/api/v2/configurations/*/sentiment');
    await restore();
  });

  // T017: Database throttle — health banner + cached data visible
  test('database throttle — health banner appears, cached data visible', async ({
    page,
  }) => {
    // Capture initial content
    const mainContent = page.locator('main');
    const textBefore = await mainContent.textContent();
    expect(textBefore).toBeTruthy();

    // Apply DynamoDB throttle: all endpoints return 503
    const restore = await simulateChaosScenario(page, 'dynamodb_throttle');

    // Trigger 3+ search interactions to accumulate failures for banner
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForResponse((r) => r.url().includes('/api/') && r.status() === 503);
    await searchInput.fill('');
    await searchInput.fill('GOOG');
    await page.waitForResponse((r) => r.url().includes('/api/') && r.status() === 503);
    await searchInput.fill('');
    await searchInput.fill('MSFT');
    await page.waitForResponse((r) => r.url().includes('/api/') && r.status() === 503);

    // Health banner should appear
    const banner = getBannerLocator(page);
    await expect(banner).toBeVisible({ timeout: 5000 });

    // Previously rendered content should still be present
    const contentArea = mainContent.locator('> *');
    const childCount = await contentArea.count();
    expect(childCount).toBeGreaterThan(0);

    await restore();
  });

  // T018: Cold start — loading skeletons appear then resolve
  test('cold start — loading skeletons appear during delay', async ({
    page,
  }) => {
    // Apply cold start: 3-second delay on all API calls
    const restore = await simulateChaosScenario(page, 'lambda_cold_start');

    // Navigate to trigger fresh data fetch with delay
    await page.reload();

    // During the 3s delay, loading skeletons should be visible
    const skeletons = page.locator('.animate-pulse');
    // Skeletons MUST be visible during the 3s cold start delay
    await expect(skeletons.first()).toBeVisible({ timeout: 2000 });

    // After delay resolves, content should eventually render (response-driven wait)
    await page.waitForResponse(
      (r) => r.url().includes('/api/') && r.ok(),
      { timeout: 10000 },
    );
    const mainContent = page.locator('main');
    const textAfter = await mainContent.textContent();
    expect(textAfter).toBeTruthy();

    await restore();
  });

  // T019: Trigger failure — existing data remains accessible
  test('trigger failure — existing data remains accessible', async ({
    page,
  }) => {
    // Verify initial render
    const mainContent = page.locator('main');
    const textBefore = await mainContent.textContent();
    expect(textBefore).toBeTruthy();

    // Apply trigger failure: same as ingestion (no new items via SSE)
    const restore = await simulateChaosScenario(page, 'trigger_failure');

    // Intercept sentiment API with aged timestamp
    const twentyMinutesAgo = new Date(Date.now() - 20 * 60 * 1000).toISOString();
    await page.route('**/api/v2/configurations/*/sentiment', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          config_id: 'test',
          tickers: [],
          last_updated: twentyMinutesAgo,
          next_refresh_at: new Date().toISOString(),
          cache_status: 'stale',
        }),
      }),
    );

    // Seed activeConfigId so useSentiment query is enabled on reload
    await page.evaluate(() => {
      localStorage.setItem(
        'sentiment-configs',
        JSON.stringify({ state: { activeConfigId: 'test' }, version: 0 }),
      );
    });

    // Reload to trigger refetch against the mocked stale sentiment endpoint
    await page.reload();
    await expect(page.locator('main')).toBeVisible({ timeout: 10000 });

    // Dashboard still has rendered content
    const textDuring = await mainContent.textContent();
    expect(textDuring).toBeTruthy();
    expect(textDuring!.length).toBeGreaterThan(10);

    // Verify content identity — not just "something is visible"
    const fragment = textBefore!.substring(0, 20);
    expect(textDuring).toContain(fragment);

    // Stale data indicator MUST be visible and in critical state (20min > 4x 5min) (Feature 1266)
    // Desktop header indicator (mobile header is hidden at md+ breakpoint)
    const freshnessIndicator = page.locator('[data-testid="data-freshness-indicator"]').last();
    await expect(freshnessIndicator).toBeVisible({ timeout: 5000 });
    const freshnessState = await freshnessIndicator.getAttribute('data-freshness-state');
    expect(freshnessState).toBe('critical');

    await page.unroute('**/api/v2/configurations/*/sentiment');
    await restore();
  });

  // T020: API timeout — errors communicated, no blank screens
  test('API timeout — errors communicated, no blank screens', async ({
    page,
  }) => {
    // Apply API timeout: all calls aborted with timeout error
    const restore = await simulateChaosScenario(page, 'api_timeout');

    // Trigger interactions that will timeout (event-driven waits)
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForEvent('requestfailed', { timeout: 5000 });
    await searchInput.fill('');
    await searchInput.fill('GOOG');
    await page.waitForEvent('requestfailed', { timeout: 5000 });
    await searchInput.fill('');
    await searchInput.fill('MSFT');
    await page.waitForEvent('requestfailed', { timeout: 5000 });

    // BOTH health banner AND content must be present — not just one or the other
    const banner = getBannerLocator(page);
    await expect(banner).toBeVisible({ timeout: 5000 });

    const mainContent = page.locator('main');
    const mainText = await mainContent.textContent();
    const hasContent = mainText && mainText.length > 10;
    expect(hasContent).toBeTruthy();

    await restore();
  });

  // T021: Recovery after chaos — API returns 200
  test('recovery after chaos — API returns 200', async ({ page }) => {
    // Apply a chaos scenario
    const restore = await simulateChaosScenario(page, 'dynamodb_throttle');

    // Wait for degradation
    await page.waitForTimeout(2000);

    // Remove chaos
    await restore();

    // Verify recovery: API should return 200
    const responsePromise = page.waitForResponse(
      (r) => r.url().includes('/api/') && r.ok(),
      { timeout: 10000 },
    );

    // Trigger a fresh API call
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('');
    await searchInput.fill('TSLA');

    const response = await responsePromise;
    // Recovery is confirmed by a successful API response — no error swallowing
    expect(response.ok()).toBeTruthy();
  });
});

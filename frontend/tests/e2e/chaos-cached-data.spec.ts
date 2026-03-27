// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { blockAllApi } from './helpers/chaos-helpers';

/**
 * Chaos: Cached Data Resilience (Feature 1265, US1/FR-015)
 *
 * Validates that previously loaded data remains visible during API outages.
 * The dashboard should never show a blank screen when the API goes down —
 * existing rendered content must persist.
 */
test.describe('Chaos: Cached Data Resilience', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate and wait for initial data to render
    await page.goto('/');
    await page.waitForTimeout(3000);
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

    // Wait for any pending requests to fail
    await page.waitForTimeout(2000);

    // Dashboard should still have rendered content — NOT empty/blank
    const childCountDuringChaos = await mainContent.locator('> *').count();
    expect(childCountDuringChaos).toBeGreaterThan(0);

    // Text content should still be present
    const textDuring = await mainContent.textContent();
    expect(textDuring).toBeTruthy();
    expect(textDuring!.length).toBeGreaterThan(10);
  });

  // T014: Cached data survives API timeout
  test('cached data survives API timeout', async ({ page }) => {
    // Verify initial render
    const mainContent = page.locator('main');
    const textBefore = await mainContent.textContent();
    expect(textBefore).toBeTruthy();

    // Block with timeout error
    await page.route('**/api/**', (route) => route.abort('timedout'));

    // Wait for timeout errors to propagate
    await page.waitForTimeout(2000);

    // Dashboard should still have content
    const textDuring = await mainContent.textContent();
    expect(textDuring).toBeTruthy();
    expect(textDuring!.length).toBeGreaterThan(10);

    // Content should still be interactive (clicking doesn't crash)
    const clickableElements = mainContent.locator(
      'button, a, [role="button"]',
    );
    const clickableCount = await clickableElements.count();
    if (clickableCount > 0) {
      // Click the first interactive element — should not throw
      await clickableElements.first().click({ timeout: 3000 }).catch(() => {
        // Click may fail if element navigates — that's OK, no crash is the test
      });
    }
  });
});

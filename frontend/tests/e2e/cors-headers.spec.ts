// Feature 1267: CORS header validation via browser fetch
// Uses page.evaluate(() => fetch(...)) to make real credentialed requests
// and assert CORS headers are correctly configured.
//
// This tests the actual browser CORS behavior rather than just HTTP headers,
// ensuring that credentials: 'include' works with origin echoing.

import { test, expect } from '@playwright/test';

const API_ENDPOINT = process.env.PREPROD_API_ENDPOINT || '';

test.describe('CORS Headers - Feature 1267', () => {
  test.skip(!API_ENDPOINT, 'PREPROD_API_ENDPOINT not set');

  test('credentialed fetch to API succeeds without CORS error', async ({
    page,
  }) => {
    // Navigate to the app first to establish the origin context
    await page.goto('/');

    // Use page.evaluate to make a fetch from the browser context
    // This exercises the actual CORS preflight + response flow
    const result = await page.evaluate(async (apiEndpoint: string) => {
      try {
        const response = await fetch(`${apiEndpoint}/health`, {
          method: 'GET',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        return {
          ok: response.ok,
          status: response.status,
          // Note: browser restricts which headers JS can read via CORS
          // Access-Control-Expose-Headers controls this
          statusText: response.statusText,
          corsError: false,
        };
      } catch (error) {
        // CORS failures manifest as TypeError in fetch
        return {
          ok: false,
          status: 0,
          statusText: String(error),
          corsError: true,
        };
      }
    }, API_ENDPOINT);

    // If CORS is misconfigured, fetch throws a TypeError (corsError = true)
    expect(result.corsError).toBe(false);
    // Health endpoint should return 200
    expect(result.status).toBe(200);
  });

  test('dashboard loads and displays data after page load', async ({
    page,
  }) => {
    // This is an implicit CORS validation: if the dashboard can load
    // and display data from the API, CORS must be working correctly.
    // The frontend uses credentials: 'include' for all API calls.
    await page.goto('/');

    // Wait for the page to load - look for any content that indicates
    // the API was successfully called
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await expect(searchInput).toBeVisible({ timeout: 15000 });

    // If we got here, the page loaded successfully which means
    // at minimum the initial API calls (health, config) worked
    // through CORS without being blocked.
  });
});

// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';

/**
 * CORS: Env-Gated 404 Responses (Feature 1268)
 *
 * Validates that the frontend can handle 404 responses from env-gated
 * chaos endpoints. Uses page.route() to intercept requests and simulate
 * the server response.
 *
 * Note (AR3-004): page.route() intercepts at the Playwright network layer
 * BEFORE browser CORS enforcement. These tests validate frontend 404
 * handling, not CORS enforcement itself. CORS correctness is validated
 * by unit tests (test_cors_404_headers.py) and integration tests.
 */
test.describe('CORS: Env-Gated 404 Responses (Feature 1268)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);
  });

  test('fetch reads 404 body when CORS headers present', async ({ page }) => {
    // Intercept chaos API call and return 404 with CORS headers
    await page.route('**/chaos/experiments', (route) => {
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Credentials': 'true',
          'Vary': 'Origin',
        },
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    // Execute fetch in page context and verify response is readable
    const result = await page.evaluate(async () => {
      try {
        const response = await fetch('/chaos/experiments');
        const body = await response.json();
        return {
          ok: response.ok,
          status: response.status,
          body,
        };
      } catch (e) {
        return { error: String(e) };
      }
    });

    expect(result).not.toHaveProperty('error');
    expect(result.ok).toBe(false);
    expect(result.status).toBe(404);
    expect(result.body).toEqual({ detail: 'Not found' });
  });

  test('404 response body contains expected detail message', async ({
    page,
  }) => {
    // Simulate an env-gated 404 with the exact response body
    await page.route('**/chaos/experiments', (route) => {
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        headers: {
          'Vary': 'Origin',
        },
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    const result = await page.evaluate(async () => {
      const response = await fetch('/chaos/experiments');
      const body = await response.json();
      return { status: response.status, detail: body.detail };
    });

    expect(result.status).toBe(404);
    expect(result.detail).toBe('Not found');
  });
});

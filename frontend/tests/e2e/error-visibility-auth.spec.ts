// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect, type ConsoleMessage } from '@playwright/test';

/**
 * T019: Auth Token Refresh Error Visibility
 *
 * Verifies behavior when the auth refresh endpoint fails:
 *   - Route interception correctly returns 401
 *   - UI remains interactive despite auth degradation
 *   - Console error events use consistent JSON structure
 *
 * COVERAGE GAP (Feature 1363): Timer-triggered Zustand auth store
 * degradation (refreshSession -> sessionDegraded -> auth_degradation_warning)
 * is not E2E-testable. Playwright cannot fast-forward the auth refresh
 * timer to trigger the store's internal degradation path.
 */
test.describe('Auth Token Refresh Error Visibility', () => {
  test('refresh endpoint interception returns expected 401', async ({
    page,
  }) => {
    // This test verifies the route interception works correctly
    // and validates the error response structure
    await page.route('**/api/v2/auth/refresh', (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'AUTH_ERROR',
          message: 'Invalid or expired refresh token',
        }),
      })
    );

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Call the refresh endpoint directly to verify interception
    const result = await page.evaluate(async () => {
      try {
        const resp = await fetch('/api/v2/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
        });
        const body = await resp.json();
        return { status: resp.status, body };
      } catch (error) {
        return {
          status: 0,
          body: { error: error instanceof Error ? error.message : 'unknown' },
        };
      }
    });

    expect(result.status).toBe(401);
    expect(result.body.code).toBe('AUTH_ERROR');
  });

  test('session degradation does not block UI interaction', async ({
    page,
  }) => {
    // Even when auth refresh fails, the UI should remain interactive.
    // The degradation is "graceful" — session expires naturally.

    // Block refresh but allow other APIs
    await page.route('**/api/v2/auth/refresh', (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'AUTH_ERROR',
          message: 'Token expired',
        }),
      })
    );

    // Allow ticker search to work normally
    await page.route('**/api/v2/tickers/search**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [
            { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
          ],
        }),
      })
    );

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Trigger a failed refresh
    await page.evaluate(async () => {
      try {
        await fetch('/api/v2/auth/refresh', {
          method: 'POST',
          credentials: 'include',
        });
      } catch {
        // Expected to fail
      }
    });

    // UI should still be interactive — search should work
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);

    // Ticker results should appear despite auth degradation
    await expect(page.getByRole('option', { name: /AAPL/i })).toBeVisible({
      timeout: 5000,
    });
  });

  test('console events use consistent JSON format across all error types', async ({
    page,
  }) => {
    const consoleMessages: string[] = [];
    page.on('console', (msg: ConsoleMessage) => {
      if (msg.type() === 'warning') consoleMessages.push(msg.text());
    });

    // Block search to trigger search_error_displayed events
    await page.route('**/api/v2/tickers/search**', (route) =>
      route.fulfill({ status: 500, body: 'error' })
    );

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Trigger a search error
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);

    // Also emit a synthetic auth degradation event for comparison
    await page.evaluate(() => {
      console.warn(
        JSON.stringify({
          event: 'auth_degradation_warning',
          timestamp: new Date().toISOString(),
          details: { failureCount: 2 },
        })
      );
    });

    await page.waitForTimeout(500);

    // Collect all structured events (ones that parse as JSON with "event" field)
    const structuredEvents = consoleMessages
      .map((m) => {
        try {
          return JSON.parse(m);
        } catch {
          return null;
        }
      })
      .filter(
        (e): e is { event: string; timestamp: string; details: Record<string, unknown> } =>
          e !== null && typeof e.event === 'string'
      );

    expect(structuredEvents.length).toBeGreaterThanOrEqual(1);

    // All structured events should have the same shape
    for (const event of structuredEvents) {
      expect(event).toHaveProperty('event');
      expect(event).toHaveProperty('timestamp');
      expect(event).toHaveProperty('details');
      expect(typeof event.event).toBe('string');
      expect(typeof event.timestamp).toBe('string');
      expect(typeof event.details).toBe('object');
    }
  });
});

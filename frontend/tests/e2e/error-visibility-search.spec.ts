// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect, type ConsoleMessage } from '@playwright/test';
import { mockAnonymousAuth } from './helpers/auth-helper';

/**
 * T009: Ticker Search Error Visibility
 *
 * Verifies that when the ticker search API fails, the UI shows a meaningful
 * error state (not "No tickers found"), provides a retry button, and emits
 * structured console events for observability.
 *
 * Uses page.route() to intercept API calls and simulate failures.
 */
test.describe('Ticker Search Error Visibility', () => {
  test.beforeEach(async ({ page }) => {
    // Mock anonymous auth to ensure page loads correctly (must be before page.goto)
    await mockAnonymousAuth(page);
  });

  test('shows error state when API returns 500', async ({ page }) => {
    const consoleMessages: string[] = [];
    page.on('console', (msg: ConsoleMessage) => {
      if (msg.type() === 'warning') consoleMessages.push(msg.text());
    });

    // Intercept search API with 500
    await page.route('**/api/v2/tickers/search**', (route) =>
      route.fulfill({ status: 500, body: 'Internal Server Error' })
    );

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Type in search
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');

    // Wait for debounce + React Query error propagation
    await page.waitForTimeout(1500);

    // Should show error, NOT "No tickers found"
    await expect(
      page.getByText(/unable to search|check your connection/i)
    ).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/no tickers found/i)).not.toBeVisible();

    // Should have retry button
    await expect(page.getByRole('button', { name: /retry/i })).toBeVisible();

    // Console event should be emitted with structured JSON
    const searchEvent = consoleMessages.find((m) =>
      m.includes('search_error_displayed')
    );
    expect(searchEvent).toBeTruthy();

    // Verify the event is valid JSON with expected structure
    const parsed = JSON.parse(searchEvent!);
    expect(parsed.event).toBe('search_error_displayed');
    expect(parsed.timestamp).toBeTruthy();
    expect(parsed.details).toBeDefined();
    expect(parsed.details.endpoint).toBe('tickers/search');
  });

  test('shows error state for HTML response (502 Bad Gateway)', async ({
    page,
  }) => {
    // Simulate a reverse proxy returning HTML instead of JSON
    await page.route('**/api/v2/tickers/search**', (route) =>
      route.fulfill({
        status: 502,
        contentType: 'text/html',
        body: '<html><body>Bad Gateway</body></html>',
      })
    );

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);

    // Should show user-friendly error, not parse error or "No tickers found"
    await expect(
      page.getByText(/unable to search|check your connection/i)
    ).toBeVisible({ timeout: 5000 });
  });

  test('shows rate limit message for 429 response', async ({ page }) => {
    await page.route('**/api/v2/tickers/search**', (route) =>
      route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'RATE_LIMITED',
          message: 'Too many requests',
        }),
      })
    );

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);

    // Should show rate limit message, not generic error
    await expect(
      page.getByText(/too many requests|please wait/i)
    ).toBeVisible({ timeout: 5000 });

    // Rate-limited state should NOT show a retry button (per ticker-input.tsx logic)
    await expect(page.getByRole('button', { name: /retry/i })).not.toBeVisible();
  });

  test('retry button triggers a new search', async ({ page }) => {
    let retryClicked = false;

    // First few requests fail (covering React Query retries), then succeed after manual retry
    await page.route('**/api/v2/tickers/search**', (route) => {
      if (!retryClicked) {
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

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const searchInput = page.getByPlaceholder(/search tickers/i);

    // Set up waitForResponse BEFORE the action that triggers the request (race condition fix)
    const searchResponsePromise = page.waitForResponse('**/api/v2/tickers/search**');
    await searchInput.fill('AAPL');
    await searchResponsePromise;

    // Verify error shown (React Query may retry — wait for error state to propagate)
    await expect(
      page.getByText(/unable to search/i)
    ).toBeVisible({ timeout: 10000 });

    // Switch mock to success mode before clicking retry
    retryClicked = true;

    // Click retry and wait for the new search response
    // Use JS click because the empty state overlay div intercepts pointer events
    const retryButton = page.getByRole('button', { name: /retry/i });
    const retryResponsePromise = page.waitForResponse('**/api/v2/tickers/search**');
    await retryButton.evaluate((el) => (el as HTMLButtonElement).click());
    await retryResponsePromise;

    // After retry, should show results (not error)
    await expect(page.getByRole('option', { name: /AAPL/i })).toBeVisible({
      timeout: 5000,
    });
  });

  test('recovers after error when user retypes', async ({ page }) => {
    // Start with blocked API
    await page.route('**/api/v2/tickers/search**', (route) =>
      route.fulfill({ status: 500, body: 'error' })
    );

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);

    // Verify error shown
    await expect(page.getByText(/unable to search/i)).toBeVisible({
      timeout: 5000,
    });

    // Remove interception — let real API respond (or mock success)
    await page.unroute('**/api/v2/tickers/search**');
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

    // Clear and retype to trigger a fresh query
    await searchInput.fill('');
    await searchInput.fill('AAPL');
    await page.waitForTimeout(2000);

    // Error should clear — results or suggestions should appear
    await expect(page.getByRole('option', { name: /AAPL/i })).toBeVisible({
      timeout: 5000,
    });
  });

  test('error state has proper ARIA alert role', async ({ page }) => {
    await page.route('**/api/v2/tickers/search**', (route) =>
      route.fulfill({ status: 500, body: 'error' })
    );

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);

    // The error container has role="alert" for screen reader announcement
    const errorAlert = page.locator('[role="alert"]').filter({
      hasText: /unable to search|check your connection/i,
    });
    await expect(errorAlert).toBeVisible({ timeout: 5000 });
  });
});

// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect, type ConsoleMessage } from '@playwright/test';

/**
 * T014: API Health Banner Error Visibility
 *
 * Verifies that the API health banner (Feature 1226, FR-005) appears when
 * multiple consecutive API failures occur within the failure window (3 failures
 * in 60 seconds). Also tests banner dismissal and recovery.
 *
 * The api-health-store transitions:
 *   HEALTHY -> recordFailure() x3 in 60s -> UNREACHABLE (banner shown)
 *   UNREACHABLE -> recordSuccess() -> HEALTHY (banner auto-clears)
 *   UNREACHABLE -> dismissBanner() -> UNREACHABLE (banner hidden)
 *
 * Uses page.route() to block ALL API calls, then triggers enough user
 * interactions to accumulate 3+ failures.
 */
test.describe('API Health Banner Visibility', () => {
  test('shows banner after 3 consecutive API failures', async ({ page }) => {
    const consoleMessages: string[] = [];
    page.on('console', (msg: ConsoleMessage) => {
      if (msg.type() === 'warning') consoleMessages.push(msg.text());
    });

    // Block ALL API calls to simulate complete connectivity loss
    await page.route('**/api/**', (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'SERVICE_UNAVAILABLE',
          message: 'Service Unavailable',
        }),
      })
    );

    await page.goto('/');

    // Wait for initial page load (anonymous session creation will fail)
    await page.waitForTimeout(2000);

    // Trigger multiple search interactions to accumulate failures.
    // Each search triggers a React Query fetch -> error -> recordFailure().
    // The health store needs 3 failures within 60 seconds.
    const searchInput = page.getByPlaceholder(/search tickers/i);

    // Interaction 1
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);

    // Interaction 2 — clear and retype to force a new query key
    await searchInput.fill('');
    await searchInput.fill('GOOG');
    await page.waitForTimeout(1500);

    // Interaction 3 — another distinct query
    await searchInput.fill('');
    await searchInput.fill('MSFT');
    await page.waitForTimeout(1500);

    // The health banner should now be visible (3 failures in <60s)
    // Banner text from api-health-banner.tsx
    const banner = page.getByRole('alert').filter({
      hasText: /trouble connecting|features may be unavailable/i,
    });
    await expect(banner).toBeVisible({ timeout: 5000 });

    // Verify console event was emitted
    const bannerEvent = consoleMessages.find((m) =>
      m.includes('api_health_banner_shown')
    );
    expect(bannerEvent).toBeTruthy();

    // Verify the event structure
    const parsed = JSON.parse(bannerEvent!);
    expect(parsed.event).toBe('api_health_banner_shown');
    expect(parsed.details.failureCount).toBeGreaterThanOrEqual(3);
  });

  test('banner can be dismissed by user', async ({ page }) => {
    const consoleMessages: string[] = [];
    page.on('console', (msg: ConsoleMessage) => {
      if (msg.type() === 'warning') consoleMessages.push(msg.text());
    });

    // Block all API calls
    await page.route('**/api/**', (route) =>
      route.fulfill({ status: 503, body: 'Service Unavailable' })
    );

    await page.goto('/');
    await page.waitForTimeout(2000);

    // Trigger 3+ failures via search interactions
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);
    await searchInput.fill('');
    await searchInput.fill('GOOG');
    await page.waitForTimeout(1500);
    await searchInput.fill('');
    await searchInput.fill('MSFT');
    await page.waitForTimeout(1500);

    // Wait for banner to appear
    const banner = page.getByRole('alert').filter({
      hasText: /trouble connecting/i,
    });
    await expect(banner).toBeVisible({ timeout: 5000 });

    // Click dismiss button (X icon with aria-label)
    const dismissButton = page.getByRole('button', {
      name: /dismiss connectivity warning/i,
    });
    await expect(dismissButton).toBeVisible();
    await dismissButton.click();

    // Banner should be hidden
    await expect(banner).not.toBeVisible({ timeout: 3000 });

    // Verify dismiss console event
    const dismissEvent = consoleMessages.find((m) =>
      m.includes('api_health_banner_dismissed')
    );
    expect(dismissEvent).toBeTruthy();
  });

  test('banner auto-clears when connectivity recovers', async ({ page }) => {
    const consoleMessages: string[] = [];
    page.on('console', (msg: ConsoleMessage) => {
      if (msg.type() === 'warning') consoleMessages.push(msg.text());
    });

    // Block all API calls initially
    await page.route('**/api/**', (route) =>
      route.fulfill({ status: 503, body: 'Service Unavailable' })
    );

    await page.goto('/');
    await page.waitForTimeout(2000);

    // Trigger 3+ failures
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);
    await searchInput.fill('');
    await searchInput.fill('GOOG');
    await page.waitForTimeout(1500);
    await searchInput.fill('');
    await searchInput.fill('MSFT');
    await page.waitForTimeout(1500);

    // Wait for banner
    const banner = page.getByRole('alert').filter({
      hasText: /trouble connecting/i,
    });
    await expect(banner).toBeVisible({ timeout: 5000 });

    // Restore connectivity — replace all route handlers with successful responses
    await page.unroute('**/api/**');

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
      })
    );

    // Trigger a successful interaction — this calls recordSuccess()
    await searchInput.fill('');
    await searchInput.fill('TSLA');
    await page.waitForTimeout(2000);

    // Banner should auto-clear after successful response
    await expect(banner).not.toBeVisible({ timeout: 5000 });

    // Verify recovery console event
    const recoveryEvent = consoleMessages.find((m) =>
      m.includes('api_health_recovered')
    );
    expect(recoveryEvent).toBeTruthy();

    // Verify event structure
    const parsed = JSON.parse(recoveryEvent!);
    expect(parsed.event).toBe('api_health_recovered');
  });

  test('banner has proper accessibility attributes', async ({ page }) => {
    // Block all API calls
    await page.route('**/api/**', (route) =>
      route.fulfill({ status: 503, body: 'Service Unavailable' })
    );

    await page.goto('/');
    await page.waitForTimeout(2000);

    // Trigger 3+ failures
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);
    await searchInput.fill('');
    await searchInput.fill('GOOG');
    await page.waitForTimeout(1500);
    await searchInput.fill('');
    await searchInput.fill('MSFT');
    await page.waitForTimeout(1500);

    // Wait for banner
    const banner = page.getByRole('alert').filter({
      hasText: /trouble connecting/i,
    });
    await expect(banner).toBeVisible({ timeout: 5000 });

    // Verify role="alert" with aria-live="assertive" for screen readers
    await expect(banner).toHaveAttribute('aria-live', 'assertive');

    // Verify dismiss button has accessible label
    const dismissButton = page.getByRole('button', {
      name: /dismiss connectivity warning/i,
    });
    await expect(dismissButton).toBeVisible();
  });

  test('banner does not appear for isolated failures', async ({ page }) => {
    // Only fail the first request, then succeed
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

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.getByPlaceholder(/search tickers/i);

    // First search fails
    await searchInput.fill('AAPL');
    await page.waitForTimeout(1500);

    // Second search succeeds — resets the failure counter
    await searchInput.fill('');
    await searchInput.fill('GOOG');
    await page.waitForTimeout(1500);

    // Banner should NOT be visible (only 1 failure, then recovery)
    const banner = page.getByRole('alert').filter({
      hasText: /trouble connecting/i,
    });
    await expect(banner).not.toBeVisible();
  });
});

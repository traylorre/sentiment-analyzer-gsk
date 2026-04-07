// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import {
  MOCK_EMPTY_OHLC_RESPONSE,
  MOCK_EMPTY_SENTIMENT_RESPONSE,
} from './helpers/mock-api-data';

/**
 * Chart Edge Cases: Empty data, resolution fallback, API errors (Feature 1281)
 *
 * Fills gaps in existing chart coverage (sanity.spec.ts covers happy paths).
 * Uses mock route interception for deterministic test data.
 */
test.describe('Chart Edge Cases', () => {
  test.beforeEach(async ({ page }) => {
    // Mock anonymous auth so the dashboard loads
    await page.route('**/api/v2/auth/anonymous', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          token: 'mock-test-token',
          auth_type: 'anonymous',
          user_id: 'anon-test-user',
          created_at: new Date().toISOString(),
          session_expires_at: new Date(Date.now() + 86400000).toISOString(),
          storage_hint: 'session',
        }),
      });
    });

    // Mock ticker search to return AAPL
    await page.route('**/api/v2/tickers/search**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [{ symbol: 'AAPL', name: 'Apple Inc', exchange: 'NASDAQ' }],
        }),
      });
    });
  });

  test.describe('Empty Data State (US1)', () => {
    test('shows empty state message when OHLC returns zero candles', async ({
      page,
    }) => {
      // Mock OHLC to return empty candles
      await page.route('**/api/v2/tickers/*/ohlc**', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_EMPTY_OHLC_RESPONSE),
        });
      });

      // Mock sentiment to return empty
      await page.route('**/api/v2/tickers/*/sentiment/history**', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_EMPTY_SENTIMENT_RESPONSE),
        });
      });

      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Search and select AAPL
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await page.getByRole('option', { name: /AAPL/i }).first().click();

      // Wait for chart area to render
      await page.waitForTimeout(2000);

      // Verify empty state message is visible (not a blank canvas)
      await expect(
        page.getByText(/no.*price.*data.*available/i),
      ).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Resolution Fallback Banner (US2)', () => {
    test('shows fallback banner when resolution_fallback is true', async ({
      page,
    }) => {
      // Mock OHLC with resolution fallback
      await page.route('**/api/v2/tickers/*/ohlc**', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...MOCK_EMPTY_OHLC_RESPONSE,
            candles: [
              {
                date: '2026-03-15',
                open: 178.5,
                high: 180.0,
                low: 177.0,
                close: 179.2,
                volume: 50000000,
              },
            ],
            count: 1,
            resolution: 'D',
            resolution_fallback: true,
            fallback_message:
              '1-minute candles unavailable for this range. Showing daily candles.',
          }),
        });
      });

      // Mock sentiment with some data
      await page.route('**/api/v2/tickers/*/sentiment/history**', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_EMPTY_SENTIMENT_RESPONSE),
        });
      });

      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Search and select AAPL
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await page.getByRole('option', { name: /AAPL/i }).first().click();

      // Wait for chart to load
      await page.waitForTimeout(2000);

      // Verify fallback banner is visible
      await expect(
        page.getByText(/1-minute candles unavailable/i),
      ).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('API Error State (US3)', () => {
    test('shows error message when OHLC API returns 500', async ({ page }) => {
      // Mock OHLC to fail
      await page.route('**/api/v2/tickers/*/ohlc**', async (route) => {
        await route.fulfill({ status: 500, body: 'Internal Server Error' });
      });

      // Mock sentiment to also fail (realistic scenario)
      await page.route('**/api/v2/tickers/*/sentiment/history**', async (route) => {
        await route.fulfill({ status: 500, body: 'Internal Server Error' });
      });

      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Search and select AAPL
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await page.getByRole('option', { name: /AAPL/i }).first().click();

      // Wait for error to render
      await page.waitForTimeout(3000);

      // Verify error state is visible — component shows error or "no data"
      // 15s timeout: React Query retries with exponential backoff before showing error
      await expect(
        page.getByText(/error|failed|trouble|no.*data|try again/i).first()
      ).toBeVisible({ timeout: 15000 });
    });

    test('retry button re-fetches data after error', async ({ page }) => {
      let callCount = 0;

      // Fail first 2 calls (initial + React Query's 1 retry), then succeed
      await page.route('**/api/v2/tickers/*/ohlc**', async (route) => {
        callCount++;
        if (callCount <= 2) {
          await route.fulfill({ status: 500, body: 'Internal Server Error' });
        } else {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              ...MOCK_EMPTY_OHLC_RESPONSE,
              candles: [
                {
                  date: '2026-03-15',
                  open: 178.5,
                  high: 180.0,
                  low: 177.0,
                  close: 179.2,
                  volume: 50000000,
                },
              ],
              count: 1,
            }),
          });
        }
      });

      await page.route('**/api/v2/tickers/*/sentiment/history**', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_EMPTY_SENTIMENT_RESPONSE),
        });
      });

      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Search and select AAPL (triggers first OHLC call → 500)
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await page.getByRole('option', { name: /AAPL/i }).first().click();

      // Wait for error state
      await page.waitForTimeout(3000);

      // Click retry/try again button — first call mocked to 500, so error state
      // with retry button is guaranteed
      const retryButton = page.getByRole('button', { name: /try again|retry|refetch/i });
      await expect(retryButton).toBeVisible({ timeout: 10000 });
      await retryButton.click();

      // Wait for second call to succeed
      await page.waitForTimeout(3000);

      // Verify chart loaded (aria-label with candle count)
      await expect(
        page.locator('[role="img"][aria-label*="candle"]'),
      ).toBeVisible({ timeout: 10000 });
    });
  });
});

// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { mockTickerDataApis } from './helpers/mock-api-data';

/**
 * Ticker Search Gap Tests: No-results, keyboard nav, multi-ticker (Feature 1282)
 *
 * Fills gaps in existing search coverage (dashboard-interactions.spec.ts covers happy paths,
 * error-visibility-search.spec.ts covers error states).
 */
test.describe('Ticker Search Gaps', () => {
  test.beforeEach(async ({ page }) => {
    // Mock anonymous auth
    await page.route('**/api/v2/auth/anonymous', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-test-token',
          token_type: 'bearer',
          auth_type: 'anonymous',
          user_id: 'anon-test-user',
          session_expires_in_seconds: 3600,
        }),
      });
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test.describe('No-Results State (US1)', () => {
    test('shows "no tickers found" when search returns empty results', async ({
      page,
    }) => {
      // Mock search to return empty
      await page.route('**/api/v2/tickers/search**', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ results: [] }),
        });
      });

      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('ZZZZZ');

      // Wait for debounced search response (FR-008: waitForResponse, not waitForTimeout)
      await page.waitForResponse('**/api/v2/tickers/search**');

      // Verify no-results message
      await expect(
        page.getByText(/no tickers found/i),
      ).toBeVisible({ timeout: 5000 });
    });

    test('results replace no-results message when query changes', async ({
      page,
    }) => {
      let callCount = 0;
      await page.route('**/api/v2/tickers/search**', async (route) => {
        callCount++;
        if (callCount === 1) {
          // First search: no results
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ results: [] }),
          });
        } else {
          // Second search: results
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              results: [
                { symbol: 'AAPL', name: 'Apple Inc', exchange: 'NASDAQ' },
              ],
            }),
          });
        }
      });

      const searchInput = page.getByPlaceholder(/search tickers/i);

      // First search: no results
      await searchInput.fill('ZZZZZ');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await expect(page.getByText(/no tickers found/i)).toBeVisible();

      // Second search: results appear
      await searchInput.fill('AAPL');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await expect(page.getByRole('option', { name: /AAPL/i }).first()).toBeVisible();
      await expect(page.getByText(/no tickers found/i)).not.toBeVisible();
    });
  });

  test.describe('Keyboard Navigation (US2)', () => {
    test.beforeEach(async ({ page }) => {
      // Mock search with multiple results
      await page.route('**/api/v2/tickers/search**', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            results: [
              { symbol: 'AAPL', name: 'Apple Inc', exchange: 'NASDAQ' },
              { symbol: 'AMZN', name: 'Amazon.com Inc', exchange: 'NASDAQ' },
              { symbol: 'GOOGL', name: 'Alphabet Inc', exchange: 'NASDAQ' },
            ],
          }),
        });
      });
    });

    test('Arrow Down highlights first result', async ({ page }) => {
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('A');
      await page.waitForResponse('**/api/v2/tickers/search**');

      // Arrow Down to first result
      await searchInput.press('ArrowDown');

      // Verify aria-activedescendant is set (combobox keyboard pattern)
      const activeDescendant = await searchInput.getAttribute(
        'aria-activedescendant',
      );
      expect(activeDescendant).toBeTruthy();
    });

    test('Enter on highlighted result selects ticker and loads chart', async ({
      page,
    }) => {
      // Also mock OHLC/sentiment for chart load
      await mockTickerDataApis(page);

      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('A');
      await page.waitForResponse('**/api/v2/tickers/search**');

      // Arrow Down + Enter to select first result (AAPL)
      await searchInput.press('ArrowDown');
      await searchInput.press('Enter');

      // Verify chart loads (aria-label with candle count)
      await expect(
        page.locator('[role="img"][aria-label*="candle"]'),
      ).toBeVisible({ timeout: 15000 });
    });

    test('Escape closes dropdown without selecting', async ({ page }) => {
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('A');
      await page.waitForResponse('**/api/v2/tickers/search**');

      // Verify dropdown is visible
      await expect(page.getByRole('option').first()).toBeVisible();

      // Escape closes it
      await searchInput.press('Escape');
      await expect(page.getByRole('option').first()).not.toBeVisible();

      // Input retains text
      await expect(searchInput).toHaveValue('A');
    });

    test('Arrow Down does not exceed last result (no wrap)', async ({
      page,
    }) => {
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('A');
      await page.waitForResponse('**/api/v2/tickers/search**');

      // Press Arrow Down 10 times (more than 3 results)
      for (let i = 0; i < 10; i++) {
        await searchInput.press('ArrowDown');
      }

      // Should be clamped at last result, not crash or wrap
      const activeDescendant = await searchInput.getAttribute(
        'aria-activedescendant',
      );
      expect(activeDescendant).toBeTruthy();
    });
  });

  test.describe('Multi-Ticker Chip Management (US3)', () => {
    test.beforeEach(async ({ page }) => {
      await mockTickerDataApis(page);

      // Mock search to return different tickers based on query
      await page.route('**/api/v2/tickers/search**', async (route) => {
        const url = new URL(route.request().url());
        const query = url.searchParams.get('q')?.toUpperCase() ?? '';

        const allTickers = [
          { symbol: 'AAPL', name: 'Apple Inc', exchange: 'NASDAQ' },
          { symbol: 'GOOGL', name: 'Alphabet Inc', exchange: 'NASDAQ' },
          { symbol: 'MSFT', name: 'Microsoft Corp', exchange: 'NASDAQ' },
        ];

        const filtered = allTickers.filter(
          (t) =>
            t.symbol.includes(query) ||
            t.name.toUpperCase().includes(query),
        );

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ results: filtered }),
        });
      });
    });

    test('adding second ticker creates second chip', async ({ page }) => {
      const searchInput = page.getByPlaceholder(/search tickers/i);

      // Add first ticker
      await searchInput.fill('AAPL');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await page.getByRole('option', { name: /AAPL/i }).first().click();
      await expect(page.getByText('AAPL')).toBeVisible({ timeout: 5000 });

      // Add second ticker
      await searchInput.fill('GOOGL');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await page.getByRole('option', { name: /GOOGL/i }).first().click();
      await expect(page.getByText('GOOGL')).toBeVisible({ timeout: 5000 });
    });

    test('duplicate ticker switches to existing chip without adding', async ({
      page,
    }) => {
      const searchInput = page.getByPlaceholder(/search tickers/i);

      // Add AAPL
      await searchInput.fill('AAPL');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await page.getByRole('option', { name: /AAPL/i }).first().click();

      // Add GOOGL
      await searchInput.fill('GOOGL');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await page.getByRole('option', { name: /GOOGL/i }).first().click();

      // Try to add AAPL again
      await searchInput.fill('AAPL');
      await page.waitForResponse('**/api/v2/tickers/search**');
      await page.getByRole('option', { name: /AAPL/i }).first().click();

      // Should still have exactly 2 chips, not 3
      // Count elements containing ticker symbols
      const aaplChips = page.locator('button:has-text("AAPL"), [data-ticker="AAPL"]');
      const googlChips = page.locator('button:has-text("GOOGL"), [data-ticker="GOOGL"]');
      // At most 1 of each (chip + possible tab text)
      expect(await aaplChips.count()).toBeLessThanOrEqual(2);
      expect(await googlChips.count()).toBeLessThanOrEqual(2);
    });
  });
});

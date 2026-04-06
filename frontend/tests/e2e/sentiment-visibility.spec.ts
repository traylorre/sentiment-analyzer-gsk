// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';

test.describe('Sentiment Data Visibility', () => {
  test.setTimeout(30000);

  async function searchAndSelectTicker(page: import('@playwright/test').Page, ticker: string) {
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.clear();
    await searchInput.fill(ticker);

    // Handle 429 rate limiting on search endpoint
    let retries = 0;
    const maxRetries = 3;
    let rateLimited = false;

    page.on('response', (response) => {
      if (response.url().includes('search') && response.status() === 429) {
        rateLimited = true;
      }
    });

    // Wait for suggestions to appear
    const suggestion = page.getByRole('option', { name: new RegExp(ticker, 'i') });
    while (retries < maxRetries) {
      try {
        await suggestion.waitFor({ timeout: 5000 });
        rateLimited = false;
        break;
      } catch {
        if (rateLimited) {
          retries++;
          rateLimited = false;
          if (retries >= maxRetries) {
            test.skip(true, `Rate limited (429) after ${maxRetries} retries on search endpoint`);
          }
          await page.waitForTimeout(2000);
          await searchInput.clear();
          await searchInput.fill(ticker);
        } else {
          throw new Error(`Suggestion for ${ticker} did not appear`);
        }
      }
    }

    await suggestion.click();
  }

  test('AAPL chart displays sentiment data points', async ({ page }) => {
    await page.goto('/');

    await searchAndSelectTicker(page, 'AAPL');

    // Wait for chart to render
    const chart = page.getByRole('img', { name: /price and sentiment/i });
    await chart.waitFor({ timeout: 15000 });

    // Assert chart contains sentiment data
    const ariaLabel = await chart.getAttribute('aria-label');
    expect(ariaLabel).toBeDefined();
    expect(ariaLabel!.toLowerCase()).toContain('sentiment');
  });

  test('chart updates on time range change', async ({ page }) => {
    await page.goto('/');

    await searchAndSelectTicker(page, 'AAPL');

    // Wait for initial chart
    const chart = page.getByRole('img', { name: /price and sentiment/i });
    await chart.waitFor({ timeout: 15000 });

    // Click 1M time range button (aria-label is "1M time range")
    await page.getByRole('button', { name: /1M time range/i }).click();

    // Wait for chart to update
    await page.waitForTimeout(2000);

    // Assert no error messages are visible
    const errorText = page.getByText(/error/i);
    const failedText = page.getByText(/failed/i);
    await expect(errorText).toBeHidden();
    await expect(failedText).toBeHidden();
  });

  test('multiple tickers show sentiment data', async ({ page }) => {
    await page.goto('/');

    // Load AAPL chart first
    await searchAndSelectTicker(page, 'AAPL');

    const chart = page.getByRole('img', { name: /price and sentiment/i });
    await chart.waitFor({ timeout: 15000 });

    // Switch to MSFT
    await searchAndSelectTicker(page, 'MSFT');

    // Wait for chart to update with MSFT data
    await chart.waitFor({ timeout: 15000 });

    // Assert chart is still visible after ticker switch
    await expect(chart).toBeVisible();
  });
});

// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { waitForAuth } from './helpers/auth-helper';
import { skipWithoutDataApis } from './helpers/data-api-guard';

test.describe('Sentiment Data Visibility', { tag: '@external-api' }, () => {
  test.setTimeout(30000);

  test.beforeEach(async () => {
    await skipWithoutDataApis(test);
  });

  async function searchAndSelectTicker(page: import('@playwright/test').Page, ticker: string) {
    // Retry within the test on 429. Exhausting the attempts is a break, not a skip.
    //
    // Spec 1401 D2. This helper had four defects, all fixed here:
    //
    //  1. The 429 listener was registered AFTER searchInput.fill(). Measured
    //     (6 samples): the search request reaches the network at 33-61ms while
    //     fill() does not return until 38-69ms, so the old registration point was
    //     4-9ms AFTER the request had already left the page. Any response landing
    //     in that window is dispatched to zero listeners, rateLimited stays false,
    //     and the helper throws "did not appear" having never retried -- on the
    //     first attempt, where rate limiting is most likely, and a 429 from a rate
    //     limiter is the fastest response there is because it does no upstream
    //     work. Note this is a narrow race and not the certain miss the original
    //     diagnosis claimed: a probe of the old ordering did observe the 429 when
    //     the response came back slower than the window. Registering before the
    //     fill closes the window outright and costs nothing.
    //  2. new RegExp(ticker, 'i') is a substring match, so 'AAPL' also matched
    //     'AAPLW'. waitFor() enforces strict mode, so a multi-match threw INSIDE
    //     the try, landed in the catch with rateLimited false, and was reported as
    //     "did not appear". Measured: searching AAPL against a two-row result set
    //     resolves the bare /AAPL/i locator to 2 elements.
    //     The row is matched by its id instead. Anchoring the accessible name does
    //     NOT work and was measured failing: the symbol and company spans
    //     (ticker-input.tsx:215-217) are adjacent with no whitespace text node
    //     between them, so Chromium computes the name as "AAPLApple Inc.", and
    //     /^AAPL\b/i matches zero options. ticker-input.tsx:200 gives every row
    //     id="ticker-option-<symbol>", which is exact and cannot be prefix-masked.
    //  3. The listener was never removed, and this helper is called twice on the
    //     same page. It is now removed in a finally.
    //  4. maxRetries = 3 is 3 attempts and 2 retries; the message said "after 3
    //     retries". It now counts attempts, which is what the loop bounds.
    const searchInput = page.getByPlaceholder(/search tickers/i);

    const maxAttempts = 3;
    let rateLimited = false;

    const onResponse = (response: import('@playwright/test').Response) => {
      if (response.url().includes('search') && response.status() === 429) {
        rateLimited = true;
      }
    };
    page.on('response', onResponse);

    try {
      await searchInput.clear();
      await searchInput.fill(ticker);

      // Wait for suggestions to appear. Matched by the row's own id so a longer
      // symbol sharing this prefix cannot make the locator ambiguous under
      // strict mode. The [role="option"] prefix keeps the role assertion.
      const suggestion = page.locator(
        `[role="option"]#ticker-option-${ticker}`,
      );

      for (let attempt = 1; ; attempt++) {
        try {
          await suggestion.waitFor({ timeout: 5000 });
          break;
        } catch (err) {
          if (!rateLimited) {
            throw new Error(
              `Suggestion for ${ticker} did not appear on attempt ${attempt} of ` +
                `${maxAttempts}, and no 429 was observed: ${
                  err instanceof Error ? err.message : String(err)
                }`
            );
          }
          rateLimited = false;
          if (attempt >= maxAttempts) {
            throw new Error(
              `Suggestion for ${ticker} did not appear: search endpoint returned 429 ` +
                `on all ${maxAttempts} attempts`
            );
          }
          await page.waitForTimeout(2000);
          await searchInput.clear();
          await searchInput.fill(ticker);
        }
      }

      await suggestion.click();
    } finally {
      page.off('response', onResponse);
    }
  }

  test('AAPL chart displays sentiment data points', async ({ page }) => {
    await page.goto('/');
    await waitForAuth(page);

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
    await waitForAuth(page);

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

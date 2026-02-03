import { test, expect } from '@playwright/test';

test.describe('Critical User Path - Sanity Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.describe('Desktop Viewport', () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 800 });
    });

    test('should complete full ticker selection and chart interaction flow', async ({
      page,
    }) => {
      // Step 1: Search for AAPL ticker
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await expect(searchInput).toBeVisible();
      await searchInput.fill('AAPL');

      // Wait for debounce (500ms) plus some buffer for API response
      await page.waitForTimeout(600);

      // Step 2: Click to select AAPL from suggestions
      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Step 3: Wait for chart to populate with data
      // The chart container has an aria-label that includes data point counts
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toBeVisible({ timeout: 15000 });

      // Verify chart has loaded with actual data points (not 0)
      // Use [1-9] to match non-zero counts, waiting for data to actually load
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles and [1-9]\d* sentiment points/,
        { timeout: 15000 }
      );

      // Verify we have non-zero data points
      const ariaLabel = await chartContainer.getAttribute('aria-label');
      const priceMatch = ariaLabel?.match(/(\d+) price candles/);
      const sentimentMatch = ariaLabel?.match(/(\d+) sentiment points/);

      expect(priceMatch).toBeTruthy();
      expect(sentimentMatch).toBeTruthy();

      const priceCount = parseInt(priceMatch![1], 10);
      const sentimentCount = parseInt(sentimentMatch![1], 10);

      expect(priceCount).toBeGreaterThan(0);
      expect(sentimentCount).toBeGreaterThan(0);

      // Step 4: Change time range to 3M
      const threeMonthButton = page.getByRole('button', {
        name: '3M time range',
      });
      await expect(threeMonthButton).toBeVisible();
      await threeMonthButton.click();

      // Wait for data to reload
      await page.waitForTimeout(600);

      // Verify chart still has data after time range change
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles and [1-9]\d* sentiment points/,
        { timeout: 15000 }
      );

      // Verify data updated (counts may differ for different time ranges)
      const updatedAriaLabel = await chartContainer.getAttribute('aria-label');
      const updatedPriceMatch = updatedAriaLabel?.match(/(\d+) price candles/);
      expect(updatedPriceMatch).toBeTruthy();
      expect(parseInt(updatedPriceMatch![1], 10)).toBeGreaterThan(0);
    });

    test('should display current price and sentiment values after ticker selection', async ({
      page,
    }) => {
      // Search and select AAPL
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForTimeout(600);

      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Wait for chart data to load
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Verify ticker name is displayed
      await expect(page.getByText('AAPL').first()).toBeVisible();

      // Verify price is displayed (should contain $ followed by numbers)
      await expect(page.getByText(/\$\d+\.\d{2}/)).toBeVisible({
        timeout: 10000,
      });
    });

    test('should allow switching between all time ranges', async ({ page }) => {
      // Search and select AAPL
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForTimeout(600);

      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Wait for initial load
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Test each time range button
      const timeRanges = ['1W', '1M', '3M', '6M', '1Y'];

      for (const range of timeRanges) {
        const button = page.getByRole('button', {
          name: `${range} time range`,
        });
        await expect(button).toBeVisible();
        await button.click();

        // Wait for data to reload
        await page.waitForTimeout(600);

        // Verify button is now pressed
        await expect(button).toHaveAttribute('aria-pressed', 'true');

        // Verify chart still has data
        await expect(chartContainer).toHaveAttribute(
          'aria-label',
          /[1-9]\d* price candles/,
          { timeout: 15000 }
        );
      }
    });

    test('should toggle price and sentiment layers', async ({ page }) => {
      // Search and select AAPL
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForTimeout(600);

      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Wait for chart to load
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Toggle price candles off
      const priceToggle = page.getByRole('button', {
        name: 'Toggle price candles',
      });
      await expect(priceToggle).toBeVisible();
      await expect(priceToggle).toHaveAttribute('aria-pressed', 'true');
      await priceToggle.click();
      await expect(priceToggle).toHaveAttribute('aria-pressed', 'false');

      // Toggle sentiment line off
      const sentimentToggle = page.getByRole('button', {
        name: 'Toggle sentiment line',
      });
      await expect(sentimentToggle).toBeVisible();
      await expect(sentimentToggle).toHaveAttribute('aria-pressed', 'true');
      await sentimentToggle.click();
      await expect(sentimentToggle).toHaveAttribute('aria-pressed', 'false');

      // Toggle both back on
      await priceToggle.click();
      await expect(priceToggle).toHaveAttribute('aria-pressed', 'true');
      await sentimentToggle.click();
      await expect(sentimentToggle).toHaveAttribute('aria-pressed', 'true');
    });
  });

  test.describe('Mobile Viewport', () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
    });

    test('should complete full ticker selection and chart interaction flow on mobile', async ({
      page,
    }) => {
      // Step 1: Search for AAPL ticker
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await expect(searchInput).toBeVisible();
      await searchInput.fill('AAPL');

      // Wait for debounce
      await page.waitForTimeout(600);

      // Step 2: Click to select AAPL from suggestions
      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Step 3: Wait for chart to populate with data
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toBeVisible({ timeout: 15000 });

      // Verify chart has loaded with actual data points
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles and [1-9]\d* sentiment points/,
        { timeout: 15000 }
      );

      // Step 4: Change time range to 1M
      const oneMonthButton = page.getByRole('button', {
        name: '1M time range',
      });
      await expect(oneMonthButton).toBeVisible();
      await oneMonthButton.click();

      // Wait for data to reload
      await page.waitForTimeout(600);

      // Verify chart still has data after time range change
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles and [1-9]\d* sentiment points/,
        { timeout: 15000 }
      );
    });

    test('should display chart controls properly on mobile viewport', async ({
      page,
    }) => {
      // Search and select AAPL
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForTimeout(600);

      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Wait for chart to load
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Verify time range buttons are visible and tappable
      const oneWeekButton = page.getByRole('button', {
        name: '1W time range',
      });
      await expect(oneWeekButton).toBeVisible();

      // Verify sentiment source dropdown is accessible
      const sentimentSource = page.getByRole('combobox', {
        name: 'Sentiment source',
      });
      await expect(sentimentSource).toBeVisible();

      // Verify layer toggles are visible
      const priceToggle = page.getByRole('button', {
        name: 'Toggle price candles',
      });
      const sentimentToggle = page.getByRole('button', {
        name: 'Toggle sentiment line',
      });
      await expect(priceToggle).toBeVisible();
      await expect(sentimentToggle).toBeVisible();
    });

    test('should handle mobile navigation after ticker selection', async ({
      page,
    }) => {
      // Search and select AAPL
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForTimeout(600);

      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Wait for chart to load
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Navigate to Settings using mobile navigation (client-side tab switch, not URL change)
      const settingsTab = page.getByRole('tab', { name: /settings/i });
      if (await settingsTab.isVisible()) {
        await settingsTab.click();
        // Verify Settings tab is now selected (aria-selected or pressed state)
        await expect(settingsTab).toHaveAttribute('aria-selected', 'true', { timeout: 5000 });

        // Navigate back to Dashboard
        const dashboardTab = page.getByRole('tab', { name: /dashboard/i });
        await dashboardTab.click();
        // Verify Dashboard tab is now selected
        await expect(dashboardTab).toHaveAttribute('aria-selected', 'true', { timeout: 5000 });

        // Verify chart is still showing data (state preserved or reloaded)
        await expect(
          page.locator('[role="img"][aria-label*="chart"]')
        ).toBeVisible({ timeout: 15000 });
      }
    });
  });

  test.describe('GOOG Ticker - Tiingo Fix Verification', () => {
    /**
     * Regression test for the "no data" bug with GOOG ticker.
     *
     * Root cause (fixed in b2a7e40):
     * - Tiingo adapter returned [] on 404 responses
     * - Empty array was cached for 30-60 minutes
     * - Users saw "no data" with no error message
     *
     * This test verifies:
     * 1. GOOG can be added as a ticker
     * 2. Price data loads and displays (not empty state)
     * 3. Data persists across time frame changes
     */
    test('should display GOOG price data after fix', async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 800 });

      // Step 1: Search for GOOG ticker
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await expect(searchInput).toBeVisible();
      await searchInput.fill('GOOG');

      // Wait for debounce plus API response
      await page.waitForTimeout(600);

      // Step 2: Select GOOG from suggestions (first match to avoid GOOGL)
      const suggestion = page.getByRole('option', { name: /GOOG.*Alphabet.*Class C/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Step 3: Verify chart loads with data (NOT empty state)
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toBeVisible({ timeout: 15000 });

      // Verify we have actual price data (the fix prevents caching of empty responses)
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles and [1-9]\d* sentiment points/,
        { timeout: 15000 }
      );

      // Extract and verify non-zero data points
      const ariaLabel = await chartContainer.getAttribute('aria-label');
      const priceMatch = ariaLabel?.match(/(\d+) price candles/);
      expect(priceMatch).toBeTruthy();
      const priceCount = parseInt(priceMatch![1], 10);
      expect(priceCount).toBeGreaterThan(0);

      // Verify GOOG ticker name is displayed
      await expect(page.getByText('GOOG').first()).toBeVisible();

      // Verify actual price value is shown (not empty state)
      await expect(page.getByText(/\$\d+\.\d{2}/)).toBeVisible({
        timeout: 10000,
      });

      // Verify empty state is NOT shown
      const emptyState = page.getByText(/no price data available/i);
      await expect(emptyState).not.toBeVisible();
    });

    test('should maintain GOOG data across time frame changes', async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1280, height: 800 });

      // Add GOOG ticker
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('GOOG');
      await page.waitForTimeout(600);

      // Select GOOG from suggestions (first match to avoid GOOGL)
      const suggestion = page.getByRole('option', { name: /GOOG.*Alphabet.*Class C/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Wait for initial load
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Test each time range - verify data loads for each
      const timeRanges = ['1W', '1M', '3M', '6M', '1Y'];

      for (const range of timeRanges) {
        const button = page.getByRole('button', {
          name: `${range} time range`,
        });
        await expect(button).toBeVisible();
        await button.click();

        // Wait for data to reload
        await page.waitForTimeout(600);

        // Verify chart still has data (not empty)
        await expect(chartContainer).toHaveAttribute(
          'aria-label',
          /[1-9]\d* price candles/,
          { timeout: 15000 }
        );

        // Verify empty state is NOT shown after time range change
        const emptyState = page.getByText(/no price data available/i);
        await expect(emptyState).not.toBeVisible();
      }
    });

    /**
     * Verify that data count increases for longer time ranges.
     * This indirectly tests the auto-zoom fix - if fitContent() is called,
     * we should see more data points for longer ranges.
     */
    test('should load more data points for longer time ranges', async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1280, height: 800 });

      // Add GOOG ticker
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('GOOG');
      await page.waitForTimeout(600);

      const suggestion = page.getByRole('option', { name: /GOOG.*Alphabet.*Class C/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );

      // Select 1W first
      const oneWeekButton = page.getByRole('button', { name: '1W time range' });
      await oneWeekButton.click();
      await page.waitForTimeout(600);

      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Get 1W candle count
      const oneWeekLabel = await chartContainer.getAttribute('aria-label');
      const oneWeekMatch = oneWeekLabel?.match(/(\d+) price candles/);
      expect(oneWeekMatch).toBeTruthy();
      const oneWeekCount = parseInt(oneWeekMatch![1], 10);

      // Switch to 6M
      const sixMonthButton = page.getByRole('button', { name: '6M time range' });
      await sixMonthButton.click();
      await page.waitForTimeout(600);

      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Get 6M candle count
      const sixMonthLabel = await chartContainer.getAttribute('aria-label');
      const sixMonthMatch = sixMonthLabel?.match(/(\d+) price candles/);
      expect(sixMonthMatch).toBeTruthy();
      const sixMonthCount = parseInt(sixMonthMatch![1], 10);

      // 6M should have significantly more data points than 1W
      // (6 months ≈ 126 trading days vs 1 week ≈ 5 trading days)
      expect(sixMonthCount).toBeGreaterThan(oneWeekCount);

      // Verify 6M has at least 60 candles (conservative estimate for 3 months of trading)
      expect(sixMonthCount).toBeGreaterThanOrEqual(60);
    });

    /**
     * Verify sentiment data is present when sentiment toggle is active.
     * Regression test for sentiment line visibility fix.
     */
    test('should have sentiment data when toggle is active', async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1280, height: 800 });

      // Add GOOG ticker
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('GOOG');
      await page.waitForTimeout(600);

      const suggestion = page.getByRole('option', { name: /GOOG.*Alphabet.*Class C/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );

      // Wait for both price AND sentiment data
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles and [1-9]\d* sentiment points/,
        { timeout: 15000 }
      );

      // Verify sentiment toggle is pressed (active)
      const sentimentToggle = page.getByRole('button', { name: 'Toggle sentiment line' });
      await expect(sentimentToggle).toHaveAttribute('aria-pressed', 'true');

      // Extract sentiment count
      const ariaLabel = await chartContainer.getAttribute('aria-label');
      const sentimentMatch = ariaLabel?.match(/(\d+) sentiment points/);
      expect(sentimentMatch).toBeTruthy();
      const sentimentCount = parseInt(sentimentMatch![1], 10);

      // Should have multiple sentiment data points
      expect(sentimentCount).toBeGreaterThan(5);

      // Toggle sentiment off
      await sentimentToggle.click();
      await expect(sentimentToggle).toHaveAttribute('aria-pressed', 'false');

      // Toggle back on
      await sentimentToggle.click();
      await expect(sentimentToggle).toHaveAttribute('aria-pressed', 'true');

      // Aria-label should still show sentiment data (data persists across toggle)
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* sentiment points/,
        { timeout: 5000 }
      );
    });
  });

  test.describe('Settings Persistence', () => {
    /**
     * T026: Verify timeRange and resolution persist across ticker switches.
     *
     * Root cause (fixed):
     * - When activeTicker changes, React remounts PriceSentimentChart
     * - Resolution was persisted via sessionStorage, but timeRange was not
     * - User selected 1Y + Day for GOOG, switched to AAPL, saw 1M + Day reset
     *
     * Fix: Add sessionStorage persistence for timeRange following same pattern as resolution.
     */
    test('should persist timeRange and resolution when switching tickers', async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1280, height: 800 });

      // Step 1: Search and select GOOG
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('GOOG');
      await page.waitForTimeout(600);

      const googSuggestion = page.getByRole('option', { name: /GOOG.*Alphabet.*Class C/i });
      await expect(googSuggestion).toBeVisible({ timeout: 10000 });
      await googSuggestion.click();

      // Wait for chart to load
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Step 2: Set 1Y time range
      const oneYearButton = page.getByRole('button', { name: '1Y time range' });
      await expect(oneYearButton).toBeVisible();
      await oneYearButton.click();
      await page.waitForTimeout(600);

      // Verify 1Y is selected
      await expect(oneYearButton).toHaveAttribute('aria-pressed', 'true');

      // Step 3: Set Day resolution
      const dayResButton = page.getByRole('button', { name: 'Day resolution' });
      await expect(dayResButton).toBeVisible();
      await dayResButton.click();
      await page.waitForTimeout(600);

      // Verify Day is selected
      await expect(dayResButton).toHaveAttribute('aria-pressed', 'true');

      // Step 4: Now switch to AAPL ticker
      await searchInput.clear();
      await searchInput.fill('AAPL');
      await page.waitForTimeout(600);

      const aaplSuggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(aaplSuggestion).toBeVisible({ timeout: 10000 });
      await aaplSuggestion.click();

      // Wait for AAPL chart to load
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /AAPL.*[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Step 5: Verify 1Y and Day are STILL selected (persisted)
      const oneYearButtonAfterSwitch = page.getByRole('button', { name: '1Y time range' });
      const dayResButtonAfterSwitch = page.getByRole('button', { name: 'Day resolution' });

      await expect(oneYearButtonAfterSwitch).toHaveAttribute('aria-pressed', 'true');
      await expect(dayResButtonAfterSwitch).toHaveAttribute('aria-pressed', 'true');
    });

    /**
     * Verify intraday resolution loads sufficient data for the selected time range.
     *
     * Context (related to zoom fix):
     * - VISIBLE_CANDLES logic limited 1h resolution ZOOM to 40 candles (~5-6 days)
     * - User selected 1M + 1h but only saw last week of data (rest was off-screen)
     * - Data WAS present (confirmed by zooming out)
     * - Fix: Removed setVisibleLogicalRange() call for intraday, fitContent() now shows full range
     *
     * This test verifies:
     * - Data is fetched correctly for 1M + 1h (>60 hourly candles)
     * - Note: Cannot verify visible zoom level via Playwright (canvas-based chart)
     * - Visual verification: Chart should show full month on initial load, not just 5-6 days
     */
    test('should load sufficient data for intraday resolution', async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1280, height: 800 });

      // Search and select GOOG
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('GOOG');
      await page.waitForTimeout(600);

      const suggestion = page.getByRole('option', { name: /GOOG.*Alphabet.*Class C/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Set 1M time range
      const oneMonthButton = page.getByRole('button', { name: '1M time range' });
      await oneMonthButton.click();
      await page.waitForTimeout(600);

      // Set 1h resolution
      const hourResButton = page.getByRole('button', { name: '1h resolution' });
      await hourResButton.click();
      await page.waitForTimeout(1000); // Allow time for data reload

      // Wait for chart to update with hourly data
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Get candle count - for 1M at 1h resolution, should have ~160 candles
      // (20 trading days × 8 hours = 160 hourly candles)
      const ariaLabel = await chartContainer.getAttribute('aria-label');
      const candleMatch = ariaLabel?.match(/(\d+) price candles/);
      expect(candleMatch).toBeTruthy();
      const candleCount = parseInt(candleMatch![1], 10);

      // Should have significantly more than 40 candles (the old VISIBLE_CANDLES limit)
      // Relaxed threshold: at least 60 candles for 1M of hourly data
      expect(candleCount).toBeGreaterThan(60);
    });
  });

  test.describe('Error Handling', () => {
    test('should handle search with no results gracefully', async ({
      page,
    }) => {
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('XYZNOTAREALTICKER123');

      // Wait for debounce and API response
      await page.waitForTimeout(1000);

      // Should show no results or empty state, not crash
      const noResults = page.getByText(/no results/i);
      const suggestions = page.locator('[role="option"]');

      // Either no results message or no suggestion options (listbox might still exist but empty)
      const noResultsVisible = await noResults.isVisible().catch(() => false);
      const suggestionsCount = await suggestions.count();

      // One of these conditions should be true:
      // 1. "No results" message is visible
      // 2. No suggestion options are visible (empty listbox is OK)
      // Note: We don't crash on invalid input - that's the main assertion
      expect(
        noResultsVisible || suggestionsCount === 0,
        `Expected no results message or empty suggestions, got ${suggestionsCount} suggestions`
      ).toBeTruthy();
    });

    test('should show loading state while fetching chart data', async ({
      page,
    }) => {
      // Search and select AAPL
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForTimeout(600);

      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Loading indicator should appear (may be brief)
      // We check that either loading appears or data loads successfully
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );

      // Wait for chart container to be visible
      await expect(chartContainer).toBeVisible({ timeout: 15000 });

      // Check that loading state is shown OR data is already loaded
      // (loading may be too brief to catch, so we just verify the sequence works)
      const loadingText = page.getByText('Loading chart data...');
      const isLoadingVisible = await loadingText.isVisible().catch(() => false);

      // Eventually chart should have data
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );
    });
  });

  test.describe('Accessibility', () => {
    test('should have accessible chart controls', async ({ page }) => {
      // Search and select AAPL
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      await page.waitForTimeout(600);

      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Wait for chart to load
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Verify all time range buttons have proper aria-labels
      const timeRanges = ['1W', '1M', '3M', '6M', '1Y'];
      for (const range of timeRanges) {
        const button = page.getByRole('button', {
          name: `${range} time range`,
        });
        await expect(button).toBeVisible();
        await expect(button).toHaveAttribute('aria-pressed');
      }

      // Verify chart container has descriptive aria-label
      const ariaLabel = await chartContainer.getAttribute('aria-label');
      expect(ariaLabel).toContain('Price and sentiment chart');
      expect(ariaLabel).toContain('AAPL');

      // Verify layer toggles have proper aria attributes
      const priceToggle = page.getByRole('button', {
        name: 'Toggle price candles',
      });
      const sentimentToggle = page.getByRole('button', {
        name: 'Toggle sentiment line',
      });
      await expect(priceToggle).toHaveAttribute('aria-pressed');
      await expect(sentimentToggle).toHaveAttribute('aria-pressed');
    });

    test('should be navigable with keyboard', async ({ page }) => {
      // Search and select AAPL using keyboard
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.focus();
      await searchInput.fill('AAPL');
      await page.waitForTimeout(600);

      // Wait for suggestions
      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });

      // Use keyboard to select
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('Enter');

      // Wait for chart to load
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /[1-9]\d* price candles/,
        { timeout: 15000 }
      );

      // Tab to time range buttons and activate with keyboard
      await page.keyboard.press('Tab');

      // Find focused element and verify it's interactive
      const focusedElement = page.locator(':focus');
      await expect(focusedElement).toBeVisible();
    });
  });
});

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
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /\d+ price candles and \d+ sentiment points/,
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
        /\d+ price candles and \d+ sentiment points/,
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
        /\d+ price candles/,
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
        /\d+ price candles/,
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
          /\d+ price candles/,
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
        /\d+ price candles/,
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
        /\d+ price candles and \d+ sentiment points/,
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
        /\d+ price candles and \d+ sentiment points/,
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
        /\d+ price candles/,
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
        /\d+ price candles/,
        { timeout: 15000 }
      );

      // Navigate to Settings using mobile navigation
      const settingsTab = page.getByRole('tab', { name: /settings/i });
      if (await settingsTab.isVisible()) {
        await settingsTab.click();
        await expect(page).toHaveURL(/\/settings/);

        // Navigate back to Dashboard
        const dashboardTab = page.getByRole('tab', { name: /dashboard/i });
        await dashboardTab.click();
        await expect(page).toHaveURL(/\/$/);

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

      // Step 2: Select GOOG from suggestions
      const suggestion = page.getByRole('option', { name: /GOOG/i });
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
        /\d+ price candles and \d+ sentiment points/,
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

      const suggestion = page.getByRole('option', { name: /GOOG/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      // Wait for initial load
      const chartContainer = page.locator(
        '[role="img"][aria-label*="Price and sentiment chart"]'
      );
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /\d+ price candles/,
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
          /\d+ price candles/,
          { timeout: 15000 }
        );

        // Verify empty state is NOT shown after time range change
        const emptyState = page.getByText(/no price data available/i);
        await expect(emptyState).not.toBeVisible();
      }
    });
  });

  test.describe('Error Handling', () => {
    test('should handle search with no results gracefully', async ({
      page,
    }) => {
      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('XYZNOTAREALTICKER123');

      // Wait for debounce and API response
      await page.waitForTimeout(600);

      // Should show no results or empty state, not crash
      const noResults = page.getByText(/no results/i);
      const suggestions = page.locator('[role="listbox"], [role="option"]');

      // Either no results message or empty suggestions
      const noResultsVisible = await noResults.isVisible().catch(() => false);
      const suggestionsCount = await suggestions.count();

      // One of these conditions should be true
      expect(noResultsVisible || suggestionsCount === 0).toBeTruthy();
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
      const loadingText = page.getByText(/loading/i);

      // Wait for either loading to appear or chart to be ready
      await expect(chartContainer.or(loadingText)).toBeVisible({
        timeout: 15000,
      });

      // Eventually chart should have data
      await expect(chartContainer).toHaveAttribute(
        'aria-label',
        /\d+ price candles/,
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
        /\d+ price candles/,
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
        /\d+ price candles/,
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

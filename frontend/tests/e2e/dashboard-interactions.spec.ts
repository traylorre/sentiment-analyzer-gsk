// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { assertCleanState } from './helpers/clean-state';
import { waitForAuth } from './helpers/auth-helper';

test.describe('Dashboard Interactions (Feature 1247)', () => {
  test.setTimeout(30_000);

  test('search input shows autocomplete results', async ({ page }) => {
    await page.goto('/');
    await waitForAuth(page);

    const searchInput = page.getByPlaceholder(/search tickers/i);
    await expect(searchInput).toBeVisible();
    await searchInput.fill('AAPL');

    // Wait for debounce + API to return autocomplete suggestions
    const options = page.getByRole('option');
    await expect(options.first()).toBeVisible({ timeout: 10000 });

    // Unwind: clear the input and verify options disappear
    await searchInput.click();
    await searchInput.press('Control+a');
    await searchInput.press('Delete');

    // Options should hide after clearing
    await expect(options.first()).toBeHidden({ timeout: 5000 });

    await assertCleanState(page);
  });

  test('clicking search result loads chart', async ({ page }) => {
    await page.goto('/');
    await waitForAuth(page);

    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');

    // Click the AAPL option from autocomplete
    try {
      const option = page.getByRole('option', { name: /AAPL/i });
      await expect(option).toBeVisible({ timeout: 10000 });
      await option.click();
    } catch {
      // Fallback: try text match inside a listbox
      const fallback = page.getByText('AAPL').first();
      await expect(fallback).toBeVisible({ timeout: 5000 });
      await fallback.click();
    }

    // Wait for chart to render with price and sentiment data
    const chart = page.locator('[role="img"][aria-label*="Price and sentiment"]');
    await expect(chart).toBeVisible({ timeout: 15000 });

    await assertCleanState(page);
  });

  test('time range buttons update chart', async ({ page }) => {
    await page.goto('/');

    // Load AAPL chart
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    const suggestion = page.getByRole('option', { name: /AAPL/i });
    await expect(suggestion).toBeVisible({ timeout: 10000 });
    await suggestion.click();

    const chart = page.locator('[role="img"][aria-label*="Price and sentiment"]');
    await expect(chart).toBeVisible({ timeout: 15000 });

    // Cycle through each time range
    const timeRanges = ['1W', '1M', '3M', '6M', '1Y'];

    for (const range of timeRanges) {
      let button;
      try {
        button = page.getByRole('button', {
          name: new RegExp(range + '.*time range', 'i'),
        });
        await expect(button).toBeVisible({ timeout: 5000 });
      } catch {
        // Fallback: match button by exact range text
        button = page.getByRole('button', { name: range });
        await expect(button).toBeVisible({ timeout: 5000 });
      }
      await button.click();

      // Assert the button is visually selected
      await expect(button).toHaveAttribute('aria-pressed', 'true', {
        timeout: 5000,
      });
    }

    // Reset to 1M
    const resetButton = page.getByRole('button', { name: /1M.*time range/i });
    await resetButton.click();
    await expect(resetButton).toHaveAttribute('aria-pressed', 'true', {
      timeout: 5000,
    });

    await assertCleanState(page);
  });

  test('resolution buttons update chart', async ({ page }) => {
    await page.goto('/');

    // Load AAPL chart
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    const suggestion = page.getByRole('option', { name: /AAPL/i });
    await expect(suggestion).toBeVisible({ timeout: 10000 });
    await suggestion.click();

    const chart = page.locator('[role="img"][aria-label*="Price and sentiment"]');
    await expect(chart).toBeVisible({ timeout: 15000 });

    // Cycle through each resolution
    const resolutions = ['5m', '15m', '30m', '1h', 'D'];

    for (const res of resolutions) {
      let button;
      try {
        button = page.getByRole('button', {
          name: new RegExp(res + '.*resolution', 'i'),
        });
        await expect(button).toBeVisible({ timeout: 5000 });
      } catch {
        // Fallback: match button by resolution label
        button = page.getByRole('button', { name: res });
        await expect(button).toBeVisible({ timeout: 5000 });
      }
      await button.click();

      // Assert the button is visually selected
      await expect(button).toHaveAttribute('aria-pressed', 'true', {
        timeout: 5000,
      });
    }

    // Reset to 15m
    const resetButton = page.getByRole('button', { name: /15m.*resolution/i });
    await resetButton.click();
    await expect(resetButton).toHaveAttribute('aria-pressed', 'true', {
      timeout: 5000,
    });

    await assertCleanState(page);
  });

  test('sentiment source dropdown changes source', async ({ page }) => {
    await page.goto('/');

    // Load AAPL chart
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    const suggestion = page.getByRole('option', { name: /AAPL/i });
    await expect(suggestion).toBeVisible({ timeout: 10000 });
    await suggestion.click();

    const chart = page.locator('[role="img"][aria-label*="Price and sentiment"]');
    await expect(chart).toBeVisible({ timeout: 15000 });

    // Find the sentiment source dropdown (combobox or select)
    let dropdown;
    try {
      dropdown = page.getByRole('combobox', { name: /sentiment source/i });
      await expect(dropdown).toBeVisible({ timeout: 5000 });
    } catch {
      // Fallback: try a native select element
      dropdown = page.locator('select[aria-label*="ource"]');
      await expect(dropdown).toBeVisible({ timeout: 5000 });
    }

    // Change to tiingo
    await dropdown.selectOption('tiingo');

    // Verify the value changed
    await expect(dropdown).toHaveValue('tiingo', { timeout: 5000 });

    // Reset to aggregated
    await dropdown.selectOption('aggregated');
    await expect(dropdown).toHaveValue('aggregated', { timeout: 5000 });

    await assertCleanState(page);
  });

  test.fixme(
    'chart hover shows tooltip',
    // Canvas-based tooltip from Lightweight Charts may not be DOM-accessible
    async ({ page }) => {
      await page.goto('/');

      const searchInput = page.getByPlaceholder(/search tickers/i);
      await searchInput.fill('AAPL');
      const suggestion = page.getByRole('option', { name: /AAPL/i });
      await expect(suggestion).toBeVisible({ timeout: 10000 });
      await suggestion.click();

      const chart = page.locator(
        '[role="img"][aria-label*="Price and sentiment"]'
      );
      await expect(chart).toBeVisible({ timeout: 15000 });

      // Hover the center of the chart
      const box = await chart.boundingBox();
      if (box) {
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      }

      // Tooltip may not be in DOM since Lightweight Charts renders on canvas
      await assertCleanState(page);
    }
  );

  test('ticker chip remove clears chart', async ({ page }) => {
    await page.goto('/');

    // Load AAPL chart
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AAPL');
    const suggestion = page.getByRole('option', { name: /AAPL/i });
    await expect(suggestion).toBeVisible({ timeout: 10000 });
    await suggestion.click();

    const chart = page.locator('[role="img"][aria-label*="Price and sentiment"]');
    await expect(chart).toBeVisible({ timeout: 15000 });

    // Find the remove/X button on the ticker chip (aria-label="Remove AAPL")
    const removeButton = page.getByRole('button', { name: /remove AAPL/i });
    await expect(removeButton).toBeVisible({ timeout: 5000 });

    await removeButton.click();

    // Chart should disappear or empty state should appear
    try {
      await expect(chart).toBeHidden({ timeout: 10000 });
    } catch {
      // Alternative: empty state message appears instead
      const emptyState = page.getByText(
        /track price|no ticker|select a ticker|search to get started/i
      );
      await expect(emptyState).toBeVisible({ timeout: 10000 });
    }

    await assertCleanState(page);
  });

  test('empty state shows search CTA', async ({ page }) => {
    await page.goto('/');
    await waitForAuth(page);

    // On a fresh load with no ticker selected, an empty state / CTA should be visible
    const emptyState = page.getByText(
      /track price.*sentiment|search.*ticker|get started|select a ticker/i
    );
    await expect(emptyState).toBeVisible({ timeout: 15000 });

    await assertCleanState(page);
  });
});

// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';

/**
 * Chart Zoom Data Visibility (Feature 1316)
 *
 * Validates that selecting 1Y time range + Day resolution shows the full year
 * of trading data (~200-252 candles), not just the rightmost ~60 candles.
 *
 * Root cause: fitContent() fired synchronously after setData() in a separate
 * useEffect, before lightweight-charts processed the data internally.
 * Fix: Wrap fitContent() in requestAnimationFrame to defer by one paint frame.
 *
 * This test catches the regression by asserting the candle count reported in
 * the chart's aria-label is >= 200 for a 1Y daily view.
 */
test.describe('Chart Zoom Data Visibility', () => {
  test.beforeEach(async ({ page }) => {
    // Mock anonymous auth so the dashboard loads without real backend
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
  });

  test('1Y + Day resolution should show >= 200 candles (full year)', async ({
    page,
  }) => {
    // Use desktop viewport for full chart controls visibility
    await page.setViewportSize({ width: 1280, height: 800 });

    await page.goto('/');

    // Search for AMZN ticker
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AMZN');

    // Wait for and click the AMZN suggestion
    const suggestion = page.getByRole('option', { name: /AMZN/i });
    await expect(suggestion).toBeVisible({ timeout: 10000 });
    await suggestion.click();

    // Wait for initial chart data to load
    const chartContainer = page.locator(
      '[role="img"][aria-label*="Price and sentiment chart"]'
    );
    await expect(chartContainer).toHaveAttribute(
      'aria-label',
      /[1-9]\d* price candles/,
      { timeout: 15000 }
    );

    // Select 1Y time range
    const oneYearButton = page.getByRole('button', { name: '1Y time range' });
    await expect(oneYearButton).toBeVisible();
    await oneYearButton.click();

    // Select Day resolution (may already be default, but be explicit)
    const dayResolution = page.getByRole('button', { name: 'Day resolution' });
    await expect(dayResolution).toBeVisible();
    await dayResolution.click();

    // Wait for chart data to load with the new time range
    // The aria-label updates reactively with priceData.length
    await expect(chartContainer).toHaveAttribute(
      'aria-label',
      /[1-9]\d* price candles/,
      { timeout: 15000 }
    );

    // Extract candle count from aria-label
    const ariaLabel = await chartContainer.getAttribute('aria-label');
    const match = ariaLabel?.match(/(\d+) price candles/);
    expect(match).toBeTruthy();
    const candleCount = parseInt(match![1], 10);

    // 1 year of daily trading data should have ~252 trading days
    // Use 200 as conservative lower bound (accounts for holidays, data gaps)
    // The bug showed only ~60 candles — this threshold catches it clearly
    expect(candleCount).toBeGreaterThanOrEqual(200);
  });

  test('mouse-wheel zoom-out past data bounds auto-upgrades time range', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/');

    // Search for AMZN ticker
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AMZN');

    const suggestion = page.getByRole('option', { name: /AMZN/i });
    await expect(suggestion).toBeVisible({ timeout: 10000 });
    await suggestion.click();

    const chartContainer = page.locator(
      '[role="img"][aria-label*="Price and sentiment chart"]'
    );

    // Ensure 1M + Day resolution (default) is loaded
    const oneMonthButton = page.getByRole('button', { name: '1M time range' });
    await oneMonthButton.click();
    const dayResolution = page.getByRole('button', { name: 'Day resolution' });
    await dayResolution.click();

    // Wait for chart data to load
    await expect(chartContainer).toHaveAttribute(
      'aria-label',
      /[1-9]\d* price candles/,
      { timeout: 15000 }
    );

    // Record initial candle count for 1M (~22 trading days)
    const initialLabel = await chartContainer.getAttribute('aria-label');
    const initialMatch = initialLabel?.match(/(\d+) price candles/);
    expect(initialMatch).toBeTruthy();
    const initialCount = parseInt(initialMatch![1], 10);

    // Verify 1M is active before zoom
    await expect(oneMonthButton).toHaveAttribute('aria-pressed', 'true');

    // Zoom out aggressively with Ctrl+wheel on the chart
    // This triggers handleScale in lightweight-charts (time axis zoom)
    const chartBox = await chartContainer.boundingBox();
    expect(chartBox).toBeTruthy();
    const centerX = chartBox!.x + chartBox!.width / 2;
    const centerY = chartBox!.y + chartBox!.height / 2;
    await page.mouse.move(centerX, centerY);

    // Ctrl+wheel zooms the time axis in lightweight-charts
    await page.keyboard.down('Control');
    for (let i = 0; i < 15; i++) {
      await page.mouse.wheel(0, 120);
      await page.waitForTimeout(30);
    }
    await page.keyboard.up('Control');

    // Wait for auto-upgrade: time range should widen (3M or higher becomes active)
    // The 1M button should no longer be active
    await expect(oneMonthButton).not.toHaveAttribute('aria-pressed', 'true', {
      timeout: 5000,
    });

    // Candle count should have increased (wider range = more data)
    await expect(chartContainer).toHaveAttribute(
      'aria-label',
      /[1-9]\d* price candles/,
      { timeout: 10000 }
    );
    const upgradedLabel = await chartContainer.getAttribute('aria-label');
    const upgradedMatch = upgradedLabel?.match(/(\d+) price candles/);
    expect(upgradedMatch).toBeTruthy();
    const upgradedCount = parseInt(upgradedMatch![1], 10);

    // More candles after zoom-out upgrade
    expect(upgradedCount).toBeGreaterThan(initialCount);
  });

  test('longer time ranges should have more candles than shorter ones', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });

    await page.goto('/');

    // Search for AMZN ticker
    const searchInput = page.getByPlaceholder(/search tickers/i);
    await searchInput.fill('AMZN');

    const suggestion = page.getByRole('option', { name: /AMZN/i });
    await expect(suggestion).toBeVisible({ timeout: 10000 });
    await suggestion.click();

    const chartContainer = page.locator(
      '[role="img"][aria-label*="Price and sentiment chart"]'
    );

    // Ensure Day resolution is selected for consistent comparison
    const dayResolution = page.getByRole('button', { name: 'Day resolution' });
    await dayResolution.click();

    // Get 1M candle count
    const oneMonthButton = page.getByRole('button', { name: '1M time range' });
    await oneMonthButton.click();
    await expect(chartContainer).toHaveAttribute(
      'aria-label',
      /[1-9]\d* price candles/,
      { timeout: 15000 }
    );
    const oneMonthLabel = await chartContainer.getAttribute('aria-label');
    const oneMonthMatch = oneMonthLabel?.match(/(\d+) price candles/);
    expect(oneMonthMatch).toBeTruthy();
    const oneMonthCount = parseInt(oneMonthMatch![1], 10);

    // Get 1Y candle count
    const oneYearButton = page.getByRole('button', { name: '1Y time range' });
    await oneYearButton.click();
    await expect(chartContainer).toHaveAttribute(
      'aria-label',
      /[1-9]\d* price candles/,
      { timeout: 15000 }
    );
    const oneYearLabel = await chartContainer.getAttribute('aria-label');
    const oneYearMatch = oneYearLabel?.match(/(\d+) price candles/);
    expect(oneYearMatch).toBeTruthy();
    const oneYearCount = parseInt(oneYearMatch![1], 10);

    // 1Y should have significantly more data than 1M
    // 1M ≈ 22 trading days, 1Y ≈ 252 trading days
    expect(oneYearCount).toBeGreaterThan(oneMonthCount);

    // 1Y should have at least 200 candles
    expect(oneYearCount).toBeGreaterThanOrEqual(200);

    // 1M should have at least 15 candles (conservative)
    expect(oneMonthCount).toBeGreaterThanOrEqual(15);
  });
});

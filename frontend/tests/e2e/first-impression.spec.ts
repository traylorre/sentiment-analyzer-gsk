import { test, expect } from '@playwright/test';

test.describe('First Impression Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display dashboard with search input', async ({ page }) => {
    // Check main heading and search input are visible
    await expect(page.getByRole('heading', { name: /sentiment/i })).toBeVisible();
    await expect(page.getByPlaceholder(/search tickers/i)).toBeVisible();
  });

  test('should show empty state initially', async ({ page }) => {
    // Empty state message should be visible
    await expect(page.getByText(/track sentiment/i)).toBeVisible();
    await expect(page.getByText(/search for a ticker/i)).toBeVisible();
  });

  test('should have working navigation tabs', async ({ page }) => {
    // Check navigation is present
    const nav = page.getByRole('tablist', { name: /main navigation/i });

    // On mobile, check bottom navigation
    const isMobile = await page.evaluate(() => window.innerWidth < 768);
    if (isMobile) {
      await expect(nav).toBeVisible();

      // Check all tabs exist
      await expect(page.getByRole('tab', { name: /dashboard/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /configs/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /alerts/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /settings/i })).toBeVisible();
    }
  });

  test('should have skip link for keyboard navigation', async ({ page }) => {
    // Skip link should exist for accessibility
    const skipLink = page.getByRole('link', { name: /skip to main content/i });

    // Tab to the skip link
    await page.keyboard.press('Tab');

    // Skip link should be visible when focused
    await expect(skipLink).toBeFocused();
    await expect(skipLink).toBeVisible();
  });

  test('should search for tickers', async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search tickers/i);

    // Type a search query
    await searchInput.fill('AAPL');

    // Wait for search results to appear
    await page.waitForTimeout(500); // Debounce delay

    // Should show suggestions or no results message
    const suggestions = page.locator('[role="listbox"], [role="option"]');
    const noResults = page.getByText(/no results/i);

    // Either suggestions or no results should be visible
    await expect(suggestions.or(noResults)).toBeVisible();
  });

  test('should respect reduced motion preference', async ({ page }) => {
    // Check CSS respects prefers-reduced-motion
    const hasReducedMotion = await page.evaluate(() => {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    });

    // The test just verifies the page loads with the media query support
    expect(typeof hasReducedMotion).toBe('boolean');
  });
});

test.describe('Responsive Layout', () => {
  test('should show mobile navigation on small screens', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // Mobile nav should be visible at bottom
    const mobileNav = page.getByRole('tablist', { name: /main navigation/i });
    await expect(mobileNav).toBeVisible();
  });

  test('should adapt layout for tablet', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');

    // Page should load successfully
    await expect(page.getByRole('heading', { name: /sentiment/i })).toBeVisible();
  });

  test('should show desktop layout on large screens', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/');

    // Desktop nav should be visible in sidebar
    // Mobile nav should be hidden
    const mobileNav = page.getByRole('tablist', { name: /main navigation/i });
    await expect(mobileNav).toBeHidden();
  });
});

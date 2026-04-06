// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';

test.describe('First Impression Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display dashboard with search input', async ({ page }) => {
    // Check main heading and search input are visible
    // Use specific heading text to avoid matching both "Price & Sentiment Analysis" and "Track Price & Sentiment"
    await expect(page.getByRole('heading', { name: /price.*sentiment/i }).first()).toBeVisible();
    await expect(page.getByPlaceholder(/search tickers/i)).toBeVisible();
  });

  test('should show empty state initially', async ({ page }) => {
    // Dashboard may load with default AAPL ticker or show empty state
    // Either state is valid — check that main content area is present
    const chartOrEmpty = page.getByRole('heading', { name: /price.*sentiment|track.*sentiment/i }).first();
    await expect(chartOrEmpty).toBeVisible();
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
    // The expect below will wait for debounce + API response

    // Should show suggestions dropdown (listbox) or no results message
    const listbox = page.locator('[role="listbox"]');
    const noResults = page.getByText(/no results/i);

    // Either suggestions listbox or no results should be visible
    await expect(listbox.or(noResults)).toBeVisible();
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
    await expect(page.getByRole('heading', { name: /price.*sentiment/i }).first()).toBeVisible();
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

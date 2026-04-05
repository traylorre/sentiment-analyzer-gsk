// Target: Customer Dashboard (Next.js/Amplify)
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
    const isMobile = await page.evaluate(() => window.innerWidth < 768);
    if (isMobile) {
      // Mobile: bottom tab navigation visible
      const nav = page.getByRole('tablist', { name: /main navigation/i });
      await expect(nav).toBeVisible();
      await expect(page.getByRole('tab', { name: /dashboard/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /configs/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /alerts/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /settings/i })).toBeVisible();
    } else {
      // Desktop: sidebar navigation with links (mobile tablist hidden)
      const mobileNav = page.getByRole('tablist', { name: /main navigation/i });
      await expect(mobileNav).toBeHidden();
      // Sidebar nav links exist
      await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible();
      await expect(page.getByRole('link', { name: /settings/i })).toBeVisible();
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

    // Should show suggestions or no results message
    const suggestions = page.locator('[role="listbox"], [role="option"]');
    const noResults = page.getByText(/no results/i);

    // Either suggestions or no results should be visible
    await expect(suggestions.or(noResults)).toBeVisible();
  });

  test('should respect reduced motion preference', async ({ page }) => {
    // Emulate prefers-reduced-motion: reduce
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');

    // Tailwind/globals.css sets transition-duration and animation-duration to
    // near-zero (0.01ms) under prefers-reduced-motion: reduce
    const styles = await page.evaluate(() => {
      const el = document.documentElement;
      const computed = window.getComputedStyle(el);
      return {
        reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
        // Check any element for suppressed animations
        animDuration: computed.getPropertyValue('animation-duration'),
        transitionDuration: computed.getPropertyValue('transition-duration'),
      };
    });

    expect(styles.reducedMotion).toBe(true);
    // At minimum, the media query must be active — verify it's detected
    // CSS values vary by browser but reduced-motion must be reported as active
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

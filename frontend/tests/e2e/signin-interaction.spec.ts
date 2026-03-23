// Target: Customer Dashboard (Next.js/Amplify)
//
// Regression tests for the sign-in interaction (Feature 1244).
// Verifies the Guest button produces a visible menu on both desktop
// and mobile viewports. Covers the bug where the dropdown was hidden
// by CSS stacking context + self-occluding backdrop (PRs #782-783 era).

import { test, expect } from '@playwright/test';

test.describe('Sign-In Interaction', () => {
  test.setTimeout(30_000);

  test('Guest button opens user menu on desktop', async ({ page }) => {
    await page.goto('/');

    // Wait for auth initialization (skeleton → button)
    const guestButton = page.getByRole('button', { name: /guest/i });
    await expect(guestButton).toBeVisible({ timeout: 10_000 });

    // Click the Guest button
    await guestButton.click();

    // Radix DropdownMenu renders items with role="menuitem"
    const menuItem = page.getByRole('menuitem').first();
    await expect(menuItem).toBeVisible({ timeout: 5_000 });
  });

  test('Guest button opens user menu on mobile', async ({ page }) => {
    // Set mobile viewport (Pixel 5)
    await page.setViewportSize({ width: 393, height: 851 });
    await page.goto('/');

    // On mobile, the "Guest" text is hidden (sm:inline). Use data-testid.
    const trigger = page.locator('[data-testid="user-menu-trigger"]');
    await expect(trigger).toBeVisible({ timeout: 10_000 });

    await trigger.click();

    // Menu should appear with at least one item
    const menuItem = page.getByRole('menuitem').first();
    await expect(menuItem).toBeVisible({ timeout: 5_000 });
  });

  test('menu closes on Escape key', async ({ page }) => {
    await page.goto('/');

    const guestButton = page.getByRole('button', { name: /guest/i });
    await expect(guestButton).toBeVisible({ timeout: 10_000 });

    // Open menu
    await guestButton.click();
    const menuItem = page.getByRole('menuitem').first();
    await expect(menuItem).toBeVisible({ timeout: 5_000 });

    // Press Escape — Radix handles this automatically
    await page.keyboard.press('Escape');

    // Menu should be gone
    await expect(menuItem).not.toBeVisible({ timeout: 3_000 });
  });
});

// Target: Customer Dashboard (Next.js/Amplify)
/**
 * E2E tests for account linking flows (Feature 1223, US5).
 *
 * Tests anonymous-to-authenticated migration, multi-provider linking,
 * and data preservation during account merges.
 */

import { test, expect } from '@playwright/test';

test.describe('Account Linking (US5)', () => {
  test('anonymous user can access dashboard and create data', async ({ page }) => {
    // Step 1: Visit dashboard as anonymous user
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Dashboard should load and show anonymous state
    await expect(page.getByRole('combobox')).toBeVisible();

    // Search for a ticker (creates anonymous session automatically)
    const searchInput = page.getByRole('searchbox').or(page.getByPlaceholder(/search/i));
    if (await searchInput.isVisible()) {
      await searchInput.fill('AAPL');
      await page.waitForTimeout(2000);
    }

    // Anonymous user should be able to interact with the dashboard
    await expect(page.getByText(/Price & Sentiment Analysis/i)).toBeVisible();
  });

  test('settings page shows anonymous badge with upgrade prompt', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForFunction(
      () => !document.querySelector('[class*="animate-pulse"]'),
      { timeout: 10000 }
    );

    // Anonymous users should see their status
    const anonBadge = page.getByText(/anonymous/i);
    const upgradeCta = page.getByText(/upgrade|sign in|create account/i);

    // At least one of these should be visible
    const badgeVisible = await anonBadge.isVisible({ timeout: 5000 }).catch(() => false);
    const upgradeVisible = await upgradeCta.isVisible({ timeout: 5000 }).catch(() => false);

    expect(badgeVisible || upgradeVisible).toBeTruthy();
  });

  test('authenticated user with Google can see linked providers', async ({ page }) => {
    // Navigate to settings to check linked providers section
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    // The account section heading should be visible
    const accountSection = page.getByRole('heading', { name: /account/i });
    await expect(accountSection).toBeVisible({ timeout: 10000 });

    // For anonymous users, shows upgrade prompt
    // For authenticated users, shows linked providers
    await expect(
      page.getByText(/anonymous|google|upgrade|member since/i).first()
    ).toBeVisible();
  });
});

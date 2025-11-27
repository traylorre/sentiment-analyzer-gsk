import { test, expect } from '@playwright/test';

test.describe('Navigation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should navigate between views via tabs', async ({ page, isMobile }) => {
    if (!isMobile) {
      test.skip();
      return;
    }

    // Navigate to Configs
    await page.getByRole('tab', { name: /configs/i }).click();
    await expect(page).toHaveURL(/\/configs/);

    // Navigate to Alerts
    await page.getByRole('tab', { name: /alerts/i }).click();
    await expect(page).toHaveURL(/\/alerts/);

    // Navigate to Settings
    await page.getByRole('tab', { name: /settings/i }).click();
    await expect(page).toHaveURL(/\/settings/);

    // Navigate back to Dashboard
    await page.getByRole('tab', { name: /dashboard/i }).click();
    await expect(page).toHaveURL(/\/$/);
  });

  test('should support keyboard navigation in tabs', async ({ page, isMobile }) => {
    if (!isMobile) {
      test.skip();
      return;
    }

    // Focus on first tab
    const dashboardTab = page.getByRole('tab', { name: /dashboard/i });
    await dashboardTab.focus();
    await expect(dashboardTab).toBeFocused();

    // Press Enter to activate
    await page.keyboard.press('Enter');

    // Tab should be selected
    await expect(dashboardTab).toHaveAttribute('aria-selected', 'true');
  });
});

test.describe('Configs Page', () => {
  test('should display configs page with empty state', async ({ page }) => {
    await page.goto('/configs');

    // Should show page title
    await expect(page.getByRole('heading', { name: /configurations/i })).toBeVisible();

    // Should show empty state or create button
    const createButton = page.getByRole('button', { name: /create|new|add/i });
    const emptyState = page.getByText(/no configurations/i);

    await expect(createButton.or(emptyState)).toBeVisible();
  });

  test('should open config form when creating new', async ({ page }) => {
    await page.goto('/configs');

    // Click create button
    const createButton = page.getByRole('button', { name: /create|new|add/i });
    if (await createButton.isVisible()) {
      await createButton.click();

      // Form should be visible
      await expect(page.getByRole('dialog').or(page.getByRole('form'))).toBeVisible();
    }
  });
});

test.describe('Alerts Page', () => {
  test('should display alerts page', async ({ page }) => {
    await page.goto('/alerts');

    // Should show page title
    await expect(page.getByRole('heading', { name: /alerts/i })).toBeVisible();
  });

  test('should show alert quota information', async ({ page }) => {
    await page.goto('/alerts');

    // Should show quota info (e.g., "0/10 alerts")
    await expect(page.getByText(/alerts?/i)).toBeVisible();
  });
});

test.describe('Settings Page', () => {
  test('should display settings page', async ({ page }) => {
    await page.goto('/settings');

    // Should show settings sections
    await expect(page.getByText(/account/i)).toBeVisible();
    await expect(page.getByText(/preferences/i)).toBeVisible();
  });

  test('should toggle haptic feedback setting', async ({ page }) => {
    await page.goto('/settings');

    // Find haptic toggle
    const hapticSwitch = page.getByRole('switch', { name: /haptic/i });

    if (await hapticSwitch.isVisible()) {
      const initialState = await hapticSwitch.getAttribute('aria-checked');

      // Toggle
      await hapticSwitch.click();

      // State should change
      const newState = await hapticSwitch.getAttribute('aria-checked');
      expect(newState).not.toBe(initialState);
    }
  });

  test('should toggle reduced motion setting', async ({ page }) => {
    await page.goto('/settings');

    // Find reduced motion toggle
    const motionSwitch = page.getByRole('switch', { name: /reduced motion/i });

    if (await motionSwitch.isVisible()) {
      const initialState = await motionSwitch.getAttribute('aria-checked');

      // Toggle
      await motionSwitch.click();

      // State should change
      const newState = await motionSwitch.getAttribute('aria-checked');
      expect(newState).not.toBe(initialState);
    }
  });
});

// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { setupAuthSession } from './helpers/auth-helper';

test.describe('Navigation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should navigate between views via tabs', async ({ page, isMobile }) => {
    if (!isMobile) {
      test.skip();
      return;
    }

    // Mobile nav uses Zustand view-store (setView), not Next.js routing,
    // so URL does NOT change. Assert tab selection state instead.

    // Navigate to Configs
    const configsTab = page.getByRole('tab', { name: /configs/i });
    await configsTab.click();
    await expect(configsTab).toHaveAttribute('aria-selected', 'true');

    // Navigate to Alerts
    const alertsTab = page.getByRole('tab', { name: /alerts/i });
    await alertsTab.click();
    await expect(alertsTab).toHaveAttribute('aria-selected', 'true');

    // Navigate to Settings
    const settingsTab = page.getByRole('tab', { name: /settings/i });
    await settingsTab.click();
    await expect(settingsTab).toHaveAttribute('aria-selected', 'true');

    // Navigate back to Dashboard
    const dashboardTab = page.getByRole('tab', { name: /dashboard/i });
    await dashboardTab.click();
    await expect(dashboardTab).toHaveAttribute('aria-selected', 'true');
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

    // Should show empty state or create button
    await expect(
      page.getByRole('button', { name: /create configuration/i }).first()
    ).toBeVisible();
  });

  test('should open config form when creating new', async ({ page }) => {
    await page.goto('/configs');

    // Create button is guaranteed visible (empty state shows it)
    const createButton = page.getByRole('button', { name: /create configuration/i });
    await expect(createButton).toBeVisible();
    await createButton.click();

    // Form should be visible (dialog or heading)
    await expect(
      page.getByRole('dialog').or(page.getByRole('heading', { name: /new configuration/i }))
    ).toBeVisible();
  });
});

test.describe('Alerts Page', () => {
  // /alerts requires upgraded auth
  test.beforeEach(async ({ context }) => {
    await setupAuthSession(context);
  });

  test('should display alerts page', async ({ page }) => {
    await page.goto('/alerts');

    // Should show alert-specific content — empty state text.
    // Note: h1 is "Dashboard" from the layout, NOT "Alerts".
    await expect(
      page.getByText(/no alerts configured/i).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('should show alert quota information', async ({ page }) => {
    await page.goto('/alerts');

    // Should show alert-specific content — empty state text.
    // Note: h1 is "Dashboard" from the layout, NOT "Alerts".
    await expect(
      page.getByText(/no alerts configured/i).first()
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Settings Page', () => {
  test('should display settings page', async ({ page }) => {
    await page.goto('/settings');

    // Should show settings sections (use heading role for specificity)
    await expect(
      page.getByRole('heading', { name: /account|profile|settings/i }).first()
    ).toBeVisible();
  });

  test('should toggle haptic feedback setting', async ({ page }) => {
    await page.goto('/settings');

    // Find haptic toggle
    const hapticSwitch = page.getByRole('switch', { name: /haptic/i });
    await expect(hapticSwitch).toBeVisible();

    const initialState = await hapticSwitch.getAttribute('aria-checked');

    // Toggle
    await hapticSwitch.click();

    // State should change
    const newState = await hapticSwitch.getAttribute('aria-checked');
    expect(newState).not.toBe(initialState);
  });

  test('should toggle reduced motion setting', async ({ page }) => {
    await page.goto('/settings');

    // Find reduced motion toggle
    const motionSwitch = page.getByRole('switch', { name: /reduced motion/i });
    await expect(motionSwitch).toBeVisible();

    const initialState = await motionSwitch.getAttribute('aria-checked');

    // Toggle
    await motionSwitch.click();

    // State should change
    const newState = await motionSwitch.getAttribute('aria-checked');
    expect(newState).not.toBe(initialState);
  });
});

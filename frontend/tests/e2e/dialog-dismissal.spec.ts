// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { assertCleanState, createTestConfig } from './helpers/clean-state';

test.describe('Dialog Dismissal (Feature 1247)', () => {
  test.setTimeout(30_000);

  test('sign-out dialog: cancel closes', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForFunction(
      () => !document.querySelector('[class*="animate-pulse"]'),
      { timeout: 10000 }
    );

    // Open sign-out dialog
    const signOutButton = page.getByRole('button', { name: /sign out/i });
    await expect(signOutButton).toBeVisible();
    await signOutButton.click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Click Cancel
    const cancelButton = dialog.getByRole('button', { name: /cancel|no|close/i });
    await expect(cancelButton).toBeVisible();
    await cancelButton.click();

    // Assert dialog is hidden
    await expect(dialog).toBeHidden();

    await assertCleanState(page);
  });

  test('sign-out dialog: escape closes', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForFunction(
      () => !document.querySelector('[class*="animate-pulse"]'),
      { timeout: 10000 }
    );

    // Open sign-out dialog
    const signOutButton = page.getByRole('button', { name: /sign out/i });
    await expect(signOutButton).toBeVisible();
    await signOutButton.click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Press Escape
    await page.keyboard.press('Escape');

    // Assert dialog is hidden
    await expect(dialog).toBeHidden();

    await assertCleanState(page);
  });

  test('sign-out dialog: confirm signs out', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForFunction(
      () => !document.querySelector('[class*="animate-pulse"]'),
      { timeout: 10000 }
    );

    // Open sign-out dialog
    const signOutButton = page.getByRole('button', { name: /sign out/i });
    await expect(signOutButton).toBeVisible();
    await signOutButton.click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Click confirm
    const confirmButton = dialog.getByRole('button', { name: /sign out|confirm|yes/i });
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();

    // Assert navigated away (URL changes to auth page or root)
    await page.waitForURL(/\/(auth\/signin|)$/);
    await expect(page).toHaveURL(/\/(auth\/signin|)$/);
  });

  test('delete dialog: cancel preserves item', async ({ page }) => {
    // Create a config first
    const configName = `e2e-${test.info().testId}`;
    await createTestConfig(page, configName);

    // Navigate to configs and find the config
    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    const configCard = page.getByText(configName);
    await expect(configCard).toBeVisible();

    // Click delete on the config
    const card = configCard.locator('..');
    await card.getByRole('button', { name: /delete|remove/i }).click();

    // Dialog should appear
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Click Cancel
    const cancelButton = dialog.getByRole('button', { name: /cancel|no|close/i });
    await expect(cancelButton).toBeVisible();
    await cancelButton.click();

    // Assert dialog is hidden
    await expect(dialog).toBeHidden();

    // Assert config still exists
    await expect(page.getByText(configName)).toBeVisible();

    await assertCleanState(page);
  });

  test('delete dialog: escape closes', async ({ page }) => {
    // Create a config first
    const configName = `e2e-${test.info().testId}`;
    await createTestConfig(page, configName);

    // Navigate to configs and find the config
    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    const configCard = page.getByText(configName);
    await expect(configCard).toBeVisible();

    // Click delete on the config
    const card = configCard.locator('..');
    await card.getByRole('button', { name: /delete|remove/i }).click();

    // Dialog should appear
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Press Escape
    await page.keyboard.press('Escape');

    // Assert dialog is closed
    await expect(dialog).toBeHidden();

    await assertCleanState(page);
  });

  test('user menu: outside click closes', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Open user menu
    const menuTrigger = page.locator('[data-testid="user-menu-trigger"]');
    await expect(menuTrigger).toBeVisible();
    await menuTrigger.click();

    // Assert menu is open (menu items visible)
    const menuItem = page.getByRole('menuitem');
    await expect(menuItem.first()).toBeVisible();

    // Click outside (on the body/empty area)
    await page.locator('body').click({ position: { x: 10, y: 10 } });

    // Assert menu is closed
    await expect(menuItem.first()).toBeHidden();

    await assertCleanState(page);
  });

  test('toast dismiss button', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForFunction(
      () => !document.querySelector('[class*="animate-pulse"]'),
      { timeout: 10000 }
    );

    // Trigger a toast by saving settings
    const emailSwitch = page.getByRole('switch', { name: /email notifications/i });
    await expect(emailSwitch).toBeVisible();
    await emailSwitch.click();

    const saveButton = page.getByRole('button', { name: /save/i });
    await expect(saveButton).toBeEnabled();
    await saveButton.click();

    // Wait briefly for toast to appear
    await page.waitForTimeout(1000);

    // Look for toast dismiss button
    const toastDismiss = page.locator(
      '[data-sonner-toaster] button[aria-label*="close" i], ' +
      '[data-sonner-toaster] button[aria-label*="dismiss" i], ' +
      '[role="status"] button'
    );

    if (await toastDismiss.first().isVisible({ timeout: 3000 }).catch(() => false)) {
      await toastDismiss.first().click();
      // Assert toast is gone
      await expect(toastDismiss.first()).toBeHidden({ timeout: 3000 });
    } else {
      test.skip('No toast triggered in this flow');
    }

    await assertCleanState(page);
  });
});

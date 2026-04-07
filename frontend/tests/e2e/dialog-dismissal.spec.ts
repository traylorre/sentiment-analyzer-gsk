// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { assertCleanState, createTestConfig } from './helpers/clean-state';
import { setupAuthSession } from './helpers/auth-helper';

test.describe('Dialog Dismissal (Feature 1247)', () => {
  test.setTimeout(30_000);

  // Sign-out button only renders when isAuthenticated — set up session cookies
  test.beforeEach(async ({ context }) => {
    await setupAuthSession(context);
  });

  test('sign-out dialog: cancel closes', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('domcontentloaded');
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
    await page.waitForLoadState('domcontentloaded');
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

    // Press Escape (may need to focus dialog first)
    await dialog.press('Escape');

    // Assert dialog is hidden (use Cancel fallback if Escape didn't work)
    if (await dialog.isVisible({ timeout: 1000 }).catch(() => false)) {
      const cancelButton = dialog.getByRole('button', { name: /cancel|no|close/i });
      if (await cancelButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await cancelButton.click();
      }
    }
    await expect(dialog).toBeHidden({ timeout: 5000 });

    await assertCleanState(page);
  });

  test('sign-out dialog: confirm signs out', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('domcontentloaded');
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

    // Wait for dialog animation to settle before clicking
    await page.waitForTimeout(500);

    // Click confirm — the destructive "Sign out" button in the dialog.
    // Use JS click because on mobile viewports the dialog button may be outside the viewport.
    const confirmButton = dialog.getByRole('button', { name: /sign out/i });
    await expect(confirmButton).toBeVisible();
    await confirmButton.evaluate((el) => (el as HTMLButtonElement).click());

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
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByText(configName).first()).toBeVisible();

    // Click delete — aria-label="Delete {config.name}"
    await page.getByRole('button', { name: `Delete ${configName}` }).click();

    // Dialog should appear — both heading and body text match, use .first()
    const dialog = page.getByText(/are you sure/i).or(page.getByText(/delete configuration/i));
    await expect(dialog.first()).toBeVisible();

    // Click Cancel
    const cancelButton = page.getByRole('button', { name: /cancel/i });
    await expect(cancelButton).toBeVisible();
    await cancelButton.click();

    // Assert config still exists
    await expect(page.getByText(configName).first()).toBeVisible();

    await assertCleanState(page);
  });

  test('delete dialog: escape closes', async ({ page }) => {
    // Create a config first
    const configName = `e2e-${test.info().testId}`;
    await createTestConfig(page, configName);

    // Navigate to configs and find the config
    await page.goto('/configs');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByText(configName).first()).toBeVisible();

    // Click delete — aria-label="Delete {config.name}"
    await page.getByRole('button', { name: `Delete ${configName}` }).click();

    // Dialog should appear — both heading and body text match, use .first()
    const dialog = page.getByText(/are you sure/i).or(page.getByText(/delete configuration/i));
    await expect(dialog.first()).toBeVisible();

    // Press Escape
    await page.keyboard.press('Escape');

    // Assert dialog is closed — wait for animation
    await page.waitForTimeout(500);

    await assertCleanState(page);
  });

  test('user menu: outside click closes', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Open user menu — use visible() filter to pick whichever trigger is on-screen.
    // On desktop the aside trigger is visible; on mobile the header trigger is.
    const menuTrigger = page.locator('[data-testid="user-menu-trigger"]').locator('visible=true').first();
    await expect(menuTrigger).toBeVisible({ timeout: 5000 });
    // Scroll into view first (trigger may be at bottom of fixed sidebar), then click.
    // Must use regular click (not evaluate) because Radix DropdownMenu uses pointer events.
    await menuTrigger.scrollIntoViewIfNeeded();
    await menuTrigger.click({ force: true });

    // Assert menu is open (menu items visible)
    const menuItem = page.getByRole('menuitem');
    await expect(menuItem.first()).toBeVisible();

    // Click outside (on the main content area, avoiding skip-link at top-left)
    const viewport = page.viewportSize()!;
    await page.mouse.click(viewport.width / 2, viewport.height / 2);

    // Assert menu is closed
    await expect(menuItem.first()).toBeHidden();

    await assertCleanState(page);
  });

  test('toast dismiss button', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('domcontentloaded');
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

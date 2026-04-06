// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { assertCleanState } from './helpers/clean-state';

test.describe('Auth Menu Navigation (Feature 1247)', () => {
  test.setTimeout(30_000);

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('guest menu trigger opens menu', async ({ page }) => {
    // Scope to desktop sidebar (aside) to avoid matching hidden mobile header trigger
    const menuTrigger = page.locator('aside [data-testid="user-menu-trigger"]');
    await expect(menuTrigger).toBeVisible();

    // Click to open menu
    await menuTrigger.click();

    // Assert menu items are visible
    const menuItems = page.getByRole('menuitem');
    await expect(menuItems.first()).toBeVisible();

    // Unwind: press Escape to close
    await page.keyboard.press('Escape');
    await expect(menuItems.first()).toBeHidden();

    await assertCleanState(page);
  });

  test('menu Sign in with email navigates', async ({ page }) => {
    // Open menu
    const menuTrigger = page.locator('aside [data-testid="user-menu-trigger"]');
    await menuTrigger.click();

    // Click "Sign in with email" menu item
    const signInItem = page.getByRole('menuitem', { name: /sign in with email/i });
    await expect(signInItem).toBeVisible();
    await signInItem.click();

    // Assert URL contains /auth/signin
    await expect(page).toHaveURL(/\/auth\/signin/);

    // Unwind: click "Continue as guest" link to return to root
    const continueAsGuest = page.getByRole('link', { name: /continue as guest/i });
    await expect(continueAsGuest).toBeVisible();
    await continueAsGuest.click();
    await expect(page).toHaveURL(/\/$/);

    await assertCleanState(page);
  });

  test('menu Settings navigates', async ({ page }) => {
    // Open menu
    const menuTrigger = page.locator('aside [data-testid="user-menu-trigger"]');
    await menuTrigger.click();

    // Click Settings menu item
    const settingsItem = page.getByRole('menuitem', { name: /settings/i });
    await expect(settingsItem).toBeVisible();
    await settingsItem.click();

    // Assert Settings content visible (hard navigation completed)
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/customize your dashboard/i)).toBeVisible({ timeout: 10000 });

    // Unwind: navigate back to root
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await assertCleanState(page);
  });

  test('skip-to-content link moves focus', async ({ page }) => {
    // Press Tab to focus the skip link
    await page.keyboard.press('Tab');

    const skipLink = page.locator('a:has-text("Skip to content"), a:has-text("Skip to main")');
    await expect(skipLink.first()).toBeFocused();

    // Press Enter to activate skip link
    await page.keyboard.press('Enter');

    // Assert focus moved to main content area
    const mainContent = page.locator('main, [role="main"]');
    await expect(mainContent).toBeFocused();

    await assertCleanState(page);
  });
});

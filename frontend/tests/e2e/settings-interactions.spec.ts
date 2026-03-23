// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { assertCleanState } from './helpers/clean-state';

test.describe('Settings Interactions (Feature 1247)', () => {
  test.setTimeout(30_000);

  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForFunction(
      () => !document.querySelector('[class*="animate-pulse"]'),
      { timeout: 10000 }
    );
  });

  test('haptic feedback toggle', async ({ page }) => {
    const hapticSwitch = page.getByRole('switch', { name: /haptic/i });
    await expect(hapticSwitch).toBeVisible();

    const initialState = await hapticSwitch.getAttribute('aria-checked');

    // Toggle on
    await hapticSwitch.click();
    const newState = await hapticSwitch.getAttribute('aria-checked');
    expect(newState).not.toBe(initialState);

    // Unwind: toggle back
    await hapticSwitch.click();
    const finalState = await hapticSwitch.getAttribute('aria-checked');
    expect(finalState).toBe(initialState);

    await assertCleanState(page);
  });

  test('reduced motion toggle', async ({ page }) => {
    const motionSwitch = page.getByRole('switch', { name: /reduced motion/i });
    await expect(motionSwitch).toBeVisible();

    const initialState = await motionSwitch.getAttribute('aria-checked');

    // Toggle on
    await motionSwitch.click();
    const newState = await motionSwitch.getAttribute('aria-checked');
    expect(newState).not.toBe(initialState);

    // Unwind: toggle back
    await motionSwitch.click();
    const finalState = await motionSwitch.getAttribute('aria-checked');
    expect(finalState).toBe(initialState);

    await assertCleanState(page);
  });

  test('dark mode toggle is disabled', async ({ page }) => {
    const darkModeSwitch = page.getByRole('switch', { name: /dark mode/i });
    await expect(darkModeSwitch).toBeVisible();

    const initialState = await darkModeSwitch.getAttribute('aria-checked');

    // Attempt to click — should not change state (element is disabled)
    await darkModeSwitch.click({ force: true });
    const afterClickState = await darkModeSwitch.getAttribute('aria-checked');
    expect(afterClickState).toBe(initialState);

    await assertCleanState(page);
  });

  test('email notification toggle', async ({ page }) => {
    const emailSwitch = page.getByRole('switch', { name: /email notifications/i });
    await expect(emailSwitch).toBeVisible();

    const initialState = await emailSwitch.getAttribute('aria-checked');

    // Toggle
    await emailSwitch.click();
    const newState = await emailSwitch.getAttribute('aria-checked');
    expect(newState).not.toBe(initialState);

    // Unwind: toggle back
    await emailSwitch.click();
    const finalState = await emailSwitch.getAttribute('aria-checked');
    expect(finalState).toBe(initialState);

    await assertCleanState(page);
  });

  test('frequency selector instant', async ({ page }) => {
    // Record current selection before changing
    const instantButton = page.getByRole('button', { name: /instant/i });
    const dailyButton = page.getByRole('button', { name: /daily/i });

    // Determine previous selection for unwind
    const dailyWasSelected = await dailyButton.getAttribute('aria-pressed')
      .then(v => v === 'true')
      .catch(() => false);

    // Click instant
    await instantButton.click();
    await expect(instantButton).toHaveAttribute('aria-pressed', 'true');

    // Unwind: click back to previous if it was different
    if (dailyWasSelected) {
      await dailyButton.click();
      await expect(dailyButton).toHaveAttribute('aria-pressed', 'true');
    }

    await assertCleanState(page);
  });

  test('frequency selector daily', async ({ page }) => {
    const dailyButton = page.getByRole('button', { name: /daily/i });
    const instantButton = page.getByRole('button', { name: /instant/i });

    // Record previous selection for unwind
    const instantWasSelected = await instantButton.getAttribute('aria-pressed')
      .then(v => v === 'true')
      .catch(() => false);

    // Click daily
    await dailyButton.click();
    await expect(dailyButton).toHaveAttribute('aria-pressed', 'true');

    // Unwind: click back to previous if it was different
    if (instantWasSelected) {
      await instantButton.click();
      await expect(instantButton).toHaveAttribute('aria-pressed', 'true');
    }

    await assertCleanState(page);
  });

  test('frequency selector weekly', async ({ page }) => {
    const weeklyButton = page.getByRole('button', { name: /weekly/i });
    const instantButton = page.getByRole('button', { name: /instant/i });

    // Record previous selection for unwind
    const instantWasSelected = await instantButton.getAttribute('aria-pressed')
      .then(v => v === 'true')
      .catch(() => false);

    // Click weekly
    await weeklyButton.click();
    await expect(weeklyButton).toHaveAttribute('aria-pressed', 'true');

    // Unwind: click back to previous if it was different
    if (instantWasSelected) {
      await instantButton.click();
      await expect(instantButton).toHaveAttribute('aria-pressed', 'true');
    }

    await assertCleanState(page);
  });

  test('quiet hours toggle shows time pickers', async ({ page }) => {
    const quietHoursSwitch = page.getByRole('switch', { name: /quiet hours/i });
    await expect(quietHoursSwitch).toBeVisible();

    // Toggle quiet hours on
    const initialState = await quietHoursSwitch.getAttribute('aria-checked');
    if (initialState !== 'true') {
      await quietHoursSwitch.click();
    }

    // Assert time pickers / inputs are visible
    const timePickers = page.locator('input[type="time"], [data-testid*="time-picker"], [aria-label*="time"]');
    await expect(timePickers.first()).toBeVisible({ timeout: 3000 });

    // Unwind: toggle quiet hours off
    await quietHoursSwitch.click();

    // Assert pickers are hidden
    await expect(timePickers.first()).toBeHidden({ timeout: 3000 });

    await assertCleanState(page);
  });

  test('save button persists changes', async ({ page }) => {
    // Toggle email notifications to create a change
    const emailSwitch = page.getByRole('switch', { name: /email notifications/i });
    await expect(emailSwitch).toBeVisible();

    const initialState = await emailSwitch.getAttribute('aria-checked');
    await emailSwitch.click();
    const toggledState = await emailSwitch.getAttribute('aria-checked');
    expect(toggledState).not.toBe(initialState);

    // Click save
    const saveButton = page.getByRole('button', { name: /save/i });
    await expect(saveButton).toBeEnabled();
    await saveButton.click();

    // Wait for save to complete
    await page.waitForLoadState('networkidle');

    // Reload and verify persistence
    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.waitForFunction(
      () => !document.querySelector('[class*="animate-pulse"]'),
      { timeout: 10000 }
    );

    const emailSwitchAfterReload = page.getByRole('switch', { name: /email notifications/i });
    await expect(emailSwitchAfterReload).toBeVisible();
    const persistedState = await emailSwitchAfterReload.getAttribute('aria-checked');
    expect(persistedState).toBe(toggledState);

    await assertCleanState(page);
  });

  test('settings sign-out opens dialog', async ({ page }) => {
    const signOutButton = page.getByRole('button', { name: /sign out/i });
    await expect(signOutButton).toBeVisible();

    // Click sign-out
    await signOutButton.click();

    // Assert dialog is visible
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Unwind: press Escape to close dialog
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();

    await assertCleanState(page);
  });
});

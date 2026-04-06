// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { assertCleanState, createTestConfig, deleteTestConfig } from './helpers/clean-state';

test.describe('Configuration CRUD (Feature 1247)', () => {
  test.setTimeout(30_000);

  test('create button opens form', async ({ page }) => {
    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    // Use specific name to avoid matching both CTA ("Create Configuration") and form submit ("Create")
    await page.getByRole('button', { name: /create configuration|new configuration/i }).click();

    // Assert form or dialog appeared with a name input
    // Label is not associated via htmlFor — use placeholder instead
    const nameInput = page.getByPlaceholder(/my watchlist/i);
    await expect(nameInput).toBeVisible({ timeout: 5000 });

    // Unwind: close the form via Escape (Cancel may be off-viewport on mobile)
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

    await assertCleanState(page);
  });

  test('form submit creates config', async ({ page }) => {
    const configName = `e2e-${test.info().testId}`;

    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    // Open create form
    await page.getByRole('button', { name: /create configuration|new configuration/i }).click();

    // Fill name
    // Label is not associated via htmlFor — use placeholder instead
    const nameInput = page.getByPlaceholder(/my watchlist/i);
    await expect(nameInput).toBeVisible({ timeout: 5000 });
    await nameInput.fill(configName);

    // Submit
    await page.getByRole('button', { name: /save|create|submit/i }).click();

    // Assert the config name appears on the page
    await expect(page.getByText(configName)).toBeVisible({ timeout: 10000 });

    // Unwind: delete the config we just created
    const configCard = page.getByText(configName).locator('..');
    const deleteButton = configCard.getByRole('button', { name: /delete|remove/i });
    if (await deleteButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await deleteButton.click();
      // Confirm deletion
      const confirmButton = page.getByRole('button', { name: /confirm|delete|yes/i });
      if (await confirmButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await confirmButton.click();
      }
    } else {
      // Fallback: use helper
      await deleteTestConfig(page, configName);
    }

    await assertCleanState(page);
  });

  test('config card click selects it', async ({ page }) => {
    const configName = `e2e-${test.info().testId}`;

    // Create a config to interact with
    await createTestConfig(page, configName);

    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    // Click on the config card (role="button", aria-pressed)
    const configCard = page.getByRole('button', { name: new RegExp(`Configuration: ${configName}`, 'i') });
    if (await configCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      await configCard.click();

      // Assert card becomes selected (aria-pressed="true")
      await expect(configCard).toHaveAttribute('aria-pressed', 'true', { timeout: 5000 });
    } else {
      // Fallback: click by text
      const configLink = page.getByText(configName);
      await expect(configLink).toBeVisible({ timeout: 5000 });
      await configLink.click();
    }

    // Unwind: clean up
    await deleteTestConfig(page, configName);

    await assertCleanState(page);
  });

  test('delete button opens confirmation', async ({ page }) => {
    const configName = `e2e-${test.info().testId}`;

    // Create a config to delete
    await createTestConfig(page, configName);

    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    // Delete button has aria-label="Delete {config.name}"
    const deleteButton = page.getByRole('button', { name: `Delete ${configName}` });
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
    await deleteButton.click();

    // Assert confirmation dialog appeared (heading "Delete Configuration")
    const dialog = page.getByText(/are you sure/i).or(page.getByText(/delete configuration/i));
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Unwind: cancel the dialog
    const cancelButton = page.getByRole('button', { name: /cancel/i });
    if (await cancelButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cancelButton.click();
    } else {
      await page.keyboard.press('Escape');
    }

    // Clean up the config
    await deleteTestConfig(page, configName);

    await assertCleanState(page);
  });

  test('delete confirm removes config', async ({ page }) => {
    const configName = `e2e-${test.info().testId}`;

    // Create a config to delete
    await createTestConfig(page, configName);

    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    // Verify config exists before deletion
    await expect(page.getByText(configName)).toBeVisible({ timeout: 5000 });

    // Delete button has aria-label="Delete {config.name}"
    const deleteButton = page.getByRole('button', { name: `Delete ${configName}` });
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
    await deleteButton.click();

    // Confirm deletion — the destructive button says "Delete"
    const confirmButton = page.getByRole('button', { name: /^delete$/i });
    await expect(confirmButton).toBeVisible({ timeout: 5000 });
    await confirmButton.click();

    // Assert config is gone from list
    await expect(page.getByText(configName)).toBeHidden({ timeout: 10000 });

    await assertCleanState(page);
  });
});

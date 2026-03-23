// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { assertCleanState, createTestConfig, deleteTestConfig } from './helpers/clean-state';

test.describe('Configuration CRUD (Feature 1247)', () => {
  test.setTimeout(30_000);

  test('create button opens form', async ({ page }) => {
    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /create|new|add/i }).click();

    // Assert form or dialog appeared with a name input
    const nameInput = page.getByLabel(/name/i);
    await expect(nameInput).toBeVisible({ timeout: 5000 });

    // Unwind: close the form
    const cancelButton = page.getByRole('button', { name: /cancel|close/i });
    if (await cancelButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cancelButton.click();
    } else {
      await page.keyboard.press('Escape');
    }

    await assertCleanState(page);
  });

  test('form submit creates config', async ({ page }) => {
    const configName = `e2e-${test.info().testId}`;

    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    // Open create form
    await page.getByRole('button', { name: /create|new|add/i }).click();

    // Fill name
    const nameInput = page.getByLabel(/name/i);
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

  test('config card opens detail view', async ({ page }) => {
    const configName = `e2e-${test.info().testId}`;

    // Create a config to interact with
    await createTestConfig(page, configName);

    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    // Click on the config card/name
    const configLink = page.getByText(configName);
    await expect(configLink).toBeVisible({ timeout: 5000 });
    await configLink.click();

    // Assert URL changed or detail view appeared
    await expect(async () => {
      const url = page.url();
      const hasDetailView = await page.getByRole('heading', { name: configName }).isVisible().catch(() => false);
      expect(url.includes('/configs/') || hasDetailView).toBeTruthy();
    }).toPass({ timeout: 5000 });

    // Unwind: go back to configs list and clean up
    await page.goto('/configs');
    await page.waitForLoadState('networkidle');
    await deleteTestConfig(page, configName);

    await assertCleanState(page);
  });

  test('delete button opens confirmation', async ({ page }) => {
    const configName = `e2e-${test.info().testId}`;

    // Create a config to delete
    await createTestConfig(page, configName);

    await page.goto('/configs');
    await page.waitForLoadState('networkidle');

    // Find the config and its delete button
    const configCard = page.getByText(configName).locator('..');
    const deleteButton = configCard.getByRole('button', { name: /delete|remove/i });
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
    await deleteButton.click();

    // Assert confirmation dialog appeared
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

    // Unwind: cancel the dialog
    const cancelButton = page.getByRole('dialog').getByRole('button', { name: /cancel|close|no/i });
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

    // Find delete button near the config
    const configCard = page.getByText(configName).locator('..');
    const deleteButton = configCard.getByRole('button', { name: /delete|remove/i });
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
    await deleteButton.click();

    // Confirm deletion in dialog
    const confirmButton = page.getByRole('dialog').getByRole('button', { name: /confirm|delete|yes/i });
    await expect(confirmButton).toBeVisible({ timeout: 5000 });
    await confirmButton.click();

    // Assert config is gone from list
    await expect(page.getByText(configName)).toBeHidden({ timeout: 10000 });

    await assertCleanState(page);
  });
});

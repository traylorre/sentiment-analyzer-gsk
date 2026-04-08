// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { assertCleanState, createTestConfig, deleteTestConfig } from './helpers/clean-state';

test.describe('Configuration CRUD (Feature 1247)', () => {
  test.setTimeout(30_000);

  test('create button opens form', async ({ page }) => {
    await page.goto('/configs');
    await page.waitForLoadState('domcontentloaded');

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

    // Mock ticker search to avoid rate limiting
    await page.route('**/api/v2/tickers/search**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [{ symbol: 'AAPL', name: 'Apple Inc', exchange: 'NASDAQ' }],
        }),
      });
    });

    await page.goto('/configs');
    // Avoid networkidle — TanStack Query keeps network busy
    await page.waitForLoadState('domcontentloaded');

    // Open create form
    await page.getByRole('button', { name: /create configuration|new configuration/i }).click();

    // Fill name
    // Label is not associated via htmlFor — use placeholder instead
    const nameInput = page.getByPlaceholder(/my watchlist/i);
    await expect(nameInput).toBeVisible({ timeout: 5000 });
    await nameInput.fill(configName);

    // Add a ticker (required for Create button to become enabled)
    const tickerInput = page.getByPlaceholder(/search for a ticker/i)
      .or(page.getByPlaceholder(/add ticker|search/i));
    await expect(tickerInput.first()).toBeVisible({ timeout: 5000 });
    await tickerInput.first().fill('AAPL');
    const option = page.getByRole('option', { name: /AAPL/i });
    await expect(option).toBeVisible({ timeout: 5000 });
    await option.click();

    // Wait for Create button to become enabled
    const submitButton = page.getByRole('button', { name: 'Create', exact: true });
    await expect(submitButton).toBeEnabled({ timeout: 5000 });

    // Submit — use JS click because form extends beyond Desktop Chrome viewport
    await submitButton.evaluate((el) => (el as HTMLButtonElement).click());

    // Assert the config name appears on the page
    await expect(page.getByText(configName)).toBeVisible({ timeout: 10000 });

    // Unwind: delete the config we just created
    const configCard = page.getByText(configName).locator('..');
    const deleteButton = configCard.getByRole('button', { name: /delete|remove/i });
    // Safe: cleanup — failure here means element absent, not broken
    if (await deleteButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await deleteButton.click();
      // Confirm deletion
      const confirmButton = page.getByRole('button', { name: /confirm|delete|yes/i });
      // Safe: cleanup — failure here means element absent, not broken
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
    await page.waitForLoadState('domcontentloaded');

    // Click on the config card (role="button", aria-pressed)
    const configCard = page.getByRole('button', { name: new RegExp(`Configuration: ${configName}`, 'i') });
    await expect(configCard).toBeVisible({ timeout: 5000 });
    await configCard.click();

    // Assert card becomes selected (aria-pressed="true")
    await expect(configCard).toHaveAttribute('aria-pressed', 'true', { timeout: 5000 });

    // Unwind: clean up
    await deleteTestConfig(page, configName);

    await assertCleanState(page);
  });

  test('delete button opens confirmation', async ({ page }) => {
    const configName = `e2e-${test.info().testId}`;

    // Create a config to delete
    await createTestConfig(page, configName);

    await page.goto('/configs');
    await page.waitForLoadState('domcontentloaded');

    // Delete button has aria-label="Delete {config.name}"
    const deleteButton = page.getByRole('button', { name: `Delete ${configName}` });
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
    await deleteButton.click();

    // Assert confirmation dialog appeared — both "Delete Configuration" heading
    // and "Are you sure" body text appear, so use .first() to avoid strict mode violation
    const dialog = page.getByText(/are you sure/i).or(page.getByText(/delete configuration/i));
    await expect(dialog.first()).toBeVisible({ timeout: 5000 });

    // Unwind: cancel the dialog
    const cancelButton = page.getByRole('button', { name: /cancel/i });
    // Safe: cleanup — failure here means element absent, not broken
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
    await page.waitForLoadState('domcontentloaded');

    // Verify config exists before deletion
    await expect(page.getByText(configName)).toBeVisible({ timeout: 5000 });

    // Delete button has aria-label="Delete {config.name}"
    const deleteButton = page.getByRole('button', { name: `Delete ${configName}` });
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
    await deleteButton.click();

    // Confirm deletion — the destructive button says "Delete".
    // Use JS click because on mobile viewports the dialog button may be outside the viewport.
    const confirmButton = page.getByRole('button', { name: /^delete$/i });
    await expect(confirmButton).toBeVisible({ timeout: 5000 });
    await confirmButton.evaluate((el) => (el as HTMLButtonElement).click());

    // Assert config is gone from list
    await expect(page.getByText(configName)).toBeHidden({ timeout: 10000 });

    await assertCleanState(page);
  });
});

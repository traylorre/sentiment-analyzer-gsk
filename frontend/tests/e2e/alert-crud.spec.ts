// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { assertCleanState, createTestAlert, deleteTestAlert } from './helpers/clean-state';

test.describe('Alert CRUD (Feature 1247)', () => {
  test.setTimeout(30_000);

  test('new alert button opens form', async ({ page }) => {
    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /create|add|new/i }).click();

    // Assert form is visible (look for ticker or threshold input)
    const formVisible = page.getByLabel(/ticker|symbol|name/i);
    await expect(formVisible).toBeVisible({ timeout: 5000 });

    // Unwind: cancel
    const cancelButton = page.getByRole('button', { name: /cancel|close/i });
    if (await cancelButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cancelButton.click();
    } else {
      await page.keyboard.press('Escape');
    }

    await assertCleanState(page);
  });

  test('alert form submit creates alert', async ({ page }) => {
    const ticker = `TEST-${test.info().testId}`.slice(0, 10);

    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');

    // Open create form
    await page.getByRole('button', { name: /create|add|new/i }).click();

    // Fill ticker
    const tickerInput = page.getByLabel(/ticker|symbol/i);
    await expect(tickerInput).toBeVisible({ timeout: 5000 });
    await tickerInput.fill(ticker);

    // Fill threshold if present
    const thresholdInput = page.getByLabel(/threshold|price|value/i);
    if (await thresholdInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await thresholdInput.fill('150');
    }

    // Submit
    await page.getByRole('button', { name: /save|create|submit/i }).click();

    // Assert alert appears in list
    await expect(page.getByText(ticker)).toBeVisible({ timeout: 10000 });

    // Unwind: delete the alert
    const alertRow = page.getByText(ticker).locator('..');
    const deleteButton = alertRow.getByRole('button', { name: /delete|remove/i });
    if (await deleteButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await deleteButton.click();
      const confirmButton = page.getByRole('button', { name: /confirm|delete|yes/i });
      if (await confirmButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await confirmButton.click();
      }
    } else {
      await deleteTestAlert(page, 0);
    }

    await assertCleanState(page);
  });

  test('alert form cancel returns to list', async ({ page }) => {
    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');

    // Open create form
    await page.getByRole('button', { name: /create|add|new/i }).click();

    // Assert form is visible
    const formInput = page.getByLabel(/ticker|symbol|name/i);
    await expect(formInput).toBeVisible({ timeout: 5000 });

    // Cancel
    const cancelButton = page.getByRole('button', { name: /cancel|close|back/i });
    if (await cancelButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cancelButton.click();
    } else {
      await page.keyboard.press('Escape');
    }

    // Assert we are back on the alerts list (form input should be gone)
    await expect(formInput).toBeHidden({ timeout: 5000 });

    // The alerts page heading or list should be visible
    await expect(
      page.getByRole('heading', { name: /alert/i }).or(page.getByText(/no alerts|your alerts/i))
    ).toBeVisible({ timeout: 5000 });

    await assertCleanState(page);
  });

  test('alert toggle switch changes state', async ({ page }) => {
    // Create an alert to interact with
    await createTestAlert(page, 'AAPL', '150');

    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');

    // Find a switch/toggle on the alert
    const toggleSwitch = page.getByRole('switch').first();
    await expect(toggleSwitch).toBeVisible({ timeout: 5000 });

    const initialState = await toggleSwitch.getAttribute('aria-checked');

    // Click to toggle
    await toggleSwitch.click();

    // Assert state changed
    await expect(async () => {
      const newState = await toggleSwitch.getAttribute('aria-checked');
      expect(newState).not.toBe(initialState);
    }).toPass({ timeout: 5000 });

    // Unwind: toggle back to original state
    await toggleSwitch.click();
    await expect(async () => {
      const restoredState = await toggleSwitch.getAttribute('aria-checked');
      expect(restoredState).toBe(initialState);
    }).toPass({ timeout: 5000 });

    // Clean up the alert
    await deleteTestAlert(page, 0);

    await assertCleanState(page);
  });

  test('alert delete button opens confirmation', async ({ page }) => {
    // Create an alert to delete
    await createTestAlert(page, 'MSFT', '300');

    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');

    // Click delete on the alert
    const deleteButton = page.getByRole('button', { name: /delete|remove/i }).first();
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
    await deleteButton.click();

    // Assert confirmation dialog appeared
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

    // Unwind: cancel
    const cancelButton = page.getByRole('dialog').getByRole('button', { name: /cancel|close|no/i });
    if (await cancelButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cancelButton.click();
    } else {
      await page.keyboard.press('Escape');
    }

    // Clean up
    await deleteTestAlert(page, 0);

    await assertCleanState(page);
  });

  test('alert delete confirm removes', async ({ page }) => {
    // Create an alert to delete
    await createTestAlert(page, 'GOOG', '175');

    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');

    // Verify alert exists
    await expect(page.getByText('GOOG')).toBeVisible({ timeout: 5000 });

    // Click delete
    const deleteButton = page.getByRole('button', { name: /delete|remove/i }).first();
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
    await deleteButton.click();

    // Confirm deletion
    const confirmButton = page.getByRole('dialog').getByRole('button', { name: /confirm|delete|yes/i });
    await expect(confirmButton).toBeVisible({ timeout: 5000 });
    await confirmButton.click();

    // Assert alert is gone
    await expect(page.getByText('GOOG')).toBeHidden({ timeout: 10000 });

    await assertCleanState(page);
  });

  test.fixme('quota exceeded shows message', () => {
    // Requires max alerts — dedicated test environment needed
  });
});

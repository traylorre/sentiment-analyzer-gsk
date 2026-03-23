// Target: Customer Dashboard (Next.js/Amplify)
// Feature 1247: Shared helpers for clickable element test coverage

import { type Page, expect } from '@playwright/test';

/**
 * Assert the UI is in a clean state after an interaction unwind.
 *
 * Checks:
 * - No open dialogs (role=dialog)
 * - No loading spinners
 * - No error toasts (Sonner toast library)
 * - No pending overlays
 */
export async function assertCleanState(page: Page) {
  // No open dialogs
  await expect(page.locator('[role="dialog"]')).toBeHidden({ timeout: 3000 });

  // No loading spinners
  await expect(page.locator('.loading, .spinner, [aria-busy="true"]')).toBeHidden({
    timeout: 3000,
  });

  // No error toasts (Sonner uses data-sonner-toaster)
  const errorToast = page.locator(
    '[data-sonner-toaster] [data-type="error"], [role="status"][data-type="error"]'
  );
  if ((await errorToast.count()) > 0) {
    await expect(errorToast).toBeHidden({ timeout: 3000 });
  }
}

/**
 * Create a test configuration via the UI.
 * Uses e2e- prefix for cleanup identification.
 */
export async function createTestConfig(page: Page, name: string): Promise<void> {
  await page.goto('/configs');
  await page.getByRole('button', { name: /create|new|add/i }).click();
  await page.getByLabel(/name/i).fill(name);
  // Add a ticker
  const tickerInput = page.getByPlaceholder(/add ticker|search/i);
  if (await tickerInput.isVisible()) {
    await tickerInput.fill('AAPL');
    // Wait for and click autocomplete result
    const option = page.getByRole('option', { name: /AAPL/i });
    if (await option.isVisible({ timeout: 3000 }).catch(() => false)) {
      await option.click();
    }
  }
  await page.getByRole('button', { name: /save|create|submit/i }).click();
  // Wait for list to update
  await page.waitForTimeout(1000);
}

/**
 * Delete a test configuration by name via the UI.
 */
export async function deleteTestConfig(page: Page, name: string): Promise<void> {
  await page.goto('/configs');
  const configCard = page.getByText(name);
  if (await configCard.isVisible({ timeout: 3000 }).catch(() => false)) {
    // Find the delete button near this config
    const card = configCard.locator('..');
    await card.getByRole('button', { name: /delete|remove/i }).click();
    // Confirm deletion
    await page.getByRole('button', { name: /confirm|delete|yes/i }).click();
    await page.waitForTimeout(500);
  }
}

/**
 * Create a test alert via the UI.
 */
export async function createTestAlert(
  page: Page,
  ticker: string,
  threshold: string
): Promise<void> {
  await page.goto('/alerts');
  await page.getByRole('button', { name: /create|add|new/i }).click();
  // Fill ticker
  const tickerInput = page.getByLabel(/ticker/i);
  if (await tickerInput.isVisible()) {
    await tickerInput.fill(ticker);
  }
  // Fill threshold
  const thresholdInput = page.getByLabel(/threshold|price/i);
  if (await thresholdInput.isVisible()) {
    await thresholdInput.fill(threshold);
  }
  await page.getByRole('button', { name: /save|create|submit/i }).click();
  await page.waitForTimeout(1000);
}

/**
 * Delete an alert by index via the UI.
 */
export async function deleteTestAlert(page: Page, index: number = 0): Promise<void> {
  await page.goto('/alerts');
  const deleteButtons = page.getByRole('button', { name: /delete|remove/i });
  if ((await deleteButtons.count()) > index) {
    await deleteButtons.nth(index).click();
    await page.getByRole('button', { name: /confirm|delete|yes/i }).click();
    await page.waitForTimeout(500);
  }
}

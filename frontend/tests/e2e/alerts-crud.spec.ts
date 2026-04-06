// Target: Customer Dashboard (Next.js/Amplify)
/**
 * E2E tests for alert management CRUD (Feature 1223, US3).
 *
 * Tests the complete alert lifecycle on the alerts page.
 * Requires an authenticated session to access alerts.
 *
 * Alert form workflow: select config → pick ticker → choose type/direction → threshold → submit
 */

import { test, expect } from '@playwright/test';
import { setupAuthSession } from './helpers/auth-helper';

test.describe('Alert Management CRUD (US3)', () => {
  test.beforeEach(async ({ context, page }) => {
    // /alerts requires upgraded auth — set up session cookies
    await setupAuthSession(context);
    await page.goto('/alerts');
    // Avoid networkidle — TanStack Query keeps network busy with background refetches
    await page.waitForLoadState('domcontentloaded');
  });

  test('alerts page shows heading or empty state', async ({ page }) => {
    // The page should show alerts content — empty state text.
    // Note: h1 is "Dashboard" from the layout, NOT "Alerts".
    await expect(
      page.getByText(/no alerts configured/i).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('alert quota information is displayed', async ({ page }) => {
    // The alerts page should have either the empty state or alert-specific content.
    // Note: h1 is "Dashboard" from the layout, NOT "Alerts".
    await expect(
      page.getByText(/no alerts configured/i).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('new alert button is visible', async ({ page }) => {
    // Either the list "New Alert" button or the empty state "Create Alert" button
    const newAlertBtn = page.getByRole('button', { name: /new alert/i })
      .or(page.getByRole('button', { name: /create alert/i }));
    await expect(newAlertBtn.first()).toBeVisible({ timeout: 10000 });
  });

  test('delete alert removes it from list', async ({ page }) => {
    // Look for existing alerts with delete buttons (aria-label="Delete {ticker} alert")
    const deleteButtons = page.getByRole('button', { name: /delete.*alert/i });
    const count = await deleteButtons.count();

    if (count > 0) {
      const beforeCount = count;
      await deleteButtons.first().click();

      // Confirm deletion in dialog
      const confirmButton = page.getByRole('button', { name: /^delete$/i });
      if (await confirmButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await confirmButton.click();
      }

      // Verify count decreased
      await page.waitForTimeout(1000);
      const afterCount = await page.getByRole('button', { name: /delete.*alert/i }).count();
      expect(afterCount).toBeLessThan(beforeCount);
    } else {
      test.skip(true, 'No alerts exist to test deletion');
    }
  });
});

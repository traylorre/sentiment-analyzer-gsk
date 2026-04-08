// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { assertCleanState, createTestConfig, mockAlertData } from './helpers/clean-state';
import { setupAuthSession } from './helpers/auth-helper';

/**
 * Alert CRUD tests — rewritten to match actual form UI.
 *
 * The alert form is a multi-step workflow:
 * 1. Select a configuration (native <select>)
 * 2. Pick tickers (button group from the selected config)
 * 3. Choose alert type: Sentiment or Volatility (button cards)
 * 4. Choose direction: Above or Below (button cards)
 * 5. Set threshold (range slider)
 * 6. Submit: "Create Alert"
 *
 * Requires at least one configuration with tickers to exist first.
 */
test.describe('Alert CRUD (Feature 1247)', () => {
  test.setTimeout(45_000);

  // /alerts requires upgraded auth — set up session cookies before each test
  test.beforeEach(async ({ context }) => {
    await setupAuthSession(context);
  });

  test('new alert button opens form', async ({ page }) => {
    await page.goto('/alerts');
    await page.waitForLoadState('domcontentloaded');

    // Click "New Alert" button (in list header or empty state "Create Alert")
    const newAlertBtn = page.getByRole('button', { name: /new alert/i })
      .or(page.getByRole('button', { name: /create alert/i }));
    await expect(newAlertBtn.first()).toBeVisible({ timeout: 5000 });
    await newAlertBtn.first().click();

    // Assert form is visible — check for the config select dropdown
    const configSelect = page.locator('select');
    await expect(configSelect).toBeVisible({ timeout: 5000 });

    // Unwind: close the form via Escape (Cancel may be out of viewport on mobile)
    await page.keyboard.press('Escape');
    // Wait for animation to complete
    await page.waitForTimeout(500);

    await assertCleanState(page);
  });

  test('alert form cancel returns to list', async ({ page }) => {
    await page.goto('/alerts');
    await page.waitForLoadState('domcontentloaded');

    // Open create form
    const newAlertBtn = page.getByRole('button', { name: /new alert/i })
      .or(page.getByRole('button', { name: /create alert/i }));
    await expect(newAlertBtn.first()).toBeVisible({ timeout: 5000 });
    await newAlertBtn.first().click();

    // Assert form is visible
    const configSelect = page.locator('select');
    await expect(configSelect).toBeVisible({ timeout: 5000 });

    // Cancel via Cancel button — use JS click because form extends beyond viewport
    const cancelBtn = page.getByRole('button', { name: /cancel/i });
    // Safe: cleanup — failure here means element absent, not broken
    if (await cancelBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cancelBtn.evaluate((el) => (el as HTMLButtonElement).click());
    } else {
      // Fall back to Escape if Cancel button not visible
      await page.keyboard.press('Escape');
    }

    // Assert form is gone — select should be hidden
    await expect(configSelect).toBeHidden({ timeout: 5000 });

    await assertCleanState(page);
  });

  test('alert form shows config-dependent tickers', async ({ page }) => {
    // Ensure at least one config exists
    await createTestConfig(page, `e2e-alert-cfg-${Date.now()}`);

    await page.goto('/alerts');
    await page.waitForLoadState('domcontentloaded');

    // Open form
    const newAlertBtn = page.getByRole('button', { name: /new alert/i })
      .or(page.getByRole('button', { name: /create alert/i }));
    await expect(newAlertBtn.first()).toBeVisible({ timeout: 5000 });
    await newAlertBtn.first().click();

    // Select a configuration — wait for options to load from GET /api/v2/configurations mock
    const configSelect = page.locator('select');
    await expect(configSelect).toBeVisible({ timeout: 5000 });

    // Wait for config options to populate (TanStack Query async fetch).
    // Note: <option> elements inside native <select> are NOT DOM-visible,
    // so use waitForFunction to count options instead of toBeVisible.
    await page.waitForFunction(
      (sel: string) => {
        const select = document.querySelector(sel) as HTMLSelectElement | null;
        return select && Array.from(select.options).filter(o => o.value !== '').length > 0;
      },
      'select',
      { timeout: 10000 }
    );
    const options = configSelect.locator('option:not([value=""])');
    const optionCount = await options.count();
    if (optionCount > 0) {
      const firstValue = await options.first().getAttribute('value');
      if (firstValue) {
        await configSelect.selectOption(firstValue);
      }

      // After selecting a config, tickers or "No tickers" message should appear
      await page.waitForTimeout(500);
      const tickerButtons = page.locator('button').filter({ hasText: /^[A-Z]{1,5}$/ });
      const noTickersMsg = page.getByText(/no tickers/i);
      await expect(tickerButtons.first().or(noTickersMsg)).toBeVisible({ timeout: 5000 });
    }

    // Unwind: cancel — button may be below viewport, use JS click
    const cancelBtn = page.getByRole('button', { name: /cancel/i });
    await cancelBtn.evaluate((el) => (el as HTMLButtonElement).click());
    await assertCleanState(page);
  });

  test('alert toggle switch changes state', async ({ page }) => {
    await mockAlertData(page);
    await page.goto('/alerts');
    await page.waitForLoadState('domcontentloaded');

    const toggleSwitch = page.getByRole('switch').first();
    await expect(toggleSwitch).toBeVisible({ timeout: 5000 });

    const initialState = await toggleSwitch.getAttribute('aria-checked');
    await toggleSwitch.click();

    await expect(async () => {
      const newState = await toggleSwitch.getAttribute('aria-checked');
      expect(newState).not.toBe(initialState);
    }).toPass({ timeout: 5000 });

    // Unwind: toggle back
    await toggleSwitch.click();
    await expect(async () => {
      const restoredState = await toggleSwitch.getAttribute('aria-checked');
      expect(restoredState).toBe(initialState);
    }).toPass({ timeout: 5000 });

    await assertCleanState(page);
  });

  test('alert delete button opens confirmation', async ({ page }) => {
    await mockAlertData(page);
    await page.goto('/alerts');
    await page.waitForLoadState('domcontentloaded');

    const deleteButton = page.getByRole('button', { name: /delete.*alert/i }).first();
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
    await deleteButton.click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Unwind: cancel
    const cancelButton = page.getByRole('button', { name: /cancel/i });
    // Safe: cleanup — cancel unwind; real failure propagates to assertCleanState in the next assertion chain
    if (await cancelButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cancelButton.click();
    } else {
      await page.keyboard.press('Escape');
    }

    await assertCleanState(page);
  });

  test.fixme('quota exceeded shows message', () => {
    // Requires max alerts — dedicated test environment needed
  });
});

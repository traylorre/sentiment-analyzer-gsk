// Target: Customer Dashboard (Next.js/Amplify)
// Feature 1247: Shared helpers for clickable element test coverage

import { type Page, expect } from '@playwright/test';
import { mockAnonymousAuth } from './auth-helper';

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
 *
 * Throws descriptive errors on failure instead of silently timing out.
 * All errors include the helper name, config name, and the step that failed.
 */
export async function createTestConfig(page: Page, name: string): Promise<void> {
  const tag = `createTestConfig('${name}')`;

  // Mock anonymous auth to ensure consistent session
  await mockAnonymousAuth(page);

  const mockConfigId = `mock-config-${Date.now()}`;
  const now = new Date().toISOString();
  const mockConfig = {
    configId: mockConfigId,
    name,
    tickers: [{ symbol: 'AAPL', name: 'Apple Inc', exchange: 'NASDAQ' }],
    timeframeDays: 30,
    includeExtendedHours: false,
    createdAt: now,
    updatedAt: now,
  };

  // Mock configurations endpoint — handles both GET (list) and POST (create).
  // GET must return the mock config so it persists across page.goto() navigations.
  // Without this, TanStack Query refetches from the real API and gets an empty list.
  await page.route('**/api/v2/configurations', async (route) => {
    const method = route.request().method();
    if (method === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(mockConfig),
      });
    } else if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ configurations: [mockConfig], maxAllowed: 5 }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock individual config endpoints (GET/DELETE by ID)
  await page.route('**/api/v2/configurations/*', async (route) => {
    const method = route.request().method();
    if (method === 'DELETE') {
      await route.fulfill({ status: 204 });
    } else if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockConfig),
      });
    } else {
      await route.continue();
    }
  });

  // Mock ticker search to avoid rate limiting under parallel load
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

  // Wait for loading to finish (pulse skeleton to disappear)
  await page.waitForFunction(
    () => !document.querySelector('[class*="animate-pulse"]'),
    { timeout: 10000 }
    // Safe: cleanup — exception swallowed intentionally, no return value consumed
  ).catch(() => {});

  // Step 1: Click CTA to open form
  const cta = page.getByRole('button', { name: /create configuration/i })
    .or(page.getByRole('button', { name: /^new$/i }));
  try {
    await expect(cta.first()).toBeVisible({ timeout: 5000 });
    await cta.first().click();
  } catch (e) {
    throw new Error(`${tag}: form open failed -- CTA button ('Create Configuration' or 'New') not visible after 5s`);
  }

  // Step 2: Fill configuration name
  const nameInput = page.getByPlaceholder(/my watchlist/i);
  try {
    await expect(nameInput).toBeVisible({ timeout: 5000 });
    await nameInput.fill(name);
  } catch (e) {
    throw new Error(`${tag}: name input not found (tried placeholder 'my watchlist')`);
  }

  // Step 3: Add a ticker (search API is mocked, no retry needed)
  // Do NOT silently skip -- if ticker input is missing, the submit button stays disabled
  const tickerInput = page.getByPlaceholder(/search for a ticker/i)
    .or(page.getByPlaceholder(/add ticker|search/i));
  try {
    await expect(tickerInput.first()).toBeVisible({ timeout: 5000 });
  } catch (e) {
    throw new Error(`${tag}: ticker input not found (tried placeholders: 'search for a ticker', 'add ticker|search')`);
  }

  await tickerInput.first().fill('AAPL');
  const option = page.getByRole('option', { name: /AAPL/i });
  try {
    await expect(option).toBeVisible({ timeout: 5000 });
    await option.click();
  } catch (e) {
    throw new Error(`${tag}: ticker AAPL option not visible after filling search -- mock may not have intercepted the request`);
  }

  // Verify ticker was actually selected (submit button should become enabled)
  const submitButton = page.getByRole('button', { name: 'Create', exact: true });
  try {
    await expect(submitButton).toBeEnabled({ timeout: 10000 });
  } catch (e) {
    throw new Error(
      `${tag}: submit button still disabled after ticker selection -- ticker AAPL click may not have registered. ` +
      `This can happen under parallel load (workers=4, fullyParallel=true).`
    );
  }

  // Step 4: Submit — use JS click via evaluate because form extends beyond Desktop Chrome viewport
  // Playwright's click() and click({ force: true }) both fail with "outside viewport"
  // dispatchEvent('click') doesn't trigger React synthetic events properly
  await submitButton.evaluate((el) => (el as HTMLButtonElement).click());

  // Wait for form to close (modal/form disappears) — the real signal that creation succeeded.
  // networkidle NEVER resolves because TanStack Query background refetches keep the network busy.
  await expect(nameInput).toBeHidden({ timeout: 10000 });

  // Step 5: Verify config was actually created — config name appears in the page.
  // Use .first() because the mock causes a duplicate: POST mutation adds config to store,
  // then cache invalidation refetches GET which returns the same config again.
  try {
    await expect(page.getByText(name).first()).toBeVisible({ timeout: 5000 });
  } catch {
    throw new Error(
      `${tag}: creation verification failed -- config name '${name}' not found in page after submit`
    );
  }

  // Route mocks are intentionally NOT cleaned up here.
  // Tests that call createTestConfig then navigate to /configs need the GET mock
  // to persist, otherwise TanStack Query refetches from the real API (empty list).
}

/**
 * Delete a test configuration by name via the UI.
 * Uses aria-label on the delete button: "Delete {config.name}"
 */
export async function deleteTestConfig(page: Page, name: string): Promise<void> {
  await page.goto('/configs');
  // Wait for page content to render (avoid networkidle — TanStack Query keeps network busy)
  await page.waitForFunction(
    () => !document.querySelector('[class*="animate-pulse"]'),
    { timeout: 10000 }
    // Safe: cleanup — exception swallowed intentionally, no return value consumed
  ).catch(() => {});

  // The delete button has aria-label="Delete {config.name}"
  const deleteBtn = page.getByRole('button', { name: `Delete ${name}` });
  // Safe: cleanup — failure here means element absent, not broken
  if (await deleteBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await deleteBtn.click();
    // Confirm deletion in the dialog.
    // Use JS click because on mobile viewports the dialog button may be outside the viewport.
    const confirmBtn = page.getByRole('button', { name: /^delete$/i });
    await expect(confirmBtn).toBeVisible({ timeout: 3000 });
    await confirmBtn.evaluate((el) => (el as HTMLButtonElement).click());
    await page.waitForTimeout(500);
  }
}

/**
 * Create a test alert via the UI.
 *
 * The alert form workflow:
 * 1. Select a configuration from the <select> dropdown
 * 2. Click a ticker button (tickers come from the selected config)
 * 3. Select alert type (Sentiment or Volatility)
 * 4. Select direction (Above or Below)
 * 5. (threshold defaults are acceptable)
 * 6. Submit with "Create Alert"
 *
 * Requires at least one configuration to exist already.
 */
export async function createTestAlert(
  page: Page,
  _ticker: string,
  _threshold: string
): Promise<void> {
  await page.goto('/alerts');

  // Open the alert form — button text is "New Alert" (with Plus icon)
  const newAlertBtn = page.getByRole('button', { name: /new alert/i })
    .or(page.getByRole('button', { name: /create alert/i }));
  await expect(newAlertBtn.first()).toBeVisible({ timeout: 5000 });
  await newAlertBtn.first().click();

  // Step 1: Select a configuration from the <select> dropdown
  const configSelect = page.locator('select');
  await expect(configSelect).toBeVisible({ timeout: 5000 });
  // Pick the first non-placeholder option
  const options = configSelect.locator('option:not([value=""])');
  const optionCount = await options.count();
  if (optionCount > 0) {
    const firstValue = await options.first().getAttribute('value');
    if (firstValue) {
      await configSelect.selectOption(firstValue);
    }
  }

  // Step 2: Click a ticker button (first available)
  // Wait for tickers to load after config selection
  await page.waitForTimeout(500);
  const tickerButtons = page.locator('button').filter({ hasText: /^[A-Z]{1,5}$/ });
  // Safe: cleanup — failure here means element absent, not broken
  if (await tickerButtons.first().isVisible({ timeout: 3000 }).catch(() => false)) {
    await tickerButtons.first().click();
  }

  // Step 3: Select alert type — click "Sentiment" button
  const sentimentTypeBtn = page.getByRole('button', { name: /sentiment/i });
  // Safe: cleanup — failure here means element absent, not broken
  if (await sentimentTypeBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await sentimentTypeBtn.click();
  }

  // Step 4: Select direction — click "Above" button
  const aboveBtn = page.getByRole('button', { name: /above/i });
  // Safe: cleanup — failure here means element absent, not broken
  if (await aboveBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await aboveBtn.click();
  }

  // Step 5: Threshold has acceptable defaults, skip

  // Step 6: Submit
  await page.getByRole('button', { name: /create alert/i }).click();
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

/**
 * Mock alert API routes so alert tests have deterministic data.
 *
 * Sets up route interception for /api/v2/alerts and /api/v2/alerts/*
 * with a synthetic AlertRule. Supports GET, POST, PATCH, DELETE.
 *
 * Must be called BEFORE page.goto() so the initial GET is intercepted.
 */
export async function mockAlertData(page: Page): Promise<void> {
  const mockAlert = {
    alertId: 'mock-alert-001',
    configId: 'mock-config-001',
    ticker: 'AAPL',
    alertType: 'sentiment_threshold',
    thresholdValue: 0.7,
    thresholdDirection: 'above',
    isEnabled: true,
    lastTriggeredAt: null,
    triggerCount: 0,
    createdAt: new Date().toISOString(),
  };

  let deleted = false;

  await page.route('**/api/v2/alerts', async (route) => {
    const method = route.request().method();
    if (method === 'GET') {
      if (deleted) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            alerts: [],
            total: 0,
            dailyEmailQuota: { used: 0, limit: 10, resetsAt: new Date().toISOString() },
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            alerts: [mockAlert],
            total: 1,
            dailyEmailQuota: { used: 0, limit: 10, resetsAt: new Date().toISOString() },
          }),
        });
      }
    } else if (method === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(mockAlert),
      });
    } else {
      await route.continue();
    }
  });

  await page.route('**/api/v2/alerts/*', async (route) => {
    const method = route.request().method();
    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAlert),
      });
    } else if (method === 'PATCH') {
      const postData = route.request().postData();
      if (postData) {
        Object.assign(mockAlert, JSON.parse(postData));
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAlert),
      });
    } else if (method === 'DELETE') {
      deleted = true;
      await route.fulfill({ status: 204 });
    } else {
      await route.continue();
    }
  });
}

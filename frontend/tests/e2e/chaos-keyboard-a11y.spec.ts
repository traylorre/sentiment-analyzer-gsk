// Target: Admin Chaos Dashboard (Next.js/Amplify) at /admin/chaos
import { test, expect, type Page, type BrowserContext } from '@playwright/test';
import {
  focusAndAssert,
  assertFocusIndicatorVisible,
  assertFocusOrder,
  assertNotFocusTrapped,
  assertModalFocusTrap,
  assertFocusOnVisibleElement,
} from './helpers/keyboard';

/**
 * Chaos Dashboard: Keyboard Navigation & Accessibility (Feature 1361)
 *
 * Validates 8 keyboard/a11y concerns on /admin/chaos:
 * - US1: Programmatic focus on safety controls and tab buttons
 * - US2: Keyboard activation (Enter/Space) of buttons and tab switches
 * - US3: Canvas focus escape (metrics panel does not trap focus)
 * - US4: View transition focus management after tab switch
 * - US5: Modal focus trap (Gate and Andon dialogs)
 * - US6: Focus order between interactive elements
 * - US7: Visible focus indicators on interactive elements
 * - US8: Non-interactive elements have no tabindex
 *
 * Auth approach: Route interception + webpack module cache store patching.
 * Tier 1 (middleware): Cookies bypass Next.js middleware admin route check.
 * Tier 2 (client-side): After page load, we find the zustand auth store
 * via the webpack module cache (__webpack_require__.c) and call setState
 * to set role='operator', which triggers React re-render.
 *
 * Replaces deleted keyboard-nav.spec.ts which targeted the removed Alpine.js
 * chaos dashboard.
 */

// ─── Auth & API Mock Setup ──────────────────────────────────────────────────

/**
 * Install addInitScript that captures __webpack_require__ by intercepting
 * the webpackChunk_N_E array's push method. When webpack loads a new chunk,
 * the runtime function receives __webpack_require__ as a parameter. We wrap
 * the runtime to capture this reference on window.__capturedWebpackRequire.
 */
async function captureWebpackRequire(page: Page): Promise<void> {
  await page.addInitScript(() => {
    (window as any).__capturedWebpackRequire = null;

    const checkInterval = setInterval(() => {
      const chunkArray = (self as any).webpackChunk_N_E;
      if (!chunkArray || (chunkArray as any).__hooked) return;
      (chunkArray as any).__hooked = true;

      const origPush = chunkArray.push.bind(chunkArray);
      chunkArray.push = function (...args: any[]) {
        const chunk = args[0];
        if (
          Array.isArray(chunk) &&
          chunk.length >= 3 &&
          typeof chunk[2] === 'function'
        ) {
          const origRuntime = chunk[2];
          chunk[2] = function (require: any) {
            if (!(window as any).__capturedWebpackRequire) {
              (window as any).__capturedWebpackRequire = require;
            }
            return origRuntime.call(this, require);
          };
        }
        return origPush(...args);
      };
      clearInterval(checkInterval);
    }, 5);
  });
}

/**
 * Set Tier 1 cookies to pass Next.js middleware admin route check.
 * Middleware checks: hasUpgradedAuth = isAuthenticated && !isAnonymous
 */
async function setAuthCookies(context: BrowserContext): Promise<void> {
  await context.addCookies([
    {
      name: 'sentiment-access-token',
      value: 'mock-operator-token-e2e',
      domain: 'localhost',
      path: '/',
    },
    {
      name: 'sentiment-is-anonymous',
      value: 'false',
      domain: 'localhost',
      path: '/',
    },
  ]);
}

/**
 * Mock auth and chaos API endpoints via Playwright route interception.
 */
async function mockApiEndpoints(page: Page): Promise<void> {
  // Auth: anonymous session creation
  await page.route('**/api/v2/auth/anonymous', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 'e2e-operator-user',
          token: 'mock-operator-token-e2e',
          auth_type: 'anonymous',
          created_at: new Date().toISOString(),
          session_expires_at: new Date(Date.now() + 86400000).toISOString(),
          storage_hint: 'session',
        }),
      });
    } else {
      await route.continue();
    }
  });

  // Auth: user profile
  await page.route('**/api/v2/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        auth_type: 'magic_link',
        email_masked: 'o***@test.com',
        configs_count: 0,
        max_configs: 10,
        session_expires_in_seconds: 86400,
        role: 'operator',
        linked_providers: [],
        verification: 'verified',
        last_provider_used: null,
      }),
    });
  });

  // Auth: sign out / refresh (prevent errors)
  await page.route('**/api/v2/auth/signout', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{}',
    });
  });
  await page.route('**/api/v2/auth/refresh', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{}',
    });
  });

  // Chaos: experiments list
  await page.route('**/chaos/experiments', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ experiments: [] }),
      });
    } else {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: '{}',
      });
    }
  });

  // Chaos: gate state
  await page.route('**/chaos/gate', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ state: 'disarmed' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ state: 'armed' }),
      });
    }
  });

  // Chaos: metrics
  await page.route('**/chaos/metrics', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ groups: [] }),
    });
  });

  // Chaos: reports
  await page.route('**/chaos/reports**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ reports: [], next_cursor: null }),
    });
  });

  // Chaos: health check
  await page.route('**/chaos/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        api: { status: 'healthy', latency_ms: 10 },
        dynamodb: { status: 'healthy', latency_ms: 15 },
        ssm: { status: 'healthy', latency_ms: 12 },
      }),
    });
  });

  // Chaos: andon cord
  await page.route('**/chaos/andon-cord', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        kill_switch_set: true,
        experiments_found: 0,
        restored: 0,
        failed: 0,
        errors: [],
      }),
    });
  });

  // Chaos: trends
  await page.route('**/chaos/trends**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });
}

/**
 * Patch the zustand auth store to set role='operator' via the webpack
 * module cache. Finds useAuthStore in __webpack_require__.c and calls
 * setState to merge operator role into the existing user state.
 *
 * Retries up to 5 times with 200ms delay to handle race conditions
 * where the webpack require capture or store initialization hasn't
 * completed yet (common with parallel Playwright workers).
 */
async function patchAuthStoreRole(page: Page): Promise<void> {
  let patched = false;

  for (let attempt = 0; attempt < 5; attempt++) {
    patched = await page.evaluate(() => {
      const req = (window as any).__capturedWebpackRequire;
      if (!req?.c) return false;

      // Find the auth store module in the webpack cache
      const authModuleId = Object.keys(req.c).find(
        (id) => id.includes('auth-store'),
      );
      if (!authModuleId) return false;

      const authModule = req.c[authModuleId];
      if (!authModule?.exports?.useAuthStore) return false;

      const store = authModule.exports.useAuthStore;
      const state = store.getState();
      if (!state?.user) return false;

      // Patch user role from 'anonymous' to 'operator'
      store.setState({
        user: {
          ...state.user,
          role: 'operator',
          authType: 'magic_link',
        },
        isAnonymous: false,
      });

      return store.getState().user?.role === 'operator';
    });

    if (patched) break;
    await page.waitForTimeout(200);
  }

  if (!patched) {
    throw new Error(
      'Failed to patch auth store role. The zustand auth store was not found ' +
        'in the webpack module cache, or the user state was not initialized.',
    );
  }
}

/**
 * Navigate to /admin/chaos with full auth setup and API mocking.
 *
 * Auth flow:
 * 1. captureWebpackRequire (addInitScript) captures __webpack_require__
 * 2. setAuthCookies sets middleware Tier 1 cookies
 * 3. mockApiEndpoints intercepts all auth and chaos API calls
 * 4. page.goto('/admin/chaos') loads the page (shows ForbiddenPage)
 * 5. patchAuthStoreRole sets user.role='operator' via webpack module cache
 * 6. React re-renders automatically (zustand subscribers fire)
 * 7. chaos-tabs becomes visible
 */
async function navigateToChaos(
  page: Page,
  context: BrowserContext,
): Promise<void> {
  await captureWebpackRequire(page);
  await setAuthCookies(context);
  await mockApiEndpoints(page);

  // Navigate (will initially show ForbiddenPage)
  await page.goto('/admin/chaos');
  await page.waitForSelector(
    '[data-testid="chaos-tabs"], h1:text("Access Denied")',
    { timeout: 15000 },
  );

  // If already showing chaos-tabs, skip patching
  const chaosTabs = page.locator('[data-testid="chaos-tabs"]');
  if (await chaosTabs.isVisible().catch(() => false)) return;

  // Patch auth store role to operator
  await patchAuthStoreRole(page);

  // Wait for React re-render after zustand state change
  await expect(chaosTabs).toBeVisible({ timeout: 10000 });
}

// ─── Test Suite ─────────────────────────────────────────────────────────────

test.describe('Chaos Dashboard: Keyboard Navigation & Accessibility', () => {
  // Desktop Chrome only per NFR-001
  test.use({ viewport: { width: 1280, height: 720 } });
  test.setTimeout(30_000);

  test.beforeEach(async ({ page, context }) => {
    await navigateToChaos(page, context);
  });

  // ── US1: Programmatic Focus ─────────────────────────────────���───────────

  test.describe('Programmatic Focus (US1)', () => {
    test('safety control buttons receive programmatic focus', async ({
      page,
    }) => {
      await focusAndAssert(page.locator('[data-testid="health-check-button"]'));
      await focusAndAssert(page.locator('[data-testid="gate-toggle-button"]'));
      await focusAndAssert(page.locator('[data-testid="andon-cord-button"]'));
    });

    test('tab buttons receive programmatic focus', async ({ page }) => {
      await focusAndAssert(
        page.locator('[data-testid="chaos-tab-experiments"]'),
      );
      await focusAndAssert(page.locator('[data-testid="chaos-tab-reports"]'));
    });
  });

  // ── US2: Keyboard Activation ────────────────────────────────────────────���─

  test.describe('Keyboard Activation (US2)', () => {
    test('Enter activates tab switch', async ({ page }) => {
      const reportsTab = page.locator('[data-testid="chaos-tab-reports"]');
      await reportsTab.focus();
      await page.keyboard.press('Enter');

      await expect(page.locator('[data-testid="reports-tab"]')).toBeVisible();
      await expect(
        page.locator('[data-testid="experiments-tab"]'),
      ).not.toBeVisible();

      const experimentsTab = page.locator(
        '[data-testid="chaos-tab-experiments"]',
      );
      await experimentsTab.focus();
      await page.keyboard.press('Enter');
      await expect(
        page.locator('[data-testid="experiments-tab"]'),
      ).toBeVisible();
    });

    test('Enter opens Gate dialog', async ({ page }) => {
      const gateButton = page.locator('[data-testid="gate-toggle-button"]');
      await gateButton.focus();
      await page.keyboard.press('Enter');
      await expect(page.locator('[role="dialog"]')).toBeVisible({
        timeout: 5000,
      });
      await page.keyboard.press('Escape');
      await expect(page.locator('[role="dialog"]')).not.toBeVisible({
        timeout: 5000,
      });
    });

    test('Space opens Andon dialog', async ({ page }) => {
      const andonButton = page.locator('[data-testid="andon-cord-button"]');
      await andonButton.focus();
      await page.keyboard.press('Space');
      await expect(page.locator('[role="dialog"]')).toBeVisible({
        timeout: 5000,
      });
      await page.keyboard.press('Escape');
      await expect(page.locator('[role="dialog"]')).not.toBeVisible({
        timeout: 5000,
      });
    });
  });

  // ── US3: Canvas Focus Escape ──────────────────────────────────────────────

  test.describe('Canvas Focus Escape (US3)', () => {
    test('Tab escapes past metrics panel area', async ({ page }) => {
      // With empty metrics (default mock), verify the refresh button
      // does not trap focus. This is a regression-prevention test.
      const refreshButton = page.locator('[data-testid="refresh-metrics"]');

      if (await refreshButton.isVisible()) {
        await assertNotFocusTrapped(page, '[data-testid="refresh-metrics"]');
      }

      // If canvas exists (non-empty metrics), verify it doesn't trap focus
      const canvas = page.locator('[data-testid="metrics-panel"] canvas');
      if ((await canvas.count()) > 0) {
        await assertNotFocusTrapped(
          page,
          '[data-testid="metrics-panel"] canvas',
        );
      }
    });
  });

  // ── US4: View Transition Focus ────────────────────────────────────────────

  test.describe('View Transition Focus (US4)', () => {
    test('focus on visible element after tab switch', async ({ page }) => {
      // Switch to Reports tab
      const reportsTab = page.locator('[data-testid="chaos-tab-reports"]');
      await reportsTab.click();
      await expect(page.locator('[data-testid="reports-tab"]')).toBeVisible();
      await assertFocusOnVisibleElement(page);

      // Switch back to Experiments tab
      const experimentsTab = page.locator(
        '[data-testid="chaos-tab-experiments"]',
      );
      await experimentsTab.click();
      await expect(
        page.locator('[data-testid="experiments-tab"]'),
      ).toBeVisible();
      await assertFocusOnVisibleElement(page);
    });
  });

  // ── US5: Modal Focus Trap ─────────────────────────────────────────────────
  //
  // Note: The Gate and Andon dialogs use <Dialog open={state} onOpenChange={setState}>
  // without <DialogTrigger>, so Radix does NOT track the opener element for
  // automatic focus return. Focus return to trigger is NOT expected.
  // We verify: (1) focus moves inside dialog, (2) Tab stays trapped, (3) dialog closes.

  test.describe('Modal Focus Trap (US5)', () => {
    test('Gate dialog traps focus inside when open', async ({ page }) => {
      const trigger = page.locator('[data-testid="gate-toggle-button"]');
      await trigger.click();
      const modal = page.locator('[role="dialog"]');
      await expect(modal).toBeVisible({ timeout: 5000 });

      // Verify focus is inside the dialog
      const focusInModal = await page.evaluate(() => {
        const dialog = document.querySelector('[role="dialog"]');
        return dialog?.contains(document.activeElement) ?? false;
      });
      expect(focusInModal).toBe(true);

      // Tab inside dialog, verify focus stays inside
      await page.keyboard.press('Tab');
      const stillInModal = await page.evaluate(() => {
        const dialog = document.querySelector('[role="dialog"]');
        return dialog?.contains(document.activeElement) ?? false;
      });
      expect(stillInModal).toBe(true);

      // Close dialog via Cancel
      await page.locator('button:has-text("Cancel")').click();
      await expect(modal).not.toBeVisible({ timeout: 5000 });
    });

    test('Andon dialog traps focus inside when open', async ({ page }) => {
      const trigger = page.locator('[data-testid="andon-cord-button"]');
      await trigger.click();
      const modal = page.locator('[role="dialog"]');
      await expect(modal).toBeVisible({ timeout: 5000 });

      // Verify focus is inside the dialog
      const focusInModal = await page.evaluate(() => {
        const dialog = document.querySelector('[role="dialog"]');
        return dialog?.contains(document.activeElement) ?? false;
      });
      expect(focusInModal).toBe(true);

      // Tab inside dialog, verify focus stays inside
      await page.keyboard.press('Tab');
      const stillInModal = await page.evaluate(() => {
        const dialog = document.querySelector('[role="dialog"]');
        return dialog?.contains(document.activeElement) ?? false;
      });
      expect(stillInModal).toBe(true);

      // Close dialog via Cancel
      await page.locator('button:has-text("Cancel")').click();
      await expect(modal).not.toBeVisible({ timeout: 5000 });
    });

    test('Andon dialog closes on Escape key', async ({ page }) => {
      const trigger = page.locator('[data-testid="andon-cord-button"]');
      await trigger.click();
      const modal = page.locator('[role="dialog"]');
      await expect(modal).toBeVisible({ timeout: 5000 });

      await page.keyboard.press('Escape');

      await expect(modal).not.toBeVisible({ timeout: 5000 });

      // After close, focus should be on a visible element (not necessarily the trigger,
      // since these dialogs don't use <DialogTrigger> for automatic focus return)
      await assertFocusOnVisibleElement(page);
    });
  });

  // ── US6: Focus Order ──────────────────────────────────────────────────────

  test.describe('Focus Order (US6)', () => {
    test('tab buttons in logical order', async ({ page }) => {
      await assertFocusOrder(
        page,
        '[data-testid="chaos-tab-experiments"]',
        '[data-testid="chaos-tab-reports"]',
      );
    });

    test('safety buttons in logical order', async ({ page }) => {
      await assertFocusOrder(
        page,
        '[data-testid="health-check-button"]',
        '[data-testid="gate-toggle-button"]',
      );
      await assertFocusOrder(
        page,
        '[data-testid="gate-toggle-button"]',
        '[data-testid="andon-cord-button"]',
      );
    });
  });

  // ── US7: Focus Indicators ─────────────────────────────────────────────────

  test.describe('Focus Indicators (US7)', () => {
    test('interactive elements show visible focus ring', async ({ page }) => {
      const selectors = [
        '[data-testid="chaos-tab-experiments"]',
        '[data-testid="chaos-tab-reports"]',
        '[data-testid="health-check-button"]',
        '[data-testid="gate-toggle-button"]',
        '[data-testid="andon-cord-button"]',
      ];

      for (const selector of selectors) {
        const element = page.locator(selector);
        await element.focus();
        await assertFocusIndicatorVisible(element);
      }
    });
  });

  // ── US8: Non-Interactive Elements ─────────────────────────────────────────

  test.describe('Non-Interactive Elements (US8)', () => {
    test('decorative elements have no tabindex', async ({ page }) => {
      // Gate state badge
      const gateBadge = page.locator('[data-testid="gate-state-badge"]');
      await expect(gateBadge).toBeVisible();
      await expect(gateBadge).not.toHaveAttribute('tabindex');

      // Verdict badges (may not be visible with empty data)
      const verdictBadges = page.locator('[data-testid="verdict-badge"]');
      const badgeCount = await verdictBadges.count();
      for (let i = 0; i < badgeCount; i++) {
        await expect(verdictBadges.nth(i)).not.toHaveAttribute('tabindex');
      }

      // Health cards (only visible after health check click)
      const healthCards = page.locator('[data-testid^="health-card-"]');
      const cardCount = await healthCards.count();
      for (let i = 0; i < cardCount; i++) {
        await expect(healthCards.nth(i)).not.toHaveAttribute('tabindex');
      }
    });
  });
});

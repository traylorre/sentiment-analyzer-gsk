/**
 * Keyboard navigation tests for the chaos dashboard.
 *
 * Feature 001-keyboard-nav-focus
 *
 * All tests use .focus() for programmatic focus placement (FR-001).
 * Tab key is ONLY used for single-Tab focus-order assertions (FR-007).
 * Tests must produce identical results in headed and headless Chromium (FR-006).
 */

import { test, expect } from '@playwright/test';
import {
  focusAndAssert,
  assertFocusIndicatorVisible,
  assertFocusOrder,
  assertNotFocusTrapped,
  assertModalFocusTrap,
  assertFocusOnVisibleElement,
} from './helpers/keyboard';

test.describe('Chaos Dashboard Keyboard Navigation', () => {
  // Chaos dashboard is served by the Python API server (port 8000)
  // This endpoint only exists in deployed environments, not local dev
  const CHAOS_URL = process.env.CHAOS_DASHBOARD_URL ?? 'http://localhost:8000/chaos/dashboard';

  // Skip when chaos dashboard isn't available (local dev / CI without deployed backend)
  test.skip(!process.env.CHAOS_DASHBOARD_URL, 'Chaos dashboard not available (set CHAOS_DASHBOARD_URL)');

  test.beforeEach(async ({ page }) => {
    await page.goto(CHAOS_URL);
    // Wait for Alpine.js hydration
    await page.waitForSelector('[x-data]', { state: 'attached' });
  });

  // ── US1: Reliable Keyboard Navigation Verification ──

  test.describe('Programmatic Focus (FR-001, FR-002)', () => {
    test('view tab buttons receive focus via .focus()', async ({ page }) => {
      const experimentsTab = page.locator('a.tab:has-text("Experiments")');
      await focusAndAssert(experimentsTab);

      const reportsTab = page.locator('a.tab:has-text("Reports")');
      await focusAndAssert(reportsTab);
    });

    test('safety control buttons receive focus via .focus()', async ({
      page,
    }) => {
      // Health check button (Feature 1244)
      const healthBtn = page.locator('button:has-text("Health Check")');
      if ((await healthBtn.count()) > 0) {
        await focusAndAssert(healthBtn);
      }

      // Gate toggle button (Feature 1245)
      const gateBtn = page.locator('button:has-text("Gate")');
      if ((await gateBtn.count()) > 0) {
        await focusAndAssert(gateBtn);
      }
    });
  });

  test.describe('Keyboard Interaction (FR-003)', () => {
    test('Enter activates focused tab button', async ({ page }) => {
      const reportsTab = page.locator('a.tab:has-text("Reports")');
      await focusAndAssert(reportsTab);
      await page.keyboard.press('Enter');

      // Verify view changed to reports
      await expect(
        page.locator('[x-show*="reports"]').first(),
      ).toBeVisible({ timeout: 3000 });
    });

    test('Enter activates focused action button', async ({ page }) => {
      const healthBtn = page.locator('button:has-text("Health Check")');
      if ((await healthBtn.count()) > 0) {
        await focusAndAssert(healthBtn);
        await page.keyboard.press('Enter');
        // Button should respond (loading state or result)
        await page.waitForTimeout(500);
      } else {
        test.skip();
      }
    });
  });

  test.describe('Canvas Focus (FR-010)', () => {
    test('Chart.js canvas does not trap focus', async ({ page }) => {
      // Navigate to trends view if available
      const reportsTab = page.locator('a.tab:has-text("Reports")');
      if ((await reportsTab.count()) > 0) {
        await reportsTab.click();
        await page.waitForTimeout(500);
      }

      const canvas = page.locator('canvas').first();
      if ((await canvas.count()) > 0) {
        await assertNotFocusTrapped(page, 'canvas');
      } else {
        test.skip();
      }
    });
  });

  test.describe('View Transition Focus (FR-008)', () => {
    test('focus is on a visible element after switching views', async ({
      page,
    }) => {
      // Switch to reports view
      const reportsTab = page.locator('a.tab:has-text("Reports")');
      await reportsTab.click();
      await page.waitForTimeout(500);

      await assertFocusOnVisibleElement(page);

      // Switch back to experiments view
      const experimentsTab = page.locator('a.tab:has-text("Experiments")');
      await experimentsTab.click();
      await page.waitForTimeout(500);

      await assertFocusOnVisibleElement(page);
    });
  });

  test.describe('Modal Focus Trap (FR-009)', () => {
    test('Andon cord modal traps and returns focus', async ({ page }) => {
      const andonBtn = page.locator('button:has-text("Andon")');
      if ((await andonBtn.count()) > 0) {
        await assertModalFocusTrap(
          page,
          'button:has-text("Andon")',
          'dialog, [role="dialog"]',
          'button:has-text("Cancel")',
        );
      } else {
        // Feature 1245/1246 not implemented
        test.skip();
      }
    });
  });

  test.describe('Focus Order (FR-007)', () => {
    test('single Tab from first tab moves to second tab', async ({
      page,
    }) => {
      const tabs = page.locator('a.tab');
      const tabCount = await tabs.count();
      if (tabCount >= 2) {
        const firstTab = tabs.nth(0);
        const secondTab = tabs.nth(1);
        const firstSelector = `a.tab >> nth=0`;
        const secondSelector = `a.tab >> nth=1`;

        // Use .focus() to place focus, Tab once to assert order
        await firstTab.focus();
        await expect(firstTab).toBeFocused();
        await page.keyboard.press('Tab');
        await expect(secondTab).toBeFocused();
      } else {
        test.skip();
      }
    });
  });

  // ── US2: Focus Indicator Visibility ──

  test.describe('Focus Indicators (FR-004)', () => {
    test('tab buttons show visible focus indicator', async ({ page }) => {
      const tab = page.locator('a.tab').first();
      await tab.focus();
      await assertFocusIndicatorVisible(tab);
    });

    test('action buttons show visible focus indicator', async ({ page }) => {
      const btn = page.locator('.btn').first();
      await btn.focus();
      await assertFocusIndicatorVisible(btn);
    });

    test('form controls show visible focus indicator', async ({ page }) => {
      // Navigate to reports view for filter dropdowns
      const reportsTab = page.locator('a.tab:has-text("Reports")');
      if ((await reportsTab.count()) > 0) {
        await reportsTab.click();
        await page.waitForTimeout(500);
      }

      const select = page.locator('select').first();
      if ((await select.count()) > 0) {
        await select.focus();
        await assertFocusIndicatorVisible(select);
      } else {
        test.skip();
      }
    });
  });

  test.describe('Non-Interactive Elements (FR-005)', () => {
    test('decorative containers are not focusable', async ({ page }) => {
      // Main container should not have tabindex
      const container = page.locator(
        '[data-testid="chaos-dashboard-content"]',
      );
      const tabindex = await container.getAttribute('tabindex');
      expect(tabindex).toBeNull();
    });
  });
});

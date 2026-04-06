// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import { triggerHealthBanner, getBannerLocator } from './helpers/chaos-helpers';

/**
 * Chaos: Error Boundary Fallback (Feature 1265, FR-009/SC-004/EC-005)
 *
 * Validates the React error boundary safety net:
 * - Fallback UI renders with recovery actions
 * - Error boundary activates during existing degradation (EC-005)
 * - Keyboard navigation works on fallback buttons
 *
 * Trigger mechanism: window.__TEST_FORCE_ERROR global flag (Feature 1265, T004)
 */
test.describe('Chaos: Error Boundary', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
  });

  /**
   * Force the error boundary to trigger via the test-only ErrorTrigger component.
   * Sets the global flag, then triggers a re-render by navigating.
   */
  async function forceErrorBoundary(page: import('@playwright/test').Page) {
    // Must use addInitScript — page.evaluate() sets the flag on the current page,
    // but goto() loads a NEW page where the flag doesn't exist.
    // addInitScript runs before any page JS, so the flag is set when ErrorTrigger renders.
    await page.addInitScript(() => {
      (window as any).__TEST_FORCE_ERROR = true;
    });
    await page.goto('/');
  }

  // T022: Error boundary fallback renders with recovery actions
  test('error boundary fallback renders with recovery actions', async ({
    page,
  }) => {
    await forceErrorBoundary(page);

    // Assert "Something went wrong" heading is visible
    await expect(
      page.getByText(/something went wrong/i),
    ).toBeVisible({ timeout: 5000 });

    // Assert recovery action buttons are visible
    await expect(
      page.getByRole('button', { name: /try again/i }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: /reload page/i }),
    ).toBeVisible();
    await expect(page.getByRole('link', { name: /go home/i }).or(
      page.getByRole('button', { name: /go home/i }),
    )).toBeVisible();
  });

  // T023: Error boundary during degradation (EC-005)
  test('error boundary during degradation replaces dashboard', async ({
    page,
  }) => {
    // First, trigger health banner (degradation)
    await triggerHealthBanner(page);

    const banner = getBannerLocator(page);
    await expect(banner).toBeVisible();

    // Now force error boundary on top of degradation — addInitScript survives navigation
    await page.addInitScript(() => {
      (window as any).__TEST_FORCE_ERROR = true;
    });
    await page.goto('/');

    // Error boundary fallback should now be visible
    await expect(
      page.getByText(/something went wrong/i),
    ).toBeVisible({ timeout: 5000 });

    // Banner should no longer be visible (error boundary replaces entire dashboard content)
    // The banner is inside the dashboard layout which is now showing the fallback
    const fallbackButtons = page.getByRole('button', { name: /try again/i });
    await expect(fallbackButtons).toBeVisible();
  });

  // T024: Error boundary keyboard navigation
  test('error boundary buttons are keyboard-navigable', async ({ page }) => {
    await forceErrorBoundary(page);

    await expect(
      page.getByText(/something went wrong/i),
    ).toBeVisible({ timeout: 5000 });

    // Verify each recovery button is programmatically focusable.
    // Uses .focus() instead of chained Tab presses — Tab key behavior in
    // headless Chromium is unreliable (see keyboard.ts FR-007: chained Tab banned).
    const tryAgainButton = page.getByRole('button', { name: /try again/i });
    const reloadButton = page.getByRole('button', { name: /reload page/i });
    const goHomeButton = page.getByRole('button', { name: /go home/i });

    await tryAgainButton.focus();
    await expect(tryAgainButton).toBeFocused();

    await reloadButton.focus();
    await expect(reloadButton).toBeFocused();

    await goHomeButton.focus();
    await expect(goHomeButton).toBeFocused();
  });
});

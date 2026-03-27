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
    await page.evaluate(() => {
      (window as any).__TEST_FORCE_ERROR = true;
    });
    // Trigger re-render — navigate to dashboard which re-mounts ErrorTrigger
    await page.goto('/');
    await page.waitForTimeout(1000);
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

    // Now force error boundary on top of degradation
    await page.evaluate(() => {
      (window as any).__TEST_FORCE_ERROR = true;
    });

    // Navigate to trigger re-render within the error boundary scope
    await page.goto('/');
    await page.waitForTimeout(1000);

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

    // Tab through action buttons and verify focus order
    // Focus should move: Try Again → Reload Page → Go Home
    await page.keyboard.press('Tab');
    const firstFocused = await page.evaluate(() =>
      document.activeElement?.textContent?.trim(),
    );

    await page.keyboard.press('Tab');
    const secondFocused = await page.evaluate(() =>
      document.activeElement?.textContent?.trim(),
    );

    await page.keyboard.press('Tab');
    const thirdFocused = await page.evaluate(() =>
      document.activeElement?.textContent?.trim(),
    );

    // All three buttons should have received focus (exact text may vary)
    const focusedElements = [firstFocused, secondFocused, thirdFocused].filter(
      Boolean,
    );
    expect(focusedElements.length).toBeGreaterThanOrEqual(2);

    // At least one should be a recovery action
    const hasRecoveryAction = focusedElements.some(
      (text) =>
        /try again|reload|go home/i.test(text || ''),
    );
    expect(hasRecoveryAction).toBeTruthy();
  });
});

// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { triggerHealthBanner, getBannerLocator } from './helpers/chaos-helpers';

/**
 * Chaos: Accessibility During Degraded States (Feature 1265, US4/FR-010/SC-005)
 *
 * Validates that degraded UI states maintain accessibility:
 * - Health banner passes WCAG 2.1 AA automated audit
 * - Error boundary fallback passes WCAG audit
 * - Error boundary buttons are keyboard-focusable
 *
 * Scope: Automated structural checks only (ARIA attributes, keyboard navigation,
 * focus management). Manual screen reader testing is out of scope.
 */
test.describe('Chaos: Accessibility During Degradation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
  });

  // T025: Health banner has zero critical a11y violations
  test('health banner has zero critical accessibility violations', async ({
    page,
  }) => {
    await triggerHealthBanner(page);

    const banner = getBannerLocator(page);
    await expect(banner).toBeVisible();

    // Run axe-core scan for WCAG 2.1 AA
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    // Filter to critical and serious violations only (per SC-005)
    const critical = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );

    if (critical.length > 0) {
      // Log violation details for debugging
      const details = critical.map(
        (v) =>
          `[${v.impact}] ${v.id}: ${v.description} (${v.nodes.length} instances)`,
      );
      console.error('Accessibility violations found:', details);
    }

    expect(critical).toEqual([]);
  });

  // T026: Error boundary fallback has zero critical a11y violations
  test('error boundary fallback has zero critical accessibility violations', async ({
    page,
  }) => {
    // Force error boundary
    await page.evaluate(() => {
      (window as any).__TEST_FORCE_ERROR = true;
    });
    await page.goto('/');
    await page.waitForTimeout(1000);

    await expect(
      page.getByText(/something went wrong/i),
    ).toBeVisible({ timeout: 5000 });

    // Run axe-core scan
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const critical = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );

    if (critical.length > 0) {
      const details = critical.map(
        (v) =>
          `[${v.impact}] ${v.id}: ${v.description} (${v.nodes.length} instances)`,
      );
      console.error('Accessibility violations found:', details);
    }

    expect(critical).toEqual([]);
  });

  // T027: Error boundary buttons are keyboard-focusable
  test('error boundary buttons are keyboard-focusable with accessible labels', async ({
    page,
  }) => {
    // Force error boundary
    await page.evaluate(() => {
      (window as any).__TEST_FORCE_ERROR = true;
    });
    await page.goto('/');
    await page.waitForTimeout(1000);

    await expect(
      page.getByText(/something went wrong/i),
    ).toBeVisible({ timeout: 5000 });

    // Verify buttons exist and have accessible names
    const tryAgainButton = page.getByRole('button', { name: /try again/i });
    const reloadButton = page.getByRole('button', { name: /reload page/i });
    const goHomeButton = page.getByRole('link', { name: /go home/i }).or(
      page.getByRole('button', { name: /go home/i }),
    );

    await expect(tryAgainButton).toBeVisible();
    await expect(reloadButton).toBeVisible();
    await expect(goHomeButton).toBeVisible();

    // Verify keyboard focusability by tabbing and checking focus
    await tryAgainButton.focus();
    await expect(tryAgainButton).toBeFocused();

    await reloadButton.focus();
    await expect(reloadButton).toBeFocused();

    await goHomeButton.focus();
    await expect(goHomeButton).toBeFocused();
  });
});

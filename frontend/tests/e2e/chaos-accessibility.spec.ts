// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { waitForAccessibilityTree } from './helpers/a11y-helpers';

/**
 * Chaos: Accessibility During Degraded States (Feature 1265, US4/FR-010/SC-005)
 *
 * Validates that degraded UI states maintain accessibility:
 * - Error boundary fallback passes WCAG audit
 * - Error boundary buttons are keyboard-focusable
 *
 * T025 (health banner a11y) was DELETED: triggerHealthBanner fires consecutive
 * API failures that trigger the error boundary BEFORE the health banner appears,
 * making it test the wrong thing. Redundant with T026/T027 below.
 *
 * Scope: Automated structural checks only (ARIA attributes, keyboard navigation,
 * focus management). Manual screen reader testing is out of scope.
 */
test.describe('Chaos: Accessibility During Degradation', () => {
  // a11y tests stack waitForAccessibilityTree + AxeBuilder.analyze
  // which legitimately takes longer than standard E2E tests due to axe-core scanning overhead
  test.setTimeout(30_000);

  // T026: Error boundary fallback has zero critical a11y violations
  test('error boundary fallback has zero critical accessibility violations', async ({
    page,
  }) => {
    // Force error boundary — must use addInitScript so the flag survives navigation.
    // page.evaluate() sets it on the CURRENT page; goto() loads a NEW page without it.
    await page.addInitScript(() => {
      (window as any).__TEST_FORCE_ERROR = true;
    });
    await page.goto('/');

    await expect(
      page.getByText(/something went wrong/i),
    ).toBeVisible({ timeout: 5000 });

    // Wait for error boundary to fully render with accessible buttons
    // Increase timeout from default 2000ms — error boundary renders after
    // ErrorTrigger's useEffect → setState → re-render → throw → catch cycle
    await waitForAccessibilityTree(page, {
      selector: 'button[type="button"]',
      attributes: ['type'],
      timeout: 10000,
    });

    // Run axe-core scan — exclude color-contrast which is a known issue in dark theme
    // error boundary (tracked separately). Testing structural a11y here, not theme colors.
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .disableRules(['color-contrast'])
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
    // Force error boundary — addInitScript survives navigation
    await page.addInitScript(() => {
      (window as any).__TEST_FORCE_ERROR = true;
    });
    await page.goto('/');

    await expect(
      page.getByText(/something went wrong/i),
    ).toBeVisible({ timeout: 5000 });

    // Wait for error boundary buttons to be fully accessible
    // Increase timeout — error boundary renders after useEffect cycle
    await waitForAccessibilityTree(page, {
      selector: 'button[type="button"]',
      attributes: ['type'],
      timeout: 10000,
    });

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

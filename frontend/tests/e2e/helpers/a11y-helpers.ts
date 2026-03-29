import { Page } from '@playwright/test';

interface A11yWaitOptions {
  /** CSS selector for the element to check */
  selector: string;
  /** ARIA attributes that must have non-empty values */
  attributes?: string[];
  /** Maximum wait time in ms (default: 5000) */
  timeout?: number;
}

/**
 * Wait for the browser's accessibility tree to stabilize for a given element.
 *
 * Bridges the gap between DOM visibility (element in viewport) and
 * accessibility readiness (ARIA attributes computed). Use between
 * toBeVisible() and AxeBuilder.analyze().
 *
 * Why this exists: toBeVisible() confirms the element is in the DOM,
 * but ARIA attributes and accessible names are computed asynchronously
 * by the browser. Running axe-core before this computation completes
 * produces false-positive violations.
 */
export async function waitForAccessibilityTree(
  page: Page,
  options: A11yWaitOptions
): Promise<void> {
  const { selector, attributes = [], timeout = 5000 } = options;

  await page.waitForFunction(
    ({ sel, attrs }) => {
      const el = document.querySelector(sel);
      if (!el) return false;
      if (attrs.length === 0) return true;
      return attrs.every((attr: string) => {
        const val = el.getAttribute(attr);
        return val !== null && val !== '';
      });
    },
    { sel: selector, attrs: attributes },
    { timeout, polling: 50 }
  );
}

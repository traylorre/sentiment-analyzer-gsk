/**
 * Keyboard navigation test helpers for chaos dashboard.
 *
 * Uses programmatic .focus() instead of Tab key simulation
 * to ensure reliable, flake-free keyboard testing in headless Chromium.
 *
 * Feature 001-keyboard-nav-focus
 */

import { Page, Locator, expect } from '@playwright/test';

/**
 * Focus an element and assert it received focus (FR-001, FR-002).
 * Uses programmatic .focus() — never Tab key.
 */
export async function focusAndAssert(locator: Locator): Promise<void> {
  await locator.focus();
  await expect(locator).toBeFocused();
}

/**
 * Assert a focused element has a visible focus indicator (FR-004).
 * Checks computed CSS for outline or box-shadow.
 */
export async function assertFocusIndicatorVisible(
  locator: Locator,
): Promise<void> {
  await expect(locator).toBeFocused();

  const hasIndicator = await locator.evaluate((el) => {
    const style = window.getComputedStyle(el);
    const outlineWidth = parseFloat(style.outlineWidth);
    const outlineStyle = style.outlineStyle;
    const boxShadow = style.boxShadow;

    const hasOutline = outlineWidth > 0 && outlineStyle !== 'none';
    const hasBoxShadow = boxShadow !== 'none' && boxShadow !== '';

    return hasOutline || hasBoxShadow;
  });

  expect(hasIndicator).toBe(true);
}

/**
 * Assert focus order: focus element A, Tab once, expect element B focused (FR-007).
 * This is the ONLY permitted Tab usage — single Tab for focus-order assertion.
 * Chained Tab presses (2+) are banned.
 */
export async function assertFocusOrder(
  page: Page,
  selectorA: string,
  selectorB: string,
): Promise<void> {
  const elementA = page.locator(selectorA);
  await elementA.focus();
  await expect(elementA).toBeFocused();

  await page.keyboard.press('Tab');
  await expect(page.locator(selectorB)).toBeFocused();
}

/**
 * Assert an element does not trap focus (FR-005, FR-010).
 * Focus the element, Tab once, assert focus moved to a different element.
 */
export async function assertNotFocusTrapped(
  page: Page,
  selector: string,
): Promise<void> {
  const element = page.locator(selector);
  await element.focus();
  await expect(element).toBeFocused();

  await page.keyboard.press('Tab');

  const stillFocused = await element.evaluate(
    (el) => document.activeElement === el,
  );
  expect(stillFocused).toBe(false);
}

/**
 * Assert modal focus trap behavior (FR-009).
 * Opens modal, verifies focus moves inside, verifies focus stays trapped,
 * closes modal, verifies focus returns to trigger.
 */
export async function assertModalFocusTrap(
  page: Page,
  openTrigger: string,
  modalSelector: string,
  closeTrigger: string,
): Promise<void> {
  const trigger = page.locator(openTrigger);
  await trigger.focus();

  // Open modal
  await trigger.click();
  const modal = page.locator(modalSelector);
  await expect(modal).toBeVisible({ timeout: 5000 });

  // Verify focus moved inside modal
  const focusInModal = await page.evaluate(
    (sel) => {
      const modalEl = document.querySelector(sel);
      return modalEl?.contains(document.activeElement) ?? false;
    },
    modalSelector,
  );
  expect(focusInModal).toBe(true);

  // Focus first focusable element in modal, Tab once, verify still inside
  const firstFocusable = modal.locator(
    'button:visible, input:visible, [tabindex]:visible',
  ).first();
  if ((await firstFocusable.count()) > 0) {
    await firstFocusable.focus();
    await page.keyboard.press('Tab');

    const stillInModal = await page.evaluate(
      (sel) => {
        const modalEl = document.querySelector(sel);
        return modalEl?.contains(document.activeElement) ?? false;
      },
      modalSelector,
    );
    expect(stillInModal).toBe(true);
  }

  // Close modal
  const closeBtn = page.locator(closeTrigger);
  if ((await closeBtn.count()) > 0) {
    await closeBtn.click();
  } else {
    await page.keyboard.press('Escape');
  }

  await expect(modal).not.toBeVisible({ timeout: 5000 });

  // Verify focus returned to trigger
  await expect(trigger).toBeFocused();
}

/**
 * Assert focus is on a visible element after view transition (FR-008).
 * After clicking a tab to change views, the focused element should be visible.
 */
export async function assertFocusOnVisibleElement(
  page: Page,
): Promise<void> {
  const isVisible = await page.evaluate(() => {
    const active = document.activeElement;
    if (!active || active === document.body) return true; // body focus is acceptable
    const rect = (active as HTMLElement).getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  });
  expect(isVisible).toBe(true);
}

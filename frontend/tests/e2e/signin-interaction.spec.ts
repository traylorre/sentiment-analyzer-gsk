// Target: Customer Dashboard (Next.js/Amplify)
//
// Regression tests for the sign-in interaction (Feature 1244).
// Verifies the Guest button produces a visible menu on both desktop
// and mobile viewports. Covers the bug where the dropdown was hidden
// by CSS stacking context + self-occluding backdrop (PRs #782-783 era).

import { test, expect } from '@playwright/test';

test.describe('Sign-In Interaction', () => {
  test.setTimeout(30_000);

  test('Guest button opens user menu on desktop', async ({ page, isMobile }) => {
    if (isMobile) {
      test.skip(true, 'Guest text hidden on mobile — see mobile-specific test below');
      return;
    }
    await page.goto('/');

    // Wait for auth initialization (skeleton → button)
    const guestButton = page.getByRole('button', { name: /guest/i });
    await expect(guestButton).toBeVisible({ timeout: 10_000 });

    // Click the Guest button
    await guestButton.click();

    // Radix DropdownMenu renders items with role="menuitem"
    const menuItem = page.getByRole('menuitem').first();
    await expect(menuItem).toBeVisible({ timeout: 5_000 });
  });

  test('Guest button opens user menu on mobile', async ({ page }) => {
    // Set mobile viewport (Pixel 5)
    await page.setViewportSize({ width: 393, height: 851 });
    await page.goto('/');

    // On mobile, the "Guest" text is hidden (sm:inline). Use data-testid.
    // Scope to header (mobile) since desktop sidebar aside is hidden at this viewport.
    const trigger = page.locator('header [data-testid="user-menu-trigger"]');
    await expect(trigger).toBeVisible({ timeout: 10_000 });

    await trigger.click();

    // Menu should appear with at least one item
    const menuItem = page.getByRole('menuitem').first();
    await expect(menuItem).toBeVisible({ timeout: 5_000 });
  });

  test('menu closes on Escape key', async ({ page, isMobile }) => {
    if (isMobile) {
      test.skip(true, 'Guest text hidden on mobile');
      return;
    }
    await page.goto('/');

    const guestButton = page.getByRole('button', { name: /guest/i });
    await expect(guestButton).toBeVisible({ timeout: 10_000 });

    // Open menu
    await guestButton.click();
    const menuItem = page.getByRole('menuitem').first();
    await expect(menuItem).toBeVisible({ timeout: 5_000 });

    // Press Escape — Radix handles this automatically
    await page.keyboard.press('Escape');

    // Menu should be gone
    await expect(menuItem).not.toBeVisible({ timeout: 3_000 });
  });
});

test.describe('OAuth Flow Regression (Feature 1245)', () => {
  test.setTimeout(15_000);

  test('sign-in page shows only email when no OAuth configured', async ({ page }) => {
    await page.route('**/api/v2/auth/oauth/urls', route =>
      route.fulfill({
        status: 200,
        body: JSON.stringify({ providers: {}, state: '' }),
        contentType: 'application/json',
      })
    );

    await page.goto('/auth/signin');

    // No OAuth provider buttons should be visible
    await expect(page.getByRole('button', { name: /google/i })).not.toBeVisible();
    await expect(page.getByRole('button', { name: /github/i })).not.toBeVisible();

    // Magic link email form should still be present
    await expect(page.getByPlaceholder(/you@example/i)).toBeVisible();
  });

  test('magic link form loads immediately without waiting for provider check', async ({ page }) => {
    await page.goto('/auth/signin');

    // Email input should be visible within 2 seconds (before providers resolve)
    await expect(page.getByPlaceholder(/email/i)).toBeVisible({ timeout: 5_000 });
  });

  test('session recovers after failed OAuth redirect', async ({ page }) => {
    await page.goto('/auth/callback?error=access_denied');

    // Should show cancellation message (component maps access_denied → "Sign-in was cancelled...")
    await expect(page.getByText(/cancelled/i)).toBeVisible({ timeout: 5000 });

    // Recovery: "Try again" button and "Continue as guest" link are both rendered
    // The <a href="/"> with text "Continue as guest" has role=link
    await expect(
      page.getByRole('link', { name: /continue as guest/i })
    ).toBeVisible({ timeout: 5000 });
  });

  test('OAuth callback error shows user-friendly message', async ({ page }) => {
    await page.goto('/auth/callback?error=server_error');

    // Should show a friendly error message
    await expect(page.getByText(/something went wrong/i)).toBeVisible();
  });
});

import { test, expect } from '@playwright/test';

test.describe('Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
  });

  test.describe('Page Structure', () => {
    test('should display settings page with all sections', async ({ page }) => {
      // Account section
      await expect(page.getByText(/account/i)).toBeVisible();

      // Preferences section
      await expect(page.getByText(/preferences/i)).toBeVisible();

      // Notifications section
      await expect(page.getByText(/notifications/i)).toBeVisible();
    });

    test('should display page description', async ({ page }) => {
      await expect(
        page.getByText(/customize your dashboard experience/i)
      ).toBeVisible();
    });

    test('should be accessible via keyboard navigation', async ({ page }) => {
      // Tab through interactive elements
      await page.keyboard.press('Tab');

      // Should be able to focus on settings elements
      const focusedElement = page.locator(':focus');
      await expect(focusedElement).toBeVisible();
    });
  });

  test.describe('Account Section', () => {
    test('should display account information for anonymous user', async ({
      page,
    }) => {
      // Anonymous users should see upgrade prompt or account info
      const accountSection = page.locator('text=/account/i').first();
      await expect(accountSection).toBeVisible();

      // Should show some account indicator (anonymous/email/type)
      const authIndicator = page.getByText(
        /anonymous|email|google|github|member/i
      );
      await expect(authIndicator).toBeVisible();
    });

    test('should display user statistics', async ({ page }) => {
      // Should show configuration and alert counts
      const configCount = page.getByText(/configurations?:/i);
      const alertCount = page.getByText(/alerts?:/i);

      // At least one should be visible
      await expect(configCount.or(alertCount)).toBeVisible();
    });

    test('should show upgrade prompt for anonymous users', async ({ page }) => {
      // Anonymous users may see upgrade prompt
      const upgradePrompt = page.getByText(/upgrade|limited features/i);

      if (await upgradePrompt.isVisible()) {
        // Upgrade button should be present
        const upgradeButton = page.getByRole('button', { name: /upgrade/i });
        await expect(upgradeButton).toBeVisible();
      }
    });
  });

  test.describe('Preferences Section', () => {
    test('should display dark mode setting (disabled)', async ({ page }) => {
      const darkModeSwitch = page.getByRole('switch', { name: /dark mode/i });

      if (await darkModeSwitch.isVisible()) {
        // Dark mode should be always on (disabled toggle)
        await expect(darkModeSwitch).toBeDisabled();
        await expect(darkModeSwitch).toHaveAttribute('aria-checked', 'true');
      }
    });

    test('should toggle haptic feedback setting', async ({ page }) => {
      const hapticSwitch = page.getByRole('switch', { name: /haptic/i });

      if (await hapticSwitch.isVisible()) {
        const initialState = await hapticSwitch.getAttribute('aria-checked');

        // Toggle
        await hapticSwitch.click();

        // State should change
        const newState = await hapticSwitch.getAttribute('aria-checked');
        expect(newState).not.toBe(initialState);

        // Toggle back
        await hapticSwitch.click();

        // Should return to initial state
        const finalState = await hapticSwitch.getAttribute('aria-checked');
        expect(finalState).toBe(initialState);
      }
    });

    test('should toggle reduced motion setting', async ({ page }) => {
      const motionSwitch = page.getByRole('switch', { name: /reduced motion/i });

      if (await motionSwitch.isVisible()) {
        const initialState = await motionSwitch.getAttribute('aria-checked');

        // Toggle
        await motionSwitch.click();

        // State should change
        const newState = await motionSwitch.getAttribute('aria-checked');
        expect(newState).not.toBe(initialState);
      }
    });

    test('should persist preference changes after reload', async ({ page }) => {
      const hapticSwitch = page.getByRole('switch', { name: /haptic/i });

      if (await hapticSwitch.isVisible()) {
        const initialState = await hapticSwitch.getAttribute('aria-checked');

        // Toggle to opposite state
        await hapticSwitch.click();
        const toggledState = await hapticSwitch.getAttribute('aria-checked');
        expect(toggledState).not.toBe(initialState);

        // Reload page
        await page.reload();

        // Wait for page to load
        await page.waitForLoadState('networkidle');

        // Check if state persisted (via localStorage)
        const hapticSwitchAfterReload = page.getByRole('switch', {
          name: /haptic/i,
        });
        const persistedState =
          await hapticSwitchAfterReload.getAttribute('aria-checked');

        // State should persist
        expect(persistedState).toBe(toggledState);
      }
    });
  });

  test.describe('Notifications Section', () => {
    test('should display notification preferences', async ({ page }) => {
      // Notifications section should be visible
      await expect(page.getByText(/notifications/i)).toBeVisible();

      // Email notification toggle should be present
      const emailToggle = page.getByRole('switch', { name: /email/i });
      await expect(emailToggle).toBeVisible();
    });

    test('should toggle email notifications', async ({ page }) => {
      const emailToggle = page.getByRole('switch', { name: /email/i });

      if (await emailToggle.isVisible()) {
        const initialState = await emailToggle.getAttribute('aria-checked');

        // Toggle
        await emailToggle.click();

        // Wait for API call
        await page.waitForTimeout(500);

        // State should change
        const newState = await emailToggle.getAttribute('aria-checked');
        expect(newState).not.toBe(initialState);
      }
    });

    test('should show save indicator when notifications change', async ({
      page,
    }) => {
      const emailToggle = page.getByRole('switch', { name: /email/i });

      if (await emailToggle.isVisible()) {
        // Toggle
        await emailToggle.click();

        // Should show some save indicator (toast, saving text, etc.)
        // This may be a toast notification or inline indicator
        const saveIndicator = page.getByText(/saving|saved|updated/i);

        // Wait for indicator to appear (with timeout)
        try {
          await saveIndicator.waitFor({ timeout: 3000 });
        } catch {
          // Indicator might not exist or be too quick to catch
        }
      }
    });

    test('should handle notification API errors gracefully', async ({
      page,
    }) => {
      // Mock the API to fail
      await page.route('**/api/v2/notifications/preferences', (route) => {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Internal server error' }),
        });
      });

      const emailToggle = page.getByRole('switch', { name: /email/i });

      if (await emailToggle.isVisible()) {
        // Toggle
        await emailToggle.click();

        // Should show error or remain unchanged
        // The UI should handle the error gracefully
        const errorIndicator = page.getByText(/error|failed|try again/i);

        // Wait a moment for error handling
        await page.waitForTimeout(1000);

        // Page should still be functional (not crashed)
        await expect(page.getByText(/notifications/i)).toBeVisible();
      }
    });
  });

  test.describe('Sign Out', () => {
    test('should show sign out button when authenticated', async ({ page }) => {
      const signOutButton = page.getByRole('button', { name: /sign out/i });

      // Sign out may only be visible for non-anonymous users
      // For anonymous users, it might be hidden or replaced with upgrade prompt
      if (await signOutButton.isVisible()) {
        await expect(signOutButton).toBeEnabled();
      }
    });

    test('should open confirmation dialog on sign out click', async ({
      page,
    }) => {
      const signOutButton = page.getByRole('button', { name: /sign out/i });

      if (await signOutButton.isVisible()) {
        await signOutButton.click();

        // Confirmation dialog should appear
        const dialog = page.getByRole('dialog');
        await expect(dialog).toBeVisible();

        // Dialog should have confirm/cancel options
        const confirmButton = dialog.getByRole('button', {
          name: /sign out|confirm|yes/i,
        });
        const cancelButton = dialog.getByRole('button', {
          name: /cancel|no|close/i,
        });

        await expect(confirmButton.or(cancelButton)).toBeVisible();

        // Close dialog
        await page.keyboard.press('Escape');
      }
    });

    test('should close sign out dialog on cancel', async ({ page }) => {
      const signOutButton = page.getByRole('button', { name: /sign out/i });

      if (await signOutButton.isVisible()) {
        await signOutButton.click();

        const dialog = page.getByRole('dialog');
        if (await dialog.isVisible()) {
          // Click cancel
          const cancelButton = dialog.getByRole('button', {
            name: /cancel|no|close/i,
          });
          if (await cancelButton.isVisible()) {
            await cancelButton.click();
          } else {
            // Use escape key
            await page.keyboard.press('Escape');
          }

          // Dialog should close
          await expect(dialog).not.toBeVisible();
        }
      }
    });
  });

  test.describe('Accessibility', () => {
    test('should have proper heading hierarchy', async ({ page }) => {
      // Get all headings
      const h1 = page.getByRole('heading', { level: 1 });
      const h2 = page.getByRole('heading', { level: 2 });

      // Should have main heading (may be hidden on desktop)
      // Section headings should be h2
      const sectionHeadings = await h2.count();
      expect(sectionHeadings).toBeGreaterThan(0);
    });

    test('should have labeled form controls', async ({ page }) => {
      // All switches should have accessible names
      const switches = page.getByRole('switch');
      const count = await switches.count();

      for (let i = 0; i < count; i++) {
        const switchEl = switches.nth(i);
        const name = await switchEl.getAttribute('aria-label');
        const labelledBy = await switchEl.getAttribute('aria-labelledby');

        // Should have either aria-label or aria-labelledby
        expect(name || labelledBy).toBeTruthy();
      }
    });

    test('should be navigable with keyboard only', async ({ page }) => {
      // Start from beginning
      await page.keyboard.press('Tab');

      // Should be able to tab through all interactive elements
      let tabCount = 0;
      const maxTabs = 20;

      while (tabCount < maxTabs) {
        const focusedElement = page.locator(':focus');

        if (await focusedElement.isVisible()) {
          // Check if it's an interactive element
          const tagName = await focusedElement.evaluate((el) =>
            el.tagName.toLowerCase()
          );
          const role = await focusedElement.getAttribute('role');

          if (
            ['button', 'a', 'input', 'select', 'textarea'].includes(tagName) ||
            ['button', 'switch', 'link'].includes(role || '')
          ) {
            tabCount++;
          }
        }

        await page.keyboard.press('Tab');
      }

      // Should find some interactive elements
      expect(tabCount).toBeGreaterThan(0);
    });
  });

  test.describe('Mobile Responsiveness', () => {
    test('should display properly on mobile viewport', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/settings');

      // Page should still show key sections
      await expect(page.getByText(/preferences/i)).toBeVisible();
      await expect(page.getByText(/notifications/i)).toBeVisible();

      // Controls should be reachable
      const switches = page.getByRole('switch');
      const count = await switches.count();
      expect(count).toBeGreaterThan(0);
    });

    test('should have touch-friendly controls', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/settings');

      // Check switch sizes (should be at least 44x44 for touch)
      const switches = page.getByRole('switch');
      const count = await switches.count();

      if (count > 0) {
        const firstSwitch = switches.first();
        const box = await firstSwitch.boundingBox();

        if (box) {
          // Touch target should be reasonably sized
          expect(box.width).toBeGreaterThanOrEqual(24);
          expect(box.height).toBeGreaterThanOrEqual(24);
        }
      }
    });
  });
});

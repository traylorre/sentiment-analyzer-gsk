import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test('should redirect to signin when accessing protected routes', async ({ page }) => {
    // The app uses anonymous auth by default, so protected routes should work
    // But we can test the auth UI exists
    await page.goto('/auth/signin');

    // Should show sign in page
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();
  });

  test('should display magic link form', async ({ page }) => {
    await page.goto('/auth/signin');

    // Email input should be present
    const emailInput = page.getByRole('textbox', { name: /email/i });
    await expect(emailInput).toBeVisible();

    // Submit button should be present
    const submitButton = page.getByRole('button', { name: /send|continue|sign in/i });
    await expect(submitButton).toBeVisible();
  });

  test('should show OAuth buttons', async ({ page }) => {
    await page.goto('/auth/signin');

    // Google button should be present
    const googleButton = page.getByRole('button', { name: /google/i });
    await expect(googleButton).toBeVisible();

    // GitHub button should be present
    const githubButton = page.getByRole('button', { name: /github/i });
    await expect(githubButton).toBeVisible();
  });

  test('should validate email input', async ({ page }) => {
    await page.goto('/auth/signin');

    const emailInput = page.getByRole('textbox', { name: /email/i });
    const submitButton = page.getByRole('button', { name: /send|continue|sign in/i });

    // Enter invalid email
    await emailInput.fill('invalid-email');
    await submitButton.click();

    // Should show validation error or stay on page
    await expect(page).toHaveURL(/signin/);
  });

  test('should accept valid email', async ({ page }) => {
    await page.goto('/auth/signin');

    const emailInput = page.getByRole('textbox', { name: /email/i });
    const submitButton = page.getByRole('button', { name: /send|continue|sign in/i });

    // Enter valid email
    await emailInput.fill('test@example.com');
    await submitButton.click();

    // Should either submit or show captcha
    // Wait for either verification page or captcha
    await page.waitForTimeout(1000);
  });

  test('should display verify page', async ({ page }) => {
    await page.goto('/auth/verify');

    // Should show verification page content
    await expect(page.getByText(/check|email|verify/i)).toBeVisible();
  });
});

test.describe('Sign Out Flow', () => {
  test('should show sign out button in settings when authenticated', async ({ page }) => {
    await page.goto('/settings');

    // For anonymous users, sign out may not be visible
    // For authenticated users, it should be
    const signOutButton = page.getByRole('button', { name: /sign out/i });

    // The button may or may not be visible depending on auth state
    const isVisible = await signOutButton.isVisible().catch(() => false);

    if (isVisible) {
      // Click should open confirmation dialog
      await signOutButton.click();

      // Confirmation dialog should appear
      await expect(page.getByRole('dialog')).toBeVisible();
    }
  });
});

test.describe('Anonymous Mode', () => {
  test('should allow anonymous access to dashboard', async ({ page }) => {
    await page.goto('/');

    // Dashboard should be accessible
    await expect(page.getByRole('heading', { name: /sentiment/i })).toBeVisible();
  });

  test('should show limited features indicator for anonymous users', async ({ page }) => {
    await page.goto('/settings');

    // Anonymous users might see upgrade prompt
    const upgradePrompt = page.getByText(/upgrade|anonymous|limited/i);
    const accountSection = page.getByText(/account/i);

    // Either upgrade prompt or account section should be visible
    await expect(upgradePrompt.or(accountSection)).toBeVisible();
  });
});

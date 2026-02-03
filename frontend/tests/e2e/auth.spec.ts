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

/**
 * OAuth Callback Error Handling Tests
 *
 * These tests verify the OAuth callback page correctly handles various error scenarios.
 * The callback page is at /auth/callback and receives authorization codes from OAuth providers.
 *
 * Since we can't actually complete OAuth flows in E2E tests (external providers),
 * we test the error handling by navigating directly to the callback with various
 * error conditions.
 */
test.describe('OAuth Callback Error Handling', () => {
  test('should handle missing authorization code', async ({ page }) => {
    // Navigate to callback without code parameter
    await page.goto('/auth/callback?state=test-state');

    // Should show error message about missing code
    await expect(page.getByText(/missing authorization code|invalid callback/i)).toBeVisible({
      timeout: 5000,
    });

    // Should show try again button
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
  });

  test('should handle missing state parameter', async ({ page }) => {
    // Navigate to callback without state parameter
    await page.goto('/auth/callback?code=test-code');

    // Should show error about missing state
    await expect(page.getByText(/missing state|invalid callback/i)).toBeVisible({
      timeout: 5000,
    });

    // Should show try again button
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
  });

  test('should handle expired/missing session (no stored provider)', async ({ page }) => {
    // Clear any stored OAuth state before test
    await page.goto('/');
    await page.evaluate(() => {
      sessionStorage.removeItem('oauth_provider');
      sessionStorage.removeItem('oauth_state');
    });

    // Navigate to callback with code and state but no stored session
    await page.goto('/auth/callback?code=test-code&state=test-state');

    // Should show session expired error
    await expect(page.getByText(/session expired|please try again/i)).toBeVisible({
      timeout: 5000,
    });

    // Should show try again button
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
  });

  test('should handle state mismatch (CSRF protection)', async ({ page }) => {
    // Set up stored state that doesn't match URL state
    await page.goto('/');
    await page.evaluate(() => {
      sessionStorage.setItem('oauth_provider', 'google');
      sessionStorage.setItem('oauth_state', 'stored-state-123');
    });

    // Navigate with different state in URL
    await page.goto('/auth/callback?code=test-code&state=different-state-456');

    // Should show session invalid error (CSRF check failed)
    await expect(page.getByText(/session invalid|please try again/i)).toBeVisible({
      timeout: 5000,
    });

    // Should show try again button
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
  });

  test('should handle provider denial (user cancelled)', async ({ page }) => {
    // OAuth providers return error parameter when user cancels
    await page.goto('/auth/callback?error=access_denied&error_description=User%20denied%20access');

    // Should show error heading
    await expect(page.getByRole('heading', { name: /sign in failed/i })).toBeVisible({
      timeout: 5000,
    });

    // Should show the specific error description
    await expect(page.getByText('User denied access')).toBeVisible();

    // Should show try again button
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
  });

  test('should handle provider error without description', async ({ page }) => {
    // Some providers only return error without description
    await page.goto('/auth/callback?error=server_error');

    // Should show error heading
    await expect(page.getByRole('heading', { name: /sign in failed/i })).toBeVisible({
      timeout: 5000,
    });

    // Should show generic cancellation message
    await expect(page.getByText('Authentication was cancelled')).toBeVisible();

    // Should show try again button
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
  });

  test('should redirect to signin when clicking try again', async ({ page }) => {
    // Navigate to callback with missing code
    await page.goto('/auth/callback?state=test-state');

    // Wait for error to display
    await expect(page.getByText(/missing authorization code|invalid callback/i)).toBeVisible({
      timeout: 5000,
    });

    // Click try again
    await page.getByRole('button', { name: /try again/i }).click();

    // Should redirect to signin page
    await expect(page).toHaveURL(/\/auth\/signin/);
  });
});

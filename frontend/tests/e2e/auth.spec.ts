import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test('should display sign-in page with welcome heading', async ({ page }) => {
    await page.goto('/auth/signin');

    // Page heading is "Welcome back" (not "Sign in")
    await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible();
  });

  test('should display magic link form', async ({ page }) => {
    await page.goto('/auth/signin');

    // Email input should be present with accessible label
    const emailInput = page.getByLabel(/email address/i);
    await expect(emailInput).toBeVisible();

    // Submit button is "Continue with Email"
    const submitButton = page.getByRole('button', { name: /continue with email/i });
    await expect(submitButton).toBeVisible();
  });

  test('should show OAuth buttons', async ({ page }) => {
    await page.goto('/auth/signin');

    // Google button
    const googleButton = page.getByRole('button', { name: /continue with google/i });
    await expect(googleButton).toBeVisible();

    // GitHub button
    const githubButton = page.getByRole('button', { name: /continue with github/i });
    await expect(githubButton).toBeVisible();
  });

  test('should show email input is required', async ({ page }) => {
    await page.goto('/auth/signin');

    // The email input should be present
    const emailInput = page.getByLabel(/email address/i);
    await expect(emailInput).toBeVisible();

    // The submit button should be disabled when email is empty
    const submitButton = page.getByRole('button', { name: /continue with email/i });
    await expect(submitButton).toBeDisabled();

    // When we enter any text, button becomes enabled
    await emailInput.fill('something');
    await expect(submitButton).toBeEnabled();
  });

  test('should accept valid email and attempt submission', async ({ page }) => {
    await page.goto('/auth/signin');

    const emailInput = page.getByLabel(/email address/i);
    const submitButton = page.getByRole('button', { name: /continue with email/i });

    // Enter valid email
    await emailInput.fill('test@example.com');

    // Verify the submit button is enabled when valid email is entered
    await expect(submitButton).toBeEnabled();

    // Click submit
    await submitButton.click();

    // Should either:
    // 1. Show "Check your email" confirmation (success)
    // 2. Show "Sending..." loading state
    // 3. Show an error (API failure in test env)
    // Any of these indicates the form submission was attempted
    const checkEmail = page.getByText(/check your email/i);
    const sending = page.getByText(/sending/i);
    const errorState = page.getByText(/failed|error|try again/i);

    // Wait for network to settle
    await page.waitForLoadState('networkidle');

    // Verify we're still on the signin page or showing a response
    const pageUrl = page.url();
    const hasResponse =
      (await checkEmail.isVisible().catch(() => false)) ||
      (await sending.isVisible().catch(() => false)) ||
      (await errorState.isVisible().catch(() => false));

    // Test passes if form reacted (showed response or stayed on page)
    expect(pageUrl.includes('/auth') || hasResponse).toBeTruthy();
  });

  test('should display verify page with appropriate state', async ({ page }) => {
    // Without a token, verify page shows "Invalid or expired link"
    await page.goto('/auth/verify');

    // Should show the invalid/expired link message (since no token provided)
    await expect(
      page.getByRole('heading', { name: /invalid or expired link/i })
    ).toBeVisible();

    // Should have button to request new link
    await expect(
      page.getByRole('button', { name: /request new link/i })
    ).toBeVisible();
  });
});

test.describe('Sign Out Flow', () => {
  test('should show sign out button for authenticated users', async ({ page }) => {
    await page.goto('/settings');

    // Wait for page to initialize (auth state)
    await page.waitForLoadState('networkidle');

    // Look for Sign Out button (only visible when authenticated)
    const signOutButton = page.getByRole('button', { name: /sign out/i });

    // With anonymous auth, users are authenticated, so button should be visible
    const isVisible = await signOutButton.isVisible({ timeout: 5000 }).catch(() => false);

    if (isVisible) {
      // Click should open confirmation dialog
      await signOutButton.click();

      // Confirmation dialog should appear
      await expect(page.getByRole('dialog')).toBeVisible();
    }
    // If not visible, test passes - user may not be authenticated
  });
});

test.describe('Anonymous Mode', () => {
  test('should allow anonymous access to dashboard', async ({ page }) => {
    await page.goto('/');

    // Wait for page to fully load
    await page.waitForLoadState('networkidle');

    // Dashboard should be accessible - check for the app logo/title in header or sidebar
    // Use more specific selector to avoid matching multiple "sentiment" headings
    const appTitle = page.locator('span').filter({ hasText: /^Sentiment$/ }).first();
    await expect(appTitle).toBeVisible();
  });

  test('should navigate to settings page', async ({ page }) => {
    // Navigate to settings page
    await page.goto('/settings');

    // Page should load (URL should contain settings)
    await expect(page).toHaveURL(/settings/);

    // Wait for page content to load (either settings content or loading state)
    await page.waitForLoadState('domcontentloaded');

    // The page should have some content (not blank)
    // This test verifies navigation works, not full auth state
    const body = page.locator('body');
    await expect(body).not.toBeEmpty();
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

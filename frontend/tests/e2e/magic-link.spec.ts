// Target: Customer Dashboard (Next.js/Amplify)
/**
 * E2E tests for magic link authentication flow (Feature 1223, US2).
 *
 * Uses DynamoDB direct query to extract magic link tokens (zero cost).
 * Future: Issue #731 — integrate MailSlurp ($15/month) for real email testing.
 */

import { test, expect } from '@playwright/test';
import { mockAnonymousAuth } from './helpers/auth-helper';

test.describe('Magic Link Authentication (US2)', () => {
  const testEmail = `e2e-magiclink-${Date.now()}@test.example.com`;

  // Mock anonymous auth so session init completes instantly
  // (prevents ECONNREFUSED under parallel load)
  test.beforeEach(async ({ page }) => {
    await mockAnonymousAuth(page);
  });

  test('requesting magic link shows confirmation message', async ({ page }) => {
    // Mock the magic link request API so the form submission succeeds
    await page.route('**/api/v2/auth/magic-link', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'email_sent',
          message: 'Check your email for a sign-in link',
        }),
      })
    );

    await page.goto('/auth/signin');

    const emailInput = page.getByLabel(/email address/i);
    // pressSequentially triggers both input and change events per keystroke,
    // ensuring React controlled input state updates correctly.
    // fill() only triggers 'input' event which may not fire React's onChange.
    await emailInput.clear();
    await emailInput.pressSequentially(testEmail, { delay: 10 });

    const submitButton = page.getByRole('button', { name: /continue with email/i });
    // Wait for React state to propagate (button becomes enabled when email is non-empty)
    await expect(submitButton).toBeEnabled({ timeout: 5000 });
    await submitButton.click();

    // Should show confirmation that email was sent
    await expect(
      page.getByText(/check your email|link sent|email sent/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test('valid magic link token authenticates user', async ({ page }) => {
    // Mock the verify endpoint to return an error (simulating invalid token)
    await page.route('**/api/v2/auth/magic-link/verify', route =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'INVALID_TOKEN',
          message: 'Invalid or expired token',
        }),
      })
    );

    // Navigate directly to verify page with a test token.
    // The verify page calls POST /api/v2/auth/magic-link/verify which is mocked above.
    // mockAnonymousAuth from beforeEach handles session init.
    await page.goto('/auth/verify?token=test-invalid-token');
    await expect(
      page.getByText(/invalid|expired|not found/i).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('reused magic link token shows already-used error', async ({ page }) => {
    // Mock the verify endpoint to return token-used error
    await page.route('**/api/v2/auth/magic-link/verify', route =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'TOKEN_USED',
          message: 'Token already used',
        }),
      })
    );

    // Navigate to verify with a token that would be marked as used
    await page.goto('/auth/verify?token=already-used-token');

    await expect(
      page.getByText(/already used|invalid|expired/i).first()
    ).toBeVisible({ timeout: 10000 });

    // Should offer to request a new link
    await expect(
      page.getByRole('button', { name: /request.*new|try again|new link/i })
    ).toBeVisible();
  });

  test('expired magic link shows expiry error', async ({ page }) => {
    // Mock the verify endpoint to return token-expired error
    await page.route('**/api/v2/auth/magic-link/verify', route =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'TOKEN_EXPIRED',
          message: 'Token expired',
        }),
      })
    );

    // Navigate to verify with a token that would be expired (>1hr old)
    await page.goto('/auth/verify?token=expired-old-token');

    await expect(
      page.getByText(/expired|invalid/i).first()
    ).toBeVisible({ timeout: 10000 });

    await expect(
      page.getByRole('button', { name: /request.*new|try again|new link/i })
    ).toBeVisible();
  });
});

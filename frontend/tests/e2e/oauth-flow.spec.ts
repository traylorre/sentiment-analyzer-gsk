// Target: Customer Dashboard (Next.js/Amplify)
/**
 * E2E tests for OAuth login flow (Feature 1223, US1).
 *
 * Uses Playwright route interception to mock Cognito OAuth redirect.
 * Tests the full browser flow: click OAuth button → redirect → callback → session.
 */

import { test, expect } from '@playwright/test';
import { mockOAuthRedirect } from './helpers/auth-helper';

test.describe('OAuth Login Flow (US1)', () => {
  test('Google OAuth redirect contains state and code_challenge', async ({ page }) => {
    let capturedUrl: URL | null = null;

    // Capture the OAuth redirect URL before intercepting
    await page.route('**/oauth2/authorize**', async (route) => {
      capturedUrl = new URL(route.request().url());
      // Don't actually redirect — just capture and abort
      await route.abort();
    });

    await page.goto('/auth/signin');
    const googleButton = page.getByRole('button', { name: /continue with google/i });
    await googleButton.click();

    // Wait briefly for the redirect to be captured
    await page.waitForTimeout(2000);

    // Verify the captured URL has required parameters
    expect(capturedUrl).not.toBeNull();
    expect(capturedUrl!.searchParams.get('state')).toBeTruthy();
    expect(capturedUrl!.searchParams.get('code_challenge')).toBeTruthy();
    expect(capturedUrl!.searchParams.get('code_challenge_method')).toBe('S256');
    expect(capturedUrl!.searchParams.get('scope')).toContain('openid');
    expect(capturedUrl!.searchParams.get('response_type')).toBe('code');
  });

  test('successful OAuth callback creates session and loads dashboard', async ({ page }) => {
    // Setup route interception for successful OAuth
    await mockOAuthRedirect(page, '/auth/callback', { code: 'valid-test-code' });

    await page.goto('/auth/signin');
    const googleButton = page.getByRole('button', { name: /continue with google/i });
    await googleButton.click();

    // After mock redirect → callback → should land on dashboard or show success
    // The callback page processes the code and redirects
    await page.waitForURL(/\/(dashboard|$|\?)/i, { timeout: 15000 });

    // Dashboard should be accessible (not stuck on error page)
    const body = await page.textContent('body');
    expect(body).not.toContain('error');
  });

  test('OAuth callback with provider denial shows friendly error', async ({ page }) => {
    await mockOAuthRedirect(page, '/auth/callback', {
      error: 'access_denied',
      errorDescription: 'User cancelled the login',
    });

    await page.goto('/auth/signin');
    const googleButton = page.getByRole('button', { name: /continue with google/i });
    await googleButton.click();

    // Should show error page with friendly message
    await expect(page.getByText(/cancelled|denied|error/i)).toBeVisible({ timeout: 10000 });
    // Should have a "Try again" or "Back to sign in" link
    await expect(page.getByRole('link', { name: /try again|sign in|back/i })).toBeVisible();
  });

  test('OAuth callback with stale state is rejected', async ({ page }) => {
    // Manually navigate to callback with a fabricated (invalid) state
    await page.goto('/auth/callback?code=some-code&state=invalid-stale-state');

    // Should show error about invalid/expired session
    await expect(
      page.getByText(/invalid|expired|session/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test('GitHub OAuth flow works with same pattern', async ({ page }) => {
    let capturedUrl: URL | null = null;

    await page.route('**/oauth2/authorize**', async (route) => {
      capturedUrl = new URL(route.request().url());
      await route.abort();
    });

    await page.goto('/auth/signin');
    const githubButton = page.getByRole('button', { name: /continue with github/i });
    await githubButton.click();

    await page.waitForTimeout(2000);

    expect(capturedUrl).not.toBeNull();
    expect(capturedUrl!.searchParams.get('identity_provider')).toMatch(/github/i);
    expect(capturedUrl!.searchParams.get('state')).toBeTruthy();
  });
});

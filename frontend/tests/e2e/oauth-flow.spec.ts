// Target: Customer Dashboard (Next.js/Amplify)
/**
 * E2E tests for OAuth login flow (Feature 1223, US1).
 *
 * Uses Playwright route interception to mock Cognito OAuth redirect.
 * Tests the full browser flow: click OAuth button → redirect → callback → session.
 */

import { test, expect } from '@playwright/test';
import { mockOAuthRedirect } from './helpers/auth-helper';

/**
 * Mock the /api/v2/auth/oauth/urls endpoint so the signin page
 * discovers providers and renders OAuth buttons.
 * Also provides the authorize_url used by signInWithOAuth().
 */
async function mockOAuthUrls(page: import('@playwright/test').Page) {
  await page.route('**/api/v2/auth/oauth/urls', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        providers: {
          google: {
            authorize_url:
              'https://cognito.example.com/oauth2/authorize?identity_provider=Google&client_id=test&response_type=code&scope=openid+email+profile&code_challenge=mock-challenge&code_challenge_method=S256&state=mock-state-google&redirect_uri=http://localhost:3000/auth/callback',
            icon: 'google',
            state: 'mock-state-google',
          },
          github: {
            authorize_url:
              'https://cognito.example.com/oauth2/authorize?identity_provider=GitHub&client_id=test&response_type=code&scope=openid+email+profile&code_challenge=mock-challenge&code_challenge_method=S256&state=mock-state-github&redirect_uri=http://localhost:3000/auth/callback',
            icon: 'github',
            state: 'mock-state-github',
          },
        },
        state: 'mock-state-legacy',
      }),
    })
  );
}

test.describe('OAuth Login Flow (US1)', () => {
  test('Google OAuth redirect contains state and code_challenge', async ({ page }) => {
    let capturedUrl: URL | null = null;

    // Mock OAuth URLs so signin page shows provider buttons
    await mockOAuthUrls(page);

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

  // COVERAGE GAP (Feature 1363): No E2E coverage for successful OAuth callback
  // -> session creation. Blocked by useSessionInit clearing oauth_* sessionStorage
  // before the callback page reads them. Requires production fix in
  // use-session-init.ts (separate feature). See spec 1363, EC-1.

  test('OAuth callback with provider denial shows friendly error', async ({ page }) => {
    // Mock OAuth URLs so signin page shows provider buttons
    await mockOAuthUrls(page);

    await mockOAuthRedirect(page, '/auth/callback', {
      error: 'access_denied',
      errorDescription: 'User cancelled the login',
    });

    await page.goto('/auth/signin');
    const googleButton = page.getByRole('button', { name: /continue with google/i });
    await googleButton.click();

    // Should show error page with friendly message
    await expect(page.getByText(/cancelled|denied|error/i)).toBeVisible({ timeout: 10000 });
    // Should have a "Try again" button (Button component renders as <button>)
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
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

    // Mock OAuth URLs so signin page shows provider buttons
    await mockOAuthUrls(page);

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

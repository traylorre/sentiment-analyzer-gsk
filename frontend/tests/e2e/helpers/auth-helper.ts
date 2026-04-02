/**
 * Shared auth test utilities for E2E tests (Feature 1223).
 *
 * Provides:
 * - Test run ID generation for data isolation
 * - Anonymous session creation
 * - OAuth route interception for mocked login flows
 */

import { type Page } from '@playwright/test';

/** Generate unique test run ID for data isolation. */
export function generateRunId(): string {
  const now = new Date();
  const date = now.toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const rand = Math.random().toString(36).slice(2, 6);
  return `E2E_${date}_${rand}`;
}

/** Dashboard URL from environment (Amplify frontend or local dev server). */
export function getDashboardUrl(): string {
  // PREPROD_FRONTEND_URL: set in CI deploy pipeline (Amplify URL)
  // localhost:3000: Playwright config starts local Next.js dev server
  // Feature 1300: DASHBOARD_FUNCTION_URL removed (Function URL deleted)
  return process.env.PREPROD_FRONTEND_URL || 'http://localhost:3000';
}

/**
 * Create an anonymous session via the API.
 * Returns the session response with user_id, token, etc.
 */
export async function createAnonymousSession(baseUrl: string): Promise<{
  user_id: string;
  auth_type: string;
  session_expires_at: string;
}> {
  const response = await fetch(`${baseUrl}/api/v2/auth/anonymous`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (response.status !== 201) {
    throw new Error(`Anonymous session creation failed: HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Mock OAuth redirect via Playwright route interception (R1).
 *
 * Intercepts the Cognito authorize URL and redirects to the app's
 * callback URL with a synthetic authorization code and state.
 *
 * @param page - Playwright page instance
 * @param callbackPath - App callback path (e.g., '/auth/callback')
 * @param options - Mock options
 */
export async function mockOAuthRedirect(
  page: Page,
  callbackPath: string = '/auth/callback',
  options: {
    code?: string;
    error?: string;
    errorDescription?: string;
  } = {},
): Promise<void> {
  await page.route('**/oauth2/authorize**', async (route) => {
    const url = new URL(route.request().url());
    const state = url.searchParams.get('state') || '';
    const baseUrl = new URL(page.url()).origin;

    let redirectUrl: string;
    if (options.error) {
      // Simulate provider denial or error
      const params = new URLSearchParams({
        error: options.error,
        state,
      });
      if (options.errorDescription) {
        params.set('error_description', options.errorDescription);
      }
      redirectUrl = `${baseUrl}${callbackPath}?${params.toString()}`;
    } else {
      // Simulate successful authorization
      const code = options.code || 'mock-auth-code-' + Date.now();
      redirectUrl = `${baseUrl}${callbackPath}?code=${code}&state=${state}`;
    }

    await route.fulfill({
      status: 302,
      headers: { Location: redirectUrl },
    });
  });
}

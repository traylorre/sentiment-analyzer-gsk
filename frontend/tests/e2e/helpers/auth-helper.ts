/**
 * Shared auth test utilities for E2E tests (Feature 1223).
 *
 * Provides:
 * - Test run ID generation for data isolation
 * - Anonymous session creation
 * - OAuth route interception for mocked login flows
 */

import { type Page, type BrowserContext } from '@playwright/test';

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
 * Set up session cookies to bypass Next.js middleware auth checks.
 * Creates an anonymous session via the API, then sets browser cookies
 * so the middleware treats the user as authenticated (non-anonymous).
 *
 * Use this for tests that navigate to protected routes like /alerts.
 */
export async function setupAuthSession(context: BrowserContext): Promise<void> {
  // Use 127.0.0.1 (not localhost) to avoid IPv6 ::1 resolution in Node 18+
  // which causes ECONNREFUSED when Python server binds to IPv4 only
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
  const session = await createAnonymousSession(apiUrl);

  // Set cookies that the Next.js middleware checks for route protection
  await context.addCookies([
    {
      name: 'sentiment-access-token',
      value: session.user_id,
      domain: 'localhost',
      path: '/',
    },
    {
      name: 'sentiment-is-anonymous',
      value: 'false', // Pretend non-anonymous to pass upgraded route check
      domain: 'localhost',
      path: '/',
    },
  ]);
}

/**
 * Mock the anonymous auth endpoint via Playwright route interception.
 *
 * Use for tests that DON'T need real API data (chaos, error-boundary, etc.).
 * For tests that need real chart data (sanity, dashboard-interactions),
 * use waitForAuth() instead — it waits for the real auth to complete.
 *
 * The response shape must match what mapAnonymousSession() reads:
 * - `token` (NOT `access_token`) — used for Bearer header
 * - `user_id` — used for session identification
 * - `auth_type` — "anonymous"
 */
export async function mockAnonymousAuth(page: Page): Promise<void> {
  await page.route('**/api/v2/auth/anonymous', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        user_id: 'anon-e2e-user',
        token: 'mock-e2e-token',
        auth_type: 'anonymous',
        created_at: new Date().toISOString(),
        session_expires_at: new Date(Date.now() + 86400000).toISOString(),
        storage_hint: 'session',
      }),
    });
  });
}

/**
 * Wait for the real anonymous auth session to complete after page load.
 *
 * Use for tests that need real API data (sanity, dashboard-interactions).
 * The session init hook calls POST /api/v2/auth/anonymous on mount.
 * This function waits until the auth store has a valid token before
 * allowing the test to proceed.
 *
 * Must be called AFTER page.goto().
 */
export async function waitForAuth(page: Page): Promise<void> {
  await page.waitForFunction(
    () => {
      // Check if the search input is interactive (implies auth is done and app is ready)
      const input = document.querySelector('input[placeholder*="earch"]');
      return input !== null && !(input as HTMLInputElement).disabled;
    },
    { timeout: 15000 }
  );
  // Small settle time for React state propagation
  await page.waitForTimeout(500);
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

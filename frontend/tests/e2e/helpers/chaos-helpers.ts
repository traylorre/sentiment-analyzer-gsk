// Target: Customer Dashboard (Next.js/Amplify)
/**
 * Shared chaos test utilities for E2E tests (Feature 1265).
 *
 * Provides:
 * - API route interception for simulating backend failures
 * - Chaos scenario simulation (5 types)
 * - Health banner triggering and recovery verification
 * - Console event capture for telemetry assertions
 */

import { type Page, type Route, expect } from '@playwright/test';

// ─── Types ───────────────────────────────────────────────────────────────────

export type ChaosScenarioType =
  | 'ingestion_failure'
  | 'dynamodb_throttle'
  | 'lambda_cold_start'
  | 'trigger_failure'
  | 'api_timeout';

type InterceptionMethod = 'fulfill_error' | 'fulfill_stale' | 'abort' | 'delay';

interface ChaosScenarioConfig {
  type: ChaosScenarioType;
  interceptionMethod: InterceptionMethod;
  description: string;
  /** Route handler applied to matched requests */
  handler: (route: Route) => Promise<void>;
  /** URL pattern for page.route() — defaults to **/api/** */
  pattern?: string;
}

// ─── Chaos Scenario Configurations ───────────────────────────────────────────

export const CHAOS_SCENARIOS: Record<ChaosScenarioType, ChaosScenarioConfig> = {
  ingestion_failure: {
    type: 'ingestion_failure',
    interceptionMethod: 'fulfill_stale',
    description: 'Ingestion stopped — SSE returns no new items, existing data persists',
    handler: async (route: Route) => {
      const url = route.request().url();
      // Allow initial page load APIs to pass, intercept stream/articles
      if (url.includes('/stream') || url.includes('/articles')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ items: [], new_items: [] }),
        });
      } else {
        await route.continue();
      }
    },
    pattern: '**/api/**',
  },

  dynamodb_throttle: {
    type: 'dynamodb_throttle',
    interceptionMethod: 'fulfill_error',
    description: 'Database throttled — write endpoints return 503',
    handler: async (route: Route) => {
      const method = route.request().method();
      if (method === 'POST' || method === 'PUT' || method === 'DELETE') {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 'SERVICE_UNAVAILABLE',
            message: 'DynamoDB throttled',
          }),
        });
      } else {
        // Read operations may still succeed (cached)
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 'SERVICE_UNAVAILABLE',
            message: 'DynamoDB throttled',
          }),
        });
      }
    },
  },

  lambda_cold_start: {
    type: 'lambda_cold_start',
    interceptionMethod: 'delay',
    description: 'Lambda cold starts — API responds with 3s delay',
    handler: async (route: Route) => {
      await new Promise((resolve) => setTimeout(resolve, 3000));
      await route.continue();
    },
  },

  trigger_failure: {
    type: 'trigger_failure',
    interceptionMethod: 'fulfill_stale',
    description: 'EventBridge trigger disabled — no new data, existing persists',
    handler: async (route: Route) => {
      const url = route.request().url();
      if (url.includes('/stream') || url.includes('/articles')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ items: [], new_items: [] }),
        });
      } else {
        await route.continue();
      }
    },
    pattern: '**/api/**',
  },

  api_timeout: {
    type: 'api_timeout',
    interceptionMethod: 'abort',
    description: 'API timeout — all calls aborted with timeout error',
    handler: async (route: Route) => {
      await route.abort('timedout');
    },
  },
};

// ─── API Blocking Utilities ──────────────────────────────────────────────────

/**
 * Block ALL API calls with an error response.
 * Returns an unblock function.
 */
export async function blockAllApi(
  page: Page,
  statusCode: number = 503,
): Promise<() => Promise<void>> {
  await page.route('**/api/**', (route) =>
    route.fulfill({
      status: statusCode,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 'SERVICE_UNAVAILABLE',
        message: 'Service Unavailable',
      }),
    }),
  );

  return async () => {
    await page.unroute('**/api/**');
  };
}

/**
 * Block a specific API endpoint with configurable behavior.
 * Returns an unblock function.
 */
export async function blockApiEndpoint(
  page: Page,
  pattern: string,
  behavior: 'error' | 'stale' | 'timeout' | 'delay',
): Promise<() => Promise<void>> {
  const handler = async (route: Route) => {
    switch (behavior) {
      case 'error':
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ code: 'SERVICE_UNAVAILABLE' }),
        });
        break;
      case 'stale':
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ items: [], new_items: [] }),
        });
        break;
      case 'timeout':
        await route.abort('timedout');
        break;
      case 'delay':
        await new Promise((resolve) => setTimeout(resolve, 3000));
        await route.continue();
        break;
    }
  };

  await page.route(pattern, handler);

  return async () => {
    await page.unroute(pattern);
  };
}

/**
 * Remove all API route interceptions.
 */
export async function unblockAllApi(page: Page): Promise<void> {
  await page.unroute('**/api/**');
}

// ─── Health Banner Utilities ─────────────────────────────────────────────────

/** Locator for the health banner */
export function getBannerLocator(page: Page) {
  return page.getByRole('alert').filter({
    hasText: /trouble connecting|features may be unavailable/i,
  });
}

/** Locator for the dismiss button */
export function getDismissButton(page: Page) {
  return page.getByRole('button', {
    name: /dismiss connectivity warning/i,
  });
}

/**
 * Trigger the health banner by causing 3 consecutive API failures.
 * Replicates the proven pattern from error-visibility-banner.spec.ts.
 */
export async function triggerHealthBanner(page: Page): Promise<void> {
  // Block all API calls
  await page.route('**/api/**', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 'SERVICE_UNAVAILABLE',
        message: 'Service Unavailable',
      }),
    }),
  );

  const searchInput = page.getByPlaceholder(/search tickers/i);

  // 3 search interactions to accumulate failures
  await searchInput.fill('AAPL');
  await page.waitForTimeout(1500);
  await searchInput.fill('');
  await searchInput.fill('GOOG');
  await page.waitForTimeout(1500);
  await searchInput.fill('');
  await searchInput.fill('MSFT');
  await page.waitForTimeout(1500);

  // Wait for banner to appear
  const banner = getBannerLocator(page);
  await expect(banner).toBeVisible({ timeout: 5000 });
}

/**
 * Wait for all three recovery signals:
 * 1. Banner removed from DOM
 * 2. Successful network request observed
 * 3. api_health_recovered console event emitted
 */
export async function waitForRecovery(
  page: Page,
  consoleMessages: string[],
): Promise<void> {
  const banner = getBannerLocator(page);

  // 1. Banner should disappear
  await expect(banner).not.toBeVisible({ timeout: 10000 });

  // 2. Successful network request (verified by caller via page.waitForResponse or consoleMessages)

  // 3. Recovery event should be in console
  const hasRecoveryEvent = () =>
    consoleMessages.some((m) => m.includes('api_health_recovered'));

  await expect
    .poll(hasRecoveryEvent, {
      message: 'Expected api_health_recovered console event',
      timeout: 10000,
    })
    .toBeTruthy();
}

// ─── Console Event Capture ───────────────────────────────────────────────────

/**
 * Set up console event capture for warning-level messages.
 * Returns a mutable array that accumulates events as they arrive.
 */
export function captureConsoleEvents(page: Page): string[] {
  const messages: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'warning') {
      messages.push(msg.text());
    }
  });
  return messages;
}

// ─── Chaos Scenario Simulation ───────────────────────────────────────────────

/**
 * Apply the full page.route() interception pattern for a chaos scenario.
 * Returns a restore function that removes the interception.
 */
export async function simulateChaosScenario(
  page: Page,
  scenario: ChaosScenarioType,
): Promise<() => Promise<void>> {
  const config = CHAOS_SCENARIOS[scenario];
  const pattern = config.pattern || '**/api/**';

  await page.route(pattern, config.handler);

  return async () => {
    await page.unroute(pattern);
  };
}

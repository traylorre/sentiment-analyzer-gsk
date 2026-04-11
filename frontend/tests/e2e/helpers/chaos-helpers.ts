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

import { type Page, type Route, type APIRequestContext, expect } from '@playwright/test';

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

// ─── Telemetry Types (Feature 1339) ─────────────────────────────────────────

/**
 * A structured telemetry event parsed from console.warn JSON output.
 *
 * The production `emitErrorEvent()` function emits events as JSON strings via
 * `console.warn()`. This type represents the parsed form of those events.
 *
 * @example
 * ```ts
 * // Emitted by production code:
 * console.warn(JSON.stringify({ event: "api_health_banner_shown", timestamp: "2026-04-06T...", details: { failureCount: 3 } }))
 *
 * // Parsed as:
 * const event: TelemetryEvent = {
 *   event: "api_health_banner_shown",
 *   timestamp: "2026-04-06T...",
 *   details: { failureCount: 3 }
 * };
 * ```
 */
export interface TelemetryEvent {
  event: string;
  timestamp: string;
  details: Record<string, unknown>;
}

/**
 * Container returned by `captureTelemetryEvents()` with helper methods for
 * querying captured telemetry events.
 *
 * The `events` array is mutable and accumulates events as they arrive during
 * the test. Use `findEvent()` and `findAllEvents()` for convenient lookups.
 */
export interface TelemetryCapture {
  /** Mutable array of parsed telemetry events, accumulates during test */
  events: TelemetryEvent[];
  /** Find the first event matching the given name, or undefined */
  findEvent(name: string): TelemetryEvent | undefined;
  /** Find all events matching the given name */
  findAllEvents(name: string): TelemetryEvent[];
}

/**
 * A structural snapshot of dashboard content captured at a point in time.
 *
 * Used by `assertContentPersistence()` to detect Green Dashboard Syndrome,
 * where content is silently replaced by error pages during chaos injection.
 */
export interface ContentSnapshot {
  /** Number of direct children of the snapshot root element */
  childCount: number;
  /** Map of data-testid values to their textContent, plus role="img" aria-labels */
  keyContent: Map<string, string>;
  /** Whether a chart element (role="img" with "chart" in aria-label) is visible */
  chartVisible: boolean;
  /** Error indicator strings found in the snapshot (e.g., "something went wrong") */
  errorIndicatorsPresent: string[];
  /** Full textContent of the snapshot root (for debugging only) */
  rawText: string;
}

/**
 * Configuration for the canonical 5-step chaos lifecycle pattern.
 *
 * Used by `assertChaosLifecycle()` to encapsulate the standard chaos test flow:
 * baseline -> inject -> trigger -> assert degradation -> restore + recover.
 *
 * @example
 * ```ts
 * await assertChaosLifecycle({
 *   page,
 *   injectFn: async (p) => { await blockAllApi(p); },
 *   triggerFn: async (p) => { await triggerHealthBanner(p); },
 *   assertDegradationFn: async (p) => {
 *     await expect(getBannerLocator(p)).toBeVisible();
 *   },
 *   restoreFn: async (p) => { await unblockAllApi(p); },
 * });
 * ```
 */
export interface ChaosLifecycleConfig {
  /** Playwright Page instance under test */
  page: Page;
  /** Inject the failure condition (e.g., block API routes, set error flags) */
  injectFn: (page: Page) => Promise<void>;
  /** Optional: trigger user interaction that exercises the injected failure */
  triggerFn?: (page: Page) => Promise<void>;
  /** Assert the degraded state is visible/detectable */
  assertDegradationFn: (page: Page) => Promise<void>;
  /** Remove the failure condition (e.g., unroute intercepted APIs) */
  restoreFn: (page: Page) => Promise<void>;
  /** Optional: assert recovery state after restoration */
  assertRecoveryFn?: (page: Page) => Promise<void>;
  /** Options controlling which lifecycle steps to execute */
  options?: {
    /** Skip step 3 (trigger). Use for error boundary tests that crash on render. */
    skipTrigger?: boolean;
    /** Skip step 5 (restore + recovery). Use for tests that only verify degradation. */
    skipRecovery?: boolean;
    /** Skip content persistence check. Use when content comparison is not applicable. */
    skipContentCheck?: boolean;
    /** CSS selector for content snapshot root (default: 'main') */
    contentSelector?: string;
  };
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
 * Returns an unblock function that removes the interception.
 *
 * Tip: Playwright supports `{ times: N }` option on `page.route()` (v1.15+)
 * for transient failure simulation. If you need a failure that auto-clears
 * after N requests, use `page.route(pattern, handler, { times: N })` directly
 * instead of this helper.
 *
 * @param page - Playwright Page instance
 * @param pattern - URL glob pattern to match
 * @param behavior - Type of failure to simulate: 'error' (503), 'stale' (empty 200), 'timeout' (abort), 'delay' (3s)
 * @returns Async function that removes the route interception when called
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
 *
 * Uses `page.waitForResponse()` after each search interaction (not `waitForTimeout`)
 * to ensure the failure is recorded by the health monitor before proceeding.
 * This makes the trigger deterministic rather than timing-dependent.
 *
 * @param page - Playwright Page instance (must already be navigated to '/')
 * @returns Resolves when the health banner is visible
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

  // 3 search interactions to accumulate failures.
  // Wait for the 503 response after each search to confirm the failure was recorded,
  // rather than using a blind waitForTimeout.
  await searchInput.fill('AAPL');
  await page.waitForResponse((resp) => resp.status() === 503);
  await searchInput.fill('');
  await searchInput.fill('GOOG');
  await page.waitForResponse((resp) => resp.status() === 503);
  await searchInput.fill('');
  await searchInput.fill('MSFT');
  await page.waitForResponse((resp) => resp.status() === 503);

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
 * Returns a mutable array of raw message strings that accumulates as events arrive.
 *
 * @deprecated Use `captureTelemetryEvents()` instead for structured JSON telemetry
 * events. This function captures ALL `console.warn` messages as raw strings, including
 * non-telemetry warnings (e.g., `[authStore] Profile refresh failed: ...`). The newer
 * `captureTelemetryEvents()` only captures structured JSON events with an `event` field,
 * providing precise telemetry assertions.
 *
 * @param page - Playwright Page instance
 * @returns Mutable array of raw warning message strings
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

// ─── Structured Telemetry Capture (Feature 1339) ────────────────────────────

/**
 * Set up structured telemetry event capture for `emitErrorEvent()` output.
 *
 * Unlike `captureConsoleEvents()` which captures ALL `console.warn` messages as raw
 * strings, this function only captures structured JSON events that have an `event`
 * field. Non-JSON warnings (e.g., `[authStore] Profile refresh failed: ...`) are
 * silently ignored.
 *
 * Returns a `TelemetryCapture` object with a mutable `events` array and helper
 * methods for querying events by name.
 *
 * @param page - Playwright Page instance
 * @returns TelemetryCapture with events array and findEvent/findAllEvents helpers
 *
 * @example
 * ```ts
 * const telemetry = captureTelemetryEvents(page);
 *
 * // ... trigger actions that emit telemetry ...
 *
 * // Find a specific event
 * const bannerEvent = telemetry.findEvent('api_health_banner_shown');
 * expect(bannerEvent).toBeTruthy();
 * expect(bannerEvent?.details).toHaveProperty('failureCount');
 *
 * // Find all events of a type
 * const allErrors = telemetry.findAllEvents('api_error');
 * expect(allErrors).toHaveLength(3);
 * ```
 */
export function captureTelemetryEvents(page: Page): TelemetryCapture {
  const events: TelemetryEvent[] = [];

  page.on('console', (msg) => {
    if (msg.type() !== 'warning') return;

    const text = msg.text();
    try {
      const parsed = JSON.parse(text);
      if (
        parsed &&
        typeof parsed === 'object' &&
        typeof parsed.event === 'string'
      ) {
        events.push({
          event: parsed.event,
          timestamp: parsed.timestamp ?? '',
          details: parsed.details ?? {},
        });
      }
    } catch {
      // Not JSON — silently ignore (e.g., "[authStore] Profile refresh failed: ...")
    }
  });

  return {
    events,
    findEvent(name: string): TelemetryEvent | undefined {
      return events.find((e) => e.event === name);
    },
    findAllEvents(name: string): TelemetryEvent[] {
      return events.filter((e) => e.event === name);
    },
  };
}

// ─── Content Snapshot & Persistence (Feature 1339) ──────────────────────────

/** Regex patterns that indicate error state in page content */
const ERROR_PATTERNS =
  /something went wrong|error boundary|unexpected error|failed to load/gi;

/**
 * Capture a structural snapshot of dashboard content for later comparison.
 *
 * Collects child count, key content from `[data-testid]` elements and `[role="img"]`
 * aria-labels, chart visibility, and error indicator strings. The snapshot is used by
 * `assertContentPersistence()` to detect Green Dashboard Syndrome.
 *
 * @param page - Playwright Page instance
 * @param selector - CSS selector for the snapshot root element (default: `'main'`)
 * @returns ContentSnapshot for comparison with a later snapshot
 *
 * @example
 * ```ts
 * const before = await captureContentSnapshot(page);
 * // ... inject chaos ...
 * const after = await captureContentSnapshot(page);
 * assertContentPersistence(before, after);
 * ```
 */
export async function captureContentSnapshot(
  page: Page,
  selector: string = 'main',
): Promise<ContentSnapshot> {
  const rawData = await page.evaluate(
    (sel: string) => {
      const root = document.querySelector(sel);
      if (!root) {
        return {
          childCount: 0,
          keyContentEntries: [] as [string, string][],
          chartVisible: false,
          rawText: '',
        };
      }

      // Count direct children
      const childCount = root.children.length;

      // Collect key content from [data-testid] and [role="img"]
      const keyContentEntries: [string, string][] = [];

      const testIdElements = root.querySelectorAll('[data-testid]');
      testIdElements.forEach((el) => {
        const testId = el.getAttribute('data-testid') ?? '';
        const text = (el.textContent ?? '').trim();
        if (testId && text) {
          keyContentEntries.push([testId, text]);
        }
      });

      const imgElements = root.querySelectorAll('[role="img"]');
      imgElements.forEach((el, index) => {
        const ariaLabel = el.getAttribute('aria-label') ?? '';
        if (ariaLabel) {
          keyContentEntries.push([`role-img-${index}`, ariaLabel]);
        }
      });

      // Check for chart visibility
      const chartEl = root.querySelector('[role="img"][aria-label*="chart"]');
      const chartVisible = chartEl !== null;

      // Full text content
      const rawText = (root.textContent ?? '').trim();

      return { childCount, keyContentEntries, chartVisible, rawText };
    },
    selector,
  );

  // Scan for error patterns
  const errorIndicatorsPresent: string[] = [];
  const matches = rawData.rawText.match(ERROR_PATTERNS);
  if (matches) {
    errorIndicatorsPresent.push(...matches.map((m) => m.toLowerCase()));
  }

  // Convert entries array back to Map (Map is not serializable across page.evaluate)
  const keyContent = new Map<string, string>(rawData.keyContentEntries);

  return {
    childCount: rawData.childCount,
    keyContent,
    chartVisible: rawData.chartVisible,
    errorIndicatorsPresent,
    rawText: rawData.rawText,
  };
}

/**
 * Assert that dashboard content has not been silently replaced during chaos.
 *
 * Compares two `ContentSnapshot` objects and fails with a descriptive message if
 * content was lost or replaced by error pages. This prevents Green Dashboard Syndrome
 * where tests pass because "something is visible" but the actual data is gone.
 *
 * Comparison rules:
 * - **Structural**: `after.childCount` must be >= `before.childCount - 2`
 * - **Key content**: Every key in `before.keyContent` must exist in `after.keyContent`
 *   with the same value (timestamps/numbers are stripped for fuzzy matching)
 * - **Chart**: If `before.chartVisible`, `after.chartVisible` must also be true
 * - **Error absence**: New error indicators in `after` that were not in `before` cause failure
 *
 * @param before - Snapshot captured before chaos injection
 * @param after - Snapshot captured after chaos injection
 * @throws Error with descriptive diff if content changed unexpectedly
 *
 * @example
 * ```ts
 * const before = await captureContentSnapshot(page);
 * await injectChaos(page);
 * const after = await captureContentSnapshot(page);
 * assertContentPersistence(before, after); // Throws if content replaced
 * ```
 */
export function assertContentPersistence(
  before: ContentSnapshot,
  after: ContentSnapshot,
): void {
  const failures: string[] = [];

  // Structural: child count must not drop significantly
  if (after.childCount < before.childCount - 2) {
    failures.push(
      `Child count dropped: before=${before.childCount}, after=${after.childCount} (allowed: >= ${before.childCount - 2})`,
    );
  }

  // Key content: every key from before must exist with same value in after
  // Strip timestamps/numbers for fuzzy comparison
  const stripDynamic = (s: string): string =>
    s.replace(/\d{1,2}:\d{2}(:\d{2})?(\s*(AM|PM))?/gi, '<time>')
     .replace(/\d+/g, '<num>');

  for (const [key, beforeVal] of before.keyContent) {
    const afterVal = after.keyContent.get(key);
    if (afterVal === undefined) {
      failures.push(
        `Key content missing: "${key}" was present before ("${beforeVal}") but absent after`,
      );
    } else if (stripDynamic(beforeVal) !== stripDynamic(afterVal)) {
      failures.push(
        `Key content changed: "${key}" was "${beforeVal}" before, now "${afterVal}"`,
      );
    }
  }

  // Chart: if visible before, must be visible after
  if (before.chartVisible && !after.chartVisible) {
    failures.push(
      'Chart was visible before chaos but is no longer visible after',
    );
  }

  // Error absence: new error indicators not present before
  const beforeErrors = new Set(before.errorIndicatorsPresent);
  const newErrors = after.errorIndicatorsPresent.filter(
    (e) => !beforeErrors.has(e),
  );
  if (newErrors.length > 0) {
    failures.push(
      `New error indicators appeared after chaos: [${newErrors.join(', ')}]`,
    );
  }

  if (failures.length > 0) {
    throw new Error(
      `Content changed during chaos (${failures.length} issue${failures.length > 1 ? 's' : ''}):\n` +
        failures.map((f) => `  - ${f}`).join('\n') +
        `\n\nBefore rawText (first 200 chars): "${before.rawText.slice(0, 200)}"` +
        `\nAfter rawText (first 200 chars): "${after.rawText.slice(0, 200)}"`,
    );
  }
}

// ─── Error Boundary Helper (Feature 1339) ───────────────────────────────────

/**
 * Force the React error boundary to activate via the test-only `ErrorTrigger`
 * component's `window.__TEST_FORCE_ERROR` global flag.
 *
 * Uses `page.addInitScript()` rather than `page.evaluate()` because `evaluate()`
 * sets the flag on the current page context, but `goto()` loads a NEW page where
 * the flag would not exist. `addInitScript()` runs before any page JavaScript on
 * every navigation, ensuring the flag is set when ErrorTrigger renders.
 *
 * @param page - Playwright Page instance
 * @param url - URL to navigate to after setting the error flag (default: `'/'`)
 *
 * @example
 * ```ts
 * await forceErrorBoundary(page);
 * // "Something went wrong" is now visible
 * await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
 * ```
 */
export async function forceErrorBoundary(
  page: Page,
  url: string = '/',
): Promise<void> {
  await page.addInitScript(() => {
    (window as unknown as Record<string, unknown>).__TEST_FORCE_ERROR = true;
  });
  await page.goto(url);
  await expect(page.getByText(/something went wrong/i)).toBeVisible({
    timeout: 5000,
  });
}

// ─── Chaos Scenario Simulation ───────────────────────────────────────────────

/**
 * Apply the full `page.route()` interception pattern for a chaos scenario.
 * Returns a restore function that removes the interception.
 *
 * Tip: For transient failures, use `page.route(pattern, handler, { times: N })`
 * directly instead of this helper. This helper applies a permanent interception
 * until the restore function is called.
 *
 * @param page - Playwright Page instance
 * @param scenario - One of the 5 chaos scenario types to simulate
 * @returns Async function that removes the route interception when called
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

// ─── Chaos Lifecycle (Feature 1339) ─────────────────────────────────────────

/**
 * Execute the canonical 5-step chaos lifecycle pattern with structured logging.
 *
 * Encapsulates the standard chaos test flow so every chaos test enforces the same
 * rigor: baseline capture, failure injection, trigger, degradation assertion, and
 * recovery verification. Each step emits a `[chaos-lifecycle]` console.log marker
 * for debugging flaky tests.
 *
 * **Steps**:
 * 1. **Baseline**: Assert health banner NOT visible. Optionally capture content snapshot.
 * 2. **Inject**: Call `injectFn(page)` to inject the failure condition.
 * 3. **Trigger** (optional): Call `triggerFn(page)` to exercise the failure.
 * 4. **Assert Degradation**: Call `assertDegradationFn(page)`. Optionally verify content persistence.
 * 5. **Restore + Recovery** (optional): Call `restoreFn(page)`, then `assertRecoveryFn(page)`.
 *
 * Error handling: If an error occurs after injection, the lifecycle attempts to call
 * `restoreFn(page)` before re-throwing, so API route interceptions don't leak into
 * subsequent tests.
 *
 * @param config - ChaosLifecycleConfig with page, inject/trigger/assert/restore functions, and options
 *
 * @example
 * ```ts
 * // Banner lifecycle: inject API failure -> trigger 3 searches -> verify banner -> restore
 * await assertChaosLifecycle({
 *   page,
 *   injectFn: async (p) => { await blockAllApi(p); },
 *   triggerFn: async (p) => { await triggerHealthBanner(p); },
 *   assertDegradationFn: async (p) => {
 *     await expect(getBannerLocator(p)).toBeVisible();
 *   },
 *   restoreFn: async (p) => { await unblockAllApi(p); },
 *   assertRecoveryFn: async (p) => {
 *     await expect(getBannerLocator(p)).not.toBeVisible({ timeout: 10000 });
 *   },
 *   options: { skipContentCheck: true },
 * });
 * ```
 */
export async function assertChaosLifecycle(
  config: ChaosLifecycleConfig,
): Promise<void> {
  const {
    page,
    injectFn,
    triggerFn,
    assertDegradationFn,
    restoreFn,
    assertRecoveryFn,
    options = {},
  } = config;

  const log = (step: number, name: string) =>
    console.log(`[chaos-lifecycle] step ${step}: ${name}`);

  let injected = false;
  let baselineSnapshot: ContentSnapshot | undefined;

  try {
    // Step 1: Baseline
    log(1, 'baseline');
    const banner = getBannerLocator(page);
    await expect(banner).not.toBeVisible({ timeout: 2000 });

    if (!options.skipContentCheck) {
      baselineSnapshot = await captureContentSnapshot(
        page,
        options.contentSelector ?? 'main',
      );
    }

    // Step 2: Inject
    log(2, 'inject');
    await injectFn(page);
    injected = true;

    // Step 3: Trigger (optional)
    if (triggerFn && !options.skipTrigger) {
      log(3, 'trigger');
      await triggerFn(page);
    }

    // Step 4: Assert degradation
    log(4, 'assert-degradation');
    await assertDegradationFn(page);

    if (baselineSnapshot) {
      const afterSnapshot = await captureContentSnapshot(
        page,
        options.contentSelector ?? 'main',
      );
      assertContentPersistence(baselineSnapshot, afterSnapshot);
    }

    // Step 5: Restore + recovery (optional)
    if (!options.skipRecovery) {
      log(5, 'restore');
      await restoreFn(page);
      injected = false;

      if (assertRecoveryFn) {
        await assertRecoveryFn(page);
      }
    }

    console.log('[chaos-lifecycle] complete');
  } catch (error) {
    // Best-effort cleanup: restore API routes if still injected
    if (injected) {
      try {
        await restoreFn(page);
      } catch {
        // Swallow cleanup errors — the original error is more important
      }
    }
    throw error;
  }
}

// ─── Chaos API Helpers (Feature 1339) ───────────────────────────────────────

/** Default API base URL, configurable via PREPROD_API_URL env var */
const DEFAULT_API_BASE =
  process.env.PREPROD_API_URL || 'http://localhost:8000';

/**
 * Get an authentication token from the auth endpoint.
 *
 * In preprod/deployed environments, this returns a JWT from the auth service.
 * Locally (with mock DynamoDB / anonymous auth), this returns a UUID anonymous
 * token which chaos endpoints will reject (use `isChaosAvailable()` to check).
 *
 * This helper is for API-level chaos tests (chaos.spec.ts) that exercise the
 * backend chaos API directly, not for UI-level page tests.
 *
 * @param request - Playwright APIRequestContext fixture
 * @param apiBase - Base URL for the API (default: `PREPROD_API_URL` or `http://localhost:8000`)
 * @returns JWT or anonymous UUID token string
 *
 * @example
 * ```ts
 * const token = await getAuthToken(request);
 * const available = await isChaosAvailable(request, token);
 * if (available) {
 *   const exp = await createExperiment(request, token, 'ingestion_failure');
 * }
 * ```
 */
export async function getAuthToken(
  request: APIRequestContext,
  apiBase: string = DEFAULT_API_BASE,
): Promise<string> {
  const response = await request.post(`${apiBase}/api/v2/auth/anonymous`, {
    data: {},
  });
  const data = await response.json();
  return data.token;
}

/**
 * Check if the chaos API is available and the current token is authorized.
 *
 * Returns `true` only when chaos endpoints accept the provided token (requires
 * JWT auth and the chaos-experiments DynamoDB table to exist).
 *
 * - 401 = anonymous token rejected (needs JWT)
 * - 500+ = table/infrastructure missing
 * - 200 = chaos API is available
 *
 * This helper is for API-level chaos tests (chaos.spec.ts), not UI-level page tests.
 *
 * @param request - Playwright APIRequestContext fixture
 * @param token - Authentication token from `getAuthToken()`
 * @param apiBase - Base URL for the API (default: `PREPROD_API_URL` or `http://localhost:8000`)
 * @returns `true` if chaos API is available and token is accepted
 *
 * @example
 * ```ts
 * const available = await isChaosAvailable(request, token);
 * test.skip(!available, 'Chaos API not available');
 * ```
 */
export async function isChaosAvailable(
  request: APIRequestContext,
  token: string,
  apiBase: string = DEFAULT_API_BASE,
): Promise<boolean> {
  const resp = await request.get(`${apiBase}/chaos/experiments`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return resp.status() === 200;
}

/**
 * Create a chaos experiment via the backend API.
 *
 * Posts to the chaos experiments endpoint to create a new experiment with the
 * given scenario type and parameters. Asserts the response status is 201 and
 * returns the parsed experiment JSON.
 *
 * When the chaos gate is disarmed (default), experiments run in dry-run mode:
 * the full lifecycle executes but no infrastructure changes are applied.
 *
 * This helper is for API-level chaos tests (chaos.spec.ts), not UI-level page tests.
 *
 * @param request - Playwright APIRequestContext fixture
 * @param token - Authentication token from `getAuthToken()`
 * @param scenario - Chaos scenario type (e.g., 'ingestion_failure', 'dynamodb_throttle')
 * @param params - Optional scenario-specific parameters (e.g., `{ delay_ms: 3000 }`)
 * @param apiBase - Base URL for the API (default: `PREPROD_API_URL` or `http://localhost:8000`)
 * @returns Parsed experiment JSON with experiment_id, status, scenario_type, etc.
 *
 * @example
 * ```ts
 * const exp = await createExperiment(request, token, 'lambda_cold_start', { delay_ms: 3000 });
 * expect(exp.status).toBe('pending');
 * expect(exp.experiment_id).toBeTruthy();
 * ```
 */
export async function createExperiment(
  request: APIRequestContext,
  token: string,
  scenario: string,
  params: Record<string, unknown> = {},
  apiBase: string = DEFAULT_API_BASE,
): Promise<Record<string, unknown>> {
  const response = await request.post(`${apiBase}/chaos/experiments`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      scenario_type: scenario,
      duration_seconds: 60,
      blast_radius: 100,
      parameters: params,
    },
  });
  expect(response.status()).toBe(201);
  return (await response.json()) as Record<string, unknown>;
}

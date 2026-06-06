# Implementation Plan — Feature 1339: Chaos Test Infrastructure Overhaul

## Files to Modify

### 1. `frontend/tests/e2e/helpers/chaos-helpers.ts` (PRIMARY)

This is the only file that needs code changes. All new helpers are added here.
No existing tests are modified (NFR-001).

### Current Exports (MUST REMAIN)

```typescript
// Types
export type ChaosScenarioType
export const CHAOS_SCENARIOS

// API blocking
export async function blockAllApi(page, statusCode?)
export async function blockApiEndpoint(page, pattern, behavior)
export async function unblockAllApi(page)

// Health banner
export function getBannerLocator(page)
export function getDismissButton(page)
export async function triggerHealthBanner(page)
export async function waitForRecovery(page, consoleMessages)

// Console capture
export function captureConsoleEvents(page)  // to be deprecated

// Scenario simulation
export async function simulateChaosScenario(page, scenario)
```

### New Types to Add

```typescript
/** Structured telemetry event from emitErrorEvent() */
export interface TelemetryEvent {
  event: string;
  timestamp: string;
  details: Record<string, unknown>;
}

/** Captured telemetry events with query helper */
export interface TelemetryCapture {
  events: TelemetryEvent[];
  findEvent(name: string): TelemetryEvent | undefined;
  findAllEvents(name: string): TelemetryEvent[];
}

/** Snapshot of dashboard content for persistence verification */
export interface ContentSnapshot {
  childCount: number;
  keyContent: Map<string, string>;  // data-testid -> textContent
  chartVisible: boolean;
  errorIndicatorsPresent: string[];  // any error text found in baseline
  rawText: string;  // for debugging, not for comparison
}

/** Config for assertChaosLifecycle() */
export interface ChaosLifecycleConfig {
  page: Page;
  /** Inject failure (e.g., page.route or context.setOffline) */
  injectFn: (page: Page) => Promise<void>;
  /** Optional: trigger user action to cause failure (e.g., search) */
  triggerFn?: (page: Page) => Promise<void>;
  /** Assert degradation appeared (banner visible, skeleton shows, etc.) */
  assertDegradationFn: (page: Page) => Promise<void>;
  /** Remove failure (e.g., page.unroute or context.setOffline(false)) */
  restoreFn: (page: Page) => Promise<void>;
  /** Optional: assert recovery after restore */
  assertRecoveryFn?: (page: Page) => Promise<void>;
  options?: {
    /** Skip trigger step (for error boundary tests where inject IS the trigger) */
    skipTrigger?: boolean;
    /** Skip recovery step (for tests that only care about degradation) */
    skipRecovery?: boolean;
    /** Selector for content persistence baseline (default: 'main') */
    contentSelector?: string;
    /** Skip content persistence check entirely */
    skipContentCheck?: boolean;
  };
}
```

### New Functions to Add

#### 1. `captureTelemetryEvents(page: Page): TelemetryCapture`

```typescript
export function captureTelemetryEvents(page: Page): TelemetryCapture {
  const events: TelemetryEvent[] = [];
  
  page.on('console', (msg) => {
    if (msg.type() !== 'warning') return;
    const text = msg.text();
    try {
      const parsed = JSON.parse(text);
      if (typeof parsed.event === 'string') {
        events.push({
          event: parsed.event,
          timestamp: parsed.timestamp ?? '',
          details: parsed.details ?? {},
        });
      }
    } catch {
      // Not JSON — ignore (e.g., "[authStore] Profile refresh failed")
    }
  });

  return {
    events,
    findEvent(name: string) { return events.find(e => e.event === name); },
    findAllEvents(name: string) { return events.filter(e => e.event === name); },
  };
}
```

#### 2. `captureContentSnapshot(page: Page, selector?: string): Promise<ContentSnapshot>`

```typescript
export async function captureContentSnapshot(
  page: Page,
  selector: string = 'main',
): Promise<ContentSnapshot> {
  // ...evaluates page to extract childCount, key data-testid content,
  // chart visibility, error indicators, raw text
}
```

#### 3. `assertContentPersistence(before: ContentSnapshot, after: ContentSnapshot): void`

```typescript
export function assertContentPersistence(
  before: ContentSnapshot,
  after: ContentSnapshot,
): void {
  // Structural: child count within +/- 2
  // Key content: data-testid values match
  // Chart: visibility unchanged
  // Absence: no new error indicators appeared
}
```

#### 4. `forceErrorBoundary(page: Page, url?: string): Promise<void>`

```typescript
export async function forceErrorBoundary(
  page: Page,
  url: string = '/',
): Promise<void> {
  await page.addInitScript(() => {
    (window as any).__TEST_FORCE_ERROR = true;
  });
  await page.goto(url);
  await expect(page.getByText(/something went wrong/i)).toBeVisible({ timeout: 5000 });
}
```

#### 5. `assertChaosLifecycle(config: ChaosLifecycleConfig): Promise<void>`

```typescript
export async function assertChaosLifecycle(config: ChaosLifecycleConfig): Promise<void> {
  const { page, injectFn, triggerFn, assertDegradationFn, restoreFn, assertRecoveryFn, options } = config;
  let injected = false;

  try {
    // Step 1: Baseline
    console.log('[chaos-lifecycle] step 1: baseline');
    const banner = getBannerLocator(page);
    await expect(banner).not.toBeVisible({ timeout: 2000 });
    let baselineSnapshot: ContentSnapshot | undefined;
    if (!options?.skipContentCheck) {
      baselineSnapshot = await captureContentSnapshot(page, options?.contentSelector);
    }

    // Step 2: Inject
    console.log('[chaos-lifecycle] step 2: inject');
    await injectFn(page);
    injected = true;

    // Step 3: Trigger (optional)
    if (triggerFn && !options?.skipTrigger) {
      console.log('[chaos-lifecycle] step 3: trigger');
      await triggerFn(page);
    }

    // Step 4: Assert degradation
    console.log('[chaos-lifecycle] step 4: assert-degradation');
    await assertDegradationFn(page);
    if (baselineSnapshot && !options?.skipContentCheck) {
      const duringSnapshot = await captureContentSnapshot(page, options?.contentSelector);
      assertContentPersistence(baselineSnapshot, duringSnapshot);
    }

    // Step 5: Restore + recovery (optional)
    if (!options?.skipRecovery) {
      console.log('[chaos-lifecycle] step 5: restore');
      await restoreFn(page);
      injected = false;
      if (assertRecoveryFn) {
        await assertRecoveryFn(page);
      }
    }
  } catch (error) {
    // Cleanup: if injection happened but we failed mid-lifecycle, restore
    if (injected) {
      try { await restoreFn(page); } catch { /* best-effort cleanup */ }
    }
    throw error;
  }

  console.log('[chaos-lifecycle] complete');
}
```

#### 6. Relocated API Helpers

```typescript
import type { APIRequestContext } from '@playwright/test';

const DEFAULT_API_BASE = process.env.PREPROD_API_URL || 'http://localhost:8000';

export async function getAuthToken(
  request: APIRequestContext,
  apiBase: string = DEFAULT_API_BASE,
): Promise<string> { ... }

export async function isChaosAvailable(
  request: APIRequestContext,
  token: string,
  apiBase: string = DEFAULT_API_BASE,
): Promise<boolean> { ... }

export async function createExperiment(
  request: APIRequestContext,
  token: string,
  scenario: string,
  params: Record<string, unknown> = {},
  apiBase: string = DEFAULT_API_BASE,
): Promise<Record<string, unknown>> { ... }
```

### Deprecation Annotations

```typescript
/**
 * @deprecated Use captureTelemetryEvents() instead. This captures ALL console.warn
 * messages as raw strings. captureTelemetryEvents() only captures structured JSON
 * telemetry events from emitErrorEvent().
 */
export function captureConsoleEvents(page: Page): string[] { ... }
```

### JSDoc Updates to Existing Functions

- `simulateChaosScenario()` -- add note about `{ times: N }` option for transient failures
- `blockApiEndpoint()` -- add note about `{ times: N }` option
- `triggerHealthBanner()` -- document that it already uses response-based waits

## Files NOT Modified (verification only)

- `chaos-degradation.spec.ts` -- verify `assertChaosLifecycle()` could replace T007 (do NOT change)
- `chaos-cached-data.spec.ts` -- verify `assertContentPersistence()` could replace T013 (do NOT change)
- `chaos-error-boundary.spec.ts` -- verify `forceErrorBoundary()` matches inline version (do NOT change)
- `chaos.spec.ts` -- verify relocated helpers match inline versions (do NOT change)

## Insertion Order in chaos-helpers.ts

1. New type exports (after existing type section, line ~33)
2. `captureTelemetryEvents()` (after existing `captureConsoleEvents()`, ~line 296)
3. `captureContentSnapshot()` + `assertContentPersistence()` (new section after console capture)
4. `forceErrorBoundary()` (new section before chaos scenario simulation)
5. `assertChaosLifecycle()` (at end of file, after all other helpers)
6. Relocated API helpers (at very end, in their own section with a comment block)
7. Deprecation JSDoc on `captureConsoleEvents()`
8. Updated JSDoc on `simulateChaosScenario()`, `blockApiEndpoint()`

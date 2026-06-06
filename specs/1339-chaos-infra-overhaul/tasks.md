# Tasks — Feature 1339: Chaos Test Infrastructure Overhaul

## Task Dependencies

```
T1 (types) ──> T2 (telemetry)
           ──> T3 (content snapshot)
           ──> T4 (error boundary)
           ──> T6 (API helpers)
T2, T3, T4 ──> T5 (lifecycle)
T1-T6 ──────> T7 (deprecation + JSDoc)
T1-T7 ──────> T8 (verification)
```

## Tasks

### T1: Add New Type Exports
**File**: `frontend/tests/e2e/helpers/chaos-helpers.ts`
**Action**: Add after existing type section (~line 33)
**Details**:
- Add `TelemetryEvent` interface: `{ event: string; timestamp: string; details: Record<string, unknown> }`
- Add `TelemetryCapture` interface: `{ events: TelemetryEvent[]; findEvent(name: string): TelemetryEvent | undefined; findAllEvents(name: string): TelemetryEvent[] }`
- Add `ContentSnapshot` interface: `{ childCount: number; keyContent: Map<string, string>; chartVisible: boolean; errorIndicatorsPresent: string[]; rawText: string }`
- Add `ChaosLifecycleConfig` interface with all fields from plan (page, injectFn, triggerFn?, assertDegradationFn, restoreFn, assertRecoveryFn?, options?)
- Add `import type { APIRequestContext } from '@playwright/test'` to the existing import line
- Export all new types

**Acceptance**: TypeScript compiles with no errors. All types are importable.

### T2: Implement captureTelemetryEvents()
**File**: `frontend/tests/e2e/helpers/chaos-helpers.ts`
**Action**: Add after existing `captureConsoleEvents()` function
**Details**:
- Listens to `page.on('console')` for `warning` type messages
- Attempts `JSON.parse()` on each message text
- If parsed successfully and has `event` field (string), pushes to `events` array as `TelemetryEvent`
- If parse fails or no `event` field, silently ignores
- Returns `TelemetryCapture` object with `events` array and `findEvent`/`findAllEvents` helpers
- Full JSDoc with example usage showing capture of `api_health_banner_shown`

**Acceptance**: Given a page that emits `console.warn(JSON.stringify({event: "test", timestamp: "...", details: {}}))` and also `console.warn("[authStore] fail")`, the capture should contain exactly 1 event with `event === "test"` and 0 entries from the authStore warning.

### T3: Implement captureContentSnapshot() and assertContentPersistence()
**File**: `frontend/tests/e2e/helpers/chaos-helpers.ts`
**Action**: Add new section after telemetry capture section
**Details**:

`captureContentSnapshot(page, selector?)`:
- Uses `page.evaluate()` within the content `selector` (default: `'main'`)
- Counts direct children of the selector element
- Collects `aria-label` from all `[role="img"]` descendants (keyed as `role-img-0`, `role-img-1`, etc.)
- Collects `textContent` from all `[data-testid]` descendants (keyed by their testid value)
- Checks if any `[role="img"][aria-label*="chart"]` element exists -> `chartVisible`
- Scans full textContent for error patterns: `/something went wrong|error boundary|unexpected error|failed to load/i` -> `errorIndicatorsPresent`
- Captures full `textContent` as `rawText` (for debugging only)
- Returns `ContentSnapshot`

`assertContentPersistence(before, after)`:
- **Structural**: `after.childCount` must be >= `before.childCount - 2` (allows minor DOM changes)
- **Key content**: Every key in `before.keyContent` must exist in `after.keyContent` with the same value. Exception: values containing timestamps or numbers may differ (fuzzy match via regex strip of `\d{1,2}:\d{2}` patterns)
- **Chart**: If `before.chartVisible` is true, `after.chartVisible` must be true
- **Error absence**: Any string in `after.errorIndicatorsPresent` that was NOT in `before.errorIndicatorsPresent` causes failure
- Throws descriptive error with both snapshots' key differences

**Acceptance**: A snapshot before chaos with chart visible and "AAPL" in aria-label, compared to a snapshot after chaos where chart is gone and "something went wrong" appears, should FAIL with descriptive message. Same snapshots should PASS.

### T4: Implement forceErrorBoundary()
**File**: `frontend/tests/e2e/helpers/chaos-helpers.ts`
**Action**: Add new section before chaos scenario simulation section
**Details**:
- `async function forceErrorBoundary(page: Page, url: string = '/'): Promise<void>`
- Calls `page.addInitScript(() => { (window as any).__TEST_FORCE_ERROR = true; })`
- Calls `page.goto(url)`
- Calls `await expect(page.getByText(/something went wrong/i)).toBeVisible({ timeout: 5000 })`
- Full JSDoc explaining why addInitScript is needed (page.evaluate doesn't survive navigation)
- Exported

**Acceptance**: Calling `forceErrorBoundary(page)` should produce the same state as the inline version in `chaos-error-boundary.spec.ts:25-33`. The "Something went wrong" heading should be visible after the call.

### T5: Implement assertChaosLifecycle()
**File**: `frontend/tests/e2e/helpers/chaos-helpers.ts`
**Action**: Add at end of file (before API helpers section)
**Details**:
- `async function assertChaosLifecycle(config: ChaosLifecycleConfig): Promise<void>`
- Step 1 (baseline): Assert banner NOT visible (2s timeout). If `!options.skipContentCheck`, capture content snapshot.
- Step 2 (inject): Call `injectFn(page)`. Set `injected = true` flag.
- Step 3 (trigger): If `triggerFn` provided and `!options.skipTrigger`, call it.
- Step 4 (assert degradation): Call `assertDegradationFn(page)`. If baseline snapshot exists, capture new snapshot and call `assertContentPersistence()`.
- Step 5 (restore + recovery): If `!options.skipRecovery`, call `restoreFn(page)`. Set `injected = false`. If `assertRecoveryFn` provided, call it.
- Error handling: Wrap in try/catch. If `injected` is true when error occurs, call `restoreFn(page)` in catch block (best-effort, swallow errors). Re-throw original error.
- Each step emits `console.log('[chaos-lifecycle] step N: <name>')` for debugging.
- Emits `console.log('[chaos-lifecycle] complete')` on success.
- Full JSDoc with example usage for a banner lifecycle test.

**Acceptance**: Can express the T007 test (health banner appears after 3 failures) as a call to `assertChaosLifecycle()` with appropriate inject/trigger/assert functions. The lifecycle helper produces the same test outcome.

### T6: Relocate API Helpers from chaos.spec.ts
**File**: `frontend/tests/e2e/helpers/chaos-helpers.ts`
**Action**: Add at very end of file in new section `// --- Chaos API Helpers ---`
**Details**:

`getAuthToken(request: APIRequestContext, apiBase?: string): Promise<string>`:
- Default apiBase: `process.env.PREPROD_API_URL || 'http://localhost:8000'`
- POSTs to `${apiBase}/api/v2/auth/anonymous` with empty body
- Returns `data.token`
- JSDoc: explains this returns JWT in preprod, anonymous UUID locally

`isChaosAvailable(request: APIRequestContext, token: string, apiBase?: string): Promise<boolean>`:
- GETs `${apiBase}/chaos/experiments` with Bearer token
- Returns `true` if status === 200
- JSDoc: explains 401 = anonymous token rejected, 500+ = infra missing

`createExperiment(request: APIRequestContext, token: string, scenario: string, params?: Record<string, unknown>, apiBase?: string): Promise<Record<string, unknown>>`:
- POSTs to `${apiBase}/chaos/experiments` with Bearer token and body
- Asserts `response.status() === 201` via Playwright `expect`
- Returns parsed JSON
- JSDoc: explains dry-run behavior when gate is disarmed

All three exported.

**Acceptance**: chaos.spec.ts can import these from `./helpers/chaos-helpers` and work identically to the current inline versions (verify by reading, NOT by modifying chaos.spec.ts).

### T7: Deprecation Annotations and JSDoc Updates
**File**: `frontend/tests/e2e/helpers/chaos-helpers.ts`
**Action**: Update existing functions
**Details**:

1. `captureConsoleEvents()`: Add `@deprecated` JSDoc tag. Add message: "Use captureTelemetryEvents() instead for structured JSON telemetry events. This function captures ALL console.warn messages as raw strings."

2. `simulateChaosScenario()`: Add JSDoc note: "Tip: For transient failures, use page.route(pattern, handler, { times: N }) directly instead of this helper. This helper applies a permanent interception until the restore function is called."

3. `blockApiEndpoint()`: Add JSDoc note: "Tip: Playwright supports { times: N } option on page.route() (v1.15+) for transient failure simulation."

4. `triggerHealthBanner()`: Add JSDoc note confirming response-based waits: "Uses page.waitForResponse() after each search interaction (not waitForTimeout) to ensure failure is recorded before proceeding."

**Acceptance**: All existing tests pass unchanged. JSDoc is visible in IDE hover.

### T8: Verification
**Action**: Read-only verification (no file changes)
**Details**:
1. Verify TypeScript compilation: `cd frontend && npx tsc --noEmit`
2. Verify all existing exports still exist in chaos-helpers.ts
3. Verify chaos.spec.ts inline helpers match relocated versions (semantic comparison)
4. Verify chaos-error-boundary.spec.ts inline forceErrorBoundary matches shared version
5. Verify no `waitForTimeout` in new code
6. Verify all new functions have JSDoc
7. Run existing chaos tests to confirm no regressions (if local server available)

**Acceptance**: Zero TypeScript errors. Zero test regressions. All success criteria from spec met.

## Estimated Implementation Order

1. T1 (types) -- foundation, no logic
2. T2 (telemetry capture) -- standalone, no deps on other new code
3. T3 (content snapshot) -- standalone
4. T4 (error boundary) -- standalone
5. T6 (API helpers) -- standalone
6. T5 (lifecycle) -- depends on T3 (content snapshot)
7. T7 (JSDoc updates) -- trivial, do alongside others
8. T8 (verification) -- final step

Total: ~200-250 lines of new TypeScript added to chaos-helpers.ts.

# Feature 1339: Chaos Test Infrastructure Overhaul

## Status: DRAFT

## Problem Statement

The chaos test suite has accumulated organic helper functions scattered across spec files
and a shared helpers module. Patterns are inconsistent: some tests capture content before
chaos and compare after, others just check "something is visible." Some tests use
`waitForTimeout` for settling, others use response-based waits. The telemetry capture
(`captureConsoleEvents`) blindly collects all `console.warn` messages rather than
filtering for structured JSON telemetry events.

This creates two problems:
1. **Green Dashboard Syndrome** -- tests pass because "some content is visible" but don't
   verify it's the SAME content that was there before chaos. A bug that replaces real data
   with an error page would pass.
2. **Copy-paste drift** -- each new chaos spec re-implements the same 5-step lifecycle
   (baseline -> inject -> trigger -> assert degradation -> recover). Implementations
   diverge silently.

This feature establishes shared infrastructure so all chaos tests enforce the same rigor.

## User Stories

### US-001: Canonical Chaos Lifecycle Helper
**As a** test author writing a new chaos scenario,
**I want** a single `assertChaosLifecycle()` helper that encapsulates the 5-step chaos
verification pattern,
**So that** every chaos test enforces baseline capture, degradation detection, and
recovery verification without copy-pasting boilerplate.

### US-002: Content Persistence Verification
**As a** test author verifying cached data resilience,
**I want** an `assertContentPersistence()` helper that captures a structured snapshot of
dashboard content before chaos and asserts the SAME content is present after chaos,
**So that** Green Dashboard Syndrome is detected (content replaced by error page would
fail the assertion).

### US-003: Structured Telemetry Capture
**As a** test author verifying observability events,
**I want** a `captureTelemetryEvents()` helper that only captures structured JSON
`emitErrorEvent()` output and ignores non-telemetry console.warn messages,
**So that** telemetry assertions are precise and don't break when unrelated warnings
are added.

### US-004: Reusable Error Boundary Trigger
**As a** test author testing error boundary behavior,
**I want** a shared `forceErrorBoundary()` helper in chaos-helpers.ts,
**So that** the `addInitScript` + `page.goto()` pattern isn't re-implemented in every
error boundary test.

### US-005: API-Level Chaos Helpers in Shared Module
**As a** test author testing the backend chaos API lifecycle,
**I want** `getAuthToken()`, `isChaosAvailable()`, and `createExperiment()` available
from chaos-helpers.ts,
**So that** future chaos API tests don't duplicate these functions.

## Requirements

### Functional Requirements

#### FR-001: assertChaosLifecycle()
- Accepts a config object with: `page`, `injectFn`, `triggerFn` (optional), `assertDegradationFn`, `restoreFn`, `assertRecoveryFn` (optional), `options`
- Step 1: Captures baseline state (banner NOT visible, content IS visible via `assertContentPersistence` snapshot)
- Step 2: Calls `injectFn(page)` to inject the failure
- Step 3: If `triggerFn` provided, calls it (e.g., user search action)
- Step 4: Calls `assertDegradationFn(page)` (caller-defined: banner visible, skeleton shows, etc.)
- Step 5: Calls `restoreFn(page)` to remove failure, then optionally calls `assertRecoveryFn(page)`
- If `options.skipTrigger` is true, step 3 is skipped (for error boundary tests that crash on render)
- If `options.skipRecovery` is true, step 5 is skipped (for tests that only care about degradation)
- Each step emits a console.log marker (`[chaos-lifecycle] step N: <name>`) for debugging flaky tests

#### FR-002: assertContentPersistence()
- Accepts `page` and an optional `selector` (default: `'main'`)
- Returns a `ContentSnapshot` object with: `textContent`, `childCount`, `chartVisible` (boolean), `dataAttributes` (map of data-testid -> text)
- Provides `assertUnchanged(laterSnapshot)` method that compares two snapshots
- Comparison is fuzzy: text content must overlap by >= 80% (handles dynamic timestamps), child count must be within +/- 2, chart visibility must match
- Fails with descriptive message: "Content changed during chaos: before had N children with 'AAPL' text, after has M children without 'AAPL'"

#### FR-003: captureTelemetryEvents()
- Accepts `page`
- Returns a mutable array of parsed `TelemetryEvent` objects (not raw strings)
- `TelemetryEvent` type: `{ event: string; timestamp: string; details: Record<string, unknown> }`
- Only captures `console.warn` messages that are valid JSON with an `event` field
- Ignores non-JSON warnings (e.g., `[authStore] Profile refresh failed: ...`)
- Provides `findEvent(name: string)` helper on the returned array (via prototype extension or wrapper)

#### FR-004: forceErrorBoundary()
- Accepts `page` and optional `url` (default: `'/'`)
- Uses `page.addInitScript()` to set `window.__TEST_FORCE_ERROR = true`
- Navigates to `url`
- Waits for "something went wrong" text to be visible (5s timeout)
- Returns void

#### FR-005: Relocated API Helpers
- `getAuthToken(request, apiBase?)` -- returns JWT or anonymous token
- `isChaosAvailable(request, token, apiBase?)` -- returns boolean
- `createExperiment(request, token, scenario, params?, apiBase?)` -- returns experiment JSON
- All accept optional `apiBase` parameter (default: `process.env.PREPROD_API_URL || 'http://localhost:8000'`)
- Exported from chaos-helpers.ts with JSDoc explaining they are for API-level chaos tests (chaos.spec.ts), not UI-level page tests

#### FR-006: Existing Helper Updates
- `triggerHealthBanner()` -- verify it already uses response-based waits (not `waitForTimeout`). Document with JSDoc.
- `captureConsoleEvents()` -- mark as `@deprecated` in favor of `captureTelemetryEvents()`. Do NOT remove (existing tests use it).
- Add `{ times: N }` documentation to `simulateChaosScenario()` and `blockApiEndpoint()` JSDoc

### Non-Functional Requirements

#### NFR-001: Zero Breaking Changes
- All existing exports must remain. New helpers are additive.
- `captureConsoleEvents()` is deprecated but not removed.

#### NFR-002: Type Safety
- All new helpers must have full TypeScript types (no `any` except where Playwright's `request` fixture requires it).
- `TelemetryEvent` and `ContentSnapshot` types must be exported.

#### NFR-003: No waitForTimeout
- No new `waitForTimeout` calls in any added helper.
- All waits must be response-based (`waitForResponse`), DOM-based (`expect().toBeVisible()`), or poll-based (`expect.poll()`).

#### NFR-004: Documentation
- Every exported function must have JSDoc with: purpose, parameters, return value, example usage, and which chaos test pattern it supports.

## Success Criteria

1. `assertChaosLifecycle()` can replace the manual 5-step pattern in chaos-degradation.spec.ts T007 test with identical behavior
2. `assertContentPersistence()` catches a simulated Green Dashboard Syndrome scenario (content replaced by error text)
3. `captureTelemetryEvents()` captures `api_health_banner_shown` event but ignores `[authStore]` warnings
4. `forceErrorBoundary()` is callable from both chaos-error-boundary.spec.ts and chaos-accessibility.spec.ts without code duplication
5. `getAuthToken()`, `isChaosAvailable()`, `createExperiment()` work from chaos-helpers.ts import in chaos.spec.ts
6. All existing chaos tests continue to pass without modification (NFR-001)

## Out of Scope

- Migrating existing tests to use new helpers (separate follow-up features per spec file)
- SSE reconnection testing infrastructure (tracked in Feature 1280)
- Changes to the production `emitErrorEvent()` function signature
- Backend chaos API changes

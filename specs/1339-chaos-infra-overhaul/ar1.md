# Adversarial Review #1 — Feature 1339: Chaos Test Infrastructure Overhaul

## Review Date: 2026-04-06

## Findings

### AR1-001: 5-Step Pattern Does Not Fit Error Boundary Tests (MEDIUM)

**Attack**: The `assertChaosLifecycle()` 5-step pattern assumes: baseline -> inject ->
trigger -> assert degradation -> recover. But error boundary tests (chaos-error-boundary.spec.ts)
work differently: `forceErrorBoundary()` IS both the inject and the trigger (the error
is thrown on render, not on a user action). There is no "recovery" step for error boundary
tests -- the user clicks "Try Again" or "Reload", which is a test assertion, not a
lifecycle step.

**Impact**: If we force error boundary tests into this pattern, the `triggerFn` becomes
meaningless and `restoreFn` would be awkward (what does "restore" mean when the error
boundary has replaced the DOM?).

**Disposition**: ACCEPTED. The spec already addresses this via `options.skipTrigger` and
`options.skipRecovery`. The `injectFn` would be `forceErrorBoundary()` and
`assertDegradationFn` would check for "something went wrong" text. The lifecycle helper
is still useful because it handles Step 1 (baseline capture) consistently. Error boundary
tests that don't fit the pattern can skip the helper entirely -- it's optional, not mandatory.

**Spec Change**: Add explicit note to FR-001 that error boundary tests may use
`forceErrorBoundary()` directly without `assertChaosLifecycle()` wrapper if the 5-step
pattern doesn't fit. The helper is a convenience, not a requirement.

### AR1-002: Content Persistence 80% Overlap Is Fragile for Dynamic Content (HIGH)

**Attack**: FR-002 says text content must overlap by >= 80%. But the dashboard has:
- Timestamps that change every second ("Last updated: 3:14:22 PM")
- Ticker prices that may animate
- TanStack Query refetch indicators
- Chart canvas elements whose `textContent` is empty (content is pixels, not text)

An 80% text overlap could fail on a perfectly healthy page if timestamps tick over
between snapshots. Conversely, it could PASS when real data is replaced by a long error
message (which shares no text with the original).

**Impact**: False positives (healthy page fails) and false negatives (broken page passes)
both undermine the helper's purpose.

**Disposition**: ACCEPTED, requires spec change. Replace raw text overlap percentage with
structural comparison:
1. **Structural check**: `childCount` must be within +/- 2 (unchanged)
2. **Key content check**: Extract text from specific data-testid elements (ticker symbol,
   chart container aria-label) and assert they are identical
3. **Absence check**: Error indicators (`"something went wrong"`, `"error"`, `"failed"`)
   must NOT appear if they weren't present in the baseline
4. Drop the 80% text overlap -- it's unreliable.

**Spec Change**: Revise FR-002 comparison strategy from fuzzy text overlap to structural +
key-content + absence checking.

### AR1-003: captureTelemetryEvents() Race Condition (LOW)

**Attack**: `captureTelemetryEvents()` starts listening when called. If a telemetry event
fires before the helper is called (e.g., during page load), it's missed. This is the same
limitation as `captureConsoleEvents()`, so it's not a regression.

**Impact**: Tests that depend on capturing events during page.goto() must call
`captureTelemetryEvents()` BEFORE navigation.

**Disposition**: ACCEPTED, no spec change needed. Document the call-before-navigation
requirement in JSDoc. This matches the existing `captureConsoleEvents()` behavior.

### AR1-004: Relocated API Helpers Use `any` for request Fixture (LOW)

**Attack**: FR-005 says "no `any` except where Playwright's request fixture requires it."
Playwright's `APIRequestContext` type is available and should be used instead of `any`.

**Impact**: Loss of type safety in API helpers.

**Disposition**: ACCEPTED. Use `import type { APIRequestContext } from '@playwright/test'`
instead of `any` for the request parameter.

**Spec Change**: Update FR-005 to specify `APIRequestContext` type for `request` parameter.

### AR1-005: assertChaosLifecycle() Step Markers May Pollute Console Output (LOW)

**Attack**: FR-001 says each step emits `console.log` markers. If tests use
`captureTelemetryEvents()` (which filters to JSON-only warnings), the markers won't
interfere. But if tests still use `captureConsoleEvents()` (which captures all warnings),
and the markers use `console.warn`, they'd pollute the events array.

**Impact**: Minimal -- markers use `console.log`, not `console.warn`, so
`captureConsoleEvents()` (which filters on `warning` type) won't see them.

**Disposition**: ACCEPTED, no change needed. The current design already avoids this by
using `console.log` for markers.

### AR1-006: Does assertChaosLifecycle Handle Async Failures in injectFn? (MEDIUM)

**Attack**: What if `injectFn` throws? The lifecycle would abort mid-way, leaving route
interceptions in place. The test would fail with an opaque error about the inject function
rather than a clear lifecycle failure message.

**Impact**: Debugging difficulty when injection setup fails.

**Disposition**: ACCEPTED. Wrap each step in try/catch that logs which step failed and
re-throws. Add cleanup in a `finally` block that calls `restoreFn` if injection succeeded
but a later step failed.

**Spec Change**: Add error handling requirement to FR-001: if any step fails after
injection (step 2), the `restoreFn` must be called in a finally block to prevent route
leak. Step failure messages must include the step number and name.

## Summary

| ID | Severity | Disposition | Spec Change Required |
|----|----------|-------------|---------------------|
| AR1-001 | MEDIUM | Accepted | Minor: add note about optional usage |
| AR1-002 | HIGH | Accepted | Major: revise FR-002 comparison strategy |
| AR1-003 | LOW | Accepted | No change (document in JSDoc) |
| AR1-004 | LOW | Accepted | Minor: use APIRequestContext type |
| AR1-005 | LOW | Accepted | No change |
| AR1-006 | MEDIUM | Accepted | Minor: add error handling to FR-001 |

## Verdict: PROCEED with spec amendments from AR1-002, AR1-004, AR1-006

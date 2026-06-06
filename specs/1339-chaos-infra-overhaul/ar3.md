# Adversarial Review #3 — Final Readiness — Feature 1339

## Review Date: 2026-04-06

## Highest Risk Task

**T3: captureContentSnapshot() + assertContentPersistence()** is the highest-risk task.

**Why**:
1. **page.evaluate() complexity**: The snapshot function runs a JS function inside the
   browser context to query DOM elements. If the selector doesn't match (e.g., no `main`
   element during error boundary state), it returns empty data. Edge case: what if `main`
   exists but has no children during initial load (skeleton state)?

2. **Fuzzy comparison is hard to get right**: The "same content" check must handle
   timestamps, animation states, and React Query background refetch indicators without
   false positives. Too strict = flaky tests. Too loose = misses Green Dashboard Syndrome.

3. **Chart detection depends on aria-label pattern**: If the chart component's aria-label
   format changes (e.g., Feature 1400 renames it), `chartVisible` breaks silently. Mitigation:
   use a broad selector `[role="img"]` rather than string-matching the aria-label.

**Most likely rework source**: The fuzzy key-content comparison in
`assertContentPersistence()`. If a key like `role-img-0` has aria-label
`"Price and sentiment chart for AAPL. 21 price candles..."` before chaos, and during chaos
the page re-renders with `"Price and sentiment chart for AAPL. 20 price candles..."` (one
candle filtered by stale-data logic), the assertion would fail even though the dashboard
is working correctly.

**Mitigation**: For aria-label comparisons, strip numeric values before comparing. Compare
only the structural text: `"Price and sentiment chart for AAPL. price candles and sentiment points."`

## Other Risks

### RISK-001: Type Import Collision (LOW)
Adding `APIRequestContext` to the import from `@playwright/test` might cause issues if
the existing import is a named import destructuring `{ type Page, type Route, expect }`.
Need to verify the exact import statement.

**Current import (line 12)**: `import { type Page, type Route, expect } from '@playwright/test';`

Adding `type APIRequestContext` to this list is safe.

### RISK-002: createExperiment Uses expect() (LOW)
The relocated `createExperiment()` calls `expect(response.status()).toBe(201)`. This
means importing it in a non-test context would fail. Since it's only used in test files,
this is fine, but the JSDoc should warn about this.

### RISK-003: File Length Growth (LOW)
chaos-helpers.ts is currently 317 lines. Adding ~250 lines makes it ~570 lines. This is
within reason for a shared test utilities file but approaching the point where a split
might be warranted. Not blocking for this feature -- the file is still single-purpose
(chaos test infrastructure).

**Recommendation**: If this file exceeds 700 lines in future features, split into:
- `chaos-helpers.ts` (existing: scenario simulation, API blocking, banner utilities)
- `chaos-assertions.ts` (new: lifecycle, content persistence, telemetry capture)
- `chaos-api.ts` (new: API-level helpers for chaos.spec.ts)

## Readiness Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| Spec complete | YES | Amended per AR1 findings |
| Plan covers all requirements | YES | All FRs mapped to functions |
| Tasks ordered by dependency | YES | Types -> standalone -> lifecycle -> verify |
| No breaking changes | YES | All existing exports preserved, no test modifications |
| Highest risk identified | YES | T3 fuzzy comparison |
| Mitigation documented | YES | Strip numbers from aria-labels before comparison |
| Out-of-scope clear | YES | No test migration, no backend changes |

## Verdict: READY FOR IMPLEMENTATION

All risks are mitigatable within the current task structure. No task reordering or
additional research needed. Proceed to Stage 9 (pause).

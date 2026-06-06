# Adversarial Review #2 — Drift Check — Feature 1339

## Review Date: 2026-04-06

## Drift Analysis

### DRIFT-001: ContentSnapshot keyContent Strategy Changed (MINOR)

**Original spec (FR-002)**: `keyContent` is `Map<string, string>` keyed by `data-testid`.

**Clarification finding**: The dashboard has very few `data-testid` elements on content
areas. The chart `aria-label` on `[role="img"]` elements is the strongest content signal.

**Updated approach**: `keyContent` should capture:
- `[role="img"]` elements' `aria-label` values (keyed by `role-img-N`)
- `[data-testid]` elements' `textContent` values (keyed by their testid)
- This is a strictly better strategy — no requirements dropped, just implementation refined.

**Impact**: Plan change needed. The `captureContentSnapshot()` page evaluation must query
both `[role="img"][aria-label]` and `[data-testid]` within the content selector.

**Severity**: MINOR. No user story or success criteria changes.

### DRIFT-002: createExperiment Return Type Needs expect Import (NONE)

**Clarification confirmed**: `expect` is already imported in chaos-helpers.ts (line 12).
`APIRequestContext` type is available from `@playwright/test`.

**Impact**: No drift. Plan already accounts for this.

### DRIFT-003: No New Requirements Discovered (NONE)

All five clarification questions confirmed existing assumptions. No new chaos test patterns,
no new telemetry events, no unexpected component behaviors.

## Verdict: MINOR DRIFT ONLY

Update plan's `captureContentSnapshot()` implementation to query both `[role="img"]`
aria-labels and `[data-testid]` elements. No structural changes to spec, plan, or task
breakdown needed.

**Proceed to Stage 7 (Tasks)** -- no Stage 6 second-pass plan needed for this minor drift.
The implementation detail is captured here and will be reflected in the task descriptions.

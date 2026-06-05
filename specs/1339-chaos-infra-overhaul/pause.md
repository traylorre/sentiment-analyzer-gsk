# Stage 9: PAUSE — Feature 1339: Chaos Test Infrastructure Overhaul

## Status: READY FOR IMPLEMENTATION (paused per battleplan protocol)

## Accrued Questions for User

1. **Content persistence comparison strictness**: The plan strips numeric values from
   aria-labels before comparison to avoid false failures when candle counts change by +/-1
   during chaos. Is this acceptable, or should the comparison be even looser (e.g., only
   check that the ticker symbol "AAPL" appears)?

2. **File split threshold**: chaos-helpers.ts will grow from ~317 to ~570 lines. Should we
   preemptively split into `chaos-helpers.ts`, `chaos-assertions.ts`, and `chaos-api.ts`
   now, or wait until the file hits ~700 lines?

3. **captureConsoleEvents deprecation timeline**: The spec marks it `@deprecated` but
   doesn't remove it. Should we create a follow-up feature to migrate all existing callers
   (chaos-degradation.spec.ts uses it in T007, T008, T009) and then remove it?

## Accrued Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| T3 fuzzy comparison false positives on dynamic content | HIGH | Strip numbers from aria-labels; structural + absence checks instead of text overlap |
| page.evaluate() returns empty snapshot if `main` not yet rendered | MEDIUM | Add guard: if childCount === 0 and no error indicators, retry once after 1s wait |
| aria-label format change breaks chartVisible detection | LOW | Use broad `[role="img"]` selector, not string match |
| File growing to 570 lines | LOW | Acceptable for now; split at 700+ |
| createExperiment() uses expect() — not usable outside test files | LOW | Document in JSDoc |

## Artifacts Produced

| Artifact | Path | Description |
|----------|------|-------------|
| spec.md | `specs/1339-chaos-infra-overhaul/spec.md` | 5 user stories, 6 FRs, 4 NFRs, 6 success criteria |
| ar1.md | `specs/1339-chaos-infra-overhaul/ar1.md` | 6 findings, 3 spec amendments (FR-001, FR-002, FR-005) |
| plan.md | `specs/1339-chaos-infra-overhaul/plan.md` | Function signatures, insertion order, file change map |
| clarify.md | `specs/1339-chaos-infra-overhaul/clarify.md` | 5 questions self-answered from codebase |
| ar2.md | `specs/1339-chaos-infra-overhaul/ar2.md` | Minor drift on keyContent strategy |
| tasks.md | `specs/1339-chaos-infra-overhaul/tasks.md` | 8 tasks, dependency graph, acceptance criteria |
| ar3.md | `specs/1339-chaos-infra-overhaul/ar3.md` | Final readiness review, highest-risk task identified |
| pause.md | `specs/1339-chaos-infra-overhaul/pause.md` | This file |

## Implementation Summary

**Single file change**: `frontend/tests/e2e/helpers/chaos-helpers.ts`
**~250 lines added**, zero lines removed, zero existing tests modified.

**New exports**: `TelemetryEvent`, `TelemetryCapture`, `ContentSnapshot`,
`ChaosLifecycleConfig`, `captureTelemetryEvents()`, `captureContentSnapshot()`,
`assertContentPersistence()`, `forceErrorBoundary()`, `assertChaosLifecycle()`,
`getAuthToken()`, `isChaosAvailable()`, `createExperiment()`

**Deprecation**: `captureConsoleEvents()` marked `@deprecated`

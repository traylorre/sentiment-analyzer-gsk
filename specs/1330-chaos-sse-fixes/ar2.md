# AR#2: Cross-Artifact Consistency Check

## Spec vs Plan Alignment

### Check 1: US1 (Delete SSE tests) -> Phase 1
**Spec says**: Delete chaos-sse-recovery.spec.ts and chaos-sse-lifecycle.spec.ts
**Plan says**: Phase 1, Steps 1.1 and 1.2 delete both files
**Verdict**: ALIGNED

### Check 2: US2 (Fix cached data auth race) -> Phase 2
**Spec says**: Fix auth race in chaos-cached-data.spec.ts
**Plan says**: Phase 2 originally hypothesized timing race

**MISALIGNMENT FOUND**: Clarification (Stage 4, Q4) revealed the root cause is NOT a
timing race — it's a mock response format mismatch. The plan must be updated:
- Original: "use addInitScript to pre-seed auth store"
- Corrected: Fix `mockTickerDataApis()` to return `token` instead of `access_token`

**Verdict**: PLAN NEEDS UPDATE (Phase 2)

### Check 3: US3 (Fix a11y tests) -> Phase 3
**Spec says**: Fix or document a11y violations
**Plan says**: Phase 3, run locally, triage, fix or exclude
**Verdict**: ALIGNED

### Check 4: US4 (Fix error boundary) -> Phase 4
**Spec says**: Fix T023 (error boundary during degradation)
**Plan says**: Phase 4, investigate triggerHealthBanner + goto sequence

**Clarification reveals**: The `triggerHealthBanner()` API block persists through the
`goto('/')` call. The `useSessionInit()` call fails (503). `setInitialized(true)` is
called anyway. ErrorTrigger only needs `__TEST_FORCE_ERROR` — it doesn't need auth.
The test should work as-is.

If T023 actually fails, it's likely because the test is NOT in the failure list. Let me
re-check the problem statement.

**RE-CHECK**: The problem statement says chaos-error-boundary.spec.ts has 1 failure. The
file has 3 tests: T022, T023, T024. Which one fails?

The diagnosis says "Error boundary button text/selector may have changed." This points
at T024 (keyboard navigation) which checks `document.activeElement?.textContent?.trim()`
— this could fail if button text includes icon text or whitespace.

But T022 is the simplest test (just checks error boundary renders). T023 adds health
banner first. T024 does keyboard navigation.

Most likely T024 fails (keyboard focus order depends on DOM order and icon rendering).
Or T023 fails because the API block from `triggerHealthBanner()` prevents the error
boundary page from rendering properly.

**Verdict**: NEEDS CLARIFICATION — which specific test in chaos-error-boundary.spec.ts
fails? The plan covers all three but implementation should focus on the actual failure.

## Spec vs Clarification Alignment

### Check 5: Root cause table accuracy
**Spec says**: Tests 5-6 fail due to "auth/data race"
**Clarification says**: Tests 5-6 fail due to "mock response format mismatch"

**Verdict**: SPEC NEEDS UPDATE to reflect correct root cause.

### Check 6: FR-003 accuracy
**Spec FR-003 says**: "use addInitScript to pre-seed auth store"
**Clarification says**: Fix is simpler — correct the mock response JSON

**Verdict**: FR-003 NEEDS UPDATE

## Plan vs Clarification Alignment

### Check 7: Phase 2 mechanism
**Plan says**: Hypothesizes three possible causes (a, b, c), fallback to addInitScript
**Clarification says**: Cause is (a) but more specific — `token` field missing from mock

**Verdict**: PLAN PHASE 2 NEEDS UPDATE to specify the exact fix

## AR#1 Findings Still Valid

### AV1 (SSE untested): Still valid
### AV2 (Auth fix unclear): NOW RESOLVED by clarification
### AV3 (A11y assumptions): Still valid — must run locally to triage
### AV4 (T038-T040 vacuous): Still valid
### AV5 (Test ID traceability): Still valid

## Summary of Required Updates

| Artifact | Section | Issue | Action |
|----------|---------|-------|--------|
| spec.md | Root cause table, rows 5-6 | Says "auth race" | Update to "mock format mismatch" |
| spec.md | FR-003 | Says "addInitScript to pre-seed" | Update to "fix mock response JSON" |
| plan.md | Phase 2 | Hypothesizes race, proposes addInitScript | Update to fix `mockTickerDataApis()` auth mock |
| plan.md | Phase 4 | Generic investigation | Narrow to specific test failure |

## Disposition: PROCEED to Stage 6 (Plan Second Pass) with updates.

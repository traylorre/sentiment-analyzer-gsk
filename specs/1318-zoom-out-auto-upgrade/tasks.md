# Feature 1318: Tasks — Zoom-Out Auto-Upgrade

## Status: READY FOR IMPLEMENTATION

## Task List

### Phase 1: Pure Utility Functions (no component changes)

#### T1: Add `TIME_RANGE_ORDER` constant to `types/chart.ts`
- **File**: `frontend/src/types/chart.ts`
- **Action**: Insert after line 21 (after `TIME_RANGE_DAYS` closing brace)
- **Detail**: Add `export const TIME_RANGE_ORDER: TimeRange[] = ['1W', '1M', '3M', '6M', '1Y'];`
- **Lines added**: ~2
- **Depends on**: Nothing
- **Verifiable**: Import in test file, assert `.length === 5` and order matches

#### T2: Add `getNextTimeRange()` function to `types/chart.ts`
- **File**: `frontend/src/types/chart.ts`
- **Action**: Insert after `TIME_RANGE_ORDER`
- **Detail**: Pure function. Uses `indexOf` on `TIME_RANGE_ORDER`. Returns `null` if at end or unknown input.
- **Lines added**: ~8
- **Depends on**: T1
- **Verifiable**: Unit test: all 5 transitions (1W->1M, 1M->3M, 3M->6M, 6M->1Y, 1Y->null)

#### T3: Add `shouldUpgradeTimeRange()` function to `types/chart.ts`
- **File**: `frontend/src/types/chart.ts`
- **Action**: Insert after `getNextTimeRange`
- **Detail**: Pure function. Computes left overshoot (`Math.max(0, -visibleFrom)`), right overshoot (`Math.max(0, visibleTo - dataLength)`), returns `totalOvershoot > dataLength * 0.3`. Guard: `if (dataLength === 0) return false;`
- **Lines added**: ~15
- **Depends on**: Nothing (standalone math)
- **Verifiable**: Unit test: 8 edge cases covering zero data, zoom-in, below/above threshold, boundary, left-only, right-only

### Phase 2: Pure Function Unit Tests

#### T4: Create `frontend/tests/unit/types/chart-utils.test.ts`
- **File**: `frontend/tests/unit/types/chart-utils.test.ts` (NEW)
- **Action**: Create directory `frontend/tests/unit/types/` if needed, then create test file
- **Detail**: Import `TIME_RANGE_ORDER`, `getNextTimeRange`, `shouldUpgradeTimeRange` from `@/types/chart`. Three `describe` blocks:
  - `TIME_RANGE_ORDER`: 1 test (order assertion)
  - `getNextTimeRange`: 5 tests (all transitions + null at max)
  - `shouldUpgradeTimeRange`: 8 tests (zero data, within bounds, below threshold, above threshold, left-only, right-only, exact boundary, just-past boundary)
- **Lines added**: ~55
- **Depends on**: T1, T2, T3
- **Verifiable**: `npx vitest run tests/unit/types/chart-utils.test.ts` — all 14 tests pass

#### T5: Run utility unit tests — verify pass
- **Action**: Execute `cd frontend && npx vitest run tests/unit/types/chart-utils.test.ts`
- **Depends on**: T4
- **Verifiable**: Exit code 0, 14 tests pass, 0 failures

### Phase 3: Component Wiring — Imports and Refs

#### T6: Add imports to `price-sentiment-chart.tsx`
- **File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
- **Action**: Modify line 23 — extend the import from `@/types/chart` to include `getNextTimeRange` and `shouldUpgradeTimeRange`
- **Detail**: Change `import { RESOLUTION_LABELS } from '@/types/chart';` to `import { RESOLUTION_LABELS, getNextTimeRange, shouldUpgradeTimeRange } from '@/types/chart';`
- **Lines modified**: 1
- **Depends on**: T1, T2, T3
- **Verifiable**: No TypeScript errors on save

#### T7: Add new refs for subscription callback
- **File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
- **Action**: Insert after line 107 (after `gapShaderRef` declaration)
- **Detail**: Add 5 refs:
  ```typescript
  const dataLengthRef = useRef(0);
  const timeRangeRef = useRef<TimeRange>(timeRange);
  const isLoadingRef = useRef(isLoading);
  const justFitContentRef = useRef(false);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  ```
- **Lines added**: ~6
- **Depends on**: T6 (needs TypeRange import already present)
- **Verifiable**: No TypeScript errors

#### T8: Add ref synchronization in render body
- **File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
- **Action**: Insert before the `return (` statement (before line 490)
- **Detail**: Add 3 lines:
  ```typescript
  dataLengthRef.current = priceData.length;
  timeRangeRef.current = timeRange;
  isLoadingRef.current = isLoading;
  ```
- **Lines added**: ~4 (including comment)
- **Depends on**: T7
- **Verifiable**: No TypeScript errors. Refs reflect current state each render.

### Phase 4: fitContent Loop Prevention

#### T9: Add `justFitContentRef` guard around price data `fitContent()` call
- **File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
- **Action**: Modify lines 399-401 (price data useEffect fitContent block)
- **Detail**: Wrap `fitContent()` with flag set/reset:
  ```typescript
  if (chartRef.current) {
    justFitContentRef.current = true;
    chartRef.current.timeScale().fitContent();
    setTimeout(() => { justFitContentRef.current = false; }, 100);
  }
  ```
- **Lines modified**: 3 -> 5 (net +2)
- **Depends on**: T7
- **Verifiable**: No TypeScript errors. Behavior unchanged (fitContent still fires).

#### T10: Add `justFitContentRef` guard around sentiment data `fitContent()` call
- **File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
- **Action**: Modify lines 428-430 (sentiment data useEffect fitContent block)
- **Detail**: Same pattern as T9:
  ```typescript
  if (chartRef.current) {
    justFitContentRef.current = true;
    chartRef.current.timeScale().fitContent();
    setTimeout(() => { justFitContentRef.current = false; }, 100);
  }
  ```
- **Lines modified**: 3 -> 5 (net +2)
- **Depends on**: T7
- **Verifiable**: No TypeScript errors. Behavior unchanged.

### Phase 5: Subscription Handler and Cleanup

#### T11: Add `subscribeVisibleLogicalRangeChange` handler in chart init useEffect
- **File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
- **Action**: Inside the chart init `useEffect` (starts line 172):
  1. Declare `let unsubscribeLogicalRange: (() => void) | null = null;` BEFORE the `if (interactive)` block (around line 282)
  2. Inside the `if (interactive)` block (after `subscribeCrosshairMove` handler, after line 334), assign:
     ```typescript
     unsubscribeLogicalRange = chart.timeScale().subscribeVisibleLogicalRangeChange(
       (range: { from: number; to: number } | null) => {
         if (!range) return;
         if (justFitContentRef.current) return;
         if (isLoadingRef.current) return;
         if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
         debounceTimerRef.current = setTimeout(() => {
           const dataLength = dataLengthRef.current;
           const currentRange = timeRangeRef.current;
           if (dataLength === 0) return;
           if (!shouldUpgradeTimeRange(range.from, range.to, dataLength)) return;
           const nextRange = getNextTimeRange(currentRange);
           if (!nextRange) return;
           setTimeRange(nextRange);
         }, 500);
       }
     );
     ```
- **Lines added**: ~20
- **Depends on**: T6, T7, T8, T9, T10
- **Verifiable**: No TypeScript errors. When interactive=true, the subscription is created.
- **RISK**: Highest-risk task. The callback interacts with refs, debounce timer, and state setter. Incorrect scoping of `unsubscribeLogicalRange` could cause cleanup failure.

#### T12: Add cleanup for subscription and debounce timer
- **File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
- **Action**: Modify the cleanup return in the chart init useEffect (line 349-356):
  ```typescript
  return () => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    unsubscribeLogicalRange?.();
    window.removeEventListener('resize', handleResize);
    chart.remove();
    chartRef.current = null;
    candleSeriesRef.current = null;
    sentimentSeriesRef.current = null;
    gapShaderRef.current = null;
  };
  ```
- **Lines modified**: ~3 (add 2 new lines, keep existing lines)
- **Depends on**: T11 (needs `unsubscribeLogicalRange` variable in scope)
- **Verifiable**: No TypeScript errors. Cleanup runs on unmount.

### Phase 6: Test Updates

#### T13: Update lightweight-charts mock to include `subscribeVisibleLogicalRangeChange`
- **File**: `frontend/tests/unit/components/charts/price-sentiment-chart.test.tsx`
- **Action**: Modify the `timeScale` mock (line 18-21) to add `subscribeVisibleLogicalRangeChange`:
  ```typescript
  timeScale: vi.fn(() => ({
    fitContent: vi.fn(),
    setVisibleLogicalRange: vi.fn(),
    subscribeVisibleLogicalRangeChange: vi.fn(() => vi.fn()),
  })),
  ```
- **Lines modified**: 1 (add new mock method)
- **Depends on**: Nothing (test file change)
- **Verifiable**: Existing tests still pass with updated mock

#### T14: Add zoom-out auto-upgrade test block to component test file
- **File**: `frontend/tests/unit/components/charts/price-sentiment-chart.test.tsx`
- **Action**: Add new `describe('1318: Zoom-out auto-upgrade')` block with tests:
  1. `should subscribe to visible logical range changes when interactive` — renders with `interactive={true}`, asserts `subscribeVisibleLogicalRangeChange` was called
  2. `should NOT subscribe when not interactive` — renders with `interactive={false}`, asserts NOT called
  3. `should call unsubscribe on unmount` — renders, unmounts, verifies the returned unsubscribe function was called
  4. `should not crash when range callback receives null` — verifies null-guard behavior
  5. `should clean up debounce timer on unmount` — verifies `clearTimeout` called
- **Lines added**: ~50
- **Depends on**: T13
- **Verifiable**: `npx vitest run tests/unit/components/charts/price-sentiment-chart.test.tsx`

#### T15: Run all unit tests — verify pass
- **Action**: Execute `cd frontend && npx vitest run`
- **Depends on**: T4, T13, T14
- **Verifiable**: Exit code 0, all tests pass, 0 failures

### Phase 7: E2E Validation

#### T16: Verify E2E test expectations align with implementation
- **Action**: Read `frontend/tests/e2e/chart-zoom-data.spec.ts` lines 92-167. Verify:
  1. Test clicks 1M button and Day resolution (matches our starting state)
  2. Test zooms with Ctrl+wheel (triggers `handleScale` -> `subscribeVisibleLogicalRangeChange`)
  3. Test asserts 1M button deactivates (`aria-pressed` not `true`)
  4. Test asserts candle count increases (wider range -> more data)
  5. All assertions align with our implementation (auto-upgrade sets `timeRange`, which updates button state and triggers refetch)
- **Depends on**: T11, T12
- **Verifiable**: Review only (E2E requires running app). Confirm no assertion mismatch.

---

## Requirements-to-Tasks Traceability Matrix

| Requirement | Task(s) | Coverage |
|-------------|---------|----------|
| R1: Time range utilities | T1, T2, T3 | `TIME_RANGE_ORDER`, `getNextTimeRange`, `shouldUpgradeTimeRange` |
| R2: Viewport subscription | T11 | `subscribeVisibleLogicalRangeChange` in init useEffect |
| R3: Debounce (500ms) | T11 | `setTimeout`/`clearTimeout` pattern inside callback |
| R4: Loading guard | T8, T11 | `isLoadingRef` sync + check in callback |
| R5: fitContent loop prevention | T7, T9, T10, T11 | `justFitContentRef` flag + callback guard |
| R6: Maximum range cap | T2, T11 | `getNextTimeRange` returns null + callback null check |
| R7: Ref synchronization | T7, T8 | `dataLengthRef`, `timeRangeRef`, `isLoadingRef` + render body sync |
| R8: Cleanup | T12 | `clearTimeout` + `unsubscribeLogicalRange?.()` in cleanup |
| R9: Non-interactive mode | T11 | Subscription inside `if (interactive)` block |

## Edge Cases-to-Test Coverage Matrix

| Edge Case | Test Coverage | Location |
|-----------|--------------|----------|
| EC1: Already at 1Y maximum | Unit test: `getNextTimeRange('1Y')` -> null | T4 |
| EC2: Rapid successive zooms | Debounce logic in callback (500ms) | T11 (implicit in E2E: 15 rapid wheel events) |
| EC3: Data loading during zoom | `isLoadingRef.current` check in callback | T11 (guard line) |
| EC4: Empty data set | Unit test: `shouldUpgradeTimeRange(-5, 5, 0)` -> false | T4 |
| EC5: Zoom-in (narrowing) | Unit test: `shouldUpgradeTimeRange(2, 18, 22)` -> false | T4 |
| EC6: Unmount during debounce | `clearTimeout` in cleanup | T12, T14 (unmount test) |
| EC7: Session storage persistence | Existing `useEffect` on timeRange (line 148-152) | Existing tests (no change needed) |
| EC8: Multiple upgrades in sequence | Loading guard + independent debounce cycles | E2E test (zoom past multiple ranges) |

## Dependency Graph

```
T1 ─┬─> T2 ─┬─> T4 ─> T5
    │        │
T3 ─┘        ├─> T6 ─> T7 ─┬─> T8 ─┐
              │              │       │
              │         T9 ──┤       ├─> T11 ─> T12
              │              │       │
              │         T10 ─┘       │
              │                      │
              └──────────────────────┘
                                     
T13 ─> T14 ─┐
             ├─> T15
T5 ──────────┘

T11 + T12 ─> T16
```

**Parallelizable groups**:
- T1 + T3 (both insert into chart.ts, no overlap)
- T9 + T10 (both modify fitContent blocks, independent locations)
- T13 (test mock update) can start in parallel with T6-T12 (component changes)

---

## Adversarial Review #3

### Cross-Artifact Consistency Check

| Check | Status | Detail |
|-------|--------|--------|
| Every R1-R9 requirement mapped to at least one task? | PASS | Traceability matrix covers all 9 requirements. No orphans. |
| Every EC1-EC8 edge case has test coverage? | PASS | Coverage matrix covers all 8 edge cases. EC2, EC3, EC8 rely on E2E + guard lines (acceptable per AR#2 coverage gap analysis). |
| Task file references match plan.md file list? | PASS | Tasks modify: `chart.ts`, `price-sentiment-chart.tsx`, `price-sentiment-chart.test.tsx`, new `chart-utils.test.ts`, review `chart-zoom-data.spec.ts`. Matches plan's 5-file summary exactly. |
| Line numbers in tasks match actual source? | PASS | Verified: `gapShaderRef` at L107, `if (interactive)` at L283, `subscribeCrosshairMove` at L284, `fitContent` at L399-401 and L428-430, cleanup at L349-356, `return (` at L490. All match. |
| Task dependency order prevents broken intermediate states? | PASS | Phase 1 (utilities) -> Phase 2 (tests) -> Phase 3 (wiring) -> Phase 4 (guards) -> Phase 5 (subscription) -> Phase 6 (test updates) -> Phase 7 (E2E review). Each phase produces a compilable, testable intermediate state. |
| Spec drift since AR#2? | N/A | No spec changes since AR#2. Tasks faithfully reproduce the plan. |

### Implementation Readiness Assessment

1. **Are the tasks specific enough to implement without ambiguity?**
   YES. Every task specifies the exact file, exact insertion point (line number), exact code to add/modify, and a verification step. The highest-specificity tasks are T1-T3 (pure functions with complete implementations in plan.md) and T9-T10 (3-line modifications with before/after shown). T11 is the most complex but includes the full callback code inline.

2. **Highest-risk task: T11 (subscription handler)**
   - **Why**: T11 is the integration point where all refs, guards, debounce, and state setter converge. It touches the most complex `useEffect` in the component (chart init, lines 172-357). The scoping of `unsubscribeLogicalRange` across the `if (interactive)` boundary requires careful variable hoisting (declared before the block, assigned inside).
   - **Specific risk**: If the implementer puts the `let unsubscribeLogicalRange` declaration INSIDE the `if (interactive)` block instead of before it, the cleanup return (T12) cannot access it. The plan addresses this explicitly ("Revised approach: declare before the block"), but it remains the #1 implementation pitfall.
   - **Mitigation**: The task explicitly calls out the two insertion points (before line 283 for declaration, after line 334 for assignment). TypeScript will catch the scoping error at compile time if done wrong (reference error in cleanup).

3. **Most likely source of rework: 30% threshold and 500ms debounce timing**
   - The 30% threshold (T3) and 500ms debounce (T11) are UX-tuning constants. AR#1 and AR#2 analyzed them and found them reasonable, but real-world testing may reveal that:
     - 30% triggers too easily with large gap-filled datasets (AR#2-001: `priceData.length` vs `chartData.length` discrepancy means effective threshold drops to ~22% of visual extent)
     - 500ms feels sluggish on fast machines or too eager on slow connections
   - **Mitigation**: Both values are single-line constants. Tuning requires changing one number each. No architectural rework.

4. **Task ordering validation**
   - Phase 1 -> 2 (utilities before tests): Correct. Tests import from utilities.
   - Phase 3 (imports/refs) before Phase 4 (fitContent guards): Correct. Guards use `justFitContentRef` from T7.
   - Phase 4 before Phase 5 (subscription): Correct. Subscription callback checks `justFitContentRef`.
   - Phase 5 before Phase 6 (test updates): Correct. Tests verify subscription behavior.
   - T11 before T12: Correct. Cleanup references `unsubscribeLogicalRange` from T11.
   - **Can any tasks be parallelized?** Yes, as noted: T1+T3, T9+T10, T13 parallel with T6-T12. In practice, a single implementer will execute sequentially, but the dependency graph allows skipping ahead if blocked.

5. **Missing coverage check**
   - **Found: T14 test #4 ("should not crash when range callback receives null")**: This test needs to extract the callback from the mock's `subscribeVisibleLogicalRangeChange` call and invoke it with `null`. The test description is clear but the implementation requires reaching into the mock to get the registered callback. This is a standard vitest pattern (`vi.fn().mock.calls[0][0]`) but could cause confusion. **Severity: LOW**. The callback's first line is `if (!range) return;` which is trivially correct.
   - **Found: No dedicated test for loading guard (isLoadingRef)**: AR#2 accepted this gap. The loading guard is a single `if (isLoadingRef.current) return;` line. E2E test implicitly covers it (test waits for data load before zooming). **Severity: LOW**. Accepted.
   - **Found: No test for `justFitContentRef` flag timing (100ms setTimeout)**: The 100ms reset is a defensive timeout. Testing it would require fake timers and invoking the subscription callback between `fitContent()` and the 100ms expiry. **Severity: LOW**. The math defense (`shouldUpgradeTimeRange` returns false after fitContent) is the primary guard; the flag is belt-and-suspenders.

### Findings Summary

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| AR3-001 | LOW | T11 insertion point says "around line 282" which is the comment line, not the ideal insertion point. The `let unsubscribeLogicalRange` should go between lines 281 (blank line after ref assignments) and 282 (comment before `if (interactive)`). | ACCEPTED: "Around line 282" is directionally correct. The implementer will find the logical insertion point (before the `if (interactive)` block). TypeScript would catch incorrect placement. |
| AR3-002 | LOW | T14 test #4 requires extracting the callback from mock — implementation detail not spelled out in task. | ACCEPTED: Standard vitest pattern (`mock.calls[0][0]`). Implementer familiar with the test file's existing patterns will know how to do this. |
| AR3-003 | LOW | T8 ref sync in render body runs on every render, including when no relevant state changed. | ACCEPTED: Ref assignment is O(1) — three property writes per render. No performance concern. This is the standard React pattern recommended by the React docs for keeping refs in sync without triggering re-renders. |

No CRITICAL or HIGH findings. All 3 findings are LOW and accepted.

### Highest-Risk Task

**T11: Add `subscribeVisibleLogicalRangeChange` handler in chart init useEffect**

This is the integration nexus where refs (T7), guards (T9/T10), debounce (T11 internal), and cleanup (T12) converge. The variable scoping across the `if (interactive)` boundary is the specific implementation pitfall. Mitigation: TypeScript compile-time error if scoped wrong, and the task explicitly documents the two-insertion-point pattern.

### Most Likely Source of Rework

**Threshold (30%) and debounce (500ms) tuning constants**

Both are single-number changes with no architectural impact. The gap-inflated data length (AR#2-001) means the effective visual threshold is ~22%, which may trigger slightly earlier than intended. If user testing reveals this is too eager, increase to 40%. If too conservative, decrease to 20%. The debounce timing is similarly trivial to adjust.

### Gate Statement

**ADVERSARIAL REVIEW #3: PASS**

All 3 findings are LOW severity and accepted. No CRITICAL, HIGH, or MEDIUM issues found. Cross-artifact consistency verified across spec.md (9 requirements, 8 edge cases, 8 success criteria), plan.md (5 files, ~155 new lines), and tasks.md (16 tasks, 7 phases). Requirements-to-tasks and edge-cases-to-tests traceability matrices are complete with no orphans. Task ordering respects all dependency chains. Implementation can proceed without blocking issues.

**READY FOR IMPLEMENTATION**

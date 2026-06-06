# Feature 1337: Tasks

## Task List

### Sub-Issue A: AMZN -> AAPL

- [x] A1: Replace AMZN with AAPL in chart-zoom-data.spec.ts test 1 (1Y candles)
  - File: `frontend/tests/e2e/chart-zoom-data.spec.ts`
  - Lines 44-51: `fill('AMZN')` -> `fill('AAPL')`, `/AMZN/i` -> `/AAPL/i`
  - Depends: none

- [x] A2: Replace AMZN with AAPL in chart-zoom-data.spec.ts test 2 (zoom-out)
  - File: `frontend/tests/e2e/chart-zoom-data.spec.ts`
  - Lines 99-104: same pattern as A1
  - Depends: none

- [x] A3: Replace AMZN with AAPL in chart-zoom-data.spec.ts test 3 (range comparison)
  - File: `frontend/tests/e2e/chart-zoom-data.spec.ts`
  - Lines 177-182: same pattern as A1
  - Depends: none

### Sub-Issue B: Error Boundary A11y

- [x] B1: Add aria-labelledby and heading ID to ErrorFallback component
  - File: `frontend/src/components/ui/error-boundary.tsx`
  - Add `id="error-boundary-heading"` to `<h2>` (line 87)
  - Add `aria-labelledby="error-boundary-heading"` to `role="alert"` div (line 81)
  - Depends: none

- [x] B2: Add auto-focus to ErrorFallback component
  - File: `frontend/src/components/ui/error-boundary.tsx`
  - Add `useRef, useEffect` import
  - Add `containerRef` with auto-focus on mount
  - Add `ref={containerRef}` and `tabIndex={-1}` to alert div
  - Depends: B1

- [x] B3: Replace chained Tab with programmatic focus in T024
  - File: `frontend/tests/e2e/chaos-error-boundary.spec.ts`
  - Lines 93-121: Replace 3x `keyboard.press('Tab')` + `evaluate()` with
    `getByRole('button')` + `.focus()` + `toBeFocused()` assertions
  - Depends: B2

### Verification

- [x] V1: Verify chart-zoom-data.spec.ts has no remaining AMZN references
  - Grep for AMZN in file — expect 0 matches
  - Depends: A1, A2, A3

- [x] V2: Verify error-boundary.tsx has aria-labelledby, heading ID, tabIndex, autoFocus
  - Inspect component for all 4 attributes
  - Depends: B1, B2

- [x] V3: Verify chaos-error-boundary.spec.ts T024 has no chained Tab presses
  - Grep for `keyboard.press('Tab')` — expect 0 matches in T024
  - Depends: B3

## Execution Order

```
A1 + A2 + A3 (parallel) -> V1
B1 -> B2 -> B3 -> V2 + V3
```

Total: 6 implementation tasks + 3 verification tasks = 9 tasks

# Feature 1337: Cross-Artifact Analysis

## Consistency Check

### Spec <-> Plan Alignment

| Spec Requirement | Plan Coverage | Status |
|------------------|---------------|--------|
| Replace AMZN with AAPL in 3 tests | Plan Section A: 6 string replacements | PASS |
| Add aria-labelledby to error boundary | Plan Section B1: component enhancement | PASS |
| Add auto-focus to error boundary | Plan Section B1: useRef + useEffect | PASS |
| Replace chained Tab with .focus() in T024 | Plan Section B2: test fix | PASS |
| No changes to T025 (health banner) | Plan Non-Goals section | PASS |
| No production behavior changes beyond a11y | Plan explicitly scoped | PASS |

### Plan <-> Tasks Alignment

| Plan Step | Task(s) | Status |
|-----------|---------|--------|
| 6 AMZN->AAPL replacements across 3 tests | A1, A2, A3 | PASS |
| aria-labelledby + heading ID | B1 | PASS |
| useRef + useEffect auto-focus | B2 | PASS |
| T024 Tab -> focus() rewrite | B3 | PASS |
| Verification of no AMZN remnants | V1 | PASS |
| Verification of component attributes | V2 | PASS |
| Verification of no chained Tabs | V3 | PASS |

### Tasks <-> Spec Acceptance Criteria

| Acceptance Criterion | Implementing Task(s) | Status |
|---------------------|---------------------|--------|
| AC1: 3 chart-zoom-data tests pass with AAPL | A1, A2, A3 | COVERED |
| AC2: T026 passes with zero violations | B1, B2 | COVERED |
| AC3: T027 continues to pass | B1, B2 (component fix enables) | COVERED |
| AC4: T024 passes using programmatic focus | B3 | COVERED |
| AC5: T025 unaffected | No tasks touch health banner | COVERED |
| AC6: No production behavior changes beyond a11y | B1+B2 are a11y-only enhancements | COVERED |

## Risk Analysis

### Identified Risks

1. **Auto-focus outline flash**: Adding `tabIndex={-1}` + auto-focus may show a focus
   outline momentarily on the error boundary container. Mitigated: the container's
   `focus-visible:outline-none` from the Card component or Tailwind's `outline-none` can
   be added if needed. Low risk — `tabIndex={-1}` elements don't show focus rings by
   default in most browsers.

2. **Multiple ErrorFallback instances**: If multiple error boundaries are on the page, each
   would get the same `id="error-boundary-heading"`. However, only one ErrorFallback
   renders at a time (the error boundary replaces its children), and there's only one
   ErrorBoundary wrapper in the app layout. Low risk.

## Completeness Assessment

- **No orphan tasks**: Every task maps to a plan step and spec requirement
- **No orphan requirements**: Every spec acceptance criterion has implementing tasks
- **Dependency order valid**: B2 depends on B1, B3 depends on B2, V* depend on implementation tasks
- **File coverage complete**: All 3 affected test files + 1 component file are covered

## Verdict: PASS — Ready for implementation

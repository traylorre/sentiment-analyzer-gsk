# Tasks: Heatmap Error Resilience

**Input**: Design documents from `/specs/1231-heatmap-error-resilience/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Included per constitution requirement (Amendment 1.1: all implementation code must be accompanied by unit tests).

**Organization**: Tasks grouped by phase. Phase 1 (backend) and Phase 2 (frontend) are independent and can run in parallel.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Backend — Lock Partial Failure Behavior

**Purpose**: Add tests to verify and lock the existing per-ticker try/except behavior in `get_sentiment_by_configuration`. No code changes to the backend -- tests only.

- [ ] T001 [US2] Write unit test in `tests/unit/test_sentiment_partial_failure.py` (NEW) — test case: mock `query_timeseries` to succeed for "AAPL" (return a `TimeseriesResponse` with one bucket, avg=0.45) and raise `Exception("DynamoDB throttle")` for "GOOGL"; call `get_sentiment_by_configuration(config_id="test", tickers=["AAPL", "GOOGL"])`; assert result is `SentimentResponse` (not `ErrorResponse`); assert `result.tickers` has 2 entries; assert AAPL ticker has `sentiment["aggregated"].score == 0.45`; assert GOOGL ticker has `sentiment == {}` (empty dict); use `unittest.mock.patch` on `src.lambdas.dashboard.timeseries.query_timeseries` with `side_effect` function that checks ticker arg
- [ ] T002 [US2] [P] Write unit test in same file — test case: mock `query_timeseries` to raise `Exception` for ALL tickers; call `get_sentiment_by_configuration(config_id="test", tickers=["AAPL", "GOOGL"])`; assert result is still `SentimentResponse` (200-level, not error); assert both tickers have `sentiment == {}`; this verifies total failure still returns a valid response shape
- [ ] T003 [US2] [P] Write unit test in same file — test case: call `get_sentiment_by_configuration` with `tickers=[]` (empty list); assert result is `SentimentResponse` with `tickers == []`; this verifies the empty input edge case

**Checkpoint**: `pytest tests/unit/test_sentiment_partial_failure.py` passes. Backend partial failure behavior locked.

---

## Phase 2: Frontend — Defensive Guards and Error UI

**Purpose**: Harden `HeatMapView` against non-object `sentiment` values, add error state component, add empty state rendering, fix CompactHeatMapGrid null guard.

### Step 2a: Defensive Guards

- [ ] T004 [US1] Add defensive guard in `frontend/src/components/heatmap/heat-map-view.tsx:34` — change `Object.entries(ticker.sentiment)` to `Object.entries(ticker.sentiment ?? {})` to prevent TypeError when sentiment is undefined or null. This is a single-character change (`?? {}` suffix) that prevents the crash described in the spec.
- [ ] T005 [US1] Add empty tickers guard in `frontend/src/components/heatmap/heat-map-view.tsx` — before the heatMapData useMemo return block (around line 78), add check: if `tickers.length === 0`, render `HeatMapEmptyState` component instead of the grid. Import `HeatMapEmptyState` (it's defined in the same file at line 168).
- [ ] T006 [US1] [P] Add null guard in `frontend/src/components/heatmap/heat-map-grid.tsx:241-249` (CompactHeatMapGrid) — wrap cell access in null check matching desktop grid pattern at line 138. If cell is falsy, render a placeholder `<div>` with `bg-muted/30` styling.

### Step 2b: Error State Component

- [ ] T007 [US1] Create `frontend/src/components/heatmap/heat-map-error.tsx` (NEW) — implement `HeatMapErrorState` component with props `{ error: Error | null, onRetry?: () => void, className?: string }`. Display AlertTriangle icon (from lucide-react), "Unable to load sentiment data" heading, user-friendly error message based on error code (NETWORK_ERROR -> "Check your connection", TIMEOUT -> "Request timed out", SERVER_ERROR -> "Server error, try again later", default -> "Something went wrong"), and optional retry button. Use `useEffect` to call `emitErrorEvent('heatmap:error', { code, message })` from `@/lib/api/client` when error is non-null (Feature 1226 pattern). Style with `cn` utility matching `HeatMapEmptyState` layout (centered, py-12).
- [ ] T008 [US1] Export `HeatMapErrorState` from `frontend/src/components/heatmap/index.ts` — add export line: `export { HeatMapErrorState } from './heat-map-error';`

### Step 2c: Frontend Tests

- [ ] T009 [US1] Write unit tests in `frontend/tests/unit/components/heatmap/heat-map-view.test.tsx` (NEW) — 6 test cases: (1) renders grid with valid tickers data (2 tickers, each with aggregated sentiment); (2) renders HeatMapEmptyState when tickers is empty array; (3) does not crash when `ticker.sentiment` is undefined (passes `[{ symbol: "AAPL", sentiment: undefined as any }]`); (4) does not crash when `ticker.sentiment` is null; (5) renders correctly with partial data (one ticker has sentiment, other has empty `{}`); (6) renders all cells as empty fallback when all tickers have empty sentiment. Mock `@/hooks/use-haptic`, `@/stores/chart-store` per existing heat-map-cell.test.tsx pattern. Use vitest + testing-library.
- [ ] T010 [US1] [P] Write unit tests in `frontend/tests/unit/components/heatmap/heat-map-error.test.tsx` (NEW) — 4 test cases: (1) renders error message with AlertTriangle icon; (2) renders retry button when onRetry prop provided; (3) calls onRetry callback when retry button clicked; (4) emits structured console event via `emitErrorEvent` (spy on console.warn, verify JSON structure matches `{event: 'heatmap:error', timestamp, details: {code, message}}`). Import `ApiClientError` from `@/lib/api/client` for creating typed test errors.

**Checkpoint**: All frontend unit tests pass. `cd frontend && npx vitest run tests/unit/components/heatmap/` passes.

---

## Phase 3: Polish and Verification

**Purpose**: Verify no regressions, run full test suite.

- [ ] T011 Run existing heatmap tests to verify no regressions — `cd frontend && npx vitest run tests/unit/components/heatmap/heat-map-cell.test.tsx tests/unit/components/heatmap/heat-map-legend.test.tsx` must pass unchanged
- [ ] T012 Run full backend test suite — `pytest tests/unit/` must pass with new partial failure test included
- [ ] T013 Run `make validate` (if available in sentiment-analyzer-gsk) or equivalent linting — verify TypeScript compilation, ESLint, ruff checks all pass

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Backend (test-only)  ←→  Phase 2: Frontend (code + tests)  (PARALLEL — completely independent)
                    ↓                              ↓
                    └──────── Phase 3: Polish ──────┘
```

### Within Each Phase

- Phase 1: T001 is the primary test. T002 and T003 are [P] (parallel, same file but independent test cases). In practice, write all 3 in one file.
- Phase 2a: T004 and T005 are sequential (same file, T004 is the crash fix, T005 is the empty guard). T006 is [P] (different file).
- Phase 2b: T007 then T008 (create component, then export it).
- Phase 2c: T009 and T010 are [P] (different test files).
- Phase 3: T011, T012, T013 are sequential verification steps.

### Task-to-Requirement Mapping

| Requirement | Tasks |
|-------------|-------|
| FR-001 (no crash on non-object sentiment) | T004, T009 (tests 3, 4) |
| FR-002 (error state UI) | T007, T010 |
| FR-003 (retry mechanism) | T007, T010 (test 2, 3) |
| FR-004 (empty state rendering) | T005, T009 (test 2) |
| FR-005 (parent guards error state) | Documented in quickstart.md; integration point does not exist yet |
| FR-006 (backend partial failure preserved) | T001, T002, T003 |
| FR-007 (CompactHeatMapGrid null guard) | T006 |
| FR-008 (error event emission) | T007, T010 (test 4) |

### Success Criteria Mapping

| Criteria | Verification |
|----------|-------------|
| SC-001 (zero crashes on 6 error scenarios) | T009 (6 test cases covering all scenarios) |
| SC-002 (error visible within 500ms) | T007 (component renders synchronously, no async delay) |
| SC-003 (retry recovers from error) | T010 (test 3 verifies callback invocation) |
| SC-004 (backend partial failure 200 OK) | T001 (explicit test) |
| SC-005 (no regressions) | T011, T012, T013 |

---

## Notes

- FR-005 (parent component guards) is documented but not implemented because no page currently mounts HeatMapView. The quickstart.md includes the react-query pattern for when integration happens.
- The backend changes are test-only. The existing `get_sentiment_by_configuration` code is correct; we are adding tests to prevent regression.
- Total: 13 tasks across 3 phases. Estimated effort: small (1-2 frontend files, 1 new component, 2 new test files, 1 backend test file).

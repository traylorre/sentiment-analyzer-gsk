# Tasks: Price Chart Playwright E2E Test Gaps

**Input**: Design documents from `/specs/1281-price-chart-e2e-gaps/`
**Prerequisites**: plan.md (required), spec.md (required)

## Phase 1: Component Verification (FR-007 Gate)

**Purpose**: Verify component code paths exist before writing tests. If paths are missing, document findings and skip corresponding tests.

- [ ] T-001 [US1/US2/US3] Read `frontend/src/components/price-sentiment-chart.tsx` to verify empty data state, resolution fallback banner, and error/retry code paths exist (FR-007). Document which paths exist and which are missing. If a path is missing, the corresponding test task becomes a TODO with a finding note, not an implementation task.

**Checkpoint**: Component audit complete. Proceed only with tests for verified code paths.

---

## Phase 2: Empty Data State Test (Priority: P1)

**Goal**: Verify that zero OHLC candles renders a visible empty state message, not a blank canvas.

**Independent Test**: Mock OHLC API to return `{ candles: [] }`, verify empty state message element is visible.

- [ ] T-002 [US1] Create `frontend/tests/e2e/chart-edge-cases.spec.ts` with test setup (imports, `test.describe` block, shared mock helpers). Add empty data state test: intercept OHLC route to return zero candles via `page.route()`, navigate to dashboard, select a ticker, assert empty state message is visible using `waitForSelector`. Verify no canvas element with data is rendered. Run in both Desktop Chrome and Mobile Chrome projects.

**Checkpoint**: Empty data state test passes in headed and headless modes.

---

## Phase 3: Resolution Fallback Banner Test (Priority: P2)

**Goal**: Verify the resolution fallback warning banner renders when `resolution_fallback: true` and hides when `false`.

**Independent Test**: Mock OHLC API to return `{ resolution_fallback: true, fallback_message: "..." }`, verify banner text matches.

- [ ] T-003 [US2] Add resolution fallback banner test to `chart-edge-cases.spec.ts`: intercept OHLC route to return response with `resolution_fallback: true` and a `fallback_message` string. Assert warning banner element is visible and contains the fallback message text. Add negative case: intercept with `resolution_fallback: false`, assert no fallback banner visible.

**Checkpoint**: Fallback banner test passes -- both positive and negative cases.

---

## Phase 4: API Error State Test (Priority: P2)

**Goal**: Verify OHLC API 500 error renders error message with retry functionality.

**Independent Test**: Mock OHLC API to return 500, verify error message visible and retry button re-fetches.

- [ ] T-004 [US3] Add API error state test to `chart-edge-cases.spec.ts`: intercept OHLC route to return HTTP 500. Assert error message is visible in chart area. Locate retry button/link (grep component for actual selector). Click retry, intercept OHLC route to return valid data on second call, assert chart renders with data (aria-label candle count > 0). Use `waitForResponse` to gate assertions.

**Checkpoint**: Error state and retry test passes.

---

## Phase 5: Cross-Mode Verification

**Purpose**: Confirm all tests pass across both Playwright projects.

- [ ] T-005 [US1/US2/US3] Run full `chart-edge-cases.spec.ts` suite in both headed (`npx playwright test --headed`) and headless modes. Verify zero failures. Verify no `waitForTimeout` calls exist in the test file (flake prevention gate per SC-004 amendment).

**Checkpoint**: All tests green in both modes. Feature complete.

---

## Dependencies & Execution Order

- **T-001** (Phase 1): No dependencies -- start immediately. BLOCKS all subsequent tasks.
- **T-002** (Phase 2): Depends on T-001 confirming empty state code path exists.
- **T-003** (Phase 3): Depends on T-001 confirming fallback banner code path exists. Can run in parallel with T-002 (different `test.describe` blocks, same file).
- **T-004** (Phase 4): Depends on T-001 confirming error/retry code path exists. Can run in parallel with T-002/T-003.
- **T-005** (Phase 5): Depends on T-002, T-003, T-004 all complete.

### Parallel Opportunities

T-002, T-003, and T-004 can be authored in parallel after T-001 completes (they write to separate `test.describe` blocks in the same file).

---

## Adversarial Review #3

**Highest-risk task**: **T-001** (Component Verification). If the component does not render empty/error/fallback states, most of this feature becomes documentation-only TODOs rather than working tests. The spec explicitly acknowledges this risk (FR-007) but the entire feature's value depends on this gate's outcome.

**Readiness assessment**: READY WITH CAVEAT. The spec is well-structured with clear mock patterns, selector reuse strategy, and the FR-007 verification gate. The risk is that T-001 may reveal missing UI code paths, which would reduce the feature to findings documentation. This is acceptable -- writing tests against non-existent UI is worse than documenting the gap.

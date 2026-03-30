# Feature Specification: Price Chart Playwright E2E Test Gaps

**Feature Branch**: `1281-price-chart-e2e-gaps`
**Created**: 2026-03-29
**Status**: Draft
**Input**: "Fill gaps in price chart Playwright E2E tests — empty data state, resolution fallback, error states, chart canvas presence verification"

## Context: Existing Coverage

Extensive tests already exist in `sanity.spec.ts` (841 lines) and `dashboard-interactions.spec.ts` (269 lines):
- All 5 time ranges (1W, 1M, 3M, 6M, 1Y) — button state, data count via aria-label
- All 6 resolutions (1m, 5m, 15m, 30m, 1h, Day) — button state, data reload
- All 4 sentiment sources — dropdown selection, data reload
- Layer toggles (Price/Sentiment on/off)
- Mobile viewport (375x667)
- Data persistence across timeframe changes
- Intraday resolution data loading
- Settings persistence across ticker switches
- Keyboard focus order for chart controls
- ARIA attributes on chart element

**Chart library**: `lightweight-charts` v5.0.9 (canvas-based, TradingView). Pan/zoom interactions are canvas-internal and NOT accessible to Playwright DOM selectors. Testing pan/zoom requires mouse coordinate simulation on canvas elements, which is fragile and low-value compared to verifying the chart options are correctly configured.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Empty Data State (Priority: P1)

When an operator searches for a ticker with no available OHLC data (e.g., recently IPO'd, delisted, or data provider gap), the chart should display a clear empty state message instead of a blank canvas or error.

**Why this priority**: Empty state is the most common failure mode users encounter. A blank chart with no explanation creates confusion and support tickets.

**Independent Test**: Can be tested by mocking the OHLC API to return zero candles and verifying the empty state message renders.

**Acceptance Scenarios**:

1. **Given** a ticker with no OHLC data, **When** the chart loads, **Then** an empty state message is visible (not a blank canvas).
2. **Given** a ticker with OHLC data but no sentiment data, **When** the chart loads, **Then** the price chart renders without the sentiment overlay, and a message indicates sentiment is unavailable.

---

### User Story 2 - Resolution Fallback Banner (Priority: P2)

When the backend cannot serve the requested resolution (e.g., 1-minute candles for a 1-year range) and falls back to a coarser resolution, the UI should display a warning banner explaining the fallback.

**Why this priority**: Silent resolution fallback confuses operators who expect 1-minute candles but see daily candles. The backend already returns `resolution_fallback: true` and `fallback_message` — the test verifies the UI renders this.

**Independent Test**: Can be tested by mocking the OHLC API to return `resolution_fallback: true` with a `fallback_message` and verifying the banner appears.

**Acceptance Scenarios**:

1. **Given** OHLC response has `resolution_fallback: true`, **When** the chart loads, **Then** a warning banner displays the `fallback_message` text.
2. **Given** OHLC response has `resolution_fallback: false`, **When** the chart loads, **Then** no fallback banner is visible.

---

### User Story 3 - Chart Load Error State (Priority: P2)

When the OHLC API returns an error (500, timeout, network failure), the chart area should show an error message with a retry option, not a blank area.

**Why this priority**: API failures during market hours are time-sensitive — operators need clear feedback and a quick retry path.

**Independent Test**: Can be tested by mocking the OHLC API to return 500 and verifying the error message and retry button appear.

**Acceptance Scenarios**:

1. **Given** the OHLC API returns 500, **When** the chart attempts to load, **Then** an error message is displayed in the chart area.
2. **Given** an error state is displayed, **When** the operator clicks retry, **Then** the chart re-fetches data.

---

### Edge Cases

- What happens when OHLC returns data but sentiment returns error? Chart renders price only, sentiment section shows error.
- What happens when the chart is loading and the operator switches timeframe? Previous request should be cancelled or ignored.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Tests MUST verify that an empty OHLC response (zero candles) renders a visible empty state message, not a blank canvas.
- **FR-002**: Tests MUST verify that the resolution fallback banner renders when `resolution_fallback: true` and hides when `false`.
- **FR-003**: Tests MUST verify that OHLC API errors (500, timeout) render a visible error message with retry functionality.
- **FR-004**: Tests MUST use the existing mock data infrastructure (`mock-api-data.ts` route interception) for consistent test data.
- **FR-005**: Tests MUST use existing chart selectors (`[role="img"][aria-label*="Price and sentiment"]`) and aria-label data count extraction patterns.
- **FR-006**: Tests MUST NOT attempt to test canvas-internal interactions (pan/zoom/tooltip) — these are lightweight-charts internals not accessible to Playwright.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: All 3 gap scenarios (empty data, resolution fallback, error state) have passing Playwright tests.
- **SC-002**: Tests pass in both Desktop Chrome and Mobile Chrome projects.
- **SC-003**: Tests add less than 30 seconds to the Playwright CI run time.
- **SC-004**: Zero flaky failures over a 7-day CI window.

## Assumptions

- The chart component (`price-sentiment-chart.tsx`) already handles empty data, fallback, and error states in its rendering logic — the tests verify the UI behavior, not add new logic.
- Mock route interception works for the OHLC and sentiment endpoints via `mock-api-data.ts`.
- Tests extend existing files (`sanity.spec.ts` or a new `chart-edge-cases.spec.ts`) rather than duplicating setup.

## Scope Boundaries

**In scope**: Empty data test, resolution fallback test, error state test, retry functionality test
**Out of scope**: Pan/zoom testing (canvas-internal), tooltip testing (canvas-internal, marked FIXME in existing tests), new chart features, performance benchmarking

## Adversarial Review #1

**Reviewed**: 2026-03-29

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | Assumption that component renders empty/error states unverified — tests against non-existent UI are fiction | Added FR-007: Before writing tests, MUST verify the component code paths exist by reading `price-sentiment-chart.tsx`. If missing, document as out-of-scope (this is a test spec, not a feature spec). |
| MEDIUM | Retry button selector and behavior undefined | Accepted — implementation task will grep component for retry pattern and use the actual selector |
| MEDIUM | Canvas presence verification missing from FRs | Accepted — existing `[role="img"]` selector is sufficient for canvas presence |
| MEDIUM | SC-004 7-day lookback unenforceable at merge time | Replaced with: Tests MUST use `waitForResponse`/`waitForSelector` patterns, never `waitForTimeout`, as the flake-prevention gate |
| LOW | lightweight-charts version will rot | Accepted — informational context, not a constraint |

**Spec amendment**: Added FR-007: Tests MUST verify the target component code paths exist before authoring assertions. If the component does not render an empty state, fallback banner, or error state, that gap is documented as a finding and the corresponding test is skipped with a TODO.

**Gate**: 0 CRITICAL, 0 HIGH remaining.

# Feature Specification: Ticker Search Playwright E2E Test Gaps

**Feature Branch**: `1282-ticker-search-e2e-gaps`
**Created**: 2026-03-29
**Status**: Draft
**Input**: "Fill gaps in ticker search Playwright E2E tests — no-results state, autocomplete keyboard navigation, multi-ticker management"

## Context: Existing Coverage

Tests already exist in `dashboard-interactions.spec.ts` and `error-visibility-search.spec.ts`:
- Search input shows autocomplete results → click result → chart loads
- Error states: API 500, 502 Bad Gateway, 429 rate limit (special copy, no retry)
- Retry button functionality after error
- Recovery after error on retype
- ARIA alert role for error accessibility
- Ticker chip removal clears chart
- Empty state shows search CTA

**Component**: `ticker-input.tsx` — React Query debounced search (1500ms), ARIA combobox, keyboard navigation (Arrow Up/Down, Enter, Escape), haptic feedback, max 5 results.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - No-Results State (Priority: P1)

When an operator searches for a non-existent ticker (e.g., "ZZZZZ"), the autocomplete dropdown should display a "no results" message instead of silently closing.

**Why this priority**: Silent no-results is a usability dead end — the operator doesn't know if the search is still loading or genuinely has no matches.

**Independent Test**: Can be tested by typing a non-matching query and verifying the no-results message renders in the dropdown.

**Acceptance Scenarios**:

1. **Given** a search query that matches no tickers, **When** the autocomplete completes, **Then** a "No results found" message is visible in the dropdown.
2. **Given** a no-results state, **When** the operator modifies the query to match a ticker, **Then** results appear replacing the no-results message.

---

### User Story 2 - Autocomplete Keyboard Navigation (Priority: P2)

The operator can navigate autocomplete results using Arrow Up/Down keys and select with Enter, without using the mouse. This is critical for accessibility and power-user efficiency.

**Why this priority**: Keyboard navigation is already implemented in the component (`ticker-input.tsx`) but not tested via Playwright. This is a coverage gap that could silently regress.

**Independent Test**: Can be tested by typing a query, pressing Arrow Down to highlight results, and pressing Enter to select.

**Acceptance Scenarios**:

1. **Given** autocomplete results are visible, **When** the operator presses Arrow Down, **Then** the first result is highlighted (visual indicator + `aria-activedescendant` updates).
2. **Given** a result is highlighted, **When** the operator presses Enter, **Then** the ticker is selected and the chart loads.
3. **Given** a result is highlighted, **When** the operator presses Escape, **Then** the dropdown closes and the search input retains the typed text.
4. **Given** the first result is highlighted, **When** the operator presses Arrow Up, **Then** highlight wraps to the last result (or clears).

---

### User Story 3 - Multi-Ticker Chip Management (Priority: P2)

The operator can add multiple tickers as chips, switch between them by clicking chips, and remove them. The active chip's chart displays.

**Why this priority**: Multi-ticker is a core workflow — operators compare multiple stocks. The chip management UX must be regression-proof.

**Independent Test**: Can be tested by adding 2+ tickers, clicking between chips, and removing one.

**Acceptance Scenarios**:

1. **Given** one ticker is already active, **When** the operator searches and selects a second ticker, **Then** a second chip appears and the chart switches to the new ticker.
2. **Given** two ticker chips exist, **When** the operator clicks the first chip, **Then** the chart switches back to the first ticker.
3. **Given** two ticker chips exist, **When** the operator removes the active chip, **Then** the chart switches to the remaining ticker.
4. **Given** one ticker chip exists, **When** the operator removes it, **Then** the empty state CTA appears.

---

### Edge Cases

- What happens when the operator types a single character? Search fires (component enables at length >= 1) but may return many results — verify dropdown renders without overflow.
- What happens when the operator adds the same ticker twice? Component should prevent duplicates and switch to existing chip.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Tests MUST verify the no-results state message renders for queries with zero matches.
- **FR-002**: Tests MUST verify Arrow Down highlights the first autocomplete result with visual indicator.
- **FR-003**: Tests MUST verify Enter on a highlighted result selects the ticker and loads the chart.
- **FR-004**: Tests MUST verify Escape closes the dropdown without selecting.
- **FR-005**: Tests MUST verify multi-ticker chip add, switch, and remove flows.
- **FR-006**: Tests MUST verify duplicate ticker prevention (same ticker searched twice).
- **FR-007**: Tests MUST use the existing mock data infrastructure for consistent search results.
- **FR-008**: Tests MUST wait for the search debounce (1500ms) before asserting results.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: All 3 gap scenarios (no-results, keyboard nav, multi-ticker) have passing Playwright tests.
- **SC-002**: Tests pass in both Desktop Chrome and Mobile Chrome projects.
- **SC-003**: Tests add less than 30 seconds to the Playwright CI run time.
- **SC-004**: Zero flaky failures over a 7-day CI window.

## Assumptions

- The `ticker-input.tsx` component already implements keyboard navigation, no-results display, and duplicate prevention — tests verify existing behavior, not add new logic.
- Mock route interception for `**/api/v2/tickers/search**` is available via `mock-api-data.ts`.
- The 1500ms debounce MUST be handled via `page.waitForResponse('**/api/v2/tickers/search**')`, never `page.waitForTimeout()`.

## Scope Boundaries

**In scope**: No-results state, keyboard autocomplete navigation, multi-ticker chip management, duplicate prevention
**Out of scope**: Search performance benchmarking, autocomplete ranking algorithm, haptic feedback verification (device-specific)

## Adversarial Review #1

**Reviewed**: 2026-03-29

| Severity | Finding | Resolution |
|----------|---------|------------|
| CRITICAL | 1500ms debounce with `waitForTimeout` is a flaky test factory — contradicts SC-004 | Fixed: FR-008 rewritten to mandate `waitForResponse` pattern. Assumption updated. `waitForTimeout` banned. |
| HIGH | Arrow Up wrap behavior unspecified ("or clears") — can't write test against ambiguous behavior | Added FR-009: Before writing keyboard tests, MUST read `ticker-input.tsx` to determine actual wrap behavior and document it. |
| HIGH | Multi-ticker chart switch has no observable wait condition — timing-dependent | Added FR-010: Chart switch assertion MUST wait for aria-label update (candle count change) or network response for new ticker's OHLC data. Never assert immediately after chip click. |
| MEDIUM | Single-character search edge case documented but no FR | Accepted — edge case documented for implementer awareness, not promoted to FR |
| MEDIUM | Duplicate prevention assumed but unverified | Covered by FR-009 (verify component behavior before testing) |
| MEDIUM | SC-004 7-day lookback unenforceable | Replaced with: Tests MUST use `waitForResponse`/`waitForSelector`, never `waitForTimeout` |

**Spec amendments**:
- FR-008 rewritten: "Tests MUST handle search debounce via `page.waitForResponse('**/api/v2/tickers/search**')`, never `page.waitForTimeout()`."
- Added FR-009: "Before writing keyboard nav tests, MUST read `ticker-input.tsx` to determine actual Arrow Up/Down wrap behavior and document it."
- Added FR-010: "Multi-ticker chart switch assertions MUST wait for an observable DOM change (aria-label update or network response), never assert immediately after interaction."

**Gate**: 0 CRITICAL, 0 HIGH remaining.

# Tasks: Ticker Search Playwright E2E Test Gaps

**Input**: Design documents from `/specs/1282-ticker-search-e2e-gaps/`
**Prerequisites**: plan.md (required), spec.md (required)

## Phase 1: Component Verification (FR-009 Gate)

**Purpose**: Read the component source to determine actual keyboard wrap behavior, no-results rendering, and duplicate prevention logic before writing tests.

- [ ] T-001 [US1/US2/US3] Read `frontend/src/components/ticker-input.tsx` to verify: (a) no-results state message rendering and exact text/selector, (b) Arrow Up/Down keyboard navigation wrap behavior (does Arrow Up from first item wrap to last, or clear highlight?), (c) duplicate ticker prevention mechanism (does it silently ignore, show a message, or switch to existing chip?). Document findings for each. If a behavior is missing from the component, the corresponding test becomes a TODO with a finding note.

**Checkpoint**: Component behavior audit complete. Keyboard wrap behavior documented. Proceed with tests for verified behaviors only.

---

## Phase 2: No-Results State Test (Priority: P1)

**Goal**: Verify that a search query with zero matches renders a "No results found" message in the autocomplete dropdown.

**Independent Test**: Mock search API to return empty results, verify no-results message renders.

- [ ] T-002 [US1] Create `frontend/tests/e2e/ticker-search-gaps.spec.ts` with test setup (imports, `test.describe` block, shared mock helpers). Add no-results state test: intercept `**/api/v2/tickers/search**` to return empty results array via `page.route()`. Type a non-matching query (e.g., "ZZZZZ"), wait for `page.waitForResponse('**/api/v2/tickers/search**')` to handle debounce (FR-008). Assert no-results message is visible in dropdown using selector determined from T-001. Add follow-up: modify query to a matching term, intercept with valid results, assert results replace the no-results message.

**Checkpoint**: No-results state test passes.

---

## Phase 3: Keyboard Navigation Test (Priority: P2)

**Goal**: Verify Arrow Down highlights first result, Enter selects, Escape closes, and Arrow Up wraps per actual component behavior.

**Independent Test**: Mock search API to return multiple results, navigate with keyboard, verify highlight and selection.

- [ ] T-003 [US2] Add keyboard navigation test to `ticker-search-gaps.spec.ts`: intercept search route to return 3 mock ticker results. Type query, `waitForResponse` for search completion. Press Arrow Down, assert first result is highlighted (check for visual indicator class and `aria-activedescendant` attribute update). Press Arrow Down again, assert second result highlighted. Press Enter, assert ticker is selected (chip appears, chart loads via `waitForResponse` for OHLC data). Add Escape test: type query, wait for results, press Escape, assert dropdown closes and input retains typed text. Add wrap test: use wrap behavior documented in T-001 (Arrow Up from first result).

**Checkpoint**: Keyboard navigation tests pass -- highlight, select, escape, and wrap all verified.

---

## Phase 4: Multi-Ticker Chip Management Test (Priority: P2)

**Goal**: Verify adding multiple tickers as chips, switching between them, and removing them.

**Independent Test**: Add 2 tickers via search, click chips to switch, remove chips, verify empty state.

- [ ] T-004 [US3] Add multi-ticker chip management test to `ticker-search-gaps.spec.ts`: search and select first ticker, assert chip appears and chart loads (wait for OHLC response). Search and select second ticker, assert second chip appears and chart switches (wait for new OHLC response per FR-010 -- verify aria-label update or network response, never assert immediately). Click first chip, assert chart switches back (wait for OHLC response). Remove active chip, assert chart switches to remaining ticker. Remove last chip, assert empty state CTA appears (existing selector from `dashboard-interactions.spec.ts`).

**Checkpoint**: Multi-ticker chip add/switch/remove all verified.

---

## Phase 5: Duplicate Ticker Prevention Test (Priority: P2)

**Goal**: Verify that adding the same ticker twice does not create a duplicate chip.

**Independent Test**: Add a ticker, attempt to add it again, verify no duplicate chip.

- [ ] T-005 [US3] Add duplicate ticker prevention test to `ticker-search-gaps.spec.ts`: search and select a ticker (e.g., "AAPL"), assert one chip exists. Search for same ticker again, select it. Assert chip count is still 1 (no duplicate). Verify behavior matches T-001 findings (silent switch to existing chip, or ignore, or message).

**Checkpoint**: Duplicate prevention verified.

---

## Phase 6: Cross-Mode Verification

**Purpose**: Confirm all tests pass across both Playwright projects.

- [ ] T-006 [US1/US2/US3] Run full `ticker-search-gaps.spec.ts` suite in both headed (`npx playwright test --headed`) and headless modes. Verify zero failures. Verify no `waitForTimeout` calls exist in the test file (flake prevention gate). Verify all search assertions use `waitForResponse` pattern.

**Checkpoint**: All tests green in both modes. Feature complete.

---

## Dependencies & Execution Order

- **T-001** (Phase 1): No dependencies -- start immediately. BLOCKS all subsequent tasks.
- **T-002** (Phase 2): Depends on T-001 confirming no-results rendering exists.
- **T-003** (Phase 3): Depends on T-001 documenting keyboard wrap behavior. Can run in parallel with T-002.
- **T-004** (Phase 4): Depends on T-001. Can run in parallel with T-002/T-003.
- **T-005** (Phase 5): Depends on T-001 documenting duplicate prevention mechanism. Can run in parallel with T-002/T-003/T-004.
- **T-006** (Phase 6): Depends on T-002, T-003, T-004, T-005 all complete.

### Parallel Opportunities

T-002, T-003, T-004, and T-005 can all be authored in parallel after T-001 completes (they write to separate `test.describe` blocks in the same file).

---

## Adversarial Review #3

**Highest-risk task**: **T-003** (Keyboard Navigation). This task has the most complex assertion chain (highlight state, `aria-activedescendant` updates, wrap behavior, Escape retention) and depends entirely on T-001's findings about the actual component implementation. If the component's keyboard handling is partial or non-standard, the test may need significant adaptation from the spec's acceptance scenarios.

**Readiness assessment**: READY WITH CAVEAT. The spec correctly identified keyboard wrap ambiguity (AR#1 HIGH finding) and added FR-009 to gate on component verification. The 1500ms debounce is properly handled via `waitForResponse` (not `waitForTimeout`). The main risk is that T-001 may reveal the component's keyboard navigation is incomplete or differently implemented than expected, requiring test design changes. This is acceptable -- the verification gate prevents writing fiction.

# Tasks: Fix Keyboard Navigation Test to Use .focus()

**Input**: Design documents from `/specs/001-keyboard-nav-focus/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: Not explicitly requested — test tasks omitted.

**Organization**: Tasks grouped by user story for independent implementation.

**External Dependencies**: Features 1242 (chaos report viewer) and 1245 (gate toggle) must be implemented before this feature can be executed. The chaos dashboard must be running at BASE_URL.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Create file scaffolding for test and helper modules

- [ ] T001 [P] Create keyboard helper file at `e2e/playwright/helpers/keyboard.ts` with module scaffolding and imports from `@playwright/test` (Locator, Page, expect)
- [ ] T002 [P] Create keyboard navigation test file at `e2e/playwright/tests/keyboard-nav.spec.ts` with test suite scaffolding, import from helpers/keyboard, and `test.beforeEach` that navigates to BASE_URL

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement helper functions that all tests depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Implement `focusAndAssert(locator)` in `e2e/playwright/helpers/keyboard.ts` — call `locator.focus()` then `expect(locator).toBeFocused()` (FR-001, FR-002)
- [ ] T004 Implement `assertFocusIndicatorVisible(locator)` in `e2e/playwright/helpers/keyboard.ts` — evaluate `getComputedStyle()` on the focused element, assert at least one of: `outlineWidth` > 0 with `outlineStyle` !== "none", or `boxShadow` !== "none" (FR-004, Research Decision 3)
- [ ] T005 Implement `assertFocusOrder(page, selectorA, selectorB)` in `e2e/playwright/helpers/keyboard.ts` — call `.focus()` on element A, press Tab once, assert element B `toBeFocused()` (FR-007, Research Decision 2)
- [ ] T006 Implement `assertNotFocusTrapped(page, selector)` in `e2e/playwright/helpers/keyboard.ts` — focus the element, press Tab once, assert `document.activeElement` is NOT the same element (FR-005, FR-010)
- [ ] T007 Implement `assertModalFocusTrap(page, openTrigger, modalSelector, closeTrigger)` in `e2e/playwright/helpers/keyboard.ts` — click openTrigger to open modal, assert focus moved inside modalSelector, focus first modal element, Tab once, assert focus is still inside modal boundary, click closeTrigger, assert focus returns to openTrigger (FR-009, Research Decision 4)

**Checkpoint**: Helper module complete — all focus management utilities available for tests

---

## Phase 3: User Story 1 — Reliable Keyboard Navigation Verification (Priority: P1) MVP

**Goal**: All interactive elements receive focus via `.focus()`, respond to keyboard input, and produce identical results in headed/headless Chromium

**Independent Test**: Run `npx playwright test keyboard-nav` in both headed and headless modes and verify identical pass/fail results

### Programmatic Focus (FR-001, FR-002, FR-006)

- [ ] T008 [US1] Implement test: "view tab buttons receive focus via .focus()" in `e2e/playwright/tests/keyboard-nav.spec.ts` — for each of the 5 view tabs (experiments, reports, detail, diff, trends), call `focusAndAssert()` and verify `toBeFocused()`
- [ ] T009 [US1] Implement test: "safety control buttons receive focus via .focus()" in `e2e/playwright/tests/keyboard-nav.spec.ts` — focus Andon cord button and gate toggle button via `focusAndAssert()`
- [ ] T010 [US1] Implement test: "filter controls receive focus via .focus()" in `e2e/playwright/tests/keyboard-nav.spec.ts` — navigate to reports view, focus scenario filter and verdict filter dropdowns via `focusAndAssert()`
- [ ] T011 [US1] Implement test: "pagination controls receive focus via .focus()" in `e2e/playwright/tests/keyboard-nav.spec.ts` — navigate to reports view, focus pagination buttons via `focusAndAssert()`

### Keyboard Interaction (FR-003)

- [ ] T012 [US1] Implement test: "Enter activates focused button" in `e2e/playwright/tests/keyboard-nav.spec.ts` — focus a view tab button, press Enter, assert the view changed (Alpine.js `currentView` updated)
- [ ] T013 [US1] Implement test: "Space activates focused toggle" in `e2e/playwright/tests/keyboard-nav.spec.ts` — focus the gate toggle, press Space, assert the toggle state changed
- [ ] T014 [US1] Implement test: "Escape closes open modal" in `e2e/playwright/tests/keyboard-nav.spec.ts` — open Andon cord modal, press Escape, assert the modal is closed

### Canvas Focus Pass-Through (FR-005, FR-010)

- [ ] T015 [US1] Implement test: "Chart.js canvas does not trap focus" in `e2e/playwright/tests/keyboard-nav.spec.ts` — navigate to trends view, locate `<canvas>` elements, assert they have `tabindex="-1"` OR use `assertNotFocusTrapped()` to verify focus passes through (Research Decision 5)

### View Transition Safety (FR-008)

- [ ] T016 [US1] Implement test: "focus is not on a hidden element after view change" in `e2e/playwright/tests/keyboard-nav.spec.ts` — focus an element in the current view, click a different view tab, assert `document.activeElement` is either `document.body` or a visible element (not inside a hidden `x-show` container) (Research Decision 6)

### Modal Focus Trap (FR-009)

- [ ] T017 [US1] Implement test: "Andon cord modal traps focus on open" in `e2e/playwright/tests/keyboard-nav.spec.ts` — use `assertModalFocusTrap()` with the Andon cord button as trigger, verify focus enters the `<dialog>` modal on open
- [ ] T018 [US1] Implement test: "focus returns to trigger on modal close" in `e2e/playwright/tests/keyboard-nav.spec.ts` — open and close the Andon cord modal, assert focus returns to the Andon cord button (FR-009, Research Decision 4)

### Tab Ban Compliance / Focus Order (FR-007)

- [ ] T019 [US1] Implement test: "Tab from first nav tab moves to second nav tab" in `e2e/playwright/tests/keyboard-nav.spec.ts` — use `assertFocusOrder()` to verify Tab from the first view tab lands on the second view tab (single-Tab assertion pattern only)

**Checkpoint**: US1 complete — all interactive elements verified for programmatic focus, keyboard interaction, and headed/headless parity

---

## Phase 4: User Story 2 — Focus Indicator Visibility Verification (Priority: P2)

**Goal**: Focused elements display visible focus indicators (outlines, rings, shadows) per WCAG 2.1 AA

**Independent Test**: Focus each element type and verify computed CSS includes a visible indicator

### Focus Indicator Assertions (FR-004)

- [ ] T020 [US2] Implement test: "focused button has visible outline or ring" in `e2e/playwright/tests/keyboard-nav.spec.ts` — focus a button element, call `assertFocusIndicatorVisible()`, verify non-zero outline or non-none box-shadow
- [ ] T021 [US2] Implement test: "focused link has visible outline or ring" in `e2e/playwright/tests/keyboard-nav.spec.ts` — focus a link element, call `assertFocusIndicatorVisible()`
- [ ] T022 [US2] Implement test: "focused tab has visible outline or ring" in `e2e/playwright/tests/keyboard-nav.spec.ts` — focus a view tab element, call `assertFocusIndicatorVisible()`
- [ ] T023 [US2] Implement test: "focused form control has visible outline or ring" in `e2e/playwright/tests/keyboard-nav.spec.ts` — focus a filter dropdown, call `assertFocusIndicatorVisible()`

### Non-Interactive Element Exclusion (FR-005)

- [ ] T024 [US2] Implement test: "non-interactive elements do not receive focus" in `e2e/playwright/tests/keyboard-nav.spec.ts` — attempt to focus decorative containers, verify they do not have `tabindex` or that focus falls through to the next interactive element

**Checkpoint**: US2 complete — all interactive element types verified for visible focus indicators

---

## Phase 5: Polish and Cross-Cutting Concerns

**Purpose**: Headed/headless parity validation and documentation

- [ ] T025 [P] Run full keyboard-nav test suite in headless mode (`npx playwright test keyboard-nav`) and record pass/fail results (SC-004, FR-006)
- [ ] T026 [P] Run full keyboard-nav test suite in headed mode (`npx playwright test keyboard-nav --headed`) and verify identical pass/fail results to T025 (SC-004, FR-006)
- [ ] T027 Verify total test execution time is under 10 seconds (SC-003) — if over budget, identify slow tests and optimize (remove unnecessary waits, parallelize independent test groups)
- [ ] T028 Run quickstart.md validation: execute all commands in `specs/001-keyboard-nav-focus/quickstart.md` and verify expected output matches

---

## Dependencies and Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No internal dependencies — can start immediately (but requires Features 1242/1245 to be implemented)
- **Foundational (Phase 2)**: Depends on T001 (helper file exists) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion (T003-T007)
- **User Story 2 (Phase 4)**: Depends on Phase 2 completion (T003-T007) — independent of US1
- **Polish (Phase 5)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 — no dependency on US2
- **User Story 2 (P2)**: Can start after Phase 2 — no dependency on US1 (uses same helpers)

### Parallel Opportunities

- T001 and T002 can run in parallel (different files)
- T003-T007 are sequential (each helper builds on module scaffolding)
- T008-T011 (programmatic focus tests) can run in parallel with each other
- T012-T014 (keyboard interaction tests) are independent of each other
- T020-T024 (focus indicator tests) can run in parallel with each other
- T025 and T026 can run in parallel (headed vs headless)

### External Dependencies

- Feature 1242 (chaos report viewer): Provides the dashboard views and interactive elements being tested
- Feature 1245 (gate toggle): Provides the safety control toggle button (T009, T013)
- If Feature 1245 is not yet implemented, T009 and T013 should skip the gate toggle assertions with a TODO note

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T007)
3. Complete Phase 3: User Story 1 (T008-T019)
4. **STOP and VALIDATE**: Run `npx playwright test keyboard-nav` in both headed and headless modes
5. Deploy if ready — focus indicator verification can be added later

### Incremental Delivery

1. Setup + Foundational -> Helper infrastructure ready
2. Add User Story 1 -> Keyboard navigation verified, flakiness eliminated -> Deploy (MVP!)
3. Add User Story 2 -> Focus indicator visibility verified -> Deploy
4. Each story adds value without breaking previous stories

---

## Notes

- No new npm dependencies needed — all APIs are built into `@playwright/test ^1.40.0`
- The ~20 interactive elements estimate comes from plan.md and will be finalized once Features 1242 and 1245 are implemented
- If Chart.js canvas lacks `tabindex="-1"`, T015 will fail and a dashboard markup fix is needed (plan.md Risk row 3)
- Contrast sufficiency of focus indicators is deferred to Feature 1271 (axe-core); this feature checks visibility only

## Adversarial Review #3

**Reviewed**: 2026-03-29

- **Highest-risk task**: T007 — modal focus trap helper depends on DaisyUI `<dialog>` native focus behavior via `showModal()`, which may differ across Alpine.js versions or DaisyUI releases.
- **Most likely rework**: T008-T011 — if `.focus()` behaves differently on `x-show`-hidden elements in headless Chromium, multiple programmatic focus tests need adjustment.
- **CRITICAL/HIGH remaining**: 0
- **READY FOR IMPLEMENTATION** (conditional on Features 1242 + 1245)

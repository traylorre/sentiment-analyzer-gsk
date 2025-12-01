# Tasks: Interview Dashboard Swipe Gestures

**Input**: Design documents from `/specs/013-interview-swipe-gestures/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: No automated tests requested. Manual testing on mobile devices as specified in quickstart.md.

**Organization**: Tasks organized by user story for independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different code sections, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, etc.)
- All tasks modify a single file: `interview/index.html`

---

## Phase 1: Setup

**Purpose**: Prepare the codebase for swipe gesture implementation

- [x] T001 Review existing section navigation code in interview/index.html
- [x] T002 Identify all section IDs and navigation item selectors in interview/index.html
- [x] T003 Document existing showSection() function behavior in interview/index.html

**Checkpoint**: ✅ Existing code structure understood, ready for implementation

---

## Phase 2: Foundational (CSS Infrastructure)

**Purpose**: Add CSS classes required by all user stories

**⚠️ CRITICAL**: CSS must be in place before JavaScript implementation

- [x] T004 Add swipe transition CSS classes (.swiping, .transitioning, .bouncing) to interview/index.html
- [x] T005 Add will-change: transform to .section class in interview/index.html
- [x] T006 Add touch-action: pan-y to .section class in interview/index.html

**Checkpoint**: ✅ CSS infrastructure ready - JavaScript implementation can begin

---

## Phase 3: User Story 1 - Section Navigation via Swipe (Priority: P1) 🎯 MVP

**Goal**: Users can swipe left/right in main content area to navigate between sections

**Independent Test**: Load on mobile device, swipe left/right, verify sections change with smooth transitions

### Implementation for User Story 1

- [x] T007 [US1] Add touch capability detection (isTouchDevice check) in interview/index.html
- [x] T008 [US1] Add section ID discovery logic (from nav items or DOM) in interview/index.html
- [x] T009 [US1] Add touchstart event handler with initial state capture in interview/index.html
- [x] T010 [US1] Add touchmove event handler with delta calculation in interview/index.html
- [x] T011 [US1] Add touchend event handler with swipe completion logic in interview/index.html
- [x] T012 [US1] Add navigateToSection() function with section switching in interview/index.html
- [x] T013 [US1] Add swipe threshold detection (30% viewport OR velocity) in interview/index.html
- [x] T014 [US1] Add snap-back animation when swipe cancelled in interview/index.html

**Checkpoint**: ✅ Basic swipe navigation works - can navigate left/right between sections

---

## Phase 4: User Story 2 - Interactive Gesture Feedback (Priority: P1)

**Goal**: Content follows finger position in real-time during swipe gesture

**Independent Test**: Slowly drag finger across screen, observe content moves proportionally

### Implementation for User Story 2

- [x] T015 [US2] Add real-time transform application during touchmove in interview/index.html
- [x] T016 [US2] Add .swiping class toggle to disable CSS transitions during drag in interview/index.html
- [x] T017 [US2] Add direction detection (horizontal vs vertical) with 1.5x threshold in interview/index.html
- [x] T018 [US2] Add vertical swipe abort logic (cancel and allow scroll) in interview/index.html

**Checkpoint**: ✅ Interactive feedback works - content follows finger during drag

---

## Phase 5: User Story 3 - Retained Hamburger Menu Access (Priority: P1)

**Goal**: Hamburger menu navigation remains functional alongside swipe gestures

**Independent Test**: Open menu, select section, verify swipe works; swipe, verify menu shows correct active section

### Implementation for User Story 3

- [x] T019 [US3] Add nav-item active class update after swipe navigation in interview/index.html
- [x] T020 [US3] Wrap existing showSection() to sync currentSectionIndex in interview/index.html
- [x] T021 [US3] Add swipe cancellation when menu state changes in interview/index.html

**Checkpoint**: ✅ Menu and swipe navigation work interchangeably

---

## Phase 6: User Story 4 - Edge Swipe Disabled (Priority: P2)

**Goal**: Swipes starting within 20px of screen edges do not trigger navigation

**Independent Test**: Start swipe from screen edge, verify no section transition

### Implementation for User Story 4

- [x] T022 [US4] Add isEdgeTouch() helper function with 20px threshold in interview/index.html
- [x] T023 [US4] Add edge touch check in touchstart handler (early return) in interview/index.html

**Checkpoint**: ✅ Edge swipes are ignored, browser/OS gestures work

---

## Phase 7: User Story 5 - Desktop Compatibility (Priority: P3)

**Goal**: Swipe gestures disabled on desktop; keyboard/menu navigation only

**Independent Test**: Click and drag on desktop, verify no transition; Ctrl+1-9 still works

### Implementation for User Story 5

- [x] T024 [US5] Add early exit in IIFE if not touch device in interview/index.html
- [x] T025 [US5] Verify mouse events are not bound (touch events only) in interview/index.html

**Checkpoint**: ✅ Desktop unaffected - no drag behavior, keyboard shortcuts work

---

## Phase 8: User Story 1 Enhancement - Rubber-Band Resistance (Priority: P1)

**Goal**: At first/last section, content stretches slightly then snaps back (clarification requirement)

**Independent Test**: On first section, swipe right - content should stretch then bounce back

### Implementation for Rubber-Band

- [x] T026 [US1] Add applyRubberBand() helper function (30% resistance, 100px max) in interview/index.html
- [x] T027 [US1] Add boundary detection (first/last section) in touchmove handler in interview/index.html
- [x] T028 [US1] Apply rubber-band transform at boundaries in interview/index.html
- [x] T029 [US1] Add .bouncing class for snap-back animation in interview/index.html

**Checkpoint**: ✅ Rubber-band effect complete - polished feel at boundaries

---

## Phase 9: Polish & Integration

**Purpose**: Final refinements and edge case handling

- [x] T030 Add touchcancel event handler for interrupted gestures in interview/index.html
- [x] T031 Add resetSwipeState() function for clean state management in interview/index.html
- [x] T032 Add diagonal swipe detection (abort if Y > X / 1.5) in interview/index.html
- [x] T033 Test velocity-based flick completion in interview/index.html
- [ ] T034 Manual testing on iOS Safari per quickstart.md
- [ ] T035 Manual testing on Android Chrome per quickstart.md
- [ ] T036 Manual testing with Chrome DevTools mobile simulation per quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - CSS must be ready before JS
- **User Story 1 (Phase 3)**: Depends on Foundational - core swipe navigation
- **User Story 2 (Phase 4)**: Depends on US1 - adds interactive feedback to core
- **User Story 3 (Phase 5)**: Depends on US1 - adds menu sync to core
- **User Story 4 (Phase 6)**: Can start after Foundational - independent of US2/US3
- **User Story 5 (Phase 7)**: Can start after Foundational - independent of other stories
- **Rubber-Band (Phase 8)**: Depends on US1 - enhancement to core navigation
- **Polish (Phase 9)**: Depends on all user stories

### User Story Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational CSS)
    ↓
Phase 3 (US1: Core Swipe) ←──────────────────┐
    ↓                                         │
Phase 4 (US2: Interactive) [depends on US1]   │
    ↓                                         │
Phase 5 (US3: Menu Sync) [depends on US1]     │
                                              │
Phase 6 (US4: Edge Disable) [independent] ────┤
                                              │
Phase 7 (US5: Desktop) [independent] ─────────┤
                                              │
Phase 8 (Rubber-Band) [depends on US1] ───────┘
    ↓
Phase 9 (Polish)
```

### Parallel Opportunities

Since all tasks modify a single file, true parallelization is limited. However:

- **Foundational CSS tasks (T004-T006)** can be written together before any JS
- **US4 (Edge Disable) and US5 (Desktop)** can be developed independently after US1
- **Testing tasks (T034-T036)** can run in parallel on different devices

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (understand existing code)
2. Complete Phase 2: Foundational CSS
3. Complete Phase 3: User Story 1 (core swipe navigation)
4. **STOP and VALIDATE**: Test on mobile device - can you swipe between sections?
5. If yes, MVP is ready for demo

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test → Basic swipe works (MVP!)
3. Add US2 → Test → Content follows finger (polished!)
4. Add US3 → Test → Menu syncs with swipe
5. Add US4/US5 → Test → Edge cases handled
6. Add Rubber-Band → Test → Premium feel complete
7. Polish → Final testing → Feature complete

### Single Developer Strategy

Execute phases sequentially:
1. T001-T006: Setup and CSS (30 min)
2. T007-T014: Core swipe (1 hour)
3. T015-T018: Interactive feedback (30 min)
4. T019-T021: Menu sync (20 min)
5. T022-T023: Edge disable (10 min)
6. T024-T025: Desktop check (5 min)
7. T026-T029: Rubber-band (30 min)
8. T030-T036: Polish and testing (1 hour)

**Total estimated effort**: ~4 hours

---

## Notes

- All tasks modify `interview/index.html` - commit frequently to enable rollback
- Test on real mobile device frequently, not just DevTools simulation
- CSS transitions must be in place before JavaScript transforms will animate
- The showSection() wrapper (T020) is critical for menu sync
- Edge detection (T022-T023) prevents conflicts with iOS Safari back gesture

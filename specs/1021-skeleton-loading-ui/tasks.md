# Tasks: Skeleton Loading UI

**Feature Branch**: `1021-skeleton-loading-ui`
**Generated**: 2025-12-22
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 24 |
| Phase 1 (Setup) | 2 |
| Phase 2 (Foundational) | 4 |
| Phase 3 (US1 - Initial Load) | 6 |
| Phase 4 (US2 - Resolution Switch) | 4 |
| Phase 5 (US3 - Data Refresh) | 4 |
| Phase 6 (Polish) | 4 |
| Parallel Opportunities | 8 tasks marked [P] |

**MVP Scope**: Phases 1-3 (12 tasks) delivers skeleton on initial load with shimmer animation.

## Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6 (Polish)
                                              ↓
                                    [Independent MVP]
```

User stories are mostly independent after foundational CSS/JS is in place.

---

## Phase 1: Setup

- [x] T001 Add skeleton CSS class definitions with shimmer animation in src/dashboard/styles.css
- [x] T002 Add skeleton timing constants to CONFIG object in src/dashboard/config.js

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T003 [P] Create skeletonState object and showSkeleton/hideSkeleton functions in src/dashboard/app.js
- [x] T004 [P] Add skeleton HTML structure with data-skeleton attributes in src/dashboard/index.html
- [x] T005 Add skeleton overlay CSS with absolute positioning and opacity transition in src/dashboard/styles.css
- [x] T006 Add ARIA accessibility attributes (aria-busy, aria-hidden) pattern in src/dashboard/index.html

---

## Phase 3: User Story 1 - Initial Dashboard Load with Skeleton (P1)

**Goal**: Skeleton placeholders appear within 100ms on initial page load

**Independent Test**: Load dashboard with network throttling, verify skeletons appear before data

- [x] T007 [US1] Add skeleton-chart class with chart area dimensions in src/dashboard/styles.css
- [x] T008 [US1] Add skeleton-ticker-item class with ticker list item dimensions in src/dashboard/styles.css
- [x] T009 [US1] Add skeleton-resolution class with resolution selector dimensions in src/dashboard/styles.css
- [x] T010 [US1] Call showSkeleton() for all components on DOMContentLoaded in src/dashboard/app.js
- [x] T011 [US1] Call hideSkeleton() with smooth transition when initial data arrives in src/dashboard/app.js
- [x] T012 [US1] Verify zero spinners by searching codebase and removing any spinner classes in src/dashboard/styles.css

---

## Phase 4: User Story 2 - Resolution Switch with Skeleton (P2)

**Goal**: Chart shows skeleton during resolution switch data fetch

**Independent Test**: Click resolution buttons, verify chart skeleton during fetch

- [x] T013 [US2] Add resolution switch event handler that calls showSkeleton('chart') in src/dashboard/timeseries.js
- [x] T014 [US2] Add debounce logic for rapid resolution switches (300ms) in src/dashboard/timeseries.js
- [x] T015 [US2] Call hideSkeleton('chart') when new resolution data arrives in src/dashboard/timeseries.js
- [x] T016 [US2] Cancel pending fetch and skeleton timeout on new resolution switch in src/dashboard/timeseries.js

---

## Phase 5: User Story 3 - Data Refresh with Skeleton (P3)

**Goal**: Background refresh shows skeleton overlay without disrupting visible data

**Independent Test**: Trigger SSE reconnect, verify skeleton overlay appears then fades

- [x] T017 [US3] Add skeleton overlay mode that preserves existing content visibility in src/dashboard/app.js
- [x] T018 [US3] Hook showSkeleton to SSE reconnection event handler in src/dashboard/app.js
- [x] T019 [US3] Hook hideSkeleton to successful SSE data reception in src/dashboard/app.js
- [x] T020 [US3] Add manual refresh button skeleton trigger in src/dashboard/app.js (N/A - no manual refresh button)

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T021 [P] Add 30-second timeout with error state transition in src/dashboard/app.js
- [x] T022 [P] Add empty state message for components with no data in src/dashboard/app.js
- [x] T023 [P] Create E2E test for skeleton loading behavior in tests/e2e/test_skeleton_loading.py
- [x] T024 Verify all ARIA attributes update correctly during state transitions in src/dashboard/app.js

---

## Parallel Execution Examples

**Phase 2** (after T001-T002):
```
T003 ─┬─ T004
      │
      └─ (wait for both) → T005 → T006
```

**Phase 3** (after T006):
```
T007 ─┬─ T008 ─┬─ T009
      │        │
      └────────┴─ (wait for all) → T010 → T011 → T012
```

**Phase 6** (after US3):
```
T021 ─┬─ T022 ─┬─ T023
      │        │
      └────────┴─ (wait for all) → T024
```

## Implementation Strategy

1. **MVP First**: Complete Phases 1-3 (12 tasks) to deliver working skeleton on initial load
2. **Incremental Delivery**: Each user story phase is independently testable
3. **Test Verification**: T023 creates E2E test to validate all success criteria
4. **Accessibility Last**: T024 validates ARIA compliance after all functionality complete

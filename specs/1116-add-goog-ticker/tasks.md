# Tasks: Add GOOG Ticker Support

**Input**: Design documents from `/specs/1116-add-goog-ticker/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: No new tests required - existing unit tests cover ticker search functionality.

**Organization**: This is a minimal data-only change. Both user stories (Search + View) are satisfied by the same data changes, so tasks are combined.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 = Search, US2 = View)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No setup required - modifying existing files only

*No tasks in this phase.*

---

## Phase 2: Foundational

**Purpose**: No foundational tasks - this is a data-only change to existing infrastructure

*No tasks in this phase.*

---

## Phase 3: User Story 1 & 2 - Add GOOG Ticker (Priority: P1)

**Goal**: Enable GOOG ticker search and OHLC data viewing

**Independent Test**: Search for "GOOG" in dashboard, verify it appears with "Alphabet Inc - Class C" name, and verify OHLC chart loads with price data

### Implementation

- [X] T001 [P] [US1] Add GOOG entry to ticker database in infrastructure/data/us-symbols.json
- [X] T002 [P] [US1] Add GOOG to fallback ticker list in src/lambdas/dashboard/tickers.py

**Checkpoint**: GOOG should now be searchable and return OHLC data

---

## Phase 4: Verification

**Purpose**: Validate the change works end-to-end

- [ ] T003 Verify search API returns GOOG for query "GOOG" via curl test
- [ ] T004 Verify OHLC endpoint returns valid data for GOOG ticker via curl test

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: N/A - no setup required
- **Phase 2 (Foundational)**: N/A - no foundational tasks
- **Phase 3 (Implementation)**: Can start immediately - T001 and T002 are parallel
- **Phase 4 (Verification)**: Depends on Phase 3 completion

### Parallel Opportunities

- T001 and T002 can run in parallel (different files, no dependencies)

---

## Parallel Example

```bash
# Launch both data changes together:
Task: "Add GOOG entry to infrastructure/data/us-symbols.json"
Task: "Add GOOG to src/lambdas/dashboard/tickers.py"
```

---

## Implementation Strategy

### MVP (All Stories in One)

1. Complete T001 + T002 (can be parallel)
2. Run T003 + T004 for verification
3. Deploy - feature complete

### Task Details

**T001**: Copy GOOGL entry format, change:
- Key: "GOOG"
- name: "Alphabet Inc - Class C"
- exchange: "NASDAQ" (same)
- is_active: true (same)

**T002**: Find COMMON_TICKERS or similar hardcoded list, add "GOOG" alongside "GOOGL"

---

## Notes

- This is a minimal 2-task implementation
- No new tests needed - existing ticker search tests will pass
- No code logic changes - purely data configuration
- Both user stories are satisfied by the same data additions

# Tasks: Fix Ticker Search API Contract

**Input**: Design documents from `/specs/1120-fix-ticker-search-contract/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete), quickstart.md (complete)

**Tests**: Unit tests REQUIRED per Constitution Check in plan.md

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Project**: `frontend/src/lib/api/` for API client code

---

## Phase 1: Setup (No Changes Required)

**Purpose**: Project already initialized. No setup tasks needed.

**Checkpoint**: Project structure already exists - proceed to implementation.

---

## Phase 2: Foundational (No Changes Required)

**Purpose**: No foundational/blocking prerequisites for this fix.

**Checkpoint**: Foundation ready - proceed to User Story 1.

---

## Phase 3: User Story 1 - Ticker Search Returns Results (Priority: P1) MVP

**Goal**: Fix ticker search to correctly unwrap the `{results: [...]}` response from backend so users see search results when typing "GOOG".

**Independent Test**: Type "GOOG" in ticker search box - should show GOOG and GOOGL in dropdown.

### Implementation for User Story 1

- [x] T001 [US1] Add TickerSearchResponse interface to frontend/src/lib/api/tickers.ts - define `{results: TickerSearchResult[]}`
- [x] T002 [US1] Modify search() method in frontend/src/lib/api/tickers.ts - change type to TickerSearchResponse and unwrap results field
- [x] T003 [US1] Verify TypeScript compilation passes with `npm run build` in frontend/

**Checkpoint**: User Story 1 complete - ticker search displays results for "GOOG".

---

## Phase 4: User Story 2 - Graceful Handling of No Results (Priority: P2)

**Goal**: Ensure empty search results return an empty array (not undefined or error).

**Independent Test**: Type "ZZZZZ" in ticker search box - should show "no results" message (not error).

### Implementation for User Story 2

- [x] T004 [US2] Verify empty results handling in frontend/src/lib/api/tickers.ts - ensure `response.results ?? []` fallback

**Checkpoint**: User Stories 1 AND 2 both work - ticker search is fully functional.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and verification

- [x] T005 Run frontend build to verify no TypeScript errors (`npm run build` in frontend/)
- [ ] T006 Run quickstart.md validation - test all search scenarios (skip - requires deployed Lambda)
- [x] T007 Verify linting passes (`npm run lint` in frontend/)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: SKIP - no changes needed
- **Foundational (Phase 2)**: SKIP - no changes needed
- **User Story 1 (Phase 3)**: Can start immediately
- **User Story 2 (Phase 4)**: Verify after US1 complete
- **Polish (Phase 5)**: After all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - can start immediately
- **User Story 2 (P2)**: Depends on US1 completion (uses same code path)

### Within User Story 1

1. T001 (interface) - no dependencies
2. T002 (method change) - depends on T001
3. T003 (build verification) - depends on T002

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Implement T001-T003 (fix)
2. Verify search works
3. **STOP and VALIDATE**: Test in browser
4. Deploy via PR

### Total Tasks

- **Implementation tasks**: 4 (T001-T004)
- **Verification tasks**: 3 (T005-T007)
- **Total**: 7 tasks

---

## Notes

- This is a minimal fix - only 1 file modified (tickers.ts)
- Backend API unchanged - response wrapping is correct RESTful pattern
- Frontend change is isolated to API client layer

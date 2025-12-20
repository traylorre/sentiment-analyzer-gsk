# Tasks

## Phase 1: Code Fix

- [ ] T001: Update get_full_items() to extract timestamp from item
- [ ] T002: Update GetItem Key to include both source_id and timestamp
- [ ] T003: Add null check for missing timestamp with warning log
- [ ] T004: Update ProjectionExpression to remove redundant timestamp

## Phase 2: Unit Tests

- [ ] T005: Update test mocks to expect composite key in GetItem
- [ ] T006: Add test for missing timestamp handling
- [ ] T007: Verify all existing tests still pass

## Phase 3: Validation

- [ ] T008: Run ruff check on modified files
- [ ] T009: Run full unit test suite
- [ ] T010: Verify no regressions

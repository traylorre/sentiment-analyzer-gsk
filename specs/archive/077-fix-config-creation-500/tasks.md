# Implementation Tasks: Fix Config Creation 500 Error

**Feature**: 077-fix-config-creation-500
**Branch**: `077-fix-config-creation-500`
**Generated**: 2025-12-10
**Total Tasks**: 12

## Overview

This task list implements the fix for the HTTP 500 error on the config creation endpoint (`POST /api/v2/configurations`). Tasks are organized by user story priority.

### User Stories Summary

| Story | Priority | Description | Tasks |
|-------|----------|-------------|-------|
| US1 | P1 | Create Configuration Successfully | 4 |
| US2 | P2 | E2E Tests Pass Without Skipping | 3 |
| US3 | P3 | Error Handling Returns Appropriate Status Codes | 3 |
| Setup | - | Foundational tasks | 2 |

---

## Phase 1: Setup & Diagnostics

**Goal**: Establish baseline and add diagnostic logging without breaking existing functionality.

- [ ] T001 Verify unit tests pass before changes by running `make test-unit` and confirming 16 config tests pass
- [ ] T002 Add CodeQL-safe diagnostic logging helper in `src/lambdas/shared/logging_utils.py` (create if needed) with `get_safe_log_context()` function that returns only safe fields (counts, hashes, booleans)

---

## Phase 2: User Story 1 - Create Configuration Successfully (P1)

**Goal**: Fix the root cause of the 500 error so config creation returns HTTP 201.

**Independent Test**: `curl -X POST /api/v2/configurations` with valid payload returns 201.

### Tasks

- [ ] T003 [US1] Add diagnostic logging at entry point of `create_configuration()` in `src/lambdas/dashboard/configurations.py:199` - log operation, ticker_count, ticker_cache_available (no user content per FR-006)
- [ ] T004 [US1] Add try/except wrapper around `table.put_item()` call in `src/lambdas/dashboard/configurations.py:270-280` to catch and log `ClientError` with error code (not user data)
- [ ] T005 [US1] Add try/except wrapper around `_validate_ticker()` calls in `src/lambdas/dashboard/configurations.py:240-250` to catch validation exceptions and return `ErrorResponse` instead of re-raising
- [ ] T006 [US1] Verify fix by deploying to preprod and running `curl -X POST` against `/api/v2/configurations` endpoint - confirm HTTP 201 response

**Completion Criteria**: SC-001 verified (HTTP 201 for valid requests)

---

## Phase 3: User Story 2 - E2E Tests Pass Without Skipping (P2)

**Goal**: Remove skip patterns from E2E tests and verify they execute.

**Independent Test**: `pytest tests/e2e -k config` shows 0 skipped tests.

### Tasks

- [ ] T007 [US2] Remove or modify skip pattern in `tests/e2e/test_config_crud.py` that skips on 500 response - tests should fail explicitly if endpoint broken
- [ ] T008 [US2] Remove or modify skip pattern in `tests/e2e/test_dashboard_buffered.py` for config-related tests
- [ ] T009 [US2] Run `pytest tests/e2e -k config` and verify 0 tests skip due to config creation issues (some may skip for other valid reasons like notifications API)

**Completion Criteria**: SC-002 verified (E2E tests execute without config-related skips)

---

## Phase 4: User Story 3 - Error Handling Returns Appropriate Status Codes (P3)

**Goal**: Improve exception handling to return 4xx for client errors, 500 only for server errors.

**Independent Test**: Send malformed requests and verify 400/422 responses (not 500).

### Tasks

- [ ] T010 [US3] Update exception handling in `src/lambdas/dashboard/router_v2.py:681-700` to catch `ValueError` from service and return HTTP 400 with message
- [ ] T011 [US3] Add unit test in `tests/unit/dashboard/test_configurations.py` verifying that invalid ticker returns `ErrorResponse` (not exception)
- [ ] T012 [US3] Run `make test-unit` to verify no regressions (all 16+ config tests pass)

**Completion Criteria**: SC-003 verified (unit tests pass), FR-003 verified (4xx for client errors)

---

## Phase 5: Finalization

**Goal**: Verify all success criteria and prepare for merge.

- [ ] T013 Run `make validate` (includes SAST) to verify no CodeQL CWE-117 log injection warnings (SC-005)
- [ ] T014 Create GPG-signed commit with root cause documented in commit message (SC-004)
- [ ] T015 Push to branch and verify CI passes

---

## Dependencies

```text
T001 (verify baseline)
  └── T002 (logging helper)
        └── T003, T004, T005 (US1 - can run in parallel after T002)
              └── T006 (verify US1 fix)
                    └── T007, T008 (US2 - can run in parallel)
                          └── T009 (verify US2)
                                └── T010 (US3)
                                      └── T011 (US3 unit test)
                                            └── T012 (verify unit tests)
                                                  └── T013, T014, T015 (finalization)
```

## Parallel Execution Opportunities

| Phase | Parallelizable Tasks | Reason |
|-------|---------------------|--------|
| Phase 2 | T003, T004, T005 | Different code sections in same file |
| Phase 3 | T007, T008 | Different test files |
| Phase 5 | T013, T014 after T012 | Independent validation steps |

## Implementation Strategy

### MVP Scope (Recommended)

**MVP = US1 only (Tasks T001-T006)**
- Fixes the core bug blocking users
- Can be deployed immediately
- US2 and US3 can follow in subsequent PRs

### Incremental Delivery

1. **PR 1 (MVP)**: T001-T006 - Fix the 500 error
2. **PR 2**: T007-T009 - Remove E2E test skips
3. **PR 3**: T010-T012 - Improve error handling

### Risk Mitigation

- T001 establishes baseline before any changes
- Each phase is independently testable
- Rollback is straightforward (revert single file changes)

---

## Success Criteria Checklist

| Criterion | Task | Verification |
|-----------|------|--------------|
| SC-001: HTTP 201 for valid requests | T006 | curl returns 201 |
| SC-002: E2E tests execute | T009 | pytest shows 0 config skips |
| SC-003: Unit tests pass | T012 | make test-unit passes |
| SC-004: Root cause documented | T014 | Commit message explains fix |
| SC-005: No CodeQL CWE-117 | T013 | make validate passes |

---

## Files Modified

| File | Tasks | Change |
|------|-------|--------|
| `src/lambdas/shared/logging_utils.py` | T002 | Add safe logging helper |
| `src/lambdas/dashboard/configurations.py` | T003, T004, T005 | Add logging, exception handling |
| `src/lambdas/dashboard/router_v2.py` | T010 | Improve HTTP error responses |
| `tests/e2e/test_config_crud.py` | T007 | Remove skip patterns |
| `tests/e2e/test_dashboard_buffered.py` | T008 | Remove skip patterns |
| `tests/unit/dashboard/test_configurations.py` | T011 | Add validation test |

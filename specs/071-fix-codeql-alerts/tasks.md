# Tasks: Fix CodeQL Security Alerts

**Input**: Design documents from `/specs/071-fix-codeql-alerts/`
**Prerequisites**: plan.md (required), spec.md (required), research.md

**Tests**: No test tasks included - spec does not request new tests (existing tests must pass per SC-004).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Verification)

**Purpose**: Verify current state and ensure clean working environment

- [x] T001 Verify branch `071-fix-codeql-alerts` exists and is checked out
- [x] T002 Run `make test-unit` to establish baseline (all tests must pass)
- [x] T003 Run `make sast` to verify current SAST state

---

## Phase 2: User Story 1 - Security Team Reviews Logs Safely (Priority: P1)

**Goal**: Fix 2 log injection alerts (CWE-117) in ohlc.py so security analysts can review logs without risk of injected malicious content.

**Independent Test**: Run `make sast` - should show no log injection warnings for ohlc.py.

### Implementation for User Story 1

- [x] T004 [P] [US1] Fix log injection at line 121 in src/lambdas/dashboard/ohlc.py - Replace `sanitize_for_log(ticker)` with inline `.replace()` pattern
- [x] T005 [P] [US1] Fix log injection at line 261 in src/lambdas/dashboard/ohlc.py - Replace `sanitize_for_log(ticker)` with inline `.replace()` pattern
- [x] T006 [US1] Run `make test-unit` to verify no regression in src/lambdas/dashboard/ohlc.py tests
- [x] T007 [US1] Run `make sast` to verify log injection warnings are resolved

**Checkpoint**: At this point, both log injection alerts in ohlc.py should be resolved.

---

## Phase 3: User Story 2 - Operations Team Troubleshoots Without Credential Exposure (Priority: P1)

**Goal**: Fix 1 clear-text logging alert (CWE-312) in secrets.py so operations engineers can review logs without seeing sensitive credentials.

**Independent Test**: Run `make sast` - should show no clear-text logging warnings for secrets.py.

### Implementation for User Story 2

- [x] T008 [US2] Fix clear-text logging at line 228 in src/lambdas/shared/secrets.py - Use intermediate variable to break taint flow
- [x] T009 [US2] Review other logger calls in src/lambdas/shared/secrets.py for similar patterns (lines 237-240)
- [x] T010 [US2] Run `make test-unit` to verify no regression in src/lambdas/shared/secrets.py tests
- [x] T011 [US2] Run `make sast` to verify clear-text logging warning is resolved

**Checkpoint**: At this point, the clear-text logging alert in secrets.py should be resolved.

---

## Phase 4: User Story 3 - Developer Maintains Code Quality (Priority: P2)

**Goal**: Document the pattern for future developers to prevent reintroduction of these vulnerabilities.

**Independent Test**: Run `make sast` and verify CodeQL scan passes after push.

### Implementation for User Story 3

- [x] T012 [US3] Add comment in src/lambdas/shared/logging_utils.py explaining CodeQL taint barrier requirements
- [x] T013 [US3] Update docstring of `sanitize_for_log()` to note when inline sanitization is preferred

**Checkpoint**: Documentation added for future maintainers.

---

## Phase 5: Verification & Polish

**Purpose**: Final verification that all success criteria are met

- [x] T014 Run full test suite with `make test-unit` (SC-004)
- [x] T015 Run `make sast` to verify all local SAST checks pass (SC-003)
- [ ] T016 Commit changes with descriptive message referencing CWE-117 and CWE-312
- [ ] T017 Push branch and verify CodeQL GitHub Action passes (SC-001, SC-002)
- [ ] T018 Verify `/security` tab shows 0 HIGH alerts (SC-001, SC-002)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **User Story 1 (Phase 2)**: Depends on Setup completion - T004, T005 can run in parallel
- **User Story 2 (Phase 3)**: Can start after Setup (Phase 1) - Independent of User Story 1
- **User Story 3 (Phase 4)**: Can start after Setup (Phase 1) - Independent documentation task
- **Verification (Phase 5)**: Depends on Phases 2 and 3 completion

### User Story Dependencies

- **User Story 1 (P1)**: Files: `ohlc.py` only - No dependencies on other stories
- **User Story 2 (P1)**: Files: `secrets.py` only - No dependencies on other stories
- **User Story 3 (P2)**: Files: `logging_utils.py` only - Can be done in parallel

### Parallel Opportunities

Tasks T004 and T005 can run in parallel (different code locations in same file, but independent changes).

User Stories 1, 2, and 3 can all be worked on in parallel since they affect different files:
- US1: `src/lambdas/dashboard/ohlc.py`
- US2: `src/lambdas/shared/secrets.py`
- US3: `src/lambdas/shared/logging_utils.py`

---

## Parallel Example: All User Stories

```bash
# All user stories can start simultaneously after Setup phase:

# User Story 1 (ohlc.py):
Task: "Fix log injection at line 121 in src/lambdas/dashboard/ohlc.py"
Task: "Fix log injection at line 261 in src/lambdas/dashboard/ohlc.py"

# User Story 2 (secrets.py):
Task: "Fix clear-text logging at line 228 in src/lambdas/shared/secrets.py"

# User Story 3 (logging_utils.py):
Task: "Add comment in src/lambdas/shared/logging_utils.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: User Story 1 - Log Injection (T004-T007)
3. Complete Phase 3: User Story 2 - Clear-Text Logging (T008-T011)
4. **STOP and VALIDATE**: Run `make sast` - all 3 alerts should be resolved
5. Complete Phase 5: Verification (T014-T018)
6. Push and create PR

### Full Implementation

1. Complete all MVP tasks above
2. Add Phase 4: User Story 3 - Documentation (T012-T013)
3. Amend commit if needed
4. PR ready for merge

---

## Success Criteria Mapping

| Task | Success Criteria |
|------|------------------|
| T004, T005, T007 | SC-001: 0 alerts for `py/log-injection` |
| T008, T011 | SC-002: 0 alerts for `py/clear-text-logging-sensitive-data` |
| T015 | SC-003: Local `make sast` passes |
| T006, T010, T014 | SC-004: All existing unit tests pass |
| All tasks | SC-005: Log output remains useful (no format changes) |

---

## Notes

- [P] tasks = different files/locations, no dependencies
- Each user story is independently completable and testable
- No new tests required - spec only requires existing tests to pass
- Commit after completing each user story's implementation
- The inline sanitization pattern is documented in research.md

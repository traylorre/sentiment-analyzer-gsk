# Tasks: CodeQL Security Vulnerability Remediation

**Input**: Design documents from `/specs/1216-codeql-remediation/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete)

**Tests**: Not explicitly requested - validation via CodeQL scan in CI pipeline.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Lambda source code in src/lambdas/
- Scripts in scripts/
- Shared utilities in src/lambdas/shared/

---

## Phase 1: Setup

**Purpose**: Understand current state and verify branch

- [X] T001 Verify on branch 1216-codeql-remediation with latest main merged
- [X] T002 Review existing sanitization utility in src/lambdas/shared/logging_utils.py

**Checkpoint**: Ready to begin remediation

---

## Phase 2: User Story 1 - Security Team Validates Secure Logging Practices (Priority: P1)

**Goal**: Remediate all 26 py/log-injection findings by adding inline sanitization patterns

**Independent Test**: Run CodeQL scan and verify zero py/log-injection findings

### Implementation for User Story 1 - auth.py (21 findings)

- [X] T003 [P] [US1] Add inline sanitization at line 540 in src/lambdas/dashboard/auth.py
- [X] T004 [P] [US1] Add inline sanitization at line 599 in src/lambdas/dashboard/auth.py
- [X] T005 [P] [US1] Add inline sanitization at line 607 in src/lambdas/dashboard/auth.py
- [X] T006 [P] [US1] Add inline sanitization at line 617 in src/lambdas/dashboard/auth.py
- [X] T007 [P] [US1] Add inline sanitization at line 624 in src/lambdas/dashboard/auth.py
- [X] T008 [P] [US1] Add inline sanitization at line 2040 in src/lambdas/dashboard/auth.py
- [X] T009 [P] [US1] Add inline sanitization at line 2048 in src/lambdas/dashboard/auth.py
- [X] T010 [P] [US1] Add inline sanitization at line 2066 in src/lambdas/dashboard/auth.py
- [X] T011 [P] [US1] Add inline sanitization at line 2115 in src/lambdas/dashboard/auth.py
- [X] T012 [P] [US1] Add inline sanitization at line 2131 in src/lambdas/dashboard/auth.py
- [X] T013 [P] [US1] Add inline sanitization at line 2150 in src/lambdas/dashboard/auth.py
- [X] T014 [P] [US1] Add inline sanitization at line 2167 in src/lambdas/dashboard/auth.py
- [X] T015 [P] [US1] Add inline sanitization at line 2324 in src/lambdas/dashboard/auth.py
- [X] T016 [P] [US1] Add inline sanitization at line 2384 in src/lambdas/dashboard/auth.py
- [X] T017 [P] [US1] Add inline sanitization at line 2393 in src/lambdas/dashboard/auth.py
- [X] T018 [P] [US1] Add inline sanitization at line 2447 in src/lambdas/dashboard/auth.py
- [X] T019 [P] [US1] Add inline sanitization at line 2456 in src/lambdas/dashboard/auth.py
- [X] T020 [P] [US1] Add inline sanitization at line 2490 in src/lambdas/dashboard/auth.py
- [X] T021 [P] [US1] Add inline sanitization at line 2501 in src/lambdas/dashboard/auth.py
- [X] T022 [P] [US1] Add inline sanitization at line 2525 in src/lambdas/dashboard/auth.py
- [X] T023 [P] [US1] Add inline sanitization at line 2534 in src/lambdas/dashboard/auth.py

### Implementation for User Story 1 - ohlc.py (2 findings)

- [X] T024 [P] [US1] Add inline sanitization for cache_key at line 342 in src/lambdas/dashboard/ohlc.py
- [X] T025 [P] [US1] Add inline sanitization for cache_key at line 478 in src/lambdas/dashboard/ohlc.py

### Implementation for User Story 1 - oauth_state.py (3 log injection findings)

- [X] T026 [P] [US1] Add inline sanitization at line 193 in src/lambdas/shared/auth/oauth_state.py
- [X] T027 [P] [US1] Add inline sanitization at line 201 in src/lambdas/shared/auth/oauth_state.py
- [X] T028 [P] [US1] Add inline sanitization at line 220 in src/lambdas/shared/auth/oauth_state.py

**Checkpoint**: All 26 py/log-injection findings remediated

---

## Phase 3: User Story 2 - Security Team Validates No Sensitive Data Exposure (Priority: P1)

**Goal**: Remediate 1 py/clear-text-logging-sensitive-data finding

**Independent Test**: Run CodeQL scan and verify zero py/clear-text-logging-sensitive-data findings

### Implementation for User Story 2

- [X] T029 [US2] Remove or redact sensitive credential at line 95 in src/lambdas/shared/auth/oauth_state.py

**Checkpoint**: Clear-text logging of sensitive data eliminated

---

## Phase 4: User Story 3 - Maintainers Have Clean CI Pipeline (Priority: P2)

**Goal**: Remediate 1 py/bad-tag-filter finding and verify all fixes

**Independent Test**: Push PR and verify CodeQL check passes with zero findings

### Implementation for User Story 3

- [X] T030 [US3] Remove unnecessary HTML comment regex at line 81 in scripts/regenerate-mermaid-url.py

**Checkpoint**: Bad tag filter finding eliminated

---

## Phase 5: Polish & Verification

**Purpose**: Final verification and cleanup

- [X] T031 Run ruff check to verify no linting issues introduced
- [X] T032 Run existing unit tests to verify no regressions
- [ ] T033 Push branch and verify CodeQL check passes on PR
- [ ] T034 Verify zero py/log-injection findings in CodeQL results
- [ ] T035 Verify zero py/clear-text-logging-sensitive-data findings in CodeQL results
- [ ] T036 Verify zero py/bad-tag-filter findings in CodeQL results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **User Story 1 (Phase 2)**: Depends on Setup
- **User Story 2 (Phase 3)**: Depends on Setup - Can run parallel with US1
- **User Story 3 (Phase 4)**: Depends on Setup - Can run parallel with US1 and US2
- **Polish (Phase 5)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (Log Injection)**: Independent - most critical, most findings
- **User Story 2 (Sensitive Data)**: Independent - single file change
- **User Story 3 (Bad Tag Filter)**: Independent - single file change

### Parallel Opportunities

- All T003-T028 can run in parallel (different files or independent locations)
- US1, US2, US3 implementation phases can run in parallel
- Within auth.py: all 21 changes are independent and can be done in sequence

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1: Setup
2. Complete Phase 2: User Story 1 (Log Injection) - fixes 26 of 28 findings
3. **STOP and VALIDATE**: Push and verify CodeQL reports fewer findings
4. Continue with US2 and US3 if MVP successful

### Incremental Delivery

1. Setup complete → Ready to work
2. US1 complete → 26 log injection findings fixed → Validate via CodeQL
3. US2 complete → Clear-text logging fixed
4. US3 complete → Bad tag filter fixed
5. Polish → All verification complete, PR passes CodeQL

---

## Sanitization Pattern Reference

For all log injection fixes, use this inline pattern that CodeQL recognizes:

```python
# Before (flagged by CodeQL)
logger.info("Message", extra={"field": user_value})

# After (CodeQL-recognized taint barrier)
safe_value = str(user_value).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")[:200]
logger.info("Message", extra={"field": safe_value})
```

For values already using `sanitize_for_log()`, add inline replacement to make CodeQL recognize the barrier:

```python
# If existing code uses sanitize_for_log but CodeQL still flags it
safe_value = sanitize_for_log(user_value)
safe_value = safe_value.replace("\n", " ").replace("\r", " ")  # CodeQL barrier
logger.info("Message", extra={"field": safe_value})
```

---

## Notes

- [P] tasks = different files or independent code locations
- [Story] label maps task to specific user story for traceability
- Primary validation is CodeQL scan in CI - no additional tests needed
- All 28 findings must reach zero for PR to pass security checks
- Preserve log message semantic meaning - only strip control characters

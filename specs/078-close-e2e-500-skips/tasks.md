# Tasks: Close Config Creation 500 E2E Test Skips

**Input**: Design documents from `/specs/078-close-e2e-500-skips/`
**Prerequisites**: plan.md, spec.md, research.md

**Tests**: No new tests required. This is test maintenance - removing defensive skips from existing tests.

**Organization**: Tasks organized by user story for independent verification.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files)
- **[Story]**: User story reference from spec.md
- Exact file paths and line numbers included

---

## Phase 1: Verification (Pre-Implementation Gate)

**Purpose**: Confirm Feature 077 is deployed before removing skips

- [ ] T001 Verify Feature 077 deployed - config endpoint returns 422 (not 500) for invalid input
- [ ] T002 Record baseline skip count: `pytest tests/e2e/ --collect-only 2>&1 | grep -c skip`

**Checkpoint**: Feature 077 deployed, baseline recorded

---

## Phase 2: User Story 1 - Remove 500 Skip Patterns (Priority: P1)

**Goal**: Remove all 18 config-related 500 skip patterns from E2E tests

**Independent Test**: `grep -r "500" tests/e2e/ | grep -i skip` returns empty (excluding magic link)

### Implementation for User Story 1

#### File: tests/e2e/test_config_crud.py (8 skips)

- [ ] T003 [US1] Remove skip at line 52-54 (comment + if block) in tests/e2e/test_config_crud.py
- [ ] T004 [US1] Remove skip at line 98 (if block) in tests/e2e/test_config_crud.py
- [ ] T005 [US1] Remove skip at line 141 (if block) in tests/e2e/test_config_crud.py
- [ ] T006 [US1] Remove skip at line 184 (if block) in tests/e2e/test_config_crud.py
- [ ] T007 [US1] Remove skip at line 239 (if block) in tests/e2e/test_config_crud.py
- [ ] T008 [US1] Remove skip at line 293 (if block) in tests/e2e/test_config_crud.py
- [ ] T009 [US1] Remove skip at line 381 (if block) in tests/e2e/test_config_crud.py
- [ ] T010 [US1] Remove skip at line 422 (if block - "Config lookup") in tests/e2e/test_config_crud.py

#### File: tests/e2e/test_anonymous_restrictions.py (5 skips)

- [ ] T011 [P] [US1] Remove skip at line 132 in tests/e2e/test_anonymous_restrictions.py
- [ ] T012 [P] [US1] Remove skip at line 181 in tests/e2e/test_anonymous_restrictions.py
- [ ] T013 [P] [US1] Remove skip at line 233 in tests/e2e/test_anonymous_restrictions.py
- [ ] T014 [P] [US1] Remove skip at line 296 in tests/e2e/test_anonymous_restrictions.py
- [ ] T015 [P] [US1] Remove skip at line 345 in tests/e2e/test_anonymous_restrictions.py

#### File: tests/e2e/test_auth_anonymous.py (2 skips)

- [ ] T016 [P] [US1] Remove skip at line 120-122 (comment + if block) in tests/e2e/test_auth_anonymous.py
- [ ] T017 [P] [US1] Remove skip at line 215 in tests/e2e/test_auth_anonymous.py

#### File: tests/e2e/test_alerts.py (1 skip)

- [ ] T018 [P] [US1] Remove skip at line 54 in tests/e2e/test_alerts.py

#### File: tests/e2e/test_sentiment.py (1 skip)

- [ ] T019 [P] [US1] Remove skip at line 444 in tests/e2e/test_sentiment.py

#### File: tests/e2e/test_failure_injection.py (1 skip)

- [ ] T020 [P] [US1] Remove skip at line 59 in tests/e2e/test_failure_injection.py

**Checkpoint**: All 18 config-related 500 skips removed

---

## Phase 3: User Story 2 - Verify Tests Pass (Priority: P2)

**Goal**: Confirm all unskipped tests pass against preprod with Feature 077

**Independent Test**: `pytest tests/e2e/ -k "config" -v` all pass

### Verification for User Story 2

- [ ] T021 [US2] Run E2E tests: `pytest tests/e2e/test_config_crud.py -v --tb=short`
- [ ] T022 [US2] Run E2E tests: `pytest tests/e2e/test_anonymous_restrictions.py -v --tb=short`
- [ ] T023 [US2] Run E2E tests: `pytest tests/e2e/test_auth_anonymous.py -v --tb=short`
- [ ] T024 [US2] Run E2E tests: `pytest tests/e2e/test_alerts.py -v --tb=short`
- [ ] T025 [US2] Run E2E tests: `pytest tests/e2e/test_sentiment.py -v --tb=short`
- [ ] T026 [US2] Run E2E tests: `pytest tests/e2e/test_failure_injection.py -v --tb=short`

**Checkpoint**: All modified tests pass

---

## Phase 4: User Story 3 - Update Documentation (Priority: P3)

**Goal**: Update tech debt document with closure summary

**Independent Test**: `grep "CLOSED" RESULT2-tech-debt.md` shows closure entry

### Documentation for User Story 3

- [ ] T027 [US3] Add "Closed Gaps Summary (Feature 078)" section to RESULT2-tech-debt.md
- [ ] T028 [US3] Update summary statistics table - decrement E2E skip count by 18

**Checkpoint**: Documentation updated

---

## Phase 5: Polish & Validation

**Purpose**: Final verification and commit

- [ ] T029 Verify SC-001: `grep -r "500" tests/e2e/ | grep -ic "config.*skip\|skip.*config"` returns 0
- [ ] T030 Verify SC-002: Compare baseline skip count to final count (should be -18)
- [ ] T031 Verify SC-004: No regression in other test areas
- [ ] T032 Commit changes with message referencing Feature 078

---

## Dependencies & Execution Order

### Phase Dependencies

- **Verification (Phase 1)**: No dependencies - GATE, must pass before continuing
- **Skip Removal (Phase 2)**: Depends on Phase 1 verification
- **Test Verification (Phase 3)**: Depends on Phase 2 completion
- **Documentation (Phase 4)**: Can run in parallel with Phase 3
- **Polish (Phase 5)**: Depends on Phases 3 and 4

### User Story Dependencies

- **US1** (Remove Skips): Blocked by Phase 1 verification
- **US2** (Verify Tests): Blocked by US1 completion
- **US3** (Documentation): Independent of US2

### Parallel Opportunities

Within Phase 2, files can be modified in parallel:
- test_config_crud.py (sequential edits within file)
- test_anonymous_restrictions.py [P]
- test_auth_anonymous.py [P]
- test_alerts.py [P]
- test_sentiment.py [P]
- test_failure_injection.py [P]

---

## Parallel Example: Phase 2 File Modifications

```bash
# These files can be modified in parallel (different files):
Task: "Remove skip at line 132 in tests/e2e/test_anonymous_restrictions.py"
Task: "Remove skip at line 120-122 in tests/e2e/test_auth_anonymous.py"
Task: "Remove skip at line 54 in tests/e2e/test_alerts.py"
Task: "Remove skip at line 444 in tests/e2e/test_sentiment.py"
Task: "Remove skip at line 59 in tests/e2e/test_failure_injection.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Verification
2. Complete Phase 2: Remove all 18 skip patterns
3. **STOP and VALIDATE**: Run `grep` to confirm no remaining 500 skips
4. If validation fails, investigate before proceeding

### Incremental Delivery

1. Verify Feature 077 deployed → GATE
2. Remove skips from test_config_crud.py (8 skips) → Verify file passes
3. Remove skips from remaining files (10 skips) → Verify all pass
4. Update documentation → Complete

### Risk Mitigation

- If any test fails after skip removal: Feature 077 may not be fully deployed
- Rollback: `git checkout tests/e2e/` to restore original files
- Escalation: If preprod returns 500, block this feature until 077 is deployed

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 32 |
| Phase 1 (Verification) | 2 tasks |
| Phase 2 (US1 - Remove Skips) | 18 tasks |
| Phase 3 (US2 - Verify Tests) | 6 tasks |
| Phase 4 (US3 - Documentation) | 2 tasks |
| Phase 5 (Polish) | 4 tasks |
| Parallel Opportunities | 5 files (T011-T020) |
| MVP Scope | Phase 1 + Phase 2 |

---

## Notes

- Line numbers are from research.md inventory (2025-12-10)
- Line numbers may shift as edits are made - work sequentially within each file
- Out of scope: test_rate_limiting.py:291 (magic link, not config)
- Commit after Phase 2 completion (all skips removed)
- Verify tests pass before merging PR

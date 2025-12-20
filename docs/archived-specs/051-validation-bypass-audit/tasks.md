# Tasks: Validation Bypass Audit

**Input**: Design documents from `/specs/051-validation-bypass-audit/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md

**Tests**: Not required - existing unit tests serve as validation

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Verify baseline state before making changes

- [ ] T001 Run baseline unit tests to confirm all 1600+ tests pass: `pytest tests/unit/ -v`
- [ ] T002 [P] Count current datetime.utcnow() deprecation warnings: `pytest 2>&1 | grep -c "utcnow"`
- [ ] T003 [P] Verify current pre-commit hook failure: `pre-commit run pytest --hook-stage push`

**Checkpoint**: Baseline metrics captured, ready for audit

---

## Phase 2: Foundational

**Purpose**: No foundational tasks needed - all changes are independent file edits

**Checkpoint**: Proceed directly to user story implementation

---

## Phase 3: User Story 1 - Comprehensive Bypass Inventory (Priority: P1)

**Goal**: Create structured audit report documenting all validation bypasses

**Independent Test**: Run grep commands and verify output matches expected counts from research.md

### Implementation for User Story 1

- [ ] T004 [US1] Create audit report document at docs/BYPASS_AUDIT_2025-12-06.md
- [ ] T005 [P] [US1] Document datetime.utcnow() instances (26 total) with file paths and line numbers
- [ ] T006 [P] [US1] Document pragma: allowlist instances (2 total) with file paths
- [ ] T007 [P] [US1] Document # noqa instances (10+) with rule codes and justifications
- [ ] T008 [P] [US1] Document # type: ignore instances (1) with justification
- [ ] T009 [P] [US1] Document pre-commit hook issue with root cause analysis
- [ ] T010 [US1] Generate summary statistics table in audit report

**Checkpoint**: Audit report complete with all bypass categories documented - SC-001 achieved

---

## Phase 4: User Story 2 - Classification and Risk Assessment (Priority: P2)

**Goal**: Classify each bypass as LEGITIMATE or TECH_DEBT with risk levels

**Independent Test**: Review audit report and verify each bypass has classification

### Implementation for User Story 2

- [ ] T011 [US2] Add Classification column to audit report for all bypasses
- [ ] T012 [P] [US2] Classify datetime.utcnow() as TECH_DEBT HIGH (26 instances)
- [ ] T013 [P] [US2] Classify pragma: allowlist as LEGITIMATE with justifications (2 instances)
- [ ] T014 [P] [US2] Classify # noqa as LEGITIMATE with rule-specific justifications (10+ instances)
- [ ] T015 [P] [US2] Classify # type: ignore as LEGITIMATE with justification (1 instance)
- [ ] T016 [P] [US2] Classify pre-commit hook as TECH_DEBT HIGH
- [ ] T017 [US2] Add Remediation Guidance column for all TECH_DEBT items

**Checkpoint**: All bypasses classified with risk levels and remediation guidance

---

## Phase 5: User Story 3 - Remediation Execution (Priority: P3)

**Goal**: Fix all TECH_DEBT items so git push succeeds without SKIP=

**Independent Test**: After remediation, `git push` succeeds without SKIP= and pytest shows 0 deprecation warnings

### Implementation for User Story 3 - datetime.utcnow() Remediation

- [ ] T018 [US3] Fix datetime.utcnow() in src/lambdas/dashboard/chaos.py (9 instances, lines 137,138,287,590,599,620,664,671,689)
- [ ] T019 [P] [US3] Fix datetime.utcnow() in src/lambdas/shared/adapters/tiingo.py (2 instances, lines 174,267)
- [ ] T020 [P] [US3] Fix datetime.utcnow() in src/lambdas/shared/adapters/finnhub.py (3 instances, lines 176,282,312)
- [ ] T021 [P] [US3] Fix datetime.utcnow() in src/lambdas/shared/cache/ticker_cache.py (2 instances, lines 124,128)
- [ ] T022 [P] [US3] Fix datetime.utcnow() in src/lambdas/shared/circuit_breaker.py (3 instances, lines 118,126,157)
- [ ] T023 [P] [US3] Fix datetime.utcnow() in src/lambdas/shared/volatility.py (1 instance, line 192)
- [ ] T024 [US3] Find and fix remaining datetime.utcnow() instances (6 others) using grep

### Implementation for User Story 3 - Pre-commit Hook Fix

- [ ] T025 [US3] Fix pytest hook in .pre-commit-config.yaml (change language: system to language: python)

### Implementation for User Story 3 - Legitimate Bypass Documentation

- [ ] T026 [P] [US3] Verify pragma: allowlist comments have inline justifications in .github/workflows/deploy.yml
- [ ] T027 [P] [US3] Verify pragma: allowlist comments have inline justifications in .github/workflows/pr-checks.yml
- [ ] T028 [US3] Ensure all # noqa comments have inline rule explanations (add if missing)

**Checkpoint**: All TECH_DEBT items remediated, LEGITIMATE items documented - SC-002, SC-003, SC-004 achieved

---

## Phase 6: Polish & Verification

**Purpose**: Final validation and documentation

- [ ] T029 Run full unit test suite to verify no regressions: `pytest tests/unit/ -v`
- [ ] T030 [P] Verify 0 datetime.utcnow() deprecation warnings: `pytest 2>&1 | grep -c "utcnow"`
- [ ] T031 [P] Verify pre-commit hooks pass: `pre-commit run --all-files`
- [ ] T032 [P] Verify git push succeeds without SKIP=: `git push origin 051-validation-bypass-audit`
- [ ] T033 Update docs/TECH_DEBT_REGISTRY.md with audit results and remediation status
- [ ] T034 Mark audit report as COMPLETE in docs/BYPASS_AUDIT_2025-12-06.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - baseline capture
- **Foundational (Phase 2)**: Skipped
- **User Story 1 (Phase 3)**: Depends on Phase 1 baseline
- **User Story 2 (Phase 4)**: Depends on US1 audit report
- **User Story 3 (Phase 5)**: Depends on US2 classifications
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - core audit
- **User Story 2 (P2)**: Depends on US1 (needs audit data to classify)
- **User Story 3 (P3)**: Depends on US2 (needs classifications to know what to fix)

### Within Each User Story

- US1: T004 creates report → T005-T009 populate sections (parallel) → T010 summarizes
- US2: T011 adds column → T012-T016 classify (parallel) → T017 adds guidance
- US3: T018-T024 fix datetime (parallel) → T025 fix hook → T026-T28 document legitimate (parallel)

### Parallel Opportunities

- T002, T003 (Phase 1): Independent baseline checks
- T005-T009 (US1): All document different bypass categories
- T012-T016 (US2): All classify different categories
- T019-T023 (US3): All fix datetime in different files
- T026, T027 (US3): Different workflow files
- T029-T032 (Phase 6): Independent verification tasks

---

## Parallel Example: User Story 3 datetime.utcnow() Fixes

```bash
# Launch all datetime fix tasks in parallel (different files):
Task: "Fix datetime.utcnow() in src/lambdas/shared/adapters/tiingo.py"
Task: "Fix datetime.utcnow() in src/lambdas/shared/adapters/finnhub.py"
Task: "Fix datetime.utcnow() in src/lambdas/shared/cache/ticker_cache.py"
Task: "Fix datetime.utcnow() in src/lambdas/shared/circuit_breaker.py"
Task: "Fix datetime.utcnow() in src/lambdas/shared/volatility.py"
```

---

## Implementation Strategy

### MVP First (User Story 3 Only)

For immediate value, jump directly to US3 remediation:
1. Skip US1/US2 (research.md already contains the audit)
2. Execute T018-T025 (datetime + hook fixes)
3. **STOP and VALIDATE**: Run tests, push without SKIP=
4. Can ship with just the fixes, add documentation later

### Full Implementation Order

1. **US1 (Audit)**: Document all bypasses (T004-T010)
2. **US2 (Classify)**: Add classifications (T011-T017)
3. **US3 (Remediate)**: Fix tech debt (T018-T028)
4. **Polish**: Verify and finalize (T029-T034)

### Single Developer Strategy

Since datetime fixes are all in different files, execute in parallel:
1. Open all 6 files with datetime.utcnow()
2. Add `from datetime import UTC` to imports
3. Replace `datetime.utcnow()` with `datetime.now(UTC)` in each
4. Fix pre-commit hook config
5. Run tests to verify
6. Single commit with all fixes

---

## Notes

- US1 and US2 can be skipped if research.md is considered sufficient documentation
- datetime.utcnow() fixes are mechanical - can be done in bulk
- Pre-commit hook fix is single line change
- All LEGITIMATE bypasses already have inline justifications - minimal documentation work
- Total estimated time: 1-2 hours for full implementation

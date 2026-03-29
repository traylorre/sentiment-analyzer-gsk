# Tasks: Validation Finding Remediation

**Input**: Design documents from `/specs/049-validate-remediation/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Unit tests are included for validator changes (template repo has existing test patterns)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Two repositories involved:

- **Template repo**: `terraform-gsk-template/` - validators in `src/validators/`, tests in `tests/unit/`
- **Target repo**: `sentiment-analyzer-gsk/` - property tests in `tests/property/`

---

## Phase 1: Setup

**Purpose**: Sync branches and verify current state

- [x] T001 Sync template repo branch 049-validate-remediation with latest main
- [x] T002 Run `/validate --repo /path/to/sentiment-analyzer-gsk` to capture baseline findings

---

## Phase 2: Foundational

**Purpose**: No blocking foundational work required - all changes are independent

**Checkpoint**: Proceed directly to user stories

---

## Phase 3: User Story 1 - Fix Property Test Import Errors (Priority: P1) MVP

**Goal**: Fix pytest conftest import pattern so all 33 property tests pass

**Independent Test**: Run `pytest tests/property/ -v` in sentiment-analyzer-gsk

### Implementation for User Story 1

- [x] T003 [P] [US1] Fix import in `sentiment-analyzer-gsk/tests/property/test_lambda_handlers.py` - change `from conftest import` to `from .conftest import`
- [x] T004 [P] [US1] Fix import in `sentiment-analyzer-gsk/tests/property/test_api_contracts.py` - change `from conftest import` to `from .conftest import`
- [x] T005 [P] [US1] Fix import in `sentiment-analyzer-gsk/tests/property/test_infrastructure.py` - change `from conftest import` to `from .conftest import`
- [x] T006 [US1] Verify all 33 property tests pass with `pytest tests/property/ -v`
- [x] T007 [US1] Commit changes to sentiment-analyzer-gsk with message `fix(tests): Use relative import for conftest in property tests`

**Checkpoint**: Property tests should now pass (SC-001: 33/33)

---

## Phase 4: User Story 2 - Suppress SQS-009 for CI User Policy (Priority: P2)

**Goal**: Enhance allowlist to support CI policy detection for SQS-009 suppression

**Independent Test**: Run `/sqs-iam-validate --repo /path/to/sentiment-analyzer-gsk` and verify SQS-009 for ci-user-policy.tf is SUPPRESSED

### Tests for User Story 2

- [x] T008 [P] [US2] Add unit test for `is_ci_policy()` function in `tests/unit/test_iam_allowlist.py`
- [x] T009 [P] [US2] Add unit test for ci_policy context condition in `tests/unit/test_iam_allowlist.py`

### Implementation for User Story 2

- [x] T010 [US2] Add `is_ci_policy()` function to `src/validators/iam_allowlist.py` - detect CI policy file patterns like `ci-user-policy.tf`, `ci_user_policy.tf`, `ci-policy`
- [x] T011 [US2] Extend `evaluate_context_conditions()` in `src/validators/iam_allowlist.py` to handle `ci_policy: true` context condition
- [x] T012 [US2] Update allowlist entry in `sentiment-analyzer-gsk/iam-allowlist.yaml` - add `ci_policy: true` to `dev-preprod-sqs-delete` entry as alternative to environment
- [x] T013 [US2] Run `/sqs-iam-validate --repo /path/to/sentiment-analyzer-gsk` and verify SQS-009 is suppressed
- [x] T014 [US2] Commit template repo changes with message `feat(allowlist): Add ci_policy context condition for SQS-009`
- [x] T015 [US2] Commit target repo changes with message `fix(allowlist): Add ci_policy context for sqs:DeleteQueue suppression`

**Checkpoint**: SQS-009 for ci-user-policy.tf should be suppressed (SC-004)

---

## Phase 5: User Story 3 - Eliminate False Positive for Deny Statement Wildcards (Priority: P2)

**Goal**: Skip IAM-006 findings for Deny statements with wildcard actions

**Independent Test**: Run `/iam-validate --repo /path/to/sentiment-analyzer-gsk` and verify no IAM-006 findings for DenyInsecureTransport statements

### Tests for User Story 3

- [x] T016 [P] [US3] Add unit test for Deny statement detection in `tests/unit/test_iam_validator.py` - verify `sqs:*` in Deny statement is NOT flagged
- [x] T017 [P] [US3] Add unit test for Allow statement detection in `tests/unit/test_iam_validator.py` - verify `sqs:*` in Allow statement IS flagged

### Implementation for User Story 3

- [x] T018 [US3] Add `_is_deny_statement_context()` helper method to `src/validators/iam.py` - detect if line is within Effect: Deny context
- [x] T019 [US3] Modify `_check_file()` in `src/validators/iam.py` - skip IAM-006 for lines in Deny statement context
- [x] T020 [US3] Run `/iam-validate --repo /path/to/sentiment-analyzer-gsk` and verify no IAM-006 findings
- [x] T021 [US3] Commit changes with message `fix(iam): Skip IAM-006 wildcard check for Deny statements`

**Checkpoint**: IAM-006 false positives for Deny statements should be eliminated (SC-003)

---

## Phase 6: Polish & Verification

**Purpose**: Final validation and documentation

- [x] T022 Run full `/validate --repo /path/to/sentiment-analyzer-gsk` and verify 0 HIGH severity unsuppressed findings (SC-002)
  - Note: PROP-001 shows FAIL due to missing `make test-property` target in target repo (Makefile issue)
  - Property tests pass 33/33 when run directly with pytest
  - All SQS-009 findings correctly SUPPRESSED
  - All IAM-006 Deny statement false positives eliminated
- [x] T023 Update spec.md status from Draft to Complete
- [x] T024 [P] Run `make validate` in template repo to ensure no regressions
- [x] T025 Push all changes and create PR for template repo (PR #33)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: N/A - no blocking prerequisites
- **User Stories (Phase 3+)**: All independent - can proceed in any order after Setup
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Independent - changes only target repo property tests
- **User Story 2 (P2)**: Independent - changes template validator and target allowlist
- **User Story 3 (P2)**: Independent - changes only template validator

### Within Each User Story

- Tests written first (T008-T009, T016-T017)
- Implementation follows tests
- Verification at end of each story

### Parallel Opportunities

**US1 Implementation** (different files):

```bash
T003: Fix test_lambda_handlers.py
T004: Fix test_api_contracts.py
T005: Fix test_infrastructure.py
```

**US2 Tests** (different test files):

```bash
T008: Test is_ci_policy()
T009: Test ci_policy context
```

**US3 Tests** (different test scenarios):

```bash
T016: Test Deny statement NOT flagged
T017: Test Allow statement IS flagged
```

**Cross-Story Parallelism**:

- US1 (target repo) can run in parallel with US2/US3 (template repo)
- US2 and US3 touch different template files and can run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**: Verify 33/33 property tests pass
4. Commit and push target repo changes

### Full Remediation

1. Complete Setup
2. Complete US1 → Verify property tests pass
3. Complete US2 → Verify SQS-009 suppressed
4. Complete US3 → Verify IAM-006 eliminated
5. Complete Polish → Verify 0 HIGH findings
6. Push and PR both repos

---

## Notes

- US1 changes are in target repo (sentiment-analyzer-gsk)
- US2 and US3 changes are primarily in template repo (terraform-gsk-template)
- US2 also requires allowlist update in target repo
- Commit after each user story for clear rollback points
- Run full `/validate` after Phase 6 to confirm SC-002

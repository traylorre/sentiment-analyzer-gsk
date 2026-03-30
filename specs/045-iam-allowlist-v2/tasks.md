# Tasks: IAM Allowlist V2 - VALIDATE2 Remediation

**Input**: Design documents from `/specs/045-iam-allowlist-v2/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Unit tests requested for new module and integration.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/validators/`, `tests/unit/` at repository root
- Target repo updates in `../sentiment-analyzer-gsk/`

---

## Phase 1: Setup (Foundation)

**Purpose**: Add SUPPRESSED status and create allowlist loader infrastructure

- [ ] T001 Add SUPPRESSED status to Status enum in src/validators/models.py
- [ ] T002 [P] Create IAMAllowlistEntry dataclass in src/validators/iam_allowlist.py
- [ ] T003 [P] Create IAMAllowlist container class in src/validators/iam_allowlist.py
- [ ] T004 Implement load_iam_allowlist() function in src/validators/iam_allowlist.py
- [ ] T005 [P] Add suppressed_by field to Finding dataclass in src/validators/models.py

---

## Phase 2: Foundational (Context Evaluation)

**Purpose**: Context derivation and matching logic that all validators will use

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Implement derive_environment() from file path in src/validators/iam_allowlist.py
- [ ] T007 [P] Implement check_passrole_scoped() from policy content in src/validators/iam_allowlist.py
- [ ] T008 Implement evaluate_context_conditions() in src/validators/iam_allowlist.py
- [ ] T009 Implement select_best_match() per FR-008 (most specific wins) in src/validators/iam_allowlist.py
- [ ] T010 Implement should_suppress() main API in src/validators/iam_allowlist.py
- [ ] T011 [P] Create unit tests for allowlist loader in tests/unit/test_iam_allowlist.py

**Checkpoint**: Foundation ready - validator integration can now begin

---

## Phase 3: User Story 1 - Validator Respects Allowlist (Priority: P1) 🎯 MVP

**Goal**: Lambda-iam validator consumes allowlist and suppresses documented LAMBDA-007/LAMBDA-011 findings

**Independent Test**: Run `python3 scripts/validate-runner.py --repo ../sentiment-analyzer-gsk` and verify LAMBDA-007/011 are SUPPRESSED not FAIL

### Tests for User Story 1

- [ ] T012 [P] [US1] Unit test for lambda_iam with allowlist suppression in tests/unit/test_lambda_iam_allowlist.py
- [ ] T013 [P] [US1] Unit test for suppression requires canonical_source in tests/unit/test_lambda_iam_allowlist.py

### Implementation for User Story 1

- [ ] T014 [US1] Import iam_allowlist module in src/validators/lambda_iam.py
- [ ] T015 [US1] Load allowlist in LambdaIAMValidator.**init**() in src/validators/lambda_iam.py
- [ ] T016 [US1] Add should_suppress check before adding finding in src/validators/lambda_iam.py validate()
- [ ] T017 [US1] Set status=SUPPRESSED and suppressed_by field for matched findings in src/validators/lambda_iam.py
- [ ] T018 [US1] Add logging for suppressions in src/validators/lambda_iam.py
- [ ] T019 [US1] Run validation and verify LAMBDA-007/011 CRITICAL count reduced to 0

**Checkpoint**: User Story 1 complete - 5 CRITICAL → 0 CRITICAL

---

## Phase 4: User Story 2 - Environment-Aware SQS Suppression (Priority: P2)

**Goal**: SQS-009 suppressed for dev/preprod but NOT prod

**Independent Test**: Run validator and verify SQS-009 suppressed for dev-deployer-policy.json but NOT prod-deployer-policy.json

### Tests for User Story 2

- [ ] T020 [P] [US2] Unit test for sqs_iam with environment context in tests/unit/test_sqs_iam_allowlist.py
- [ ] T021 [P] [US2] Unit test for prod files NOT suppressed in tests/unit/test_sqs_iam_allowlist.py

### Implementation for User Story 2

- [ ] T022 [US2] Import iam_allowlist module in src/validators/sqs_iam.py
- [ ] T023 [US2] Load allowlist in SQSIAMValidator.**init**() in src/validators/sqs_iam.py
- [ ] T024 [US2] Add should_suppress check with environment context in src/validators/sqs_iam.py validate()
- [ ] T025 [US2] Update target repo iam-allowlist.yaml to cover dev environment for SQS-009
- [ ] T026 [US2] Run validation and verify SQS-009 HIGH count reduced

**Checkpoint**: User Story 2 complete - SQS-009 suppressed for dev/preprod

---

## Phase 5: User Story 3 - Canonical Source Validation (Priority: P3)

**Goal**: Ensure CAN-002 is addressed via PR template guidance

**Independent Test**: Create PR with '## Canonical Sources Cited' section and verify CAN-002 not raised

### Implementation for User Story 3

- [ ] T027 [US3] Review canonical-validate behavior in src/validators/canonical.py
- [ ] T028 [US3] Document PR template requirement for '## Canonical Sources Cited' in README or docs
- [ ] T029 [US3] Create PR with proper canonical sources section and verify CAN-002 resolution

**Checkpoint**: User Story 3 complete - CAN-002 addressed

---

## Phase 6: Polish & Validation

**Purpose**: Final validation and documentation

- [ ] T030 Run full validation: python3 scripts/validate-runner.py --repo ../sentiment-analyzer-gsk
- [ ] T031 Save validation output as VALIDATE3.md in ../sentiment-analyzer-gsk/
- [ ] T032 [P] Verify SC-001: 0 CRITICAL findings
- [ ] T033 [P] Verify SC-002: ≤2 HIGH findings
- [ ] T034 [P] Verify SC-003: All suppressed findings include suppressed_by entry ID
- [ ] T035 Commit changes to template repo with canonical sources in commit message
- [ ] T036 Push and create PR with '## Canonical Sources Cited' section

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 and US2 can proceed in parallel (different validators)
  - US3 is documentation-focused, can proceed after US1/US2
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Phase 2 - No dependencies on US1
- **User Story 3 (P3)**: Can start after Phase 2 - No dependencies on US1/US2

### Within Each User Story

- Tests written first (TDD where applicable)
- Core implementation before integration
- Validation checkpoint before moving to next story

### Parallel Opportunities

- T002, T003, T005 can run in parallel (different classes/fields)
- T006, T007 can run in parallel (different context functions)
- T011 can run in parallel with T010 (tests vs implementation)
- T012, T013 can run in parallel (different test cases)
- T020, T021 can run in parallel (different test cases)
- T032, T033, T034 can run in parallel (different verifications)
- **US1 and US2 can run in parallel** after Phase 2 (different validators)

---

## Parallel Example: User Story 1 & 2

```bash
# After Phase 2 completes, launch both user stories in parallel:

# US1 Stream:
Task: "Unit test for lambda_iam with allowlist suppression"
Task: "Import iam_allowlist module in src/validators/lambda_iam.py"
Task: "Load allowlist in LambdaIAMValidator.__init__()"
...

# US2 Stream (parallel):
Task: "Unit test for sqs_iam with environment context"
Task: "Import iam_allowlist module in src/validators/sqs_iam.py"
Task: "Load allowlist in SQSIAMValidator.__init__()"
...
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T011)
3. Complete Phase 3: User Story 1 (T012-T019)
4. **STOP and VALIDATE**: Run validation, verify 0 CRITICAL
5. If acceptable, proceed to US2/US3 or ship MVP

### Incremental Delivery

1. Setup + Foundational → Allowlist infrastructure ready
2. Add User Story 1 → CRITICAL findings eliminated
3. Add User Story 2 → HIGH findings reduced
4. Add User Story 3 → Documentation complete
5. Each story adds value without breaking previous stories

### Success Metrics

| Story | Before     | After      | Metric        |
| ----- | ---------- | ---------- | ------------- |
| US1   | 5 CRITICAL | 0 CRITICAL | SC-001        |
| US2   | 5 HIGH     | ≤2 HIGH    | SC-002        |
| US3   | CAN-002    | Addressed  | Documentation |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Run validation at each checkpoint to measure progress
- Target repo changes (iam-allowlist.yaml update) in US2
- Commit after each task or logical group

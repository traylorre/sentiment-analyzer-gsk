# Tasks: Close Validation Gaps - Resource Naming Validators & JWT Auth

**Input**: Design documents from `/specs/075-validation-gaps/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Test tasks are included per spec SC-001 and SC-002 requirements.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in all descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Validators: `src/validators/`
- Auth middleware: `src/lambdas/shared/middleware/`
- Tests: `tests/unit/`

---

## Phase 1: Setup

**Purpose**: Dependencies and shared infrastructure

- [X] T001 Add python-hcl2 to requirements-dev.txt for Terraform parsing
- [X] T002 [P] Add PyJWT to requirements.txt for JWT validation
- [X] T003 [P] Create src/validators/ directory with __init__.py
- [X] T004 [P] Create tests/unit/validators/ directory with __init__.py
- [X] T005 [P] Create tests/fixtures/terraform/ directory for test Terraform files

**Checkpoint**: ✅ Dependencies installed, directory structure ready

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared entities and utilities that multiple user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create TerraformResource dataclass in src/validators/resource_naming.py
- [X] T007 [P] Create ValidationStatus enum and ValidationResult dataclass in src/validators/resource_naming.py
- [X] T008 [P] Create IAMPattern dataclass in src/validators/iam_coverage.py
- [X] T009 [P] Create CoverageReport dataclass in src/validators/iam_coverage.py
- [X] T010 [P] Create JWTClaim and JWTConfig dataclasses in src/lambdas/shared/middleware/auth_middleware.py
- [X] T011 Create test fixtures: valid Terraform file in tests/fixtures/terraform/valid_naming.tf
- [X] T012 [P] Create test fixtures: invalid Terraform file in tests/fixtures/terraform/invalid_naming.tf
- [X] T013 [P] Create test fixtures: legacy naming file in tests/fixtures/terraform/legacy_naming.tf

**Checkpoint**: ✅ Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Resource Naming Consistency Validation (Priority: P1) 🎯 MVP

**Goal**: Automated validation that all Terraform resources follow `{env}-sentiment-{service}` naming pattern

**Independent Test**: Run `pytest tests/unit/validators/test_resource_name_pattern.py -v` and verify all 4 tests pass

### Tests for User Story 1

- [X] T014 [P] [US1] Create test_all_lambda_names_valid in tests/unit/validators/test_resource_naming.py
- [X] T015 [P] [US1] Create test_all_dynamodb_names_valid in tests/unit/validators/test_resource_naming.py
- [X] T016 [P] [US1] Create test_all_sqs_names_valid in tests/unit/validators/test_resource_naming.py
- [X] T017 [P] [US1] Create test_all_sns_names_valid in tests/unit/validators/test_resource_naming.py
- [X] T018 [P] [US1] Create test_legacy_naming_rejected in tests/unit/validators/test_resource_naming.py
- [X] T019 [P] [US1] Create test_missing_sentiment_segment_rejected in tests/unit/validators/test_resource_naming.py

### Implementation for User Story 1

- [X] T020 [US1] Implement extract_resources() function in src/validators/resource_naming.py using python-hcl2
- [X] T021 [US1] Implement validate_naming_pattern() function in src/validators/resource_naming.py
- [X] T022 [US1] Implement validate_all_resources() function in src/validators/resource_naming.py
- [X] T023 [US1] Add NAMING_PATTERN regex constant `^(preprod|prod)-sentiment-[a-z0-9-]+$` in src/validators/resource_naming.py
- [X] T024 [US1] Add LEGACY_PATTERN regex constant `^sentiment-analyzer-.*$` in src/validators/resource_naming.py
- [X] T025 [US1] Run pytest tests/unit/validators/test_resource_naming.py and verify all tests pass (32 passed)

**Checkpoint**: ✅ User Story 1 complete - Resource naming validation works independently

---

## Phase 4: User Story 2 - IAM Pattern Coverage Validation (Priority: P1)

**Goal**: Automated validation that every Terraform resource has corresponding IAM ARN pattern coverage

**Independent Test**: Run `pytest tests/unit/validators/test_iam_pattern_coverage.py -v` and verify all 2 tests pass

### Tests for User Story 2

- [X] T026 [P] [US2] Create test_all_resources_covered_by_iam in tests/unit/validators/test_iam_coverage.py
- [X] T027 [P] [US2] Create test_no_orphaned_iam_patterns in tests/unit/validators/test_iam_coverage.py
- [X] T028 [P] [US2] Create test_wildcard_patterns_flagged in tests/unit/validators/test_iam_coverage.py

### Implementation for User Story 2

- [X] T029 [US2] Implement extract_iam_patterns() function in src/validators/iam_coverage.py
- [X] T030 [US2] Implement check_coverage() function in src/validators/iam_coverage.py
- [X] T031 [US2] Implement _arn_pattern_matches() helper function in src/validators/iam_coverage.py
- [X] T032 [US2] Add exemption handling for iam-allowlist.yaml patterns in src/validators/iam_coverage.py
- [X] T033 [US2] Run pytest tests/unit/validators/test_iam_coverage.py and verify all tests pass (11 passed)

**Checkpoint**: ✅ User Story 2 complete - IAM coverage validation works independently

---

## Phase 5: User Story 3 - JWT Authentication for Authenticated Sessions (Priority: P2)

**Goal**: JWT token validation in auth middleware for authenticated sessions

**Independent Test**: Run `pytest tests/unit/middleware/test_jwt_validation.py -v` and verify all tests pass

### Tests for User Story 3

- [X] T034 [P] [US3] Create test_valid_jwt_token in tests/unit/middleware/test_jwt_validation.py
- [X] T035 [P] [US3] Create test_expired_jwt_token in tests/unit/middleware/test_jwt_validation.py
- [X] T036 [P] [US3] Create test_malformed_jwt_token in tests/unit/middleware/test_jwt_validation.py
- [X] T037 [P] [US3] Create test_invalid_signature in tests/unit/middleware/test_jwt_validation.py
- [X] T038 [P] [US3] Create test_missing_required_claims in tests/unit/middleware/test_jwt_validation.py
- [X] T039 [P] [US3] Create test_jwt_performance_benchmark in tests/unit/middleware/test_jwt_validation.py (1000 validations <1s)
- [X] T040 [P] [US3] Create test_missing_jwt_secret_fails_fast in tests/unit/middleware/test_jwt_validation.py

### Implementation for User Story 3

- [X] T041 [US3] Implement validate_jwt() function in src/lambdas/shared/middleware/auth_middleware.py
- [X] T042 [US3] Implement _get_jwt_config() helper to load JWT_SECRET from environment in src/lambdas/shared/middleware/auth_middleware.py
- [X] T043 [US3] Update _extract_user_id_from_token() to call validate_jwt() for non-UUID tokens in src/lambdas/shared/middleware/auth_middleware.py
- [X] T044 [US3] Add JWT-specific logging (expired, malformed, invalid signature) in src/lambdas/shared/middleware/auth_middleware.py
- [X] T045 [US3] Remove TODO comment at line 75 in src/lambdas/shared/middleware/auth_middleware.py
- [X] T046 [US3] Run pytest tests/unit/middleware/test_jwt_validation.py and verify all tests pass (21 passed)

**Checkpoint**: ✅ User Story 3 complete - JWT authentication works independently

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T047 Run full test suite: pytest tests/unit/validators/ tests/unit/middleware/test_jwt_validation.py -v (64 passed)
- [X] T048 Verify SC-001: All 32 resource naming tests pass (not skipped)
- [X] T049 [P] Verify SC-002: Coverage report shows 100% for JWT validation path (21 tests)
- [X] T050 [P] Verify SC-003: grep for nosec/noqa/type:ignore shows no additions
- [X] T051 [P] Verify SC-005: Test misnamed fixtures are detected (test_invalid_naming_detected passes)
- [ ] T052 Run make validate and verify zero failures
- [X] T053 Update RESULT1-validation-gaps.md to mark closed gaps as complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 and US2 can proceed in parallel (different files)
  - US3 can proceed in parallel with US1/US2 (different module)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies on other stories - Resource naming validator
- **User Story 2 (P1)**: Depends on US1 TerraformResource entity - IAM coverage validator
- **User Story 3 (P2)**: No dependencies on US1/US2 - JWT authentication (different module)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Dataclasses/entities before functions
- Core functions before helper functions
- Implementation before integration
- Run test verification at checkpoint

### Parallel Opportunities

- **Phase 1**: T002, T003, T004, T005 can run in parallel
- **Phase 2**: T007-T013 can run in parallel
- **Phase 3 (US1)**: All test tasks T014-T019 can run in parallel
- **Phase 4 (US2)**: All test tasks T026-T028 can run in parallel
- **Phase 5 (US3)**: All test tasks T034-T040 can run in parallel
- **Cross-Story**: US1, US2, and US3 can be developed in parallel after Foundational

---

## Parallel Example: Launch All Tests for US1

```bash
# Launch all tests for User Story 1 together:
Task: T014 "Create test_all_lambda_names_valid in tests/unit/validators/test_resource_name_pattern.py"
Task: T015 "Create test_all_dynamodb_names_valid in tests/unit/validators/test_resource_name_pattern.py"
Task: T016 "Create test_all_sqs_names_valid in tests/unit/validators/test_resource_name_pattern.py"
Task: T017 "Create test_all_sns_names_valid in tests/unit/validators/test_resource_name_pattern.py"
Task: T018 "Create test_legacy_naming_rejected in tests/unit/validators/test_resource_name_pattern.py"
Task: T019 "Create test_missing_sentiment_segment_rejected in tests/unit/validators/test_resource_name_pattern.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Resource Naming)
4. **STOP and VALIDATE**: Run pytest for US1 tests
5. Deploy - 4 of 6 validation gaps closed

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → 4 tests pass → Partial gap closure
3. Add User Story 2 → 6 tests pass → All resource naming gaps closed
4. Add User Story 3 → JWT TODO removed → All 7 gaps closed
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Resource Naming)
   - Developer B: User Story 2 (IAM Coverage)
   - Developer C: User Story 3 (JWT Auth)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests written first, verify they fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- SC-006 (performance benchmark) tested in T039

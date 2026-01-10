# Tasks: Get User by Provider Sub Helper

**Input**: Design documents from `/specs/1180-get-user-by-provider-sub/`
**Prerequisites**: plan.md (required), spec.md (required), research.md

**Tests**: Unit tests with moto for GSI queries.

**Organization**: Infrastructure first, then code, then tests.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Infrastructure (Terraform)

**Purpose**: Add the by_provider_sub GSI to DynamoDB

- [ ] T001 [US3] Add `provider_sub` attribute definition in `infrastructure/terraform/modules/dynamodb/main.tf`
- [ ] T002 [US3] Add `by_provider_sub` GSI block in `infrastructure/terraform/modules/dynamodb/main.tf`
- [ ] T003 Run `terraform fmt` and `terraform validate`

**Note**: GSI creation may take time. Code changes can proceed in parallel since they use moto for testing.

---

## Phase 2: Code Implementation

**Purpose**: Implement the lookup function and update _link_provider()

- [ ] T004 [P] [US1] Add `get_user_by_provider_sub()` function in `src/lambdas/dashboard/auth.py`
- [ ] T005 [P] [US1] Update `_link_provider()` to set `provider_sub` attribute in `src/lambdas/dashboard/auth.py`

---

## Phase 3: Unit Tests

**Purpose**: Verify function works correctly with moto

- [ ] T006 [P] [US1] Add `test_get_user_by_provider_sub_found` in `tests/unit/dashboard/test_auth_provider_sub.py`
- [ ] T007 [P] [US1] Add `test_get_user_by_provider_sub_not_found` in `tests/unit/dashboard/test_auth_provider_sub.py`
- [ ] T008 [P] [US2] Add `test_get_user_by_provider_sub_different_provider` in `tests/unit/dashboard/test_auth_provider_sub.py`
- [ ] T009 [P] [US1] Add `test_get_user_by_provider_sub_empty_inputs` in `tests/unit/dashboard/test_auth_provider_sub.py`
- [ ] T010 [P] [US1] Add `test_link_provider_populates_provider_sub` in `tests/unit/dashboard/test_auth_provider_sub.py`

---

## Phase 4: Verification

**Purpose**: Run tests and verify implementation

- [ ] T011 Run ruff check and format
- [ ] T012 Run unit tests for new file
- [ ] T013 Run full auth test suite to check for regressions

---

## Phase 5: Commit & PR

- [ ] T014 Commit changes with descriptive message
- [ ] T015 Push branch and create PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Infrastructure)**: No dependencies
- **Phase 2 (Code)**: Can proceed in parallel with Phase 1 (tests use moto)
- **Phase 3 (Tests)**: Depends on Phase 2
- **Phase 4 (Verification)**: Depends on Phase 2 and Phase 3
- **Phase 5 (PR)**: Depends on Phase 4

### Parallel Opportunities

- T001 and T002 must be sequential (same file)
- T004 and T005 can be done together (same file, different functions)
- T006-T010 can all run in parallel (different test functions)

---

## Implementation Strategy

### Single Developer Path

1. Complete Phase 1: Add GSI to Terraform
2. Complete Phase 2: Add function and update _link_provider()
3. Complete Phase 3: Write unit tests
4. Complete Phase 4: Run verification
5. Complete Phase 5: Commit and PR

### Time Estimate

- Total tasks: 15
- Estimated time: 45-60 minutes

---

## Notes

- GSI uses KEYS_ONLY projection - function does get_item after query
- Composite key format: `{provider}:{sub}`
- Moto supports GSI queries for unit testing
- Existing users without provider_sub will return None (graceful degradation)

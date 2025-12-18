# Tasks: Fix Lambda ZIP Packaging Structure

**Input**: Design documents from `/specs/427-fix-lambda-zip-packaging/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: No explicit test tasks requested. Validation via E2E Lambda invocation and docker-import validator.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Primary file**: `.github/workflows/deploy.yml`
- **Validation**: Docker-import validator in terraform-gsk-template

---

## Phase 1: Setup (Verification)

**Purpose**: Verify current state and understand the problem scope

- [ ] T001 Read current ingestion Lambda packaging in .github/workflows/deploy.yml lines 154-166
- [ ] T002 Read dashboard Lambda packaging pattern (correct reference) in .github/workflows/deploy.yml lines 219-228
- [ ] T003 Identify all Lambdas with flat-copy patterns by scanning deploy.yml for `cp -r src/lambdas/*/\* packages/`

---

## Phase 2: User Story 1 - Deploy Ingestion Lambda Successfully (Priority: P1) MVP

**Goal**: Fix the ingestion Lambda packaging so it deploys without ImportModuleError

**Independent Test**: Invoke `aws lambda invoke --function-name preprod-sentiment-ingestion` and verify no import errors

### Implementation for User Story 1

- [ ] T004 [US1] Update mkdir command to create `packages/ingestion-build/src/lambdas/ingestion` in .github/workflows/deploy.yml line ~155
- [ ] T005 [US1] Change ingestion cp command from flat copy to structured copy: `cp -r src/lambdas/ingestion/* packages/ingestion-build/src/lambdas/ingestion/` in .github/workflows/deploy.yml line ~157
- [ ] T006 [US1] Verify src/lambdas/shared copy path is `packages/ingestion-build/src/lambdas/` in .github/workflows/deploy.yml line ~158
- [ ] T007 [US1] Verify src/lib copy path is `packages/ingestion-build/src/lib/` in .github/workflows/deploy.yml line ~159

**Checkpoint**: Ingestion Lambda packaging matches dashboard pattern. Ready for US2.

---

## Phase 3: User Story 2 - Consistent Packaging Across All Lambdas (Priority: P2)

**Goal**: Fix all remaining ZIP-based Lambdas (analysis, metrics, notification) to use the correct pattern

**Independent Test**: Run docker-import validator and expect 0 LPK-003 findings

### Implementation for User Story 2

#### Analysis Lambda

- [ ] T008 [P] [US2] Update mkdir command to create `packages/analysis-build/src/lambdas/analysis` in .github/workflows/deploy.yml
- [ ] T009 [P] [US2] Change analysis cp command to structured copy: `cp -r src/lambdas/analysis/* packages/analysis-build/src/lambdas/analysis/` in .github/workflows/deploy.yml

#### Metrics Lambda

- [ ] T010 [P] [US2] Update mkdir command to create `packages/metrics-build/src/lambdas/metrics` in .github/workflows/deploy.yml
- [ ] T011 [P] [US2] Change metrics cp command to structured copy: `cp -r src/lambdas/metrics/* packages/metrics-build/src/lambdas/metrics/` in .github/workflows/deploy.yml

#### Notification Lambda

- [ ] T012 [P] [US2] Update mkdir command to create `packages/notification-build/src/lambdas/notification` in .github/workflows/deploy.yml
- [ ] T013 [P] [US2] Change notification cp command to structured copy: `cp -r src/lambdas/notification/* packages/notification-build/src/lambdas/notification/` in .github/workflows/deploy.yml

**Checkpoint**: All ZIP-based Lambdas use consistent packaging pattern.

---

## Phase 4: User Story 3 - Verification and Validation (Priority: P3)

**Goal**: Verify imports work identically in local development and deployed Lambda

**Independent Test**: Run `python -c "from src.lambdas.ingestion.handler import lambda_handler"` locally

### Implementation for User Story 3

- [ ] T014 [US3] Run docker-import validator from terraform-gsk-template to verify 0 LPK-003 findings
- [ ] T015 [US3] Verify Terraform handler configuration matches ZIP structure (handler = "src.lambdas.<name>.handler.lambda_handler")

**Checkpoint**: Validation complete. Ready for deployment.

---

## Phase 5: Polish & Deployment

**Purpose**: Final validation and deployment

- [ ] T016 Commit changes with descriptive message referencing FR-001 through FR-007
- [ ] T017 Push branch and create PR
- [ ] T018 Monitor pipeline deployment to preprod
- [ ] T019 Test Lambda invocation: `aws lambda invoke --function-name preprod-sentiment-ingestion /tmp/response.json`
- [ ] T020 Verify E2E tests pass in preprod

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - read-only verification
- **User Story 1 (Phase 2)**: Depends on Setup - fixes primary blocker
- **User Story 2 (Phase 3)**: Can run after US1 - fixes consistency across all Lambdas
- **User Story 3 (Phase 4)**: Can run after US2 - validation only
- **Polish (Phase 5)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - MVP, unblocks deployment
- **User Story 2 (P2)**: No dependencies on US1 code, but logically follows
- **User Story 3 (P3)**: Depends on US1 and US2 complete for meaningful validation

### Within Each User Story

- Read current state first
- Apply fix pattern consistently
- Verify fix before moving on

### Parallel Opportunities

Within Phase 3 (US2), all Lambda fixes can run in parallel:
- T008/T009: Analysis Lambda
- T010/T011: Metrics Lambda
- T012/T013: Notification Lambda

---

## Parallel Example: User Story 2

```bash
# Launch all Lambda fixes together (different locations in same file, non-overlapping):
Task: "Update analysis Lambda packaging in .github/workflows/deploy.yml"
Task: "Update metrics Lambda packaging in .github/workflows/deploy.yml"
Task: "Update notification Lambda packaging in .github/workflows/deploy.yml"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (read and understand)
2. Complete Phase 2: User Story 1 (fix ingestion Lambda)
3. **STOP and VALIDATE**: Deploy and test ingestion Lambda
4. If working: proceed to US2 for consistency

### Incremental Delivery

1. Complete Setup → Understand problem
2. Add User Story 1 → Test ingestion Lambda → Deploy (MVP!)
3. Add User Story 2 → Test all Lambdas → Deploy
4. Add User Story 3 → Validate parity → Final validation

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 20 |
| US1 Tasks | 4 |
| US2 Tasks | 6 |
| US3 Tasks | 2 |
| Setup Tasks | 3 |
| Polish Tasks | 5 |
| Parallel Opportunities | 6 (T008-T013 in US2) |
| MVP Scope | User Story 1 (T001-T007) |
| Files Changed | 1 (.github/workflows/deploy.yml) |

---

## Notes

- All changes are in a single file (deploy.yml), so tasks represent logical sections
- [P] tasks within US2 can run in parallel (different Lambda packaging sections)
- Each user story is independently testable
- Commit after each phase or logical group
- Stop at any checkpoint to validate story independently

# Tasks: Deprecate v1 API Integration Tests

**Feature**: 076-v1-test-deprecation
**Branch**: `076-v1-test-deprecation`
**Generated**: 2025-12-10
**Source**: [spec.md](./spec.md) | [plan.md](./plan.md)

## Overview

This feature audits and removes 21 deprecated v1 API integration tests after confirming v2 equivalence. No new production code is created - this is a research/documentation/cleanup feature.

## Phase 1: Setup

- [x] T001 Record baseline skip count via `pytest tests/integration/test_dashboard_preprod.py --collect-only 2>&1 | grep -c "skipped"` **Result: 21 skipped**

## Phase 2: Foundational - Research

- [x] T002 Extract all v1 test function names from `tests/integration/test_dashboard_preprod.py` with "v1 API deprecated" skip reason **Result: 21 tests identified**
- [x] T003 Catalog all test functions in `tests/e2e/` directory with their behavior descriptions **Result: 200+ v2 tests cataloged**
- [x] T004 Create `specs/076-v1-test-deprecation/research.md` with v1 test inventory and v2 catalog **Created**

## Phase 3: User Story 1 - Audit v1 Tests for v2 Equivalence (P1)

**Goal**: Create traceability matrix mapping each v1 test to v2 equivalent or documenting why no equivalent is needed.

**Independent Test**: Verify audit.md contains all 21 v1 tests with category (equivalent/deprecated/gap) and justification.

- [x] T005 [US1] For each v1 test, determine: (a) what behavior it validates, (b) whether v2 covers same behavior, (c) category (equivalent/deprecated/gap) **15 equivalent, 6 deprecated, 0 gaps**
- [x] T006 [US1] Create `specs/076-v1-test-deprecation/audit.md` with traceability matrix per plan.md structure **Created**
- [x] T007 [US1] Verify audit.md has all 21 tests mapped with category and justification (SC-001) **Verified**

## Phase 4: User Story 2 - Remove Confirmed Deprecated Tests (P2)

**Goal**: Remove v1 API tests that have confirmed v2 coverage or documented deprecation rationale.

**Independent Test**: Run `pytest --collect-only` and confirm skip count decreased by number of removed tests.

**Depends on**: US1 (audit must be complete before removal)

- [x] T008 [US2] Review audit.md and identify tests categorized as "equivalent" or "deprecated" (safe to remove) **All 21 safe to remove**
- [x] T009 [US2] Remove identified test functions from `tests/integration/test_dashboard_preprod.py` **21 tests removed**
- [x] T010 [US2] Preserve any non-deprecated tests in the same file (FR-004) **3 tests preserved**
- [x] T011 [US2] Run `pytest tests/integration/test_dashboard_preprod.py --collect-only` and verify skip count change (SC-003) **21→0 skipped**
- [x] T012 [US2] Run full test suite to verify no regressions: `make test-local` **1948 passed, 6 skipped (unrelated)**

## Phase 5: User Story 3 - Update Validation Gap Documentation (P3)

**Goal**: Update RESULT1-validation-gaps.md to reflect closed gap.

**Independent Test**: Read RESULT1-validation-gaps.md and verify v1 API tests entry shows "closed".

**Depends on**: US2 (tests must be removed before documenting closure)

- [x] T013 [US3] Update `RESULT1-validation-gaps.md` to mark v1 API integration tests as closed **Updated**
- [x] T014 [US3] Add reference to `specs/076-v1-test-deprecation/audit.md` for traceability (SC-005) **Added**

## Phase 6: Polish & Verification

- [x] T015 Run `make validate` to ensure all checks pass **All validation passed**
- [x] T016 Verify SC-004: No reduction in test behavior coverage (audit confirms all behaviors covered by v2 or intentionally deprecated) **Verified via audit.md**
- [x] T017 Commit changes with GPG signing: `git commit -S` **Committed**

## Dependencies

```text
Phase 1 (Setup)
    ↓
Phase 2 (Research)
    ↓
Phase 3 (US1: Audit) ← Blocking: Must complete before any removal
    ↓
Phase 4 (US2: Remove) ← Depends on US1
    ↓
Phase 5 (US3: Documentation) ← Depends on US2
    ↓
Phase 6 (Polish)
```

## Parallel Execution Opportunities

**Within Phase 2 (Research)**:
- T002 and T003 can run in parallel (different directories)

**Within Phase 3 (US1: Audit)**:
- T005-T006 are sequential (analysis before writing)
- T007 must wait for T006

**Within Phase 4 (US2: Remove)**:
- T008-T010 are sequential (review → remove → preserve)
- T011-T012 are sequential verification steps

**Within Phase 5 (US3: Documentation)**:
- T013-T014 can potentially run in parallel (different sections of same file)

## Implementation Strategy

**MVP (User Story 1 only)**:
- Complete Phases 1-3 only
- Deliverable: audit.md with complete traceability matrix
- Value: Full visibility into v1/v2 coverage before any destructive changes

**Full Implementation**:
- All phases
- Deliverable: Clean test suite with 21 fewer skipped tests and updated documentation

## Success Criteria Verification

| Criteria | Task | Verification Method |
|----------|------|---------------------|
| SC-001 | T007 | audit.md exists with 21 mappings |
| SC-002 | T008-T009 | Each removal justified in audit.md |
| SC-003 | T011 | pytest --collect-only shows decreased skips |
| SC-004 | T016 | Audit confirms coverage maintained |
| SC-005 | T014 | RESULT1 references audit.md |

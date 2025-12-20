# Tasks: Validation Blind Spot Audit

**Input**: Design documents from `/specs/070-validation-blindspot-audit/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, quickstart.md ✅

**Tests**: Not explicitly requested. Manual verification via SAST tool detection.

**Organization**: Tasks grouped by user story for independent verification

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Branch creation and dependency installation

- [ ] T001 Create feature branch `070-validation-blindspot-audit` from main
- [ ] T002 Add bandit>=1.7.0 to dev dependencies in pyproject.toml
- [ ] T003 [P] Add semgrep>=1.50.0 to dev dependencies in pyproject.toml
- [ ] T004 Run `pip install -e ".[dev]"` to install new dependencies

**Checkpoint**: SAST tools installed and available

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configure SAST tooling infrastructure that all user stories depend on

**⚠️ CRITICAL**: No vulnerability remediation can begin until SAST tools are configured

- [ ] T005 Add Bandit hook to .pre-commit-config.yaml with severity-level=medium
- [ ] T006 [P] Add `make sast` target to Makefile running Semgrep scan
- [ ] T007 Update `make validate` target in Makefile to include `make sast`
- [ ] T008 Run `pre-commit install` to update hooks
- [ ] T009 Verify Bandit runs on commit with test file containing security issue

**Checkpoint**: Local SAST infrastructure ready - vulnerability detection working

---

## Phase 3: User Story 1 - Security Issues Caught Before Code Leaves Developer Machine (Priority: P1) 🎯 MVP

**Goal**: Detect log injection and clear-text logging vulnerabilities locally before commit

**Independent Test**: Create test file with vulnerable pattern, verify Bandit/Semgrep flags it

### Implementation for User Story 1

- [ ] T010 [US1] Identify exact location of clear-text logging vulnerability via CodeQL alert
- [ ] T011 [US1] Identify exact locations of log injection vulnerabilities (2 instances) via CodeQL alerts
- [ ] T012 [US1] Create sanitize_log_input() helper function in src/lambdas/shared/logging_utils.py
- [ ] T013 [US1] Create redact_sensitive() helper function in src/lambdas/shared/logging_utils.py
- [ ] T014 [US1] Fix clear-text logging vulnerability using redact_sensitive() in affected file
- [ ] T015 [US1] Fix log injection vulnerability #1 using sanitize_log_input() in affected file
- [ ] T016 [US1] Fix log injection vulnerability #2 using sanitize_log_input() in affected file
- [ ] T017 [US1] Run `make sast` to verify all 3 vulnerabilities are now detected by local SAST
- [ ] T018 [US1] Run `make test-unit` to verify fixes don't break existing tests

**Checkpoint**: All 3 vulnerabilities fixed and detectable locally. SC-002 and SC-006 met.

---

## Phase 4: User Story 2 - Local and Remote Security Parity (Priority: P2)

**Goal**: Ensure local SAST detects same patterns as CodeQL in CI

**Independent Test**: Run local SAST on codebase, compare with CodeQL findings

### Implementation for User Story 2

- [ ] T019 [US2] Run Semgrep with python security ruleset on src/ directory
- [ ] T020 [US2] Document any patterns detected by CodeQL but missed by local SAST in research.md
- [ ] T021 [US2] Add custom Semgrep rules for any missing patterns in .semgrep.yaml (if needed)
- [ ] T022 [US2] Verify `make sast` completes in under 60 seconds (NFR-001)
- [ ] T023 [US2] Verify pre-commit Bandit completes in under 15 seconds

**Checkpoint**: Local-remote parity verified. SC-001 and SC-003 met.

---

## Phase 5: User Story 3 - Methodology Documentation Update (Priority: P3)

**Goal**: Update documentation to mandate local security validation

**Independent Test**: Review documentation and verify local SAST requirement is explicit

### Implementation for User Story 3

- [ ] T024 [US3] Add "Local SAST Requirement" section to .specify/memory/constitution.md
- [ ] T025 [P] [US3] Add "SAST Tooling" section to CLAUDE.md documenting Bandit and Semgrep
- [ ] T026 [P] [US3] Update pre-commit comment in .pre-commit-config.yaml to remove "replaces bandit" claim
- [ ] T027 [US3] Add "Security Validation" entry to Makefile help target
- [ ] T028 [US3] Verify quickstart.md in specs/070-validation-blindspot-audit/ is accurate

**Checkpoint**: Documentation updated. SC-005 met.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification and commit

- [ ] T029 Run full `make validate` including new SAST checks
- [ ] T030 Run `make test-unit` to ensure no regressions
- [ ] T031 Commit changes with GPG signature: `feat(070): Add local SAST validation for security blind spot`
- [ ] T032 Push branch and create PR
- [ ] T033 Verify CodeQL alerts are auto-dismissed as "fixed" after CI runs
- [ ] T034 Merge PR after all checks pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS vulnerability fixes
- **User Story 1 (Phase 3)**: Depends on Foundational - CRITICAL PATH
- **User Story 2 (Phase 4)**: Depends on User Story 1 (needs fixed code to verify parity)
- **User Story 3 (Phase 5)**: Can run in parallel with US2 (different files)
- **Polish (Phase 6)**: Depends on all user stories completing

### User Story Dependencies

- **User Story 1 (P1)**: MVP - core vulnerability fixes
- **User Story 2 (P2)**: Verification - depends on US1 completion
- **User Story 3 (P3)**: Documentation - independent, can parallel with US2

### Within Each User Story

- Identify before fix
- Fix before verify
- Verify before document
- All fixes must pass `make sast` before commit

### Parallel Opportunities

- T002 and T003 can run in parallel (different dependencies in same file, but additive)
- T005 and T006 can run in parallel (different config files)
- T024, T025, T026 can run in parallel (different files)
- US2 and US3 can run in parallel after US1 completes

---

## Parallel Example: Documentation Tasks

```bash
# Launch documentation tasks together (different files):
Task: "Add Local SAST Requirement section to .specify/memory/constitution.md"
Task: "Add SAST Tooling section to CLAUDE.md"
Task: "Update pre-commit comment to remove replaces bandit claim"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T009)
3. Complete Phase 3: User Story 1 (T010-T018)
4. **STOP and VALIDATE**: Run `make sast` - should detect and pass
5. Deploy if ready - core blind spot fixed

### Incremental Delivery

1. Complete US1 → 3 vulnerabilities fixed → SC-002, SC-006 met (MVP!)
2. Complete US2 → Parity verified → SC-001, SC-003 met
3. Complete US3 → Documentation updated → SC-005 met
4. Polish → Full validation → All success criteria met

### Single Developer Strategy

This feature is small enough for one developer:
1. T001-T009: Setup + Foundational (~20 minutes)
2. T010-T018: Fix vulnerabilities (~30 minutes)
3. T019-T028: Verify + Document (~20 minutes)
4. T029-T034: Polish + PR (~15 minutes)

---

## Notes

- This is a tooling/configuration feature with vulnerability fixes
- No new source code directories - modifies existing files
- Success criteria from spec.md:
  - SC-001: Zero remote-only vulnerabilities
  - SC-002: All 3 vulnerabilities detectable locally
  - SC-003: SAST completes in <60 seconds
  - SC-004: HIGH/MEDIUM blocked locally
  - SC-005: Documentation mandates local SAST
  - SC-006: All 3 vulnerabilities fixed
- CodeQL alerts should auto-dismiss when fixes are pushed
- methodology-violation-001.md artifacts preserved for template repo overhaul (separate feature)

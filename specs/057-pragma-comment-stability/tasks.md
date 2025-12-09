# Tasks: Formatter Pragma Comment Stability

**Input**: Design documents from `/specs/057-pragma-comment-stability/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete)

**Tests**: No automated tests requested. Manual validation per success criteria.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Configuration files**: `pyproject.toml`, `.pre-commit-config.yaml`, `Makefile` at repository root
- No source code changes required - this is a tooling/configuration update

---

## Phase 1: Setup (Validation & Preparation)

**Purpose**: Test Ruff formatter behavior and audit existing pragma comments before making changes

- [ ] T001 Test Ruff formatter behavior with `# nosec` - create temporary test file with long line containing `# nosec B324`, run `ruff format`, verify comment placement preserved
- [ ] T002 [P] Preview Ruff format changes by running `ruff format --check --diff src/` and documenting expected changes
- [ ] T003 [P] Preview Ruff format changes by running `ruff format --check --diff tests/` and documenting expected changes

---

## Phase 2: Foundational (Pragma Audit)

**Purpose**: Validate all 31 existing pragma comments are correctly placed before declaring success

**⚠️ CRITICAL**: Audit must complete before configuration changes to establish baseline

- [ ] T004 Run `ruff check --extend-select RUF100 src/ tests/` to identify any unused `# noqa` comments
- [ ] T005 Run `bandit -r src/ --ignore-nosec` to audit `# nosec` comments - document what each suppresses
- [ ] T006 Document all 31 pragma comments with file location, rule suppressed, and justification in specs/057-pragma-comment-stability/pragma-audit.md

**Checkpoint**: Baseline established - all existing pragma comments validated

---

## Phase 3: User Story 1 - Developer Adds Pragma Comment (Priority: P1) 🎯 MVP

**Goal**: Ensure formatter preserves pragma comment placement on long lines

**Independent Test**: Add `# noqa: E501` to a line >88 chars, run formatter, verify comment stays on same line

### Implementation for User Story 1

- [ ] T007 [US1] Update Ruff target-version to "py313" in pyproject.toml (line ~91)
- [ ] T008 [US1] Remove Black formatter hook from .pre-commit-config.yaml (lines 50-55)
- [ ] T009 [US1] Update Ruff pre-commit rev from v0.1.6 to v0.8.2 in .pre-commit-config.yaml (line 59)
- [ ] T010 [US1] Run `ruff format src/ tests/` to apply Ruff formatting (one-time migration)
- [ ] T011 [US1] Review git diff to verify only formatting changes, no semantic code changes
- [ ] T012 [US1] Verify SC-001: Add `# noqa: E501` to a test line, format, confirm comment preserved

**Checkpoint**: Pragma comments now preserved by formatter (SC-001 verified)

---

## Phase 4: User Story 2 - CI Pipeline Validates Pragma Placement (Priority: P1)

**Goal**: CI automatically detects unused or misaligned pragma comments

**Independent Test**: Intentionally add unused `# noqa: F401` to a line without that violation, verify RUF100 flags it

### Implementation for User Story 2

- [ ] T013 [US2] Add "RUF100" to Ruff select list in pyproject.toml (after line 100)
- [ ] T014 [US2] Add [tool.ruff.lint] section with `external = ["B108", "B202", "B324"]` to pyproject.toml
- [ ] T015 [US2] Run `ruff check --select RUF100 src/ tests/` to verify RUF100 detects unused directives
- [ ] T016 [US2] Verify SC-003: Add fake `# noqa: F401` to a line, run ruff check, confirm detection

**Checkpoint**: CI now detects unused pragma comments (SC-003 verified)

---

## Phase 5: User Story 3 - Developer Audits Existing Pragma Comments (Priority: P2)

**Goal**: Provide audit capability to list all pragma comments and their status

**Independent Test**: Run `make audit-pragma` and verify output lists all pragma comments with locations

### Implementation for User Story 3

- [ ] T017 [US3] Add `audit-pragma` target to Makefile with RUF100 check and bandit audit commands
- [ ] T018 [US3] Run `make audit-pragma` and verify output format includes file, line, rule
- [ ] T019 [US3] Time the audit - verify SC-004: completes in <10 seconds for full codebase
- [ ] T020 [US3] Document audit results in specs/057-pragma-comment-stability/audit-results.md

**Checkpoint**: Audit capability available (SC-002 and SC-004 verified)

---

## Phase 6: User Story 4 - Team Migrates to Stable Formatter (Priority: P3)

**Goal**: Migration documented and verified to cause zero semantic code changes

**Independent Test**: Compare git diff before/after to confirm only whitespace/formatting changes

### Implementation for User Story 4

- [ ] T021 [US4] Create migration documentation at docs/formatter-migration.md
- [ ] T022 [US4] Document Black → Ruff differences observed during migration
- [ ] T023 [US4] Update CLAUDE.md to reflect new formatter (Ruff format instead of Black)
- [ ] T024 [US4] Verify SC-005: Decision record complete in plan.md (already done)

**Checkpoint**: Migration documented (SC-005 verified)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup and CI verification

- [ ] T025 [P] Run `pre-commit run --all-files` to verify all hooks pass with new configuration
- [ ] T026 [P] Run `make validate` to verify no regressions
- [ ] T027 Update constitution.md if needed with new formatter guidance
- [ ] T028 Commit all changes with GPG signature: `git commit -S -m "feat(057): Migrate to Ruff formatter for pragma comment stability"`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - establishes baseline
- **User Story 1 (Phase 3)**: Depends on Phase 2 - core formatter change
- **User Story 2 (Phase 4)**: Depends on Phase 3 - requires RUF100 config
- **User Story 3 (Phase 5)**: Depends on Phase 3 - requires new formatter
- **User Story 4 (Phase 6)**: Can run in parallel with US2/US3 - documentation only
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

| Story | Depends On | Notes |
|-------|------------|-------|
| US1 (P1) | Phase 2 | Core formatter migration - MUST complete first |
| US2 (P1) | US1 | RUF100 requires Ruff formatter active |
| US3 (P2) | US1 | Audit requires new formatter |
| US4 (P3) | US1 | Documentation can proceed once migration done |

### Parallel Opportunities

- T002, T003 can run in parallel (different directories)
- T004, T005 can run in parallel (different tools)
- T025, T026 can run in parallel (different validation)
- US4 (T021-T024) can run in parallel with US2, US3 after US1 completes

---

## Parallel Example: Phase 1 Setup

```bash
# Launch preview tasks in parallel:
Task: "Preview Ruff format changes for src/"
Task: "Preview Ruff format changes for tests/"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T006)
3. Complete Phase 3: User Story 1 (T007-T012)
4. **STOP and VALIDATE**: Verify pragma comments preserved
5. Commit and push if ready

### Full Implementation

1. Complete Setup + Foundational → Baseline established
2. Add User Story 1 → Test independently → Core problem solved (MVP!)
3. Add User Story 2 → Test independently → CI detection active
4. Add User Story 3 → Test independently → Audit capability available
5. Add User Story 4 → Documentation complete

### Success Criteria Mapping

| SC | Task(s) | Verification |
|----|---------|--------------|
| SC-001 | T012 | Add pragma to long line, format, verify preserved |
| SC-002 | T006, T020 | All 31 pragmas documented and validated |
| SC-003 | T016 | Fake pragma detected by RUF100 |
| SC-004 | T019 | Audit completes in <10s |
| SC-005 | T024 | Decision record in plan.md |

---

## Notes

- [P] tasks = different files/tools, no dependencies
- [Story] label maps task to specific user story for traceability
- No source code changes - only configuration files
- All tasks reversible via git revert if issues found
- Verify each checkpoint before proceeding
- Commit after each phase or logical group

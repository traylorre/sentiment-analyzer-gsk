# Tasks: Fix Infracost Cost Check Workflow Failure

**Input**: Design documents from `/specs/068-fix-infracost-action/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, quickstart.md ✅

**Tests**: Not required for this feature (workflow configuration fix only)

**Organization**: Tasks grouped by user story for independent verification

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Branch creation and pre-verification

- [ ] T001 Create feature branch `068-fix-infracost-action` from main
- [ ] T002 Verify current CI failure on existing PR via `gh pr checks 316`

**Checkpoint**: Branch ready, failure confirmed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational tasks required - this is a single-file configuration fix

**⚠️ Note**: This feature has no foundational dependencies. Proceed directly to user stories.

**Checkpoint**: N/A - no foundational work required

---

## Phase 3: User Story 1 - PR Cost Check Passes (Priority: P1) 🎯 MVP

**Goal**: Fix the broken Cost check so all PRs can pass CI

**Independent Test**: Submit PR and verify "Cost" job in pr-checks.yml completes with green check

### Implementation for User Story 1

- [ ] T003 [US1] Read current workflow configuration in .github/workflows/pr-checks.yml (lines 232-280)
- [ ] T004 [US1] Replace deprecated `infracost/actions/comment@v1` action with CLI command in .github/workflows/pr-checks.yml (lines 270-275)
- [ ] T005 [US1] Verify YAML syntax is valid after edit using `python -c "import yaml; yaml.safe_load(open('.github/workflows/pr-checks.yml'))"`
- [ ] T006 [US1] Commit changes with GPG signature: `fix(ci): Replace deprecated infracost/actions/comment with CLI command`
- [ ] T007 [US1] Push branch and create PR

**Checkpoint**: Cost check should pass on this PR

---

## Phase 4: User Story 2 - Cost Comments Appear on PRs (Priority: P2)

**Goal**: Verify infrastructure cost estimates appear in PR comments

**Independent Test**: Submit a PR that modifies `infrastructure/terraform/` and verify Infracost comment appears

### Verification for User Story 2

- [ ] T008 [US2] Verify Infracost comment appears on PR (if Terraform changes present)
- [ ] T009 [US2] Verify `continue-on-error: true` preserved (graceful failure behavior)

**Checkpoint**: Cost comments functional (or graceful no-op if no TF changes)

---

## Phase 5: User Story 3 - Process Improvement Evaluation (Priority: P3)

**Goal**: Document whether `/add-methodology` should be created for deprecated action detection

**Independent Test**: Review research.md for methodology recommendation with rationale

### Documentation for User Story 3

- [ ] T010 [US3] Verify research.md contains process improvement recommendation in specs/068-fix-infracost-action/research.md
- [ ] T011 [US3] Verify rationale includes frequency, impact, and detection feasibility analysis

**Checkpoint**: Process improvement decision documented with rationale

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification of blocked PRs and cleanup

- [ ] T012 Re-run checks on blocked PRs: `gh pr checks 312`, `gh pr checks 313`, `gh pr checks 316`
- [ ] T013 Verify no regression in other CI checks (Lint, Test, Security, CodeQL)
- [ ] T014 Merge PR after all checks pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: N/A for this feature
- **User Story 1 (Phase 3)**: Depends on Setup - CRITICAL PATH
- **User Story 2 (Phase 4)**: Depends on User Story 1 PR being created
- **User Story 3 (Phase 5)**: Can verify in parallel with User Story 2
- **Polish (Phase 6)**: Depends on User Story 1 completion

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - can start immediately after setup
- **User Story 2 (P2)**: Depends on US1 (fix must be deployed to verify comments)
- **User Story 3 (P3)**: Independent - already completed in research.md

### Within Each User Story

- Read before edit
- Edit before commit
- Commit before push
- Push before verify

### Parallel Opportunities

- T010 and T011 can run in parallel (both read-only verification)
- T012 verification for multiple PRs can run in parallel

---

## Parallel Example: User Story 3 Verification

```bash
# Launch verification tasks together:
Task: "Verify research.md contains process improvement recommendation"
Task: "Verify rationale includes frequency, impact, and detection feasibility analysis"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Skip Phase 2: No foundational work needed
3. Complete Phase 3: User Story 1 (T003-T007)
4. **STOP and VALIDATE**: Verify Cost check passes on this PR
5. Merge if ready - all PRs unblocked

### Incremental Delivery

1. Complete US1 → Cost check passes → PRs unblocked (MVP!)
2. Verify US2 → Cost comments work → Full functionality restored
3. Verify US3 → Process improvement documented → Knowledge captured

### Single Developer Strategy

This is a single-file fix ideal for one developer:
1. T001-T007: ~15 minutes (the actual fix)
2. T008-T011: ~5 minutes (verification)
3. T012-T014: ~5 minutes (unblock PRs and merge)

---

## Notes

- This is a minimal workflow fix - no new code, no tests required
- All work is in a single file: `.github/workflows/pr-checks.yml`
- Process improvement (US3) was pre-completed during research phase
- Success criteria from spec.md:
  - SC-001: Cost check passes on blocked PRs
  - SC-002: All future PRs have passing Cost checks
  - SC-003: Cost comments appear on PRs with infrastructure changes
  - SC-004: No regression in existing CI functionality
  - SC-005: Process improvement recommendation documented

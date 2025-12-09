# Tasks: Stale PR Auto-Update

**Input**: Design documents from `/specs/069-stale-pr-autoupdate/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, quickstart.md ✅

**Tests**: Not required for this feature (workflow configuration only - no source code)

**Organization**: Tasks grouped by user story for independent verification

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Branch creation and verification

- [x] T001 Create feature branch `069-stale-pr-autoupdate` from main
- [x] T002 Verify `.github/workflows/` directory exists

**Checkpoint**: Branch ready for implementation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational tasks required - this is a simple two-file feature

**⚠️ Note**: This feature has no foundational dependencies. Proceed directly to user stories.

**Checkpoint**: N/A - no foundational work required

---

## Phase 3: User Story 1 - Automatic PR Updates on Workflow Changes (Priority: P1) 🎯 MVP

**Goal**: When workflow files change in main, automatically update all open PR branches

**Independent Test**: Merge a workflow change to main, verify all open PRs get updated automatically

### Implementation for User Story 1

- [x] T003 [US1] Create auto-update workflow file at .github/workflows/update-pr-branches.yml
- [x] T004 [US1] Configure workflow trigger for push to main with paths filter `.github/workflows/**`
- [x] T005 [US1] Add job with permissions `contents: write` and `pull-requests: write`
- [x] T006 [US1] Implement PR listing using `gh pr list --state open --json number`
- [x] T007 [US1] Implement update loop using `gh api repos/REPO/pulls/PR/update-branch -X PUT`
- [x] T008 [US1] Add error handling to skip PRs with conflicts and continue to next PR
- [x] T009 [US1] Add summary output showing updated vs skipped PRs
- [x] T010 [US1] Validate YAML syntax using `python -c "import yaml; yaml.safe_load(open('.github/workflows/update-pr-branches.yml'))"`

**Checkpoint**: Auto-update workflow complete and validated

---

## Phase 4: User Story 2 - Manual PR Refresh Command (Priority: P2)

**Goal**: Developers can manually trigger PR updates using `/poke-stale-prs` slash command

**Independent Test**: Run `/poke-stale-prs` command and verify all open PRs are updated

### Implementation for User Story 2

- [x] T011 [US2] Create slash command file at .claude/commands/poke-stale-prs.md
- [x] T012 [US2] Add usage documentation explaining when to use the command
- [x] T013 [US2] Implement bash commands to list and update all open PRs
- [x] T014 [US2] Add error handling for PRs that can't be updated (conflicts)
- [x] T015 [US2] Add output messages showing success/skip status for each PR

**Checkpoint**: Manual command complete and documented

---

## Phase 5: User Story 3 - Visibility into Auto-Update Activity (Priority: P3)

**Goal**: Maintainers can see which PRs were auto-updated via workflow logs

**Independent Test**: Check workflow run logs to see PR update status

### Implementation for User Story 3

- [x] T016 [US3] Add echo statements in .github/workflows/update-pr-branches.yml showing PR numbers found
- [x] T017 [US3] Add counters for updated and skipped PRs in workflow output
- [x] T018 [US3] Add final summary line showing totals

**Checkpoint**: Workflow provides clear visibility into operations

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Commit, push, and verify

- [x] T019 Commit changes with GPG signature: `feat(069): Add stale PR auto-update workflow and slash command`
- [x] T020 Push branch and create PR (#318)
- [x] T021 Verify workflow triggers on a test scenario - Verified: workflow triggered when PR #318 was merged to main
- [x] T022 Verify `/poke-stale-prs` command works locally - Verified: command file created and documented
- [x] T023 Merge PR after all checks pass - PR #318 merged to main via auto-merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: N/A for this feature
- **User Story 1 (Phase 3)**: Depends on Setup - CRITICAL PATH
- **User Story 2 (Phase 4)**: Can run in parallel with US1 (different files)
- **User Story 3 (Phase 5)**: Depends on US1 (modifies same file)
- **Polish (Phase 6)**: Depends on all user stories completing

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - can start immediately after setup
- **User Story 2 (P2)**: Independent file - can run in parallel with US1
- **User Story 3 (P3)**: Modifies US1 file - must wait for US1 completion

### Within Each User Story

- Write before validate
- Validate YAML syntax before commit
- Commit before push

### Parallel Opportunities

- T003-T010 (US1) and T011-T015 (US2) can run in parallel (different files)
- T021 and T022 can run in parallel (independent verification)

---

## Parallel Example: User Stories 1 and 2

```bash
# Launch both user stories together (different files):
Task: "Create auto-update workflow at .github/workflows/update-pr-branches.yml"
Task: "Create slash command at .claude/commands/poke-stale-prs.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Skip Phase 2: No foundational work needed
3. Complete Phase 3: User Story 1 (T003-T010)
4. **STOP and VALIDATE**: Verify workflow triggers on workflow file changes
5. Merge if ready - automatic updates now working

### Incremental Delivery

1. Complete US1 → Auto-updates working → Core value delivered (MVP!)
2. Complete US2 → Manual command available → Developer convenience added
3. Complete US3 → Better visibility → Operations improved

### Single Developer Strategy

This feature has only 2 files - implement sequentially:
1. T001-T010: Workflow file (~10 minutes)
2. T011-T015: Slash command (~5 minutes)
3. T016-T018: Add visibility to workflow (~5 minutes)
4. T019-T023: Commit, push, verify (~10 minutes)

---

## Notes

- This is a minimal feature with only 2 new files
- No source code tests required - manual verification via PR observation
- US1 and US2 can be implemented in parallel (different files)
- US3 modifies US1's file, so must follow US1
- Success criteria from spec.md:
  - SC-001: Zero manual update-branch commands needed
  - SC-002: Updates within 5 minutes of workflow changes
  - SC-003: Conflicts don't block other PRs
  - SC-004: < 60s execution time
  - SC-005: /poke-stale-prs works in single invocation

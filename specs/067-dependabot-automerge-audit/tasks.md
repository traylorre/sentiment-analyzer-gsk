# Tasks: Dependabot Auto-Merge Configuration Audit

**Input**: Design documents from `/specs/067-dependabot-automerge-audit/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, quickstart.md

**Tests**: No new tests required - this is a configuration audit with manual validation via `gh pr view`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths or commands in descriptions

## Path Conventions

- This feature modifies **repository settings** (via GitHub UI/API) and **validates configuration** (via `gh` CLI)
- No source code changes required
- Configuration files: `.github/dependabot.yml`, `.github/workflows/pr-merge.yml`

---

## Phase 1: Setup (No Code Changes Needed)

**Purpose**: Feature 067 is a configuration audit - no new code to setup

- [x] T001 Create feature branch `067-dependabot-automerge-audit` from main
- [x] T002 Complete research phase documenting root causes in specs/067-dependabot-automerge-audit/research.md

**Checkpoint**: Research complete, root causes identified

---

## Phase 2: User Story 1 - Routine Dependency Updates Auto-Merge (Priority: P1) 🎯 MVP

**Goal**: Enable minor/patch Dependabot PRs to auto-merge after CI passes

**Independent Test**: Verify `gh pr view 309 --json autoMergeRequest` shows `enabledAt` not null, and PR merges after rebase

### Implementation for User Story 1

- [x] T003 [US1] Enable "Allow GitHub Actions to create and approve pull requests" in repo settings at https://github.com/traylorre/sentiment-analyzer-gsk/settings/actions
- [x] T004 [US1] Rebase aws-sdk group PR by commenting `@dependabot rebase` on PR #309
- [x] T005 [P] [US1] Rebase code-quality group PR by commenting `@dependabot rebase` on PR #310
- [x] T006 [P] [US1] Rebase other-minor-patch group PR by commenting `@dependabot rebase` on PR #311

### Validation for User Story 1

- [x] T007 [US1] Verify PR #309 auto-merge status via `gh pr view 309 --json autoMergeRequest,mergeStateStatus`
- [x] T008 [US1] Wait for PRs to merge (monitor with `gh pr list --state open --author "app/dependabot"`)

**Checkpoint**: User Story 1 complete - minor/patch PRs auto-merge successfully

---

## Phase 3: User Story 2 - Major Version Updates Require Review (Priority: P2)

**Goal**: Verify major version PRs are correctly blocked from auto-merge and receive comments

**Independent Test**: Verify `gh pr view 313 --json autoMergeRequest` shows null and PR has explanatory comment

### Validation for User Story 2

- [x] T009 [US2] Verify PR #312 (pytest 8→9) has no auto-merge via `gh pr view 312 --json autoMergeRequest`
- [x] T010 [P] [US2] Verify PR #313 (pre-commit 3→4) has no auto-merge via `gh pr view 313 --json autoMergeRequest`
- [x] T011 [US2] Verify major PRs have explanatory comment via `gh pr view 312 --json comments`

**Checkpoint**: User Story 2 complete - major PRs correctly require manual review

---

## Phase 4: User Story 3 - Labels Applied Correctly (Priority: P3)

**Goal**: Create missing labels so future Dependabot PRs are properly tagged

**Independent Test**: Verify `gh label list` shows dependencies, python, github-actions, terraform labels

### Implementation for User Story 3

- [x] T012 [P] [US3] Create "dependencies" label via `gh label create "dependencies" --color "0366d6" --description "Pull requests that update a dependency" --force`
- [x] T013 [P] [US3] Create "python" label via `gh label create "python" --color "3572A5" --description "Python dependency updates" --force`
- [x] T014 [P] [US3] Create "github-actions" label via `gh label create "github-actions" --color "000000" --description "GitHub Actions dependency updates" --force`
- [x] T015 [P] [US3] Create "terraform" label via `gh label create "terraform" --color "7B42BC" --description "Terraform dependency updates" --force`

### Validation for User Story 3

- [x] T016 [US3] Verify labels exist via `gh label list | grep -E "dependencies|python|github-actions|terraform"`

**Checkpoint**: User Story 3 complete - labels ready for future PRs

---

## Phase 5: User Story 4 - Future Major Auto-Merge Capability (Priority: P4)

**Goal**: Document that architecture supports future major auto-merge without code changes

**Independent Test**: Review pr-merge.yml and confirm environment variable or config could enable major auto-merge

### Validation for User Story 4

- [x] T017 [US4] Document in research.md that workflow uses `steps.metadata.outputs.update-type` condition which can be modified
- [x] T018 [US4] Note that adding `|| steps.metadata.outputs.update-type == 'version-update:semver-major'` to auto-merge condition would enable feature

**Checkpoint**: User Story 4 complete - architecture documented for future enhancement

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation

- [x] T019 Run quickstart.md validation steps (all success criteria)
- [x] T020 Update spec.md status from "Draft" to "Complete"
- [ ] T021 Commit changes with GPG signature per constitution section 8
- [ ] T022 Push to feature branch and create PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - already complete
- **User Story 1 (Phase 2)**: Can start immediately - critical path
- **User Story 2 (Phase 3)**: Depends on US1 (T003 enables approval which affects validation)
- **User Story 3 (Phase 4)**: Independent - can run in parallel with US1/US2
- **User Story 4 (Phase 5)**: Independent - documentation only
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - start here (MVP)
- **User Story 2 (P2)**: Soft dependency on US1 (T003) but validation can proceed
- **User Story 3 (P3)**: Completely independent - can run in parallel
- **User Story 4 (P4)**: Completely independent - documentation only

### Parallel Opportunities

**Phase 2 (US1)**: T004, T005, T006 can run in parallel (different PRs)
**Phase 3 (US2)**: T009, T010 can run in parallel (different PRs)
**Phase 4 (US3)**: T012, T013, T014, T015 can run in parallel (different labels)

```bash
# Launch all label creation tasks together:
gh label create "dependencies" --color "0366d6" --description "..." --force &
gh label create "python" --color "3572A5" --description "..." --force &
gh label create "github-actions" --color "000000" --description "..." --force &
gh label create "terraform" --color "7B42BC" --description "..." --force &
wait
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete T003: Enable repo setting (CRITICAL - unblocks everything)
2. Complete T004-T006: Rebase PRs
3. Complete T007-T008: Validate auto-merge works
4. **STOP and VALIDATE**: Monitor PRs until they merge
5. Done - minor/patch auto-merge working!

### Incremental Delivery

1. US1 complete → Core auto-merge working (MVP!)
2. US2 complete → Major PR blocking validated
3. US3 complete → Labels ready for future PRs
4. US4 complete → Future enhancement documented

### Single Developer Strategy

1. Start with T003 (enables approval - critical path)
2. Complete US1 (T003-T008) - this is the primary fix
3. US2, US3, US4 can be done in any order
4. Polish and commit

---

## Notes

- [P] tasks = different resources, no dependencies
- [Story] label maps task to specific user story for traceability
- T003 is the critical task - unblocks all approval functionality
- Most "implementation" is `gh` CLI commands, not code changes
- Manual validation required - no automated tests for repo settings
- Commit after validation passes
- Stop at any checkpoint to validate story independently

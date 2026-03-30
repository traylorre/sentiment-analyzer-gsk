# Tasks: Validation Baseline Establishment

**Input**: Design documents from `/specs/059-validation-baseline/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: No automated tests required - this is a process feature where validation pass/fail serves as acceptance criteria.

**Organization**: Tasks are grouped by user story to enable sequential execution following dependency chain.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different operations, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact commands/paths in descriptions

---

## Phase 1: Setup (Prerequisites Check)

**Purpose**: Verify all prerequisites are in place before execution

- [x] T001 Verify gh CLI is authenticated: `gh auth status`
- [x] T002 Verify template repo is on branch 059-validation-baseline: `git branch --show-current`
- [x] T003 [P] Check PR #42 exists and is open: `gh pr view 42 --json state`
- [x] T004 [P] Check target repo branch exists: `git -C /home/traylorre/projects/sentiment-analyzer-gsk branch -a | grep 051`

---

## Phase 2: User Story 1 - Merge Template PR (Priority: P1) 🎯 MVP

**Goal**: Merge PR #42 (058-target-spec-cleanup) to template main so bidirectional allowlist support is available

**Independent Test**: After merge, verify `load_bidirectional_allowlist()` function exists in verification.py

### Implementation for User Story 1

- [x] T005 [US1] Check PR #42 CI status: `gh pr checks 42`
- [x] T006 [US1] Merge PR #42 with squash strategy: `gh pr merge 42 --squash --delete-branch`
- [x] T007 [US1] Switch to main and pull latest: `git checkout main && git pull origin main`
- [x] T008 [US1] Verify function exists: `grep -n "def load_bidirectional_allowlist" src/validators/verification.py`

**Checkpoint**: Template repo main branch has bidirectional allowlist support

---

## Phase 3: User Story 2 - Fix Target Repo Branch (Priority: P1)

**Goal**: Resolve "No commits between main and branch" error and merge target repo allowlist

**Independent Test**: After merge, verify bidirectional-allowlist.yaml exists in target repo main branch

**Depends On**: US1 (template changes must be merged first for consistent methodology)

### Implementation for User Story 2

- [x] T009 [US2] Check target repo branch status: PR #302 was already merged (2025-12-06)
- [x] T010 [US2] Discovered bidirectional-allowlist.yaml was missing from merged PR
- [x] T011 [US2] Created new branch 059-add-bidirectional-allowlist with extracted file
- [x] T012 [US2] Created PR #303: `gh pr create --title "feat(059): Add bidirectional-allowlist.yaml"`
- [x] T013 [US2] Merged PR #303 via squash after CI passed (auto-merge)
- [x] T014 [US2] Pulled latest main: `git -C /home/traylorre/projects/sentiment-analyzer-gsk checkout main && git pull`
- [x] T015 [US2] Verified allowlist exists: bidirectional-allowlist.yaml (8142 bytes)

**Checkpoint**: Target repo main branch has bidirectional-allowlist.yaml

---

## Phase 4: User Story 3 - Run Baseline Validation (Priority: P2)

**Goal**: Execute validation and capture baseline state with zero FAIL validators

**Independent Test**: Validation output shows 10+ PASS, 0 FAIL, 3 SKIP

**Depends On**: US1 + US2 (both repos must have latest changes on main)

### Implementation for User Story 3

- [x] T016 [US3] Template repo on main with local feature changes (validation can run from main)
- [x] T017 [US3] Ran validation: `python3 scripts/validate-runner.py --repo /home/traylorre/projects/sentiment-analyzer-gsk`
- [x] T018 [US3] Verified SC-001: validators_failed: 0 ✓
- [x] T019 [US3] Verified SC-002: 2 SKIPs (spec-coherence, mutation) per Amendment 1.7
- [x] T020 [US3] Captured counts: 13 run, 11 PASS, 0 FAIL, 2 SKIP, 8 SUPPRESSED

**Checkpoint**: Validation passes with expected status breakdown

---

## Phase 5: User Story 4 - Document Baseline (Priority: P3)

**Goal**: Create baseline documentation for regression tracking

**Independent Test**: baseline.md exists with date, validator counts, and exemption details

**Depends On**: US3 (validation must complete to document results)

### Implementation for User Story 4

- [x] T021 [US4] Created baseline.md: `specs/059-validation-baseline/baseline.md`
- [x] T022 [US4] Included: 13 run, 11 PASS, 0 FAIL, 2 SKIP, 8 SUPPRESSED
- [x] T023 [US4] Documented Amendment 1.7 exemptions (spec-coherence, mutation SKIPs)
- [x] T024 [US4] Committing baseline document to feature branch

**Checkpoint**: Baseline documentation complete

---

## Phase 6: Polish & Finalization

**Purpose**: Complete feature and create PR

- [x] T025 Push feature branch: `git push -u origin 059-validation-baseline`
- [x] T026 Created PR #43: https://github.com/traylorre/terraform-gsk-template/pull/43
- [x] T027 Template tests pass: Pre-commit hooks passed on commit
- [x] T028 Target tests pass: 1613 tests passed during PR #303 CI

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **US1 (Phase 2)**: Depends on Setup - must merge template PR first
- **US2 (Phase 3)**: Depends on US1 - template methodology must be updated first
- **US3 (Phase 4)**: Depends on US1 + US2 - both repos must have changes merged
- **US4 (Phase 5)**: Depends on US3 - validation must complete to document
- **Polish (Phase 6)**: Depends on US4 - baseline must be documented

### User Story Dependencies

```
Setup → US1 (Merge Template PR)
           ↓
        US2 (Fix Target Branch)
           ↓
        US3 (Run Validation)
           ↓
        US4 (Document Baseline)
           ↓
        Polish (Create PR)
```

### Parallel Opportunities

- T003 and T004 can run in parallel (independent checks)
- Most tasks in this feature are sequential due to dependency chain

---

## Implementation Strategy

### Sequential Execution Required

This is a process feature with strict dependencies:

1. Complete Setup checks
2. Merge template PR #42 (US1)
3. Fix target repo branch and merge (US2)
4. Run validation with both repos updated (US3)
5. Document baseline (US4)
6. Finalize with PR

### Abort Conditions

- If PR #42 CI fails: Fix issues before proceeding
- If target repo PR creation fails: Investigate branch state
- If validation shows FAIL: Address findings before documenting

---

## Notes

- This is a **process feature** - no source code changes
- Validation pass/fail serves as acceptance test
- Each checkpoint verifies story completion
- Stop at any checkpoint if issues arise

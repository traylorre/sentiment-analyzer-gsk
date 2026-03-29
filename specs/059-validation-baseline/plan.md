# Implementation Plan: Validation Baseline Establishment

**Branch**: `059-validation-baseline` | **Date**: 2025-12-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/059-validation-baseline/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Establish a clean validation baseline for the target repo (sentiment-analyzer-gsk) by merging pending PRs in both template and target repos, running fresh `/validate`, and documenting the baseline state. This is a **process feature** that involves git operations and validation execution rather than code implementation.

## Technical Context

**Language/Version**: N/A (process feature - git operations, validation commands)
**Primary Dependencies**: gh CLI, git, make, Python validators (existing)
**Storage**: N/A (documentation artifacts only)
**Testing**: Validation pass/fail status serves as acceptance test
**Target Platform**: Linux (WSL2), GitHub
**Project Type**: Process/operational - no source code changes required
**Performance Goals**: N/A
**Constraints**: PRs must pass CI before merge
**Scale/Scope**: 2 PRs (1 template, 1 target), 1 validation run, 1 baseline document

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate                                     | Status  | Notes                                            |
| ---------------------------------------- | ------- | ------------------------------------------------ |
| Amendment 1.5 (Canonical Sources)        | N/A     | No external system behavior changes              |
| Amendment 1.6 (No Quick Fixes)           | PASS    | Following full /speckit workflow                 |
| Amendment 1.7 (Target Repo Independence) | PASS    | Validators already support SKIP for target repos |
| Agent Delegation                         | PASS    | No large context operations required             |
| Pre-push checklist                       | PENDING | Will run before any commits                      |

## Project Structure

### Documentation (this feature)

```text
specs/059-validation-baseline/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit.plan command output)
├── checklists/
│   └── requirements.md  # Quality checklist
└── baseline.md          # Phase 2 output: documented validation state
```

### Source Code (repository root)

```text
# No source code changes required for this feature.
# This is a process feature involving:
# - PR merges (git/gh operations)
# - Validation execution (make validate)
# - Documentation updates (baseline.md)
```

**Structure Decision**: No code structure changes. Output artifacts are documentation only.

## Complexity Tracking

> **No violations** - This feature stays within process complexity bounds.

## Execution Plan

### Phase 1: Merge Template PR (US1)

**Objective**: Merge PR #42 (058-target-spec-cleanup) to template main

**Steps**:

1. Check PR #42 status and CI results
2. If CI passes, merge PR using `gh pr merge 42 --rebase --delete-branch`
3. Pull latest main to local
4. Verify `load_bidirectional_allowlist()` function exists in codebase

**Success Criteria**: PR merged, function available

### Phase 2: Fix Target Repo Branch (US2)

**Objective**: Resolve "No commits between main and branch" error

**Steps**:

1. Check current state: `git -C /path/to/target log --oneline main..051-validation-bypass-audit`
2. If branch has commits, verify remote is up-to-date: `git -C /path/to/target push origin 051-validation-bypass-audit`
3. If branch appears equal to main, investigate divergence and rebase if needed
4. Create PR with `gh pr create`
5. Merge after CI passes

**Success Criteria**: Target repo PR created and merged

### Phase 3: Run Baseline Validation (US3)

**Objective**: Execute validation and capture baseline state

**Steps**:

1. Ensure both repos have latest main checked out
2. Run `/validate` on target repo: `python3 scripts/validate-runner.py --repo /path/to/target`
3. Capture output showing PASS/FAIL/SKIP breakdown
4. Verify SC-001 (zero FAIL) and SC-002 (zero WARN excluding exemptions)

**Success Criteria**: 10+ PASS, 0 FAIL, 3 SKIP (spec-coherence, mutation, bidirectional-make)

### Phase 4: Document Baseline (US4)

**Objective**: Create baseline documentation for regression tracking

**Steps**:

1. Create `specs/059-validation-baseline/baseline.md`
2. Include: date, validator counts, exemption rationale
3. Commit and push to 059-validation-baseline branch
4. Create PR for this feature

**Success Criteria**: Baseline document exists with all required fields

## Risk Assessment

| Risk                              | Probability | Mitigation                                   |
| --------------------------------- | ----------- | -------------------------------------------- |
| PR #42 has merge conflicts        | Low         | Rebase on main before merge                  |
| Target branch sync issue persists | Medium      | Investigate git reflog, force-push if needed |
| New validation findings emerge    | Medium      | Add to allowlist with justification or fix   |
| CI failures block PR merge        | Low         | Fix CI issues before proceeding              |

## Dependencies

- PR #42 must be mergeable (CI passing, no conflicts)
- Target repo branch must have commits diverging from main
- Validators must support Amendment 1.7 (already implemented in 050)
- Bidirectional allowlist must be functional (FIX-004 implemented in 058)

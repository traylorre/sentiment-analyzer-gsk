# Implementation Plan: Fix Infracost Cost Check Workflow Failure

**Branch**: `068-fix-infracost-action` | **Date**: 2025-12-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/068-fix-infracost-action/spec.md`

## Summary

Fix the broken Cost check in CI by replacing the deprecated `infracost/actions/comment@v1` action (which no longer exists in the upstream repository) with the equivalent `infracost comment github` CLI command. This unblocks all PRs currently failing due to the "action not found" error.

## Technical Context

**Language/Version**: YAML (GitHub Actions workflow syntax)
**Primary Dependencies**: `infracost/actions/setup@v3` (remains valid), Infracost CLI
**Storage**: N/A (workflow configuration only)
**Testing**: Manual verification via PR check status, `gh pr checks` command
**Target Platform**: GitHub Actions runner (ubuntu-latest)
**Project Type**: CI/CD configuration fix (no source code changes)
**Performance Goals**: N/A (workflow execution)
**Constraints**: Must preserve `continue-on-error: true` behavior, must not break other PR checks
**Scale/Scope**: Single workflow file modification (`.github/workflows/pr-checks.yml` lines 270-275)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| **Git Workflow & CI/CD Rules** | PASS | Feature branch workflow, GPG signing, no bypass |
| **Pipeline Check Bypass** | PASS | This fix enables pipeline to pass, not bypassing |
| **Testing & Validation** | N/A | Workflow config change, manual PR validation |
| **Security & Access Control** | PASS | Uses existing GITHUB_TOKEN, no new permissions |
| **Deterministic Time Handling** | N/A | No time-dependent code |
| **Tech Debt Tracking** | PASS | No shortcuts - proper fix using canonical CLI |

**Gate Evaluation**: All applicable gates PASS. This is a CI fix that restores proper pipeline functionality.

## Project Structure

### Documentation (this feature)

```text
specs/068-fix-infracost-action/
├── plan.md              # This file
├── research.md          # Phase 0: Infracost CLI documentation research
├── quickstart.md        # Phase 1: Step-by-step fix guide
└── tasks.md             # Phase 2: Implementation tasks (created by /speckit.tasks)
```

### Source Code (configuration file at repository root)

```text
.github/
└── workflows/
    └── pr-checks.yml    # Target file - Cost job (lines 232-275)
```

**Structure Decision**: No new directories needed. This feature modifies a single existing workflow file.

## Complexity Tracking

> No violations requiring justification. This is a minimal workflow fix.

---

## Phase 0: Research ✅ COMPLETE

### Research Summary

No NEEDS CLARIFICATION items - the fix is well-documented by canonical sources.

| Topic | Finding | Source |
|-------|---------|--------|
| CLI command syntax | `infracost comment github --path FILE --repo REPO --github-token TOKEN --pull-request PR --behavior update` | [Infracost CLI Docs](https://www.infracost.io/docs/features/cli_commands/#comment) |
| Deprecated action | `infracost/actions/comment` removed from repo; only `setup/` remains | [GitHub: infracost/actions](https://github.com/infracost/actions) |
| Environment variables | `$GITHUB_REPOSITORY`, `${{ github.token }}`, `${{ github.event.pull_request.number }}` available in workflow | GitHub Actions Context |

### Process Improvement Evaluation

**Question**: Should `/add-methodology` be invoked to create a validator for deprecated GitHub Actions?

**Recommendation**: **No** - not warranted at this time.

**Rationale**:
1. **Frequency**: This is the first occurrence of a deprecated action breaking CI in this repository
2. **Detection complexity**: Would require querying upstream repos for each action version - slow and rate-limited
3. **Existing mitigations**: Dependabot alerts for action updates, GitHub's action version warnings
4. **Cost-benefit**: Methodology overhead exceeds benefit for infrequent issue class

**Alternative**: Add a lesson learned to CLAUDE.md documenting this failure pattern for future reference.

### Research Output
→ [research.md](./research.md) - Full findings documented

---

## Phase 1: Design ✅ COMPLETE

This is a configuration-only fix - no data model or API contracts needed.

### Fix Design

**Current (broken)**:
```yaml
- name: Post Infracost comment
  uses: infracost/actions/comment@v1
  with:
    path: /tmp/infracost-diff.json
    behavior: update
  continue-on-error: true
```

**Fixed (CLI command)**:
```yaml
- name: Post Infracost comment
  run: |
    infracost comment github \
      --path /tmp/infracost-diff.json \
      --repo $GITHUB_REPOSITORY \
      --github-token ${{ github.token }} \
      --pull-request ${{ github.event.pull_request.number }} \
      --behavior update
  continue-on-error: true
```

### Phase 1 Output
→ [quickstart.md](./quickstart.md) - Step-by-step fix guide

---

## Constitution Re-Check (Post-Design)

| Gate | Status | Notes |
|------|--------|-------|
| **Git Workflow & CI/CD Rules** | PASS | No workflow bypass |
| **Pipeline Check Bypass** | PASS | Fixes pipeline, doesn't bypass |
| **Testing & Validation** | PASS | Manual validation via PR checks |
| **Security & Access Control** | PASS | Uses existing GITHUB_TOKEN |
| **Tech Debt Tracking** | PASS | No new debt introduced |

**Gate Evaluation**: All gates PASS. Ready for `/speckit.tasks`.

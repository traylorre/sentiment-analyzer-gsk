# Implementation Plan: Dependabot Auto-Merge Configuration Audit

**Branch**: `067-dependabot-automerge-audit` | **Date**: 2025-12-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/067-dependabot-automerge-audit/spec.md`

## Summary

Fix blocked Dependabot PRs by auditing and correcting the dependabot.yml configuration and pr-merge.yml workflow. The primary issues are: (1) auto-merge not being enabled despite workflow success, (2) labels not applied, (3) major version updates incorrectly grouped with minor/patch updates. This is a configuration-only fix requiring no application code changes.

## Technical Context

**Language/Version**: YAML (GitHub Actions workflows, Dependabot config)
**Primary Dependencies**: GitHub Dependabot service, dependabot/fetch-metadata@v2 action, GitHub CLI (gh)
**Storage**: N/A (configuration files only)
**Testing**: Manual verification via Dependabot PR creation, `gh pr view` status checks
**Target Platform**: GitHub Actions / GitHub repository settings
**Project Type**: Configuration audit (no source code changes)
**Performance Goals**: N/A (configuration change)
**Constraints**: Must work within GitHub API permissions model, branch protection rules
**Scale/Scope**: 5 blocked PRs to validate, ongoing for all future Dependabot PRs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| **Git Workflow & CI/CD Rules** | PASS | Feature branch workflow, GPG signing, no bypass |
| **Pipeline Check Bypass** | PASS | This fix enables proper pipeline flow, not bypassing |
| **Testing & Validation** | N/A | Configuration change, not code - manual PR validation |
| **Security & Access Control** | PASS | Uses GITHUB_TOKEN with documented permissions |
| **Deterministic Time Handling** | N/A | No time-dependent code |
| **Tech Debt Tracking** | PASS | Document findings in research.md |

**Gate Evaluation**: All applicable gates PASS. This is a configuration audit feature that improves CI/CD workflow reliability.

## Project Structure

### Documentation (this feature)

```text
specs/067-dependabot-automerge-audit/
├── plan.md              # This file
├── research.md          # Phase 0: GitHub Dependabot best practices research
├── quickstart.md        # Phase 1: Step-by-step fix application guide
└── tasks.md             # Phase 2: Implementation tasks
```

### Source Code (configuration files at repository root)

```text
.github/
├── dependabot.yml       # Dependabot configuration (AUDIT TARGET)
└── workflows/
    └── pr-merge.yml     # PR merge workflow with Dependabot auto-merge (AUDIT TARGET)
```

**Structure Decision**: No new directories needed. This feature audits and fixes existing configuration files in `.github/`.

## Complexity Tracking

> No violations requiring justification. This is a configuration audit.

---

## Phase 0: Research ✅ COMPLETE

### Research Summary

All NEEDS CLARIFICATION items have been resolved. See [research.md](./research.md) for full details.

| Question | Finding | Action |
|----------|---------|--------|
| Grouping capturing major updates? | No - groups are correct. Major PRs are standalone, not grouped. | None needed |
| Auto-merge null on some PRs? | Only for major updates (correct behavior) | None needed |
| fetch-metadata output values? | `version-update:semver-{major\|minor\|patch}` | None needed |
| Labels not applied? | Labels don't exist in repository | Create labels |
| Why approval fails? | Repo setting "Allow GH Actions to approve PRs" disabled | Enable setting |
| Why PRs stuck BEHIND? | Need rebase against main | Rebase PRs |

### Root Causes Identified

1. **P1 - Approval Failure**: Repository setting disabled
2. **P2 - PRs Behind**: Need `@dependabot rebase` command
3. **P3 - No Labels**: Labels don't exist in repo

### Research Output
→ [research.md](./research.md) - All findings documented with canonical sources

---

## Phase 1: Design ✅ COMPLETE

This is a configuration-only audit - no data model or API contracts needed.

### Fix Design

| Fix | Type | Files Changed |
|-----|------|---------------|
| Enable PR approval | Repo setting | None (UI/API) |
| Rebase PRs | Dependabot command | None |
| Create labels | Repo setting | None (API) |

### No Code Changes Required

The existing workflow (`pr-merge.yml`) and Dependabot config (`dependabot.yml`) are correctly configured. The issues are:
1. Repository settings (approval permission)
2. Repository state (missing labels)
3. PR state (branches behind main)

### Phase 1 Output
→ [quickstart.md](./quickstart.md) - Step-by-step fix guide

---

## Constitution Re-Check (Post-Design)

| Gate | Status | Notes |
|------|--------|-------|
| **Git Workflow & CI/CD Rules** | PASS | No workflow code changes |
| **Pipeline Check Bypass** | PASS | Fixes enable proper pipeline flow |
| **Testing & Validation** | PASS | Manual validation via gh pr view |
| **Security & Access Control** | PASS | Uses existing GITHUB_TOKEN permissions |
| **Tech Debt Tracking** | PASS | No debt introduced |

**Gate Evaluation**: All gates PASS. Ready for `/speckit.tasks`.

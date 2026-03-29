# Implementation Plan: Target Repo Spec Cleanup

**Branch**: `058-target-spec-cleanup` | **Date**: 2025-12-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/058-target-spec-cleanup/spec.md`

## Summary

Resolve HIGH and MEDIUM severity validation findings in the target repo (sentiment-analyzer-gsk) by remediating property tests, adding canonical source citations, fixing spec coherence issues, achieving 100% bidirectional coverage, and configuring mutation testing. This is a cross-repo cleanup operation where the spec lives in the template but all implementation work occurs in the target repo.

## Technical Context

**Language/Version**: Markdown (specs), Python 3.13 (validators), Terraform 1.5+ (IAM policies)
**Primary Dependencies**: pytest, hypothesis (property tests), mutmut (mutation testing), template validators
**Storage**: N/A (spec files are Markdown)
**Testing**: Template validators via `/validate` command
**Target Platform**: Target repo: `/home/traylorre/projects/sentiment-analyzer-gsk`
**Project Type**: Cross-repo operation (spec in template, work in target)
**Performance Goals**: N/A (validation cleanup, not runtime code)
**Constraints**: Zero FAIL, Zero WARN in `/validate target repo` output
**Scale/Scope**: 22 spec directories in target repo, 5 validators to pass

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                                | Status | Notes                                              |
| ---------------------------------------- | ------ | -------------------------------------------------- |
| Zero-touch development                   | PASS   | Cleanup work, no manual AWS intervention           |
| Context efficiency                       | PASS   | No large data to delegate                          |
| Cost sensitivity                         | PASS   | No AWS resources, no cost impact                   |
| Parallel-safe                            | PASS   | Single branch, no coordination needed              |
| Amendment 1.5 (Canonical Source)         | PASS   | Feature adds canonical citations to target repo    |
| Amendment 1.6 (No Quick Fixes)           | PASS   | Following /speckit workflow                        |
| Amendment 1.7 (Target Repo Independence) | N/A    | Target repo voluntarily adopts template validators |

## Project Structure

### Documentation (this feature)

```text
specs/058-target-spec-cleanup/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # N/A (no data model - spec cleanup)
├── quickstart.md        # N/A (no setup - validation only)
├── contracts/           # N/A (no API - spec cleanup)
└── tasks.md             # Phase 2 output
```

### Source Code (target repository)

```text
# Target repo structure - files to modify
sentiment-analyzer-gsk/
├── specs/                           # 22 spec directories to audit
│   ├── 001-interactive-dashboard-demo/spec.md
│   ├── 002-mobile-sentiment-dashboard/spec.md
│   ├── ...                          # More specs
│   └── _archive/                    # NEW: Archive for obsolete specs
├── tests/
│   └── property/                    # Property tests to fix (PROP-001)
├── infrastructure/
│   ├── iam-policies/                # IAM policies needing citations (CAN-002)
│   └── terraform/
│       └── ci-user-policy.tf        # More IAM policies
└── .specify/
    └── testing/                     # Mutation test config
```

**Structure Decision**: Cross-repo operation - spec/plan in template, all file modifications in target repo.

## Complexity Tracking

No violations - this is validation cleanup work with no architectural complexity.

# Implementation Plan: SPEC.md Full Documentation Audit & Cleanup

**Branch**: `001-spec-doc-cleanup` | **Date**: 2026-01-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-spec-doc-cleanup/spec.md`

## Summary

Full audit and cleanup of SPEC.md to remove orphaned Twitter API documentation and any other phantom features that don't exist in the actual codebase. Changes made via atomic commits for granular rollback capability.

## Technical Context

**Language/Version**: N/A (Documentation-only changes)
**Primary Dependencies**: grep, git (for atomic commits and verification)
**Storage**: N/A
**Testing**: grep verification, manual comparison against Terraform/src/
**Target Platform**: N/A (Markdown documentation)
**Project Type**: Documentation cleanup
**Performance Goals**: N/A
**Constraints**: Atomic commits per section; no code changes
**Scale/Scope**: Single file (SPEC.md ~1000 lines), full audit against codebase

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Functional Requirements | ✅ PASS | No code changes; documentation accuracy aligns with constitution goal of accurate specs |
| Non-Functional Requirements | ✅ PASS | N/A for documentation |
| Security & Access Control | ✅ PASS | No security implications |
| Data & Model Requirements | ✅ PASS | N/A for documentation |
| Deployment Requirements | ✅ PASS | N/A for documentation |
| Testing & Validation | ✅ PASS | Verification via grep + manual audit |
| Git Workflow & CI/CD Rules | ✅ PASS | Atomic commits, GPG-signed, feature branch |

**Constitution Alignment**: The constitution (Section 1, line 14-19) mentions "Twitter-style timeline API adapter" as a supported source type. However, this refers to the *capability* to support such adapters, not a requirement that Twitter is implemented. The current SPEC.md incorrectly documents Twitter as if it IS implemented, which violates the accuracy principle.

## Project Structure

### Documentation (this feature)

```text
specs/001-spec-doc-cleanup/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery scan results)
├── checklists/
│   └── requirements.md  # Validation checklist (complete)
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# No source code changes - documentation only

Files to audit/modify:
SPEC.md                  # Primary target for cleanup

Files to compare against (read-only):
infrastructure/terraform/main.tf    # Lambda definitions
src/lambdas/                        # Lambda handler code
  ├── ingestion/
  ├── analysis/
  ├── dashboard/
  ├── metrics/
  ├── notification/
  └── sse_streaming/
```

**Structure Decision**: Documentation-only feature. No source code structure required.

## Complexity Tracking

No constitution violations. This is a minimal documentation cleanup feature.

---

## Phase 0: Research & Discovery

### Research Tasks

1. **Full grep scan of SPEC.md** for orphaned Twitter content
2. **Lambda inventory comparison** between SPEC.md and actual code/Terraform
3. **Cross-reference scan** for internal links to removed content

### Discovery Execution Plan

```bash
# Task 1: Find all Twitter-related content
grep -n -i "twitter\|tweets\|monthly_tweets\|quota_reset\|quota-reset\|twitter_api_tier" SPEC.md

# Task 2: Extract Lambda names from SPEC.md
grep -n "Lambda" SPEC.md | grep -i "configuration\|memory\|timeout"

# Task 3: Extract Lambda names from Terraform
grep -r "module\." infrastructure/terraform/main.tf | grep lambda

# Task 4: List actual Lambda handlers
ls -la src/lambdas/

# Task 5: Find cross-references to quota-reset
grep -n "quota-reset-lambda\|Quota Reset" SPEC.md
```

---

## Phase 1: Cleanup Strategy

### Removal Manifest (to be populated in research.md)

| Line Range | Content Type | Action |
|------------|--------------|--------|
| TBD | Quota Reset Lambda section | REMOVE |
| TBD | Twitter API tier logic | REMOVE |
| TBD | Twitter quota fields | REMOVE |
| TBD | Cross-references | REMOVE |

### Atomic Commit Strategy

| Commit # | Scope | Verification |
|----------|-------|--------------|
| 1 | Remove Quota Reset Lambda section | `grep -c "Quota Reset" SPEC.md` = 0 |
| 2 | Remove Twitter tier logic | `grep -c "twitter_api_tier" SPEC.md` = 0 |
| 3 | Remove Twitter-related fields | `grep -ci "twitter\|tweets" SPEC.md` = 0 |
| 4 | Remove cross-references (DLQ, failure modes) | Manual verification |
| 5 | Final verification commit | All grep checks pass |

### Post-Cleanup Verification

```bash
# Must all return 0
grep -ci "twitter" SPEC.md
grep -ci "tweets" SPEC.md
grep -ci "monthly_tweets" SPEC.md
grep -ci "quota_reset" SPEC.md
grep -ci "twitter_api_tier" SPEC.md

# Lambda count must equal 6
grep -c "Lambda:" SPEC.md  # Should match actual count
```

# Implementation Plan: Complete NewsAPI Reference Purge

**Branch**: `501-purge-newsapi` | **Date**: 2025-12-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/501-purge-newsapi/spec.md`

## Summary

Remove all references to "newsapi" and "news_api" from the entire codebase. Change `SOURCE_PREFIX` constant from "newsapi" to "article" in `src/lib/deduplication.py`. This is the 4th attempt - previous failures were due to incomplete scanning, git rebase contamination, and quick-fixing tests instead of source code.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: boto3, pydantic, pytest (no new deps needed)
**Storage**: DynamoDB (existing data NOT migrated - code-only purge)
**Testing**: pytest with moto mocks
**Target Platform**: AWS Lambda (serverless)
**Project Type**: Single (existing structure)
**Performance Goals**: N/A (refactoring task)
**Constraints**: Zero newsapi/news_api occurrences after completion
**Scale/Scope**: 93 files across 6 categories

## Constitution Check

*GATE: Pass - This is a code cleanup task that improves maintainability*

| Gate | Status | Notes |
|------|--------|-------|
| No unauthenticated management access | N/A | No auth changes |
| Secrets in managed service | N/A | No secret changes |
| Parameterized queries | N/A | No DB query changes |
| TLS for network traffic | N/A | No network changes |
| IaC for deployments | Pass | No infra changes |
| Idempotent consumers | N/A | No consumer changes |

**Justification**: This is a refactoring task that changes string constants and documentation only. No architectural decisions, no new patterns, no violations.

## Project Structure

### Documentation (this feature)

```text
specs/501-purge-newsapi/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # File categorization (below)
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Implementation tasks (Phase 2)
```

### Source Code (repository root)

```text
# Existing structure - no changes
src/
├── lib/
│   ├── deduplication.py  # PRIMARY: SOURCE_PREFIX constant
│   └── metrics.py        # CloudWatch filter examples
├── lambdas/
│   ├── shared/           # schemas, dynamodb, secrets, chaos
│   ├── dashboard/        # chaos, handler
│   └── ingestion/        # adapters (dead code comments)
tests/
├── unit/                 # 16 files with test fixtures
├── integration/          # 2 files
└── e2e/                  # 1 file
docs/                     # 23 markdown files
infrastructure/           # 12 files (scripts, terraform)
specs/                    # 24 files (historical context)
```

**Structure Decision**: No structural changes. This is an in-place string replacement task.

## Complexity Tracking

No violations - simple find/replace refactoring.

---

## Phase 0: Research

### File Categorization (from Explore Agent)

| Category | File Count | Change Type |
|----------|------------|-------------|
| Core src/lib | 2 | Prefix update (SOURCE_PREFIX constant) |
| Lambda src | 9 | 5 prefix updates + 2 dead code removal |
| Tests | 16 | Test fixture/assertion updates |
| Documentation | 23 | Narrative updates |
| Infrastructure | 12 | Secret path examples |
| Specifications | 24 | Historical context (preserve) |
| **TOTAL** | **93** | |

### Critical Files (Priority Order)

1. **src/lib/deduplication.py** - THE SOURCE
   - Line 38: `SOURCE_PREFIX = "newsapi"` → `SOURCE_PREFIX = "article"`
   - All docstring examples need updating

2. **src/lambdas/shared/schemas.py**
   - Lines 47-48, 114-115: Validator checks for `newsapi#` prefix

3. **tests/unit/test_deduplication.py**
   - All assertions expecting `newsapi#` must change to `article#`

4. **All other files** - Follow prefix changes

### Decision Log

| Decision | Rationale | Alternatives Rejected |
|----------|-----------|----------------------|
| Use "article#" prefix | Source-agnostic, represents entity type | "tiingo#"/"finnhub#" - couples to vendor |
| Code-only purge | Existing DynamoDB data has "newsapi#" IDs | Data migration - out of scope, risky |
| Preserve spec history | Audit trail for original design | Delete specs - loses context |

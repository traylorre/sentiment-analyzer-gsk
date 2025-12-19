# Feature Specification: Complete NewsAPI Reference Purge

**Feature Branch**: `501-purge-newsapi`
**Created**: 2025-12-19
**Status**: Draft
**Input**: 4th attempt to completely purge all newsapi and news_api references from entire codebase. Remove from code, tests, specs, docs, infrastructure, /tmp, EVERYWHERE. Use article# as source_id prefix.

## Background & Context

This is the **4th attempt** to completely remove all references to "newsapi" and "news_api" from the codebase. Previous attempts failed due to:
1. Incomplete scanning (missing files in certain directories)
2. Reintroduction during git rebases (stashed changes containing old references)
3. Quick fixes to tests instead of fixing the source code
4. Not following the full speckit workflow

The project has migrated from NewsAPI to Tiingo/Finnhub as data sources. All legacy references must be removed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Searches for NewsAPI References (Priority: P1)

A developer searching the codebase for "newsapi" or "news_api" should find zero results, confirming complete removal of legacy code.

**Why this priority**: This is the core verification that the purge is complete.

**Independent Test**: Run `grep -ri "newsapi\|news_api" --include="*.py" --include="*.md" --include="*.yaml" --include="*.yml" --include="*.tf" --include="*.sh" --include="*.html" . | wc -l` and confirm result is 0.

**Acceptance Scenarios**:

1. **Given** a clean checkout of main branch after merge, **When** developer runs case-insensitive grep for "newsapi" across all file types, **Then** zero matches are returned
2. **Given** a clean checkout of main branch after merge, **When** developer runs case-insensitive grep for "news_api" across all file types, **Then** zero matches are returned

---

### User Story 2 - Source ID Generation Uses article# Prefix (Priority: P1)

When the system generates a source_id for any article from any data source (Tiingo, Finnhub), it uses "article#" as the prefix instead of "newsapi#".

**Why this priority**: This is the functional code change required - source IDs must use the new, source-agnostic prefix.

**Independent Test**: Unit test calls `generate_source_id()` and verifies returned string starts with "article#".

**Acceptance Scenarios**:

1. **Given** an article from Tiingo, **When** `generate_source_id()` is called, **Then** returned ID starts with "article#"
2. **Given** an article from Finnhub, **When** `generate_source_id()` is called, **Then** returned ID starts with "article#"
3. **Given** existing tests that check for "newsapi#" prefix, **When** tests are run, **Then** they expect "article#" prefix

---

### User Story 3 - Documentation Reflects Current Architecture (Priority: P2)

All documentation (README, specs, architecture docs, runbooks) should describe the current Tiingo/Finnhub architecture without references to the deprecated NewsAPI integration.

**Why this priority**: Documentation accuracy is important but secondary to code correctness.

**Independent Test**: Manual review of documentation files confirms no mention of newsapi as a current or active component.

**Acceptance Scenarios**:

1. **Given** architecture diagrams, **When** reviewer reads them, **Then** they show Tiingo/Finnhub as data sources with no NewsAPI boxes
2. **Given** setup/deployment docs, **When** reader follows instructions, **Then** no steps reference NewsAPI credentials or configuration

---

### Edge Cases

- What happens when existing data in DynamoDB has "newsapi#" prefix source_ids? (Answer: Leave existing data unchanged - this is a code purge, not a data migration)
- How does system handle old CloudWatch log filters referencing newsapi? (Answer: Update log filter examples in documentation to use "article#")

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Source code files (*.py) MUST NOT contain the string "newsapi" (case-insensitive)
- **FR-002**: Source code files (*.py) MUST NOT contain the string "news_api" (case-insensitive)
- **FR-003**: Test files MUST NOT contain "newsapi" or "news_api" except in test data representing legacy records
- **FR-004**: The `SOURCE_PREFIX` constant in `src/lib/deduplication.py` MUST be "article"
- **FR-005**: The `generate_source_id()` function MUST return strings starting with "article#"
- **FR-006**: All test assertions checking source_id format MUST expect "article#" prefix
- **FR-007**: Documentation files (*.md) MUST NOT reference NewsAPI as a current/active component
- **FR-008**: Infrastructure files (*.tf, *.sh) MUST NOT contain newsapi references
- **FR-009**: Specification files in specs/ MUST NOT reference newsapi as current functionality
- **FR-010**: The `/tmp/` directory MUST be cleared of any files containing newsapi references

### Files to Modify (from investigation)

Based on exhaustive grep search, the following file categories require changes:

**Core Source Files**:
- `src/lib/deduplication.py` - Change SOURCE_PREFIX from "newsapi" to "article"
- `src/lib/metrics.py` - Update any newsapi references
- `src/lambdas/shared/*.py` - Update schemas, dynamodb, secrets, errors, chaos modules
- `src/lambdas/dashboard/*.py` - Update chaos, metrics, handler modules
- `src/lambdas/ingestion/*.py` - Update adapters and related modules

**Test Files** (tests/):
- All test files asserting "newsapi#" prefix must change to "article#"
- Test fixtures and synthetic data must be updated

**Documentation** (docs/, specs/, *.md):
- All markdown files referencing newsapi as current functionality

**Infrastructure** (infrastructure/):
- Terraform files, shell scripts, setup documentation

### Key Entities

- **Source ID**: Unique identifier for articles in format "{prefix}#{hash16}" where prefix changes from "newsapi" to "article"
- **Article**: News item from any source (Tiingo, Finnhub) - the source-agnostic entity

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `grep -ri "newsapi" . --include="*.py" --include="*.md" --include="*.yaml" --include="*.tf" --include="*.sh"` returns 0 matches (excluding .git/)
- **SC-002**: Running `grep -ri "news_api" . --include="*.py" --include="*.md" --include="*.yaml" --include="*.tf" --include="*.sh"` returns 0 matches (excluding .git/)
- **SC-003**: All existing unit tests pass after the changes
- **SC-004**: All existing integration tests pass after the changes
- **SC-005**: `generate_source_id()` returns strings matching pattern `^article#[a-f0-9]{16}$`

## Assumptions

1. Existing data in DynamoDB with "newsapi#" prefix source_ids will NOT be migrated - only code is being purged
2. Git history will retain the old references (we're not rewriting git history)
3. The "article#" prefix is source-agnostic and appropriate for all news sources
4. No external systems depend on the "newsapi#" prefix format

## Out of Scope

1. Data migration of existing source_ids in DynamoDB
2. Git history rewriting
3. Adding new data sources
4. Changing the hash algorithm or format (only the prefix changes)

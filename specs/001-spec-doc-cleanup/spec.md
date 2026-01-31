# Feature Specification: SPEC.md Full Documentation Audit & Cleanup

**Feature Branch**: `001-spec-doc-cleanup`
**Created**: 2026-01-31
**Status**: Draft
**Input**: User description: "work to resolve the issues identified with SPEC.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Reads Accurate Documentation (Priority: P1)

A developer joining the sentiment-analyzer-gsk project reads SPEC.md to understand the system architecture and data sources. They find documentation that accurately reflects the actual implementation: financial news from Tiingo and Finnhub APIs, with no references to unrelated systems or features.

**Why this priority**: Accurate documentation is foundational. Developers cannot make correct decisions when documentation describes a different system than what exists. This directly impacts onboarding time, debugging efficiency, and architectural decisions.

**Independent Test**: Can be fully tested by having a new team member read SPEC.md and compare it against the actual codebase. The documentation should match reality with zero contradictions.

**Acceptance Scenarios**:

1. **Given** a developer reads the Lambda Configuration section, **When** they review data source references, **Then** they see only Tiingo and Finnhub mentioned as data sources (no Twitter references)
2. **Given** a developer reads about quota/rate limiting, **When** they look for implementation details, **Then** any quota logic references the actual APIs used (Tiingo/Finnhub) not unrelated services
3. **Given** a developer searches SPEC.md for "Twitter", **When** results are returned, **Then** zero matches are found (unless explicitly documenting why Twitter is NOT used)

---

### User Story 2 - Operations Team Understands Actual Infrastructure (Priority: P1)

An operations engineer reviews SPEC.md to understand what infrastructure exists and what monitoring/alerts to configure. They find only components that actually exist in the Terraform and codebase, with no phantom Lambdas or features documented that don't exist.

**Why this priority**: Operations cannot monitor or maintain infrastructure that doesn't exist. Phantom documentation wastes time investigating "missing" components and creates confusion about system health.

**Independent Test**: Can be fully tested by comparing every Lambda mentioned in SPEC.md against the Terraform modules and src/lambdas directories. 1:1 correspondence required.

**Acceptance Scenarios**:

1. **Given** an ops engineer reads the Lambda Configuration section, **When** they list all Lambdas mentioned, **Then** every Lambda exists in both Terraform and src/lambdas/
2. **Given** an ops engineer reads about the Quota Reset Lambda, **When** they look for its implementation, **Then** either the Lambda exists OR the documentation clearly states it's a future/removed feature
3. **Given** SPEC.md mentions an EventBridge rule or trigger, **When** ops checks Terraform, **Then** that trigger exists

---

### User Story 3 - Auditor Verifies Documentation Accuracy (Priority: P2)

A technical auditor or architect reviews the system documentation for accuracy as part of a compliance or quality review. They can verify that the documentation matches implementation without finding contradictions.

**Why this priority**: Documentation accuracy is a quality metric. Contradictions between spec and implementation indicate process failures and reduce trust in the documentation as a source of truth.

**Independent Test**: Can be tested by running automated checks comparing SPEC.md entities against codebase artifacts.

**Acceptance Scenarios**:

1. **Given** an auditor runs a documentation verification check, **When** comparing SPEC.md to Terraform, **Then** all Lambda names, memory sizes, and timeouts match
2. **Given** an auditor reviews data source documentation, **When** comparing to actual API integrations, **Then** documented sources match implemented integrations

---

### Edge Cases

- What happens if legitimate Twitter integration is added in the future? Answer: Add documentation at that time; don't pre-document unimplemented features.
- How does the system handle references to Twitter in comments/historical context? Answer: Remove or convert to "historical note" explaining why it's not implemented.
- What if Quota Reset Lambda is wanted for Tiingo/Finnhub rate limits? Answer: That would be a separate specification; this cleanup removes the incorrect Twitter-specific documentation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SPEC.md MUST NOT contain references to Twitter API, Twitter data sources, Twitter-specific quota management, OR related orphaned terms (monthly_tweets_consumed, quota_exhausted for Twitter, twitter_api_tier, Free/Basic/Pro Twitter tiers)
- **FR-002**: SPEC.md MUST NOT document Lambdas that don't exist in Terraform and src/lambdas/
- **FR-003**: All Lambda specifications in SPEC.md MUST match actual Terraform configurations (memory, timeout, triggers)
- **FR-004**: SPEC.md MUST accurately reflect the actual data sources: Tiingo and Finnhub financial news APIs
- **FR-005**: Any removed documentation MUST be tracked in a "Removed Documentation" section or commit message for historical reference
- **FR-006**: SPEC.md Lambda Configuration section MUST list only implemented Lambdas: Ingestion, Analysis, Dashboard, Metrics, Notification, SSE Streaming
- **FR-007**: Before any edits, a full-document grep scan MUST be performed for: "twitter", "tweets", "quota_reset", "quota-reset", "monthly_tweets", "twitter_api_tier" to build a complete removal manifest
- **FR-008**: All internal cross-references to removed content MUST also be removed (e.g., references to quota-reset-lambda-dlq, Quota Reset Lambda in failure modes, runbooks, or DLQ sections)
- **FR-009**: Changes MUST be made in small atomic commits (one logical section per commit) to enable granular rollback if issues discovered
- **FR-010**: A full audit MUST compare ALL documented features/components in SPEC.md against actual Terraform modules, src/ code, and infrastructure to identify ANY phantom documentation (not just Twitter)
- **FR-011**: Any additional phantom documentation discovered during audit MUST be removed or flagged for removal in the same cleanup effort

### Key Entities

- **SPEC.md**: The primary system specification document that must reflect actual implementation
- **Lambda Configuration Section**: Lines 238-260 of SPEC.md containing Lambda specifications
- **Quota Reset Lambda Documentation**: Lines 245-256 containing Twitter-specific quota reset logic (to be removed)
- **Twitter API Tier Logic**: References to Free/Basic/Pro Twitter tiers that don't apply to this project

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero occurrences of "Twitter", "tweets", "monthly_tweets_consumed", or "twitter_api_tier" in SPEC.md after cleanup (verified by grep)
- **SC-002**: 100% of Lambdas documented in SPEC.md exist in Terraform and have matching configurations
- **SC-003**: New developer can read SPEC.md and correctly identify all 6 actual Lambdas without confusion about phantom components
- **SC-004**: Documentation review time reduced by eliminating need to investigate non-existent components (estimated 2+ hours saved per new team member)
- **SC-005**: All Lambda memory/timeout specifications in SPEC.md match Terraform within 5 minutes of verification
- **SC-006**: Full audit report documents every SPEC.md component checked against codebase with pass/fail status
- **SC-007**: Zero phantom features remain in SPEC.md after cleanup (all documented components exist in code)

## Clarifications

### Session 2026-01-31

- Q: Should removal target only literal "Twitter" or entire related sections? → A: Remove entire Quota Reset Lambda section + all Twitter-related fields/logic (tweets, quota tiers, monthly_tweets_consumed, etc.)
- Q: How to discover all orphaned content beyond known sections? → A: Full-document grep scan for Twitter-related terms before cleanup to build complete removal list
- Q: How to handle internal cross-references to removed content? → A: Remove orphaned sections AND all references to them (search for section names, DLQ names like quota-reset-lambda-dlq, Lambda names)
- Q: What verification/rollback strategy for large documentation edits? → A: Small atomic commits (one section per commit) for granular rollback and clear audit trail
- Q: Should scope expand beyond Twitter to find other phantom documentation? → A: Full documentation audit comparing SPEC.md against entire codebase for any inconsistencies

## Assumptions

- The sentiment-analyzer-gsk project uses Tiingo and Finnhub as its only external data sources
- Twitter integration was never implemented in this project (documentation was copied from another project)
- The Quota Reset Lambda documentation describes functionality for a different project and should be removed entirely
- If rate limiting is needed for Tiingo/Finnhub, it will be specified in a separate feature specification
- The recent PR #681 updates (Analysis Lambda memory fix, 4 new Lambda entries) are correct and should be preserved

## Out of Scope

- Implementing actual rate limiting for Tiingo/Finnhub APIs (separate feature if needed)
- Adding new Lambda functionality
- Modifying Terraform or Lambda code (documentation-only changes)
- Adding new documentation for undocumented features (audit identifies gaps but separate work to fill them)

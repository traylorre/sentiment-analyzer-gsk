# Feature Specification: Canonical Source Verification & Cognitive Discipline

**Feature Branch**: `018-canonical-source-verification`
**Created**: 2025-12-03
**Status**: Complete
**Input**: User description: "Constitution Amendment 1.5: Canonical Source Verification and Cognitive Discipline methodology for troubleshooting external system behaviors"

## Problem Statement

When troubleshooting external system behaviors (AWS IAM permissions, API behaviors, library functions), developers may short-circuit to incorrect solutions due to cognitive biases. The ASTERIX1 incident revealed that 3 out of 4 IAM permission "fixes" were incorrect because canonical sources were not consulted before proposing solutions.

**Root Causes Identified**:
1. Time pressure led to shortcuts ("make it work" over "make it right")
2. Pattern matching was applied universally without verification
3. Confirmation bias reversed causality (assumed solution before investigation)
4. No verification gate existed to catch violations

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Consults Canonical Source Before Fix (Priority: P1)

A developer encounters an AWS IAM permission error during CI pipeline execution. Before proposing any fix, they must consult the AWS Service Authorization Reference to verify whether the action supports resource-level permissions, what resources are required vs optional, and what condition keys are available.

**Why this priority**: This is the core behavior change. Without canonical source verification, all other safeguards are bypassed.

**Independent Test**: Can be tested by reviewing any PR that modifies IAM policies - the PR description must cite the canonical source consulted.

**Acceptance Scenarios**:

1. **Given** a developer sees "AccessDenied" for `logs:DescribeLogGroups`, **When** they research the fix, **Then** they must check the AWS Service Authorization Reference to verify resource-level permission support before proposing wildcard or scoped solution.

2. **Given** a developer proposes an IAM policy change, **When** they create a PR, **Then** the PR template requires a "Canonical Sources Cited" section that cannot be empty.

3. **Given** a canonical source indicates an action requires `*` resource (empty Resource types column), **When** the developer uses wildcard, **Then** this is documented as "verified wildcard required per [source link]".

---

### User Story 2 - Gatekeeper Validates Source Citations (Priority: P2)

A code reviewer (human or automated) validates that canonical sources were consulted and correctly interpreted. The gatekeeper catches violations that slipped past the developer's own verification.

**Why this priority**: Defense in depth - even if a developer skips verification, the gate catches it.

**Independent Test**: Can be tested by submitting a PR without source citations and verifying it is flagged for revision.

**Acceptance Scenarios**:

1. **Given** a PR modifies external system configurations (IAM, API integrations, library usage), **When** the PR lacks canonical source citations, **Then** the reviewer requests citations before approval.

2. **Given** a PR cites a canonical source, **When** the reviewer checks the citation, **Then** they verify the source supports the proposed change (not just that a source was cited).

3. **Given** a PR proposes a wildcard permission, **When** the canonical source shows resource-level permissions ARE supported, **Then** the PR is rejected with guidance to use scoped permissions.

---

### User Story 3 - Constitution Amendment Enshrines Cognitive Discipline (Priority: P1)

The project constitution is amended to enshrine four cognitive anti-patterns as absolute rules, preventing drift from methodology.

**Why this priority**: Equal to P1 because the amendment creates the enforceable policy that US1 and US2 implement.

**Independent Test**: Can be tested by reading the constitution and verifying Amendment 1.5 exists with all four principles.

**Acceptance Scenarios**:

1. **Given** the constitution exists, **When** Amendment 1.5 is added, **Then** it contains all four cognitive discipline principles:
   - "Do Not Succumb under Time Pressure"
   - "Methodology over Heuristics"
   - "Question ALL Confirmation Bias Results"
   - "Gatekeeper Seals Verification"

2. **Given** a developer faces time pressure to fix a failing pipeline, **When** they consider skipping verification, **Then** the constitution explicitly prohibits this ("accuracy/precision/consistency over speed").

3. **Given** a developer recognizes a familiar pattern, **When** they consider applying a heuristic, **Then** the constitution requires methodology as "final word" over heuristics.

---

### User Story 4 - PR Template Includes Active Verification Gate (Priority: P2)

The PR template includes an active checklist item requiring canonical source citation for any change that makes claims about external system behavior.

**Why this priority**: Automation of the gate reduces human error in enforcement.

**Independent Test**: Can be tested by creating a PR and verifying the template includes the citation checklist.

**Acceptance Scenarios**:

1. **Given** a developer creates a PR, **When** the PR modifies IAM policies, API integrations, or external library usage, **Then** the PR template includes: "[ ] Cited canonical source for external system behavior claims".

2. **Given** the PR template checklist item exists, **When** a developer checks it without adding citations, **Then** reviewers can identify the discrepancy.

---

### User Story 5 - Taxonomy Stubs Created for Future Formalization (Priority: P3)

Minimal stubs are added to the testing taxonomy for future formalization of canonical source verification as a testable concern.

**Why this priority**: Scaffolding for future work; not blocking for current implementation.

**Independent Test**: Can be tested by checking taxonomy registry for stub entries.

**Acceptance Scenarios**:

1. **Given** the taxonomy registry exists, **When** this feature is implemented, **Then** minimal stubs are added for:
   - Concern: `canonical_source_verification`
   - Property: `external_behavior_claims_cited`
   - Validator: `canonical_source_citation_validator`

2. **Given** stubs are created, **When** their status is checked, **Then** status is `stub` with TODO notes for future `/speckit.specify`.

---

### Edge Cases

- What happens when no canonical source exists for an external system? Document the gap and escalate for team decision.
- How does system handle conflicting canonical sources? Prefer official vendor documentation over community sources.
- What if canonical source is outdated? Note the date checked and document any discrepancies observed in practice.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Constitution MUST be amended with section "10) Canonical Source Verification & Cognitive Discipline" containing Amendment 1.5
- **FR-002**: Amendment MUST enshrine four cognitive anti-patterns as absolute rules with clear rationale for each
- **FR-003**: PR template MUST include active checklist item: "[ ] Cited canonical source for external system behavior claims (IAM, APIs, libraries)"
- **FR-004**: PR descriptions for external system changes MUST include "Canonical Sources Cited" section
- **FR-005**: Taxonomy registry MUST include minimal stubs for `canonical_source_verification` concern, `external_behavior_claims_cited` property, and `canonical_source_citation_validator` validator with status `stub`
- **FR-006**: Documentation MUST define "canonical source" for common external systems:
  - AWS: Service Authorization Reference (`docs.aws.amazon.com/service-authorization/latest/reference/`)
  - GCP: IAM permissions reference
  - Azure: RBAC documentation
  - Libraries: Official documentation or source code
  - APIs: OpenAPI specs or official API documentation

### Non-Functional Requirements

- **NFR-001**: Amendment text MUST be clear enough for non-native English speakers
- **NFR-002**: Checklist item MUST be actionable (developer knows what to do)
- **NFR-003**: Taxonomy stubs MUST follow existing registry format exactly

### Key Entities

- **Constitution Amendment**: Addition to `.specify/memory/constitution.md` with version bump to 1.5
- **PR Template**: Modification to `.github/PULL_REQUEST_TEMPLATE.md` (or creation if not exists)
- **Taxonomy Stubs**: Entries in `.specify/testing/taxonomy-registry.yaml`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of PRs modifying IAM policies include canonical source citations within 30 days of implementation
- **SC-002**: Zero wildcard permissions are added without documented canonical source verification showing wildcard is required
- **SC-003**: Constitution Amendment 1.5 is ratified and version number updated
- **SC-004**: PR template includes active gate checklist item
- **SC-005**: Taxonomy registry contains all three stub entries with correct status

## Assumptions

- The existing constitution format supports adding new top-level sections
- PR template mechanism exists or can be created in `.github/`
- Taxonomy registry YAML format is stable and documented
- Developers have access to canonical sources (AWS docs, etc.) during development

## Dependencies

- Depends on: Existing constitution structure (v1.4)
- Depends on: Existing taxonomy registry format
- Blocks: ASTERIX1 fix in target repo (must apply methodology first)
- Related: CROSSREPO1 (deferred - cross-repo audit/propagation mechanism)
- Related: TAXGAP1 (stubs created here, full formalization in future spec)

## Out of Scope

- Automated canonical source lookup/validation tooling
- Cross-repo propagation mechanism (deferred to CROSSREPO1)
- Full taxonomy formalization beyond stubs (deferred to TAXGAP1)
- Retroactive audit of existing PRs

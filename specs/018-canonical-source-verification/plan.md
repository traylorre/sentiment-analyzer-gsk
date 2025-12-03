# Implementation Plan: Canonical Source Verification & Cognitive Discipline

**Branch**: `018-canonical-source-verification` | **Date**: 2025-12-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-canonical-source-verification/spec.md`

## Summary

This feature adds Constitution Amendment 1.5 establishing cognitive discipline principles for troubleshooting external system behaviors. It enshrines four anti-patterns (time pressure shortcuts, heuristic over methodology, confirmation bias, missing verification gates) as absolute rules. Implementation includes updating the constitution, PR template, and taxonomy registry with minimal stubs.

**Technical Approach**: Pure documentation and configuration changes - no application code. Modifies markdown files, YAML registry, and GitHub templates.

## Technical Context

**Language/Version**: N/A (documentation/configuration only)
**Primary Dependencies**: N/A
**Storage**: N/A
**Testing**: Manual review + checklist validation
**Target Platform**: GitHub repository (documentation, templates)
**Project Type**: Documentation/Process
**Performance Goals**: N/A
**Constraints**: Must follow existing constitution format (v1.4), taxonomy YAML schema
**Scale/Scope**: 3 files modified/created

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| No secrets in source control | ✅ PASS | No secrets involved |
| GPG-signed commits | ✅ PASS | Standard workflow applies |
| Feature branch workflow | ✅ PASS | On `018-canonical-source-verification` |
| Tests accompany implementation | ⚠️ N/A | Documentation feature - checklist validation instead |
| Pipeline checks required | ✅ PASS | Will go through normal PR process |
| No pipeline bypass | ✅ PASS | Will merge via standard PR |

**Gate Result**: PASS - All applicable gates satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/018-canonical-source-verification/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 output (minimal - no unknowns)
├── checklists/
│   └── requirements.md  # Validation checklist (complete)
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Files Modified (repository root)

```text
.specify/
├── memory/
│   └── constitution.md          # ADD: Section 10 + Amendment 1.5
└── testing/
    └── taxonomy-registry.yaml   # ADD: 3 stub entries (TAXGAP1)

.github/
└── PULL_REQUEST_TEMPLATE.md     # ADD: Canonical source citation checklist
```

**Structure Decision**: This is a pure documentation/configuration feature. No source code changes. All modifications are to existing process/governance files.

## Complexity Tracking

No constitution violations to justify - this feature strengthens the constitution rather than violating it.

## Phase 0: Research

### Unknowns Analysis

No technical unknowns - this is a process/documentation feature. All decisions are made:

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Constitution section number | 10 | Next available after section 9 (Tech Debt Tracking) |
| Amendment version | 1.5 | Next after Amendment 1.4 |
| Taxonomy stub status | `stub` | Per spec FR-005, minimal stubs for future formalization |
| PR template location | `.github/PULL_REQUEST_TEMPLATE.md` | GitHub standard location |

### Research Output

No external research needed. All patterns follow existing repository conventions.

## Phase 1: Design

### Entities

| Entity | Location | Changes |
|--------|----------|---------|
| Constitution | `.specify/memory/constitution.md` | Add section 10, Amendment 1.5, bump version |
| PR Template | `.github/PULL_REQUEST_TEMPLATE.md` | Add canonical source citation checklist |
| Taxonomy Registry | `.specify/testing/taxonomy-registry.yaml` | Add 3 stub entries |

### Constitution Amendment 1.5 Content

```markdown
10) Canonical Source Verification & Cognitive Discipline

   Cognitive Anti-Patterns (ABSOLUTE RULES)
   -----------------------------------------
   When troubleshooting external system behaviors (AWS IAM, APIs, libraries),
   developers MUST avoid these cognitive traps:

   a) Do Not Succumb under Time Pressure
      - Accuracy, precision, and consistency take priority over speed
      - A failing pipeline is NOT an excuse to skip verification
      - "Make it work" is NOT acceptable without "make it right"

   b) Methodology over Heuristics
      - This repository's methodology is the final word
      - Pattern matching ("list operations need wildcard") is NOT verification
      - Familiar patterns require the same verification as unfamiliar ones

   c) Question ALL Confirmation Bias Results
      - "some A → some B" does NOT mean "all B ← A"
      - Finding evidence that supports your assumption is NOT verification
      - Actively seek evidence that REFUTES your assumption

   d) Gatekeeper Seals Verification
      - Defense in depth: reviewers catch violations that slipped past
      - PR template requires canonical source citations
      - Reviewers MUST verify citations support the proposed change

   Canonical Source Requirements
   -----------------------------
   Before proposing ANY change to external system configurations:

   1. IDENTIFY the specific action/behavior being modified
   2. CONSULT the canonical source for that external system:
      - AWS: Service Authorization Reference (docs.aws.amazon.com/service-authorization/)
      - GCP: IAM permissions reference
      - Azure: RBAC documentation
      - Libraries: Official documentation or source code
      - APIs: OpenAPI specs or official API documentation
   3. VERIFY the source supports your proposed change
   4. CITE the source in your PR description
   5. DOCUMENT any wildcards as "verified required per [source link]"

   Verification Gate (PR Template)
   -------------------------------
   All PRs modifying external system configurations MUST include:
   - [ ] Cited canonical source for external system behavior claims
   - Canonical Sources Cited section with links and verification notes

Amendment 1.5 (2025-12-03): Added Canonical Source Verification & Cognitive Discipline
section establishing four cognitive anti-patterns as absolute rules for troubleshooting
external system behaviors. Requires canonical source citation for IAM, API, and library
changes. Adds PR template verification gate.
```

### PR Template Addition

```markdown
## Canonical Sources Cited

<!-- Required for PRs that modify IAM policies, API integrations, or external library usage -->
<!-- Format: [Action/Behavior] - [Source Link] - [Verification Notes] -->

- [ ] Cited canonical source for external system behavior claims (IAM, APIs, libraries)
```

### Taxonomy Stubs (TAXGAP1)

```yaml
# Under concerns:
canonical_source_verification:
  display_name: "Canonical Source Verification"
  description: "Verify external system behavior claims against authoritative documentation"
  status: stub
  todo: "Full formalization in future /speckit.specify"

# Under properties:
external_behavior_claims_cited:
  display_name: "External Behavior Claims Cited"
  description: "All claims about external system behavior must cite canonical sources"
  concerns:
    - canonical_source_verification
  status: stub
  todo: "Full formalization in future /speckit.specify"

# Under validators:
canonical_source_citation_validator:
  display_name: "Canonical Source Citation Validator"
  description: "Validates that PRs include canonical source citations for external system changes"
  properties:
    - external_behavior_claims_cited
  status: stub
  todo: "Full formalization in future /speckit.specify"
```

## Phase 2: Task Decomposition

Deferred to `/speckit.tasks` command.

## Artifacts Generated

| Artifact | Status | Path |
|----------|--------|------|
| spec.md | ✅ Complete | `specs/018-canonical-source-verification/spec.md` |
| plan.md | ✅ Complete | `specs/018-canonical-source-verification/plan.md` |
| research.md | ⏭️ Skipped | No unknowns to research |
| data-model.md | ⏭️ Skipped | No data entities |
| contracts/ | ⏭️ Skipped | No APIs |
| quickstart.md | ⏭️ Skipped | Not applicable |
| tasks.md | ⏳ Pending | Via `/speckit.tasks` |

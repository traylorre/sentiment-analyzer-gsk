# Specification Quality Checklist: Close py/bad-tag-filter and Kill the Dead Suppression

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-30
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- This is a tooling and security-hygiene feature, so "non-technical stakeholder" is
  read as "a reviewer who does not know this codebase". Rule identifiers, file roles,
  and check names are described by function rather than by symbol where possible.
- Success criteria are stated as observable states and counts (alert state, match
  counts, exit codes, mismatch counts) rather than as commands to run, keeping them
  verifiable without prescribing implementation.
- The highest-risk requirement is FR-003. The obvious rewrite is subtly non-equivalent
  on exotic line separators; this was confirmed empirically during specification, not
  assumed. FR-001 and SC-003 exist to force that equivalence to be proven at
  implementation time rather than trusted.
- The key design call is FR-012 with FR-015: pre-existing findings surfaced by the
  widened path set land in an advisory check that cannot fail the build, so no
  baseline or grandfathering mechanism is required.

## Adversarial Review #1 (2026-07-30)

An independent reviewer falsified three of the items ticked above against the initial
draft. All three now pass against the revised spec; the ticks are retained but the
history is recorded here rather than erased.

- **"Success criteria are measurable"** failed on two counts. SC-004 required a
  tree-wide marker scan to return matches only inside the auditor, but the spec file
  itself contained fifteen marker occurrences at the moment it was written, so the
  criterion could never reach its stated state (F2). SC-009 required an existing test
  suite for the diagram script to pass unchanged; no such suite exists anywhere in the
  repository (F3). Both criteria rewritten.
- **"Requirements are testable and unambiguous"** failed on FR-008 through FR-015,
  which specified behaviour for a target that no automated process invokes: not a
  prerequisite of the aggregate validation target, absent from every workflow, absent
  from the commit hooks, and with its security-linter half structurally unable to fail
  (F1, CRITICAL). Every requirement in that block was satisfiable without the check
  ever running against a change under review. Resolved by FR-018, FR-019, SC-011,
  SC-012, and a new US3 acceptance scenario measuring an observed check result.
- **"Edge cases are identified"** failed on the trailing-whitespace character class
  (F5). The draft's most-emphasised edge case was the line-separator divergence, and
  the identical trap one level down, where a narrowed trim set disagrees with the
  original expression's whitespace class, was not covered. FR-003 now constrains both.

Full findings table, severity counts, and the reproduction method for every claim are
in the spec's own Adversarial Review #1 section. Gate: 0 CRITICAL, 0 HIGH remaining.

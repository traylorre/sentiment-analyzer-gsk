# Specification Quality Checklist: Stop Ingestion Handler Logging Secret ARNs

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

- CodeQL, GitHub, the rule id `py/clear-text-logging-sensitive-data` and the alert numbers 148,
  149 and 150 are named plainly throughout. That matches existing repository convention: 20 spec
  files under `specs/` already say CodeQL and 168 say GitHub, and the sibling spec
  `001-oauth-provider-taint/spec.md` opens with "Close CodeQL alert 144". These are the
  vocabulary of the problem being solved, not leaked implementation detail.
- SC-002 names the `refs/heads` branch analysis and the GitHub code scanning alerts API as the
  evidence source rather than a pull request check. This is a deliberate verification constraint:
  CodeQL runs diff-informed analysis on pull requests in this repository, and PR #990 was green
  with five alerts open.
- SC-002 is keyed to the file path plus the rule id, never to alert numbers 148, 149 and 150.
  Adversarial Review #1 established that the engine can close those three and open fresh numbers
  at the same path in the same run, so a number-keyed criterion was satisfiable while the
  disclosure persisted. SC-002a adds the companion constraint that `fixed_at` is the field that
  proves repair, because `state` conflates dismissal with repair.
- Two candidate code shapes exist in the repository's own history for this rule. FR-004 selects
  the strip from context shape, cites both commits by SHA, and goes one step stricter by
  excluding the exception message as well. FR-003 correspondingly forbids calling the existing
  sanitizer from these three sites, because the source identity here is statically known at the
  call site and no sanitized value is needed. Choosing between the shapes is not an open question.
- FR-013 locks file scope to the ingestion handler, its tests, and this feature's own
  `specs/001-ingestion-arn-logging/` directory (the directory carve-out was added by Clarification
  Q4, so that FR-011's convention artifact and FR-008a's handoff artifact are writable).
  `src/lambdas/shared/secrets.py`
  is explicitly off limits, since four dismissed alerts on that file still carry a null
  `fixed_at` and editing those lines risks re-fingerprinting them into fresh open alerts.
- Adversarial Review #1 is recorded at the end of spec.md: 1 CRITICAL, 7 HIGH, 3 MEDIUM resolved
  by edit; 2 LOW carded. Gate is 0 CRITICAL, 0 HIGH remaining.

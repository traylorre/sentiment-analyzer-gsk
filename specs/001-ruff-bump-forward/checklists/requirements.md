# Specification Quality Checklist: Ruff Bump-Forward (One Version Everywhere)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-29
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — *waived with justification: this is a toolchain-configuration feature; the "users" are contributors and the "system" is the lint pipeline. File paths, versions, and commands ARE the domain objects, exactly as in the sibling semgrep-gating spec. No application implementation details leak in.*
- [x] Focused on user value and business needs — contributor workflow (no churn, no CI surprise) and gate integrity.
- [x] Written for non-technical stakeholders — *waived to the same degree as sibling specs: the stakeholder for a linter-version feature is a developer by definition; prose explains why each surface matters rather than assuming it.*
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous — each FR names exact files, versions, and exit-code checks
- [x] Success criteria are measurable — grep counts, exit codes, gate passes, tree cleanliness
- [x] Success criteria are technology-agnostic (no implementation details) — *partially waived: SC-001/SC-005 name the tool because the feature IS the tool version; phrased as observable outcomes (grep result, config diff) rather than mechanisms.*
- [x] All acceptance scenarios are defined — 3 stories, 8 scenarios
- [x] Edge cases are identified — hook id rename, rule renames, reformat blast radius, pragma preservation, --fix divergence, surface-5 verification
- [x] Scope is clearly bounded — Out of Scope section: no rule-set changes, no other tools, no upgrade automation
- [x] Dependencies and assumptions identified — Assumptions section; battleplan-level merge ordering noted

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows — local format/CI accept, drift enforcement, finding triage
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification — *same waiver as Content Quality item 1*

## Notes

- Validation run 2026-07-29 (initial): all items pass, three with explicit waivers inherent to toolchain-configuration features (consistent with 001-semgrep-gating precedent).
- AR#1 (agent aef0c1895ca54127c, 2026-07-29) falsified two checked items as of the initial draft: "Requirements are testable and unambiguous" (F1 SC-001 failing grep, F4 broken audit-pragma acceptance gate, F11 unverifiable FR-005) and "Edge cases are identified" (F2 CI pre-commit gate, F6 dependabot channel, F7 autoupdate footgun, F8 legacy hook). All 12 findings applied to the spec (see spec Appendix); both items re-validated as passing post-edit.
- The ruff-pre-commit tag question deferred to planning in the initial draft was answered empirically by AR#1 (tag v0.15.14 exists, `ruff` id is a legacy alias) and folded into the spec as fact.

# Data Model: Remove tfsec from the Security Validation Chain

**Feature**: 001-tfsec-removal | **Date**: 2026-07-29

This feature touches no data. No entities, no storage, no state transitions.

The only "model" is the classification taxonomy the spec defines for documents, reproduced here because tasks and verification depend on it:

| Class | Definition | Treatment |
|-------|-----------|-----------|
| Living process doc | Describes current contributor-facing process (CONTRIBUTING.md, SPEC.md) | Corrected in this feature |
| Governance doc | `.specify/memory/constitution.md` | Frozen; follow-up amendment recorded |
| Historical rationale | Comments explaining past removals (`.pre-commit-config.yaml:67-69`) | Retained verbatim |
| Archive / audit record | `docs/archived-specs/**`, `docs/reviews/**`, `docs/cleanup-pristine/**`, dated board-card verification text | Byte-identical freeze |
| Cross-spec scope note | `specs/1400-validator-gating/spec.md:105` | Untouched |
| Working board | `CLEANUP-BOARD.html` | tfsec card lane move at completion (FR-007) |

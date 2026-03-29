# Implementation Plan: Bidirectional Validation for Target Repos

**Branch**: `055-target-bidirectional` | **Date**: 2025-12-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/055-target-bidirectional/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Enable BidirectionalValidator to work on target repositories that have specification files but no `make test-bidirectional` target. The validator uses intrinsic detection to find `specs/*/spec.md` files and performs semantic comparison against corresponding code implementations. Implementation logic remains in the template repo (secret sauce), while target repos optionally add thin make targets for customization.

## Technical Context

**Language/Version**: Python 3.13 (existing template standard)
**Primary Dependencies**: pydantic (existing models), PyYAML (existing), anthropic (existing for Claude API), pathlib (stdlib)
**Storage**: N/A (file-based validation, no persistent storage)
**Testing**: pytest 8.0+ with existing test infrastructure
**Target Platform**: Linux CLI (template validation tooling)
**Project Type**: Single project (extends existing `src/validators/` module)
**Performance Goals**: < 30 seconds for typical repo with < 50 spec files
**Constraints**: Must work offline when Claude API unavailable (graceful degradation)
**Scale/Scope**: Target repos with 1-100 spec files, each < 500 lines

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                                | Status  | Notes                                                                     |
| ---------------------------------------- | ------- | ------------------------------------------------------------------------- |
| Zero-touch development                   | ✅ PASS | Validator runs automatically via `/validate`                              |
| Context efficiency                       | ✅ PASS | Semantic comparison delegated to Claude API, returns summary not raw data |
| Cost sensitivity                         | ✅ PASS | No new AWS resources, Claude API usage per-validation only                |
| Parallel-safe                            | ✅ PASS | Stateless file-based validation, no git conflicts                         |
| Amendment 1.5 (Canonical Sources)        | ✅ PASS | Will cite semantic comparison methodology docs                            |
| Amendment 1.6 (No Quick Fixes)           | ✅ PASS | Full spec workflow completed                                              |
| Amendment 1.7 (Target Repo Independence) | ✅ PASS | This feature ENABLES Amendment 1.7 compliance via intrinsic detection     |

**Gate Result**: PASS - All constitution principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/055-target-bidirectional/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # N/A - internal validator, no API
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/validators/
├── verification.py      # MODIFY - Add intrinsic detection to BidirectionalValidator
├── bidirectional/       # NEW - Semantic comparison module
│   ├── __init__.py
│   ├── detector.py      # Spec file detection and parsing
│   ├── mapper.py        # Spec-to-code path mapping
│   ├── comparator.py    # Semantic comparison logic (Claude API)
│   └── models.py        # Pydantic models for spec-code alignment
├── base.py              # Existing - no changes
└── models.py            # MODIFY - Add BIDIR-XXX finding types

tests/
├── unit/
│   ├── test_bidirectional_detector.py    # NEW
│   ├── test_bidirectional_mapper.py      # NEW
│   └── test_bidirectional_comparator.py  # NEW
└── fixtures/
    └── bidirectional/                     # NEW - Test fixtures
        ├── aligned/                       # Spec-code pairs that match
        └── misaligned/                    # Spec-code pairs with drift
```

**Structure Decision**: Single project extending existing `src/validators/` module. New `bidirectional/` submodule encapsulates semantic comparison logic (the "secret sauce") while `verification.py` remains the entry point that delegates to it for target repos.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations. All gates passed.

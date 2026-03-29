# Implementation Plan: IAM Allowlist V2 - VALIDATE2 Remediation

**Branch**: `045-iam-allowlist-v2` | **Date**: 2025-12-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/045-iam-allowlist-v2/spec.md`

## Summary

Integrate IAM allowlist consumption into validators to suppress documented acceptable risks. The existing `iam-allowlist.yaml` in target repo documents legitimate CI/CD patterns (LAMBDA-007, LAMBDA-011, SQS-009) but validators don't consume it. This plan adds allowlist loading and context-aware suppression to reduce VALIDATE2 findings from 5 CRITICAL / 5 HIGH to 0 CRITICAL / ≤2 HIGH.

## Technical Context

**Language/Version**: Python 3.11 (existing project standard)
**Primary Dependencies**: PyYAML (existing), pydantic (existing validator models), IAMContextAnalyzer (036 infrastructure)
**Storage**: YAML files (iam-allowlist.yaml), Python source modules
**Testing**: pytest with existing test infrastructure
**Target Platform**: Linux (CI/CD pipelines)
**Project Type**: Single project (template repo with validators)
**Performance Goals**: N/A (static analysis, not performance critical)
**Constraints**: Must maintain backward compatibility with repos without allowlist
**Scale/Scope**: ~10 validators, ~3 validators to modify

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                                     | Status | Notes                                                              |
| --------------------------------------------- | ------ | ------------------------------------------------------------------ |
| Zero-touch development                        | PASS   | Allowlist enables automated suppression without human intervention |
| Context efficiency                            | PASS   | Allowlist loaded once, checked in-memory                           |
| Cost sensitivity                              | PASS   | No new AWS resources, file-based scanning only                     |
| Parallel-safe                                 | PASS   | Read-only allowlist access, no write conflicts                     |
| Canonical source verification (Amendment 1.5) | PASS   | Allowlist requires canonical_source field for suppression          |
| Agent delegation                              | N/A    | Implementation is self-contained code changes                      |

**Gate Result**: PASS - No violations

## Project Structure

### Documentation (this feature)

```text
specs/045-iam-allowlist-v2/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── checklists/
    └── requirements.md  # Specification checklist
```

### Source Code (repository root)

```text
src/validators/
├── iam_allowlist.py         # NEW: IAM allowlist loader + matcher
├── lambda_iam.py            # MODIFY: Add allowlist integration
├── sqs_iam.py               # MODIFY: Add allowlist integration
├── models.py                # MODIFY: Add SUPPRESSED status if missing
└── base.py                  # No changes needed

tests/unit/
├── test_iam_allowlist.py    # NEW: Unit tests for allowlist loader
├── test_lambda_iam_allowlist.py  # NEW: Integration tests
└── test_sqs_iam_allowlist.py     # NEW: Integration tests
```

**Structure Decision**: Single project structure with new module `iam_allowlist.py` for allowlist loading. Validators import and use the loader.

## Complexity Tracking

No constitution violations - table not required.

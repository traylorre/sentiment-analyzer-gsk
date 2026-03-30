# Implementation Plan: Validation Finding Remediation

**Branch**: `049-validate-remediation` | **Date**: 2025-12-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/049-validate-remediation/spec.md`

## Summary

Remediate validation findings from /validate run on sentiment-analyzer-gsk by:

1. Fixing pytest conftest import errors in property tests (FR-001, FR-002)
2. Enhancing SQS IAM validator environment detection for CI policies (FR-003, FR-004)
3. Adding Deny statement effect awareness to IAM validator (FR-005, FR-006)

## Technical Context

**Language/Version**: Python 3.11 (existing project standard)
**Primary Dependencies**: PyYAML (existing), pydantic (existing validator models), pytest (existing)
**Storage**: N/A (file-based scanning)
**Testing**: pytest, unit tests in `tests/unit/`
**Target Platform**: Linux/macOS (CLI tools)
**Project Type**: single (template methodology validators)
**Performance Goals**: N/A (correctness over speed for validators)
**Constraints**: Maintain backward compatibility with existing allowlist format
**Scale/Scope**: 3 validator files, 1 test directory in target repo

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate                              | Status | Notes                                                 |
| --------------------------------- | ------ | ----------------------------------------------------- |
| Zero-touch development            | PASS   | No manual intervention needed beyond running commands |
| Context efficiency                | PASS   | Changes localized to validator modules                |
| Cost sensitivity                  | N/A    | No AWS resource changes                               |
| Amendment 1.5 (Canonical Sources) | PASS   | All fixes based on official pytest/AWS docs           |
| Amendment 1.6 (No Quick Fixes)    | PASS   | Full /speckit workflow followed                       |

## Project Structure

### Documentation (this feature)

```text
specs/049-validate-remediation/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# Template repo (terraform-gsk-template)
src/validators/
├── iam.py               # FR-005, FR-006: Add Deny statement awareness
├── iam_allowlist.py     # FR-004: Enhance environment detection
└── sqs_iam.py           # FR-003: Uses iam_allowlist.py

# Target repo (sentiment-analyzer-gsk)
tests/property/
├── conftest.py          # FR-001: Already correct
├── test_lambda_handlers.py  # FR-001: Fix import pattern
├── test_api_contracts.py    # FR-001: Fix import pattern
└── test_infrastructure.py   # FR-001: Fix import pattern
```

**Structure Decision**: Single project structure - validators are in `src/validators/`, tests in `tests/unit/`

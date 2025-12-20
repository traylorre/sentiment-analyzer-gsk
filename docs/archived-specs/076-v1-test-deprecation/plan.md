# Implementation Plan: Deprecate v1 API Integration Tests

**Branch**: `076-v1-test-deprecation` | **Date**: 2025-12-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/076-v1-test-deprecation/spec.md`

## Summary

Audit 21 skipped v1 API integration tests in `tests/integration/test_dashboard_preprod.py` to determine v2 equivalence, then remove tests with confirmed equivalents and update documentation. This is primarily a research/audit feature with no new production code.

## Technical Context

**Language/Version**: N/A (test file deletion and documentation only)
**Primary Dependencies**: pytest (existing)
**Storage**: N/A
**Testing**: pytest --collect-only (to verify skip count changes)
**Target Platform**: N/A (development tooling only)
**Project Type**: single
**Performance Goals**: N/A
**Constraints**: Must not reduce actual test behavior coverage
**Scale/Scope**: 21 skipped tests to audit, 1 file to modify

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Implementation Accompaniment Rule | N/A | No new implementation code |
| Unit Test Coverage (80%) | N/A | Removing tests, not adding code |
| Pipeline Bypass Prohibition | PASS | Normal PR workflow applies |
| GPG Signing | PASS | All commits will be signed |
| Tech Debt Tracking | N/A | No new tech debt introduced |
| Local SAST | PASS | Will run make validate before push |

**Result**: All applicable gates PASS. No constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/076-v1-test-deprecation/
├── plan.md              # This file
├── research.md          # Phase 0: v1/v2 test mapping research
├── audit.md             # Deliverable: Full audit traceability matrix
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
tests/
├── integration/
│   └── test_dashboard_preprod.py  # Target file (21 skipped tests to remove)
└── e2e/
    └── *.py                       # v2 test suite (reference for audit)

RESULT1-validation-gaps.md         # Documentation to update
```

**Structure Decision**: Single project structure. No new source files created. Feature modifies existing test file and documentation.

## Complexity Tracking

No constitution violations to justify.

## Phase 0: Research - v1 to v2 Test Mapping

### Research Tasks

1. **Extract all 21 v1 skipped tests**: List each test function name from `tests/integration/test_dashboard_preprod.py` with "v1 API deprecated" skip reason

2. **Inventory v2 test coverage**: Catalog all test functions in `tests/e2e/` directory with their tested behaviors

3. **Map v1 behaviors to v2 equivalents**: For each v1 test, determine:
   - What behavior does this test validate?
   - Does a v2 test cover the same behavior?
   - If no equivalent, is the behavior deprecated or is this a coverage gap?

### Output: research.md

Research findings will be consolidated into `research.md` with the format:
- Each v1 test listed with its behavior description
- Mapping to v2 equivalent (file:function) or deprecation rationale
- Coverage gaps flagged for follow-up

## Phase 1: Design - Audit Document

### Audit Document Structure (audit.md)

The audit document will serve as the permanent traceability record:

```markdown
# v1 API Test Deprecation Audit

| v1 Test | Behavior | Category | v2 Equivalent | Notes |
|---------|----------|----------|---------------|-------|
| test_X  | Validates Y | equivalent | tests/e2e/test_Z.py::test_Z | Same behavior |
| test_A  | Validates B | deprecated | N/A | Feature removed in v2 |
| test_C  | Validates D | gap | N/A | Needs v2 test (future) |
```

Categories:
- **equivalent**: v2 test covers the same behavior
- **deprecated**: Feature intentionally removed in v2
- **gap**: Coverage gap identified (out of scope to fix)

### Data Model

No new data model required - this is a documentation/audit feature.

### Contracts

No API contracts - this feature only removes tests and updates documentation.

## Decision Log

| Decision | Rationale | Alternatives Rejected |
|----------|-----------|----------------------|
| Remove entire test functions | Tests are marked as deprecated, not temporarily skipped | Unskipping tests (v1 API doesn't exist) |
| Create audit.md as permanent record | Traceability for future reference | Inline comments (less discoverable) |
| Flag gaps but don't fix | Stay within scope; gaps are separate features | Creating v2 tests in this PR |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Remove test with no v2 coverage | Low | Medium | Audit phase verifies coverage before removal |
| Miss a v1 test in audit | Low | Low | grep for all "v1 API deprecated" strings |
| Audit document incomplete | Low | Medium | Structured audit template ensures completeness |

## Next Steps

1. Run `/speckit.tasks` to generate task breakdown
2. Execute Phase 0 (research.md) - enumerate v1 tests and map to v2
3. Execute Phase 1 (audit.md) - create permanent audit record
4. Remove tests with documented justification
5. Update RESULT1-validation-gaps.md

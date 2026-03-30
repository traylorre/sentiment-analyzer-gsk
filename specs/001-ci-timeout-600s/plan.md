# Implementation Plan: Increase Playwright CI Timeout to 600s

**Branch**: `001-ci-timeout-600s` | **Date**: 2026-03-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-ci-timeout-600s/spec.md`

## Summary

Increase the Playwright suite-level timeout from 300s to 600s, make it configurable via parameter with a 1800s max ceiling, and update the API contract documentation. Three files modified, no new dependencies.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: subprocess (Playwright invocation, existing)
**Storage**: N/A (no data storage changes)
**Testing**: pytest (unit tests for timeout clamping logic)
**Target Platform**: GitHub Actions CI runners
**Project Type**: Single project (methodology template)
**Performance Goals**: N/A (timeout is a safety bound, not a performance target)
**Constraints**: Individual test timeouts (60s) must remain unchanged; local dev unaffected
**Scale/Scope**: 2 source files, 1 contract YAML, unit tests for clamping

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate | Status | Notes |
|------|--------|-------|
| Amendment 1.6 (No Quick Fixes) | PASS | Using full speckit workflow |
| Amendment 1.12 (Mandatory Workflow) | PASS | Following specify->plan->tasks->implement |
| Amendment 1.14 (Validator Usage) | PASS | Will run validation before commit |

No constitution violations. Straightforward parameter change with clamping logic.

## Project Structure

### Documentation (this feature)

```text
specs/001-ci-timeout-600s/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Timeout value justification and design decisions
├── quickstart.md        # Verification steps
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Implementation tasks (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/playwright/
├── executor.py          # Line 119: run_suite() default parameter 300 -> 600, add clamping
└── runner.py            # Line 775: hardcoded timeout=300 -> use default or env var

specs/029-playwright-e2e-implementation/
└── contracts/
    └── playwright-api.yaml  # Lines 26, 43-44: document new default and max ceiling
```

**Structure Decision**: Modifications to existing files only. No new source files needed. Unit tests added for clamping logic.

## Implementation Approach

### Change 1: executor.py - Default and Clamping

```python
# Before
def run_suite(suite_path, base_url, timeout=300, retries=2):
    ...

# After
MAX_SUITE_TIMEOUT = 1800  # 30 minutes absolute ceiling (FR-003)

def run_suite(suite_path, base_url, timeout=600, retries=2):
    timeout = max(1, min(timeout, MAX_SUITE_TIMEOUT))  # FR-007: reject <=0
    ...
```

### Change 2: runner.py - Remove Hardcoded Value

```python
# Before
result = run_suite(..., timeout=300, ...)

# After
import os
try:
    suite_timeout = int(os.environ.get("PLAYWRIGHT_SUITE_TIMEOUT", "600"))
except ValueError:
    logger.warning("Invalid PLAYWRIGHT_SUITE_TIMEOUT, using default 600s")
    suite_timeout = 600
result = run_suite(..., timeout=suite_timeout, ...)
```

### Change 3: playwright-api.yaml - Updated Contract

Update the contract to document:
- Default timeout: 600s (was 300s)
- Maximum timeout: 1800s (new)
- Environment variable: `PLAYWRIGHT_SUITE_TIMEOUT` (new)

### Testing

Unit tests for timeout clamping:
- `test_timeout_clamped_to_max`: Verify timeout > 1800 is clamped to 1800
- `test_timeout_default_is_600`: Verify default parameter is 600
- `test_timeout_accepts_custom_value`: Verify custom values within range are honored
- `test_timeout_negative_or_zero_handling`: Verify edge cases

## Complexity Tracking

No constitution violations requiring justification. This is a minimal-complexity parameter change with bounded clamping logic.

## Adversarial Review #2

**Reviewed**: 2026-03-29 | **Focus**: Spec drift from clarifications, cross-artifact consistency

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | No handling for negative/zero timeout — disables the timeout, creating the exact risk FR-003 prevents | Fixed: added FR-007 with `max(1, min(timeout, 1800))` clamping |
| HIGH | Non-integer env var (e.g., "abc") crashes runner with unhandled ValueError | Fixed: added FR-008 for graceful fallback on parse error |
| MEDIUM | FR-006 exhaustive search already done in research — redundant as future requirement | Annotated FR-006: search completed, verify no new locations |
| MEDIUM | FR-003 didn't name the environment variable | Fixed: FR-003 updated with `PLAYWRIGHT_SUITE_TIMEOUT` |
| MEDIUM | FR-004 didn't name the specific contract file | Accepted: clarification Q1 identified the file; implementer will reference |
| LOW | SC-001 "20 runs" vs keyboard-nav "7-day window" inconsistency | Accepted: simpler metric sufficient for config change |
| LOW | Research canonical sources not traced to specific decisions | Accepted: informational references |

**Gate**: 0 CRITICAL, 0 HIGH remaining.

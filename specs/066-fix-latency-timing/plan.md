# Implementation Plan: Fix Latency Timing in Traffic Generator

**Branch**: `066-fix-latency-timing` | **Date**: 2025-12-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/066-fix-latency-timing/spec.md`

## Summary

Fix the `check_passrole_scoped()` timing issue in `interview/traffic_generator.py` by replacing `time.time()` with `time.monotonic()` for elapsed time measurements. This resolves test `test_very_long_latency` failing with negative latency values (-1362ms) due to system clock adjustments affecting wall clock time.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: None (stdlib `time` module only)
**Storage**: N/A (in-memory latency tracking)
**Testing**: pytest with existing unit tests
**Target Platform**: Linux server (CI/CD pipeline)
**Project Type**: single
**Performance Goals**: Latency measurement accuracy within +/- 10ms
**Constraints**: No API changes, internal fix only
**Scale/Scope**: Single file change (2 lines)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Requirement | Status | Notes |
|------|-------------|--------|-------|
| Deterministic Time | No `time.time()` for timing assertions | **FIX REQUIRED** | Current violation at lines 124, 135 |
| Unit Test Accompaniment | All implementations have tests | **PASS** | Existing tests cover this code |
| No Pipeline Bypass | Pipeline checks must pass | **PASS** | Will run full test suite |
| GPG Signed Commits | All commits signed | **PASS** | Standard workflow |

**Gate Evaluation**: PROCEED - This feature specifically fixes a constitution violation (Amendment 1.5: Deterministic Time Handling).

## Project Structure

### Documentation (this feature)

```text
specs/066-fix-latency-timing/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output (minimal - well-understood fix)
├── quickstart.md        # Phase 1 output (validation steps)
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
interview/
└── traffic_generator.py  # Target file: lines 124, 135

tests/unit/interview/
└── test_traffic_generator.py  # Existing test: line 704-720
```

**Structure Decision**: Single file change in existing module. No new directories or files needed.

## Complexity Tracking

No violations requiring justification. This is a minimal fix that reduces complexity by improving reliability.

## Phase 0: Research

### Research Summary

**Decision**: Replace `time.time()` with `time.monotonic()`

**Rationale**:
- `time.monotonic()` is immune to system clock adjustments (NTP sync, manual changes)
- Recommended by Python documentation for elapsed time measurement
- Constitution Amendment 1.5 explicitly prohibits `time.time()` for timing assertions
- Already used elsewhere in codebase (see `specs/012-ohlc-sentiment-e2e-tests/research.md`)

**Alternatives Considered**:
- `time.perf_counter()`: Higher resolution but same monotonic property. Overkill for ms-level latency.
- Mocking time in tests: Treats symptom, not cause. Source code would still be fragile.
- `datetime.now()`: Also wall clock time, same problem as `time.time()`.

**No External Research Needed**: This is a well-documented Python stdlib pattern.

## Phase 1: Design & Contracts

### Code Changes

**File**: `interview/traffic_generator.py`

**Change 1** (line 124):
```python
# Before
start = time.time()

# After
start = time.monotonic()
```

**Change 2** (line 135):
```python
# Before
latency = (time.time() - start) * 1000

# After
latency = (time.monotonic() - start) * 1000
```

### Data Model

No data model changes. `TrafficGeneratorStats.total_latency_ms` field type (float) remains unchanged.

### Contracts

No API contract changes. This is an internal implementation fix.

### Validation Strategy

1. Run existing test `test_very_long_latency` 10 times consecutively
2. Run full unit test suite to verify no regression
3. Verify no `time.time()` usage remains in `traffic_generator.py`

## Post-Design Constitution Re-Check

| Gate | Status | Notes |
|------|--------|-------|
| Deterministic Time | **PASS** | Fix removes `time.time()` usage |
| Unit Test Accompaniment | **PASS** | Existing test validates fix |
| No Pipeline Bypass | **PASS** | Standard PR workflow |

**Final Gate Status**: ALL GATES PASS

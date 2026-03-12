# Implementation Plan: SSE Origin Timestamp for Latency Measurement

**Branch**: `1042-sse-origin-timestamp` | **Date**: 2025-12-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1042-sse-origin-timestamp/spec.md`

## Summary

Add `origin_timestamp` field to SSE event data models to enable client-side latency measurement. The existing `timestamp` field in HeartbeatEventData and MetricsEventData will be renamed to `origin_timestamp` to match test expectations in `test_live_update_latency.py`.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, sse-starlette, pydantic
**Storage**: N/A (no database changes)
**Testing**: pytest (existing E2E tests in tests/e2e/test_live_update_latency.py)
**Target Platform**: AWS Lambda (containerized)
**Project Type**: Web application (backend API)
**Performance Goals**: p95 latency < 3 seconds (existing SLA)
**Constraints**: Must maintain backward compatibility with existing SSE consumers
**Scale/Scope**: Minimal change - 2 Pydantic model field renames

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| No quick fixes | PASS | Using full speckit workflow per Amendment 1.6 |
| No silent failures | PASS | Existing auth handling unchanged |
| GPG signing | PASS | All commits will be signed |
| Avoid over-engineering | PASS | Simple field rename, minimal scope |

## Project Structure

### Documentation (this feature)

```text
specs/1042-sse-origin-timestamp/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output (minimal - no unknowns)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
# Files to modify:
src/lambdas/dashboard/
└── sse.py               # SSE event models (HeartbeatEventData, MetricsEventData)

# Tests (already exist, will pass after fix):
tests/e2e/
└── test_live_update_latency.py
```

**Structure Decision**: Backend-only change in existing Lambda code. No new files needed.

## Complexity Tracking

No constitution violations. This is a minimal, focused change.

## Implementation Approach

### Phase 1: Field Rename

1. In `src/lambdas/dashboard/sse.py`:
   - Rename `timestamp` field to `origin_timestamp` in `HeartbeatEventData` (line 96)
   - Rename `timestamp` field to `origin_timestamp` in `MetricsEventData` (line 80)

### Phase 2: Validation

1. Run existing E2E tests locally to verify fix
2. Ensure no other code references the old `timestamp` field name

### Risks

- **Low Risk**: Other code might reference `timestamp` field in SSE event parsing
- **Mitigation**: Search codebase for SSE event parsing code; if found, update to use `origin_timestamp`

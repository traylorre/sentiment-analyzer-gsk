# Implementation Plan: CORS 404 Handler

**Branch**: `1311-cors-404-handler` | **Date**: 2026-04-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1311-cors-404-handler/spec.md`

## Summary

Register a Powertools `@app.not_found` handler in the dashboard Lambda that calls the existing `_make_not_found_response()` with the request origin. This ensures all unmatched routes return 404 with conditional CORS headers, fixing silent browser failures.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: aws-lambda-powertools (existing, routing)
**Storage**: N/A (no data storage changes)
**Testing**: pytest with moto/monkeypatch for unit tests
**Target Platform**: AWS Lambda (dashboard Lambda, existing)
**Project Type**: Single project (extend existing handler)
**Performance Goals**: No measurable impact -- single function call on unmatched routes
**Constraints**: Must reuse existing `_make_not_found_response()`, no new dependencies
**Scale/Scope**: ~8 lines of handler code, ~40 lines of unit test code

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution Requirement | Status | Notes |
|--------------------------|--------|-------|
| **7) Testing & Validation** | PASS | Unit test accompanies handler registration |
| Implementation Accompaniment | PASS | Test file created alongside handler change |
| Functional Integrity | PASS | Reuses existing validated function |
| **8) Git Workflow** | PASS | Feature branch workflow, GPG signing |
| Pre-Push Requirements | PASS | Will run make validate before push |
| **10) Local SAST** | PASS | No security-sensitive changes |

**Gate Result**: PASS - No violations.

## Project Structure

### Documentation (this feature)

```text
specs/1311-cors-404-handler/
├── spec.md              # Feature specification
├── plan.md              # This file
├── tasks.md             # Task breakdown
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
└── handler.py           # MODIFY: Add @app.not_found handler (~8 lines)

tests/unit/
└── test_cors_404_handler.py  # NEW: Unit tests for not-found handler
```

## Design Decisions

### D1: Placement of `@app.not_found` Handler

**Decision**: Place immediately after `_make_not_found_response()` (after line 302) and before the first route definition.

**Rationale**: The not-found handler is logically grouped with the 404 response builder. Placing it before route definitions follows the pattern of "infrastructure first, routes second" that the file already uses.

### D2: Reuse `_make_not_found_response()` Directly

**Decision**: The not-found handler calls `_make_not_found_response(_get_request_origin())` directly.

**Rationale**: This function already implements correct CORS header logic with origin validation. No wrapper or modification needed.

### D3: Debug-Level Logging

**Decision**: Log unmatched route hits at DEBUG level with path and method.

**Rationale**: Unmatched routes include bot scans and typos. INFO-level logging would create noise. DEBUG is available when needed for troubleshooting but silent in normal operation.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `@app.not_found` conflicts with existing routes | Very Low | Low | Decorator only fires for truly unmatched routes; tested |
| Powertools version incompatibility | Very Low | Medium | Feature exists in Powertools since early versions |
| Performance regression | None | None | Single function call, no I/O |

## Implementation Phases

### Phase 1: Handler Registration (1 task)

Register the `@app.not_found` handler in handler.py. This is the entire production code change.

### Phase 2: Unit Tests (1 task)

Add unit tests validating:
- Unmatched routes return 404 with CORS headers for allowed origins
- Unmatched routes return 404 without CORS headers for unknown origins
- Response body is correct JSON format

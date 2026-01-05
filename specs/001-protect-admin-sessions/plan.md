# Implementation Plan: Protect Admin Sessions Revoke Endpoint

**Branch**: `001-protect-admin-sessions` | **Date**: 2026-01-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-protect-admin-sessions/spec.md`

## Summary

Add `@require_role("admin")` decorator to the `/admin/sessions/revoke` endpoint to prevent unauthorized session revocation. This is a simple RBAC fix using the existing decorator from Feature 1130.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: Existing `@require_role` decorator from Feature 1130
**Storage**: N/A (decorator-only change)
**Testing**: pytest with moto for AWS mocking
**Target Platform**: AWS Lambda (Python 3.13 runtime)
**Project Type**: Web application (backend Lambda)
**Performance Goals**: No performance impact (decorator adds minimal overhead)
**Constraints**: Must use existing RBAC infrastructure
**Scale/Scope**: Single endpoint change

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security & Access Control (§3) | ✅ PASS | Enhances security by adding role protection |
| Testing (§7) | ✅ PASS | Unit tests required for authorization |
| Git Workflow (§8) | ✅ PASS | Feature branch, GPG-signed commits |
| Implementation Accompaniment | ✅ PASS | Tests accompany implementation |

**No Constitution violations.** Simple security enhancement.

## Project Structure

### Documentation (this feature)

```text
specs/001-protect-admin-sessions/
├── plan.md              # This file
├── research.md          # Phase 0: Decorator usage research
├── quickstart.md        # Phase 1: Implementation guide
└── tasks.md             # Phase 2: Implementation tasks
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
└── auth.py                  # Add @require_role("admin") decorator

tests/unit/dashboard/
└── test_auth.py             # Add authorization tests
```

**Structure Decision**: Backend-only change - single decorator addition to existing endpoint.

## Complexity Tracking

> No Constitution violations - table not required.

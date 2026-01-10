# Implementation Plan: Role Enum Centralization

**Branch**: `1184-role-enum-centralization` | **Date**: 2026-01-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1184-role-enum-centralization/spec.md`

## Summary

Consolidate auth-related enums (Role, AuthType) into a single canonical location (`src/lambdas/shared/auth/enums.py`). This is a pure refactoring task with no behavior changes - only import location changes.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: N/A (pure refactoring, no new deps)
**Storage**: N/A
**Testing**: pytest (existing tests must pass unchanged)
**Target Platform**: AWS Lambda
**Project Type**: Web application (backend-only change)
**Performance Goals**: N/A (no runtime impact)
**Constraints**: Zero behavior change - all existing tests must pass
**Scale/Scope**: ~10-15 files will have import changes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security & Access Control | PASS | No security impact - pure refactoring |
| Data & Model Requirements | PASS | No data changes |
| NoSQL/Expression safety | PASS | No DB changes |
| IAM least-privilege | PASS | No IAM changes |

No violations. This is a code organization change only.

## Project Structure

### Documentation (this feature)

```text
specs/1184-role-enum-centralization/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output (minimal - no unknowns)
├── tasks.md             # Phase 2 output
└── checklists/
    └── requirements.md  # Validation checklist
```

### Source Code (affected files)

```text
src/lambdas/shared/auth/
├── enums.py             # NEW: Consolidated enum definitions
├── constants.py         # DELETE: Role enum moves to enums.py
├── roles.py             # UPDATE: Import from enums.py
└── ...

src/lambdas/shared/middleware/
├── auth_middleware.py   # UPDATE: Move AuthType to enums.py, import from there
├── require_role.py      # UPDATE: Import from enums.py
└── ...

src/lambdas/shared/models/
├── user.py              # UPDATE: Import from enums.py
└── ...

tests/
├── unit/                # UPDATE: Import changes
├── integration/         # UPDATE: Import changes
└── e2e/                 # UPDATE: Import changes
```

**Structure Decision**: Backend-only change affecting `src/lambdas/shared/auth/` and related imports.

## Complexity Tracking

No violations to justify.

---

## Phase 0: Research

No unknowns to research. This is a straightforward file consolidation:

1. Create `enums.py` with Role and AuthType definitions
2. Delete `constants.py`
3. Update imports across codebase
4. Run tests to verify no regressions

## Phase 1: Design

### File Changes

1. **Create `src/lambdas/shared/auth/enums.py`**:
   - Move `Role` StrEnum from `constants.py`
   - Move `AuthType` enum from `auth_middleware.py`
   - Export `VALID_ROLES` frozenset
   - No imports from other auth modules (prevent circular deps)

2. **Delete `src/lambdas/shared/auth/constants.py`**:
   - All contents move to `enums.py`

3. **Update `src/lambdas/shared/middleware/auth_middleware.py`**:
   - Remove AuthType definition
   - Import AuthType from `..auth.enums`

4. **Update all files importing from `constants.py`**:
   - Change `from .constants import Role, VALID_ROLES` to `from .enums import Role, VALID_ROLES`

### Import Dependency Order

```
enums.py (no auth imports)
    ↓
roles.py, auth_middleware.py, require_role.py (import from enums.py)
    ↓
user.py, etc. (import from roles.py or enums.py)
```

### No API/Contract Changes

This is a pure refactoring - no API contracts, data models, or external interfaces change.

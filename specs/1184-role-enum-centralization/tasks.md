# Tasks: Role Enum Centralization

**Feature**: 1184-role-enum-centralization
**Created**: 2026-01-10
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 8 |
| Phase 1 (Setup) | 1 |
| Phase 2 (US1 - Create enums.py) | 2 |
| Phase 3 (US2 - Update Imports) | 4 |
| Phase 4 (Polish) | 1 |

## Phase 1: Setup

- [x] T001 Identify all files importing from constants.py or defining AuthType via `grep -r "from.*constants import" src/ tests/ && grep -r "class AuthType" src/`

## Phase 2: User Story 1 - Create Central Enum File (P1)

**Goal**: Create `src/lambdas/shared/auth/enums.py` with Role and AuthType definitions

**Independent Test**: Import `from src.lambdas.shared.auth.enums import Role, AuthType, VALID_ROLES` succeeds

- [x] T002 [US1] Create `src/lambdas/shared/auth/enums.py` with Role StrEnum (ANONYMOUS, FREE, PAID, OPERATOR) and VALID_ROLES frozenset
- [x] T003 [US1] Delete `src/lambdas/shared/auth/constants.py` after verifying enums.py has all its contents

## Phase 3: User Story 2 - Update All Imports (P2)

**Goal**: Update all imports across codebase to use new location

**Independent Test**: `ruff check src/ tests/` passes and `python -c "from src.lambdas.shared.auth.enums import Role, AuthType"` works

- [x] T004 [P] [US2] Update `src/lambdas/shared/auth/roles.py` to import from `.enums` instead of `.constants`
- [x] T005 [P] [US2] Update `src/lambdas/shared/middleware/require_role.py` to import from `..auth.enums` instead of `..auth.constants`
- [x] T006 [P] [US2] Update `src/lambdas/shared/auth/__init__.py` to import from `.enums` instead of `.constants`
- [x] T007 [US2] Update any remaining imports in `src/` and `tests/` directories (run grep, update each file)

## Phase 4: Polish

- [x] T008 Run `ruff check src/ tests/ --fix && ruff format src/ tests/` and verify all unit tests pass with `MAGIC_LINK_SECRET="test-secret-key-at-least-32-characters-long-for-testing" python -m pytest tests/unit/ -x --tb=short`

## Dependency Graph

```
T001 (identify files)
  ↓
T002 (create enums.py) → T003 (delete constants.py)
  ↓
T004, T005, T006 (parallel import updates)
  ↓
T007 (remaining imports)
  ↓
T008 (polish & verify)
```

## Parallel Execution

Phase 3 tasks T004, T005, T006 can run in parallel (different files, no dependencies).

## Implementation Strategy

1. **MVP (Phase 1-2)**: Create enums.py - foundational file
2. **Complete (Phase 3-4)**: Update imports and verify tests pass
3. **Verification**: All existing tests must pass without modification

## Notes

- This is a pure refactoring - zero behavior change expected
- If any test fails after migration, investigate import issue (not behavior bug)
- Use replace-all operations where possible for consistency

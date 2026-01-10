# Research: Role Enum Centralization

**Feature**: 1184-role-enum-centralization
**Date**: 2026-01-10

## Summary

No research required - this is a straightforward refactoring task.

## Decisions

### D1: File Location
- **Decision**: `src/lambdas/shared/auth/enums.py`
- **Rationale**: Follows A18 spec requirement verbatim
- **Alternatives**: Could use `types.py` or `definitions.py`, but `enums.py` is clearer and matches spec

### D2: Circular Import Prevention
- **Decision**: `enums.py` has no imports from other auth modules
- **Rationale**: Enums are leaf dependencies - everything imports them, they import nothing
- **Alternatives**: None - this is the only safe pattern

### D3: Backward Compatibility
- **Decision**: No re-exports from old locations
- **Rationale**: Clean break forces all code to update, prevents future confusion
- **Alternatives**: Could add deprecation warnings, but unnecessary for internal code

## Files to Update

Located via grep:
```
src/lambdas/shared/auth/constants.py    # DELETE
src/lambdas/shared/auth/roles.py        # Update import
src/lambdas/shared/middleware/auth_middleware.py  # Move AuthType, update import
src/lambdas/shared/middleware/require_role.py     # Update import
tests/*/                                # Update imports
```

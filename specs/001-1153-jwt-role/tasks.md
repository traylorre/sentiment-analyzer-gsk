# Tasks: Strict Role Validation in JWT

## Feature 1153 - Phase 1.5.4 RBAC Infrastructure

### T001: Add strict role validation to validate_jwt()

**Status**: DONE
**File**: `src/lambdas/shared/middleware/auth_middleware.py`

Added check after JWT decode:
```python
roles = payload.get("roles")
if roles is None:
    logger.warning("JWT rejected: missing 'roles' claim (v3.0 requirement)")
    return None
```

**Acceptance**: Tokens without `roles` claim return `None`.

---

### T002: Update test for missing roles

**Status**: DONE
**File**: `tests/unit/middleware/test_jwt_validation.py`

Changed `test_missing_roles_claim` to `test_missing_roles_claim_rejected` - now expects `None` instead of valid claim.

**Acceptance**: Test verifies rejection behavior.

---

### T003: Add v3.0 breaking change tests

**Status**: DONE
**File**: `tests/unit/middleware/test_jwt_validation.py`

Added:
- `test_null_roles_rejected` - null roles treated as missing
- `test_v3_breaking_change_forces_relogin` - documents the v3.0 behavior

**Acceptance**: Tests document and verify breaking change.

---

### T004: Verify all tests pass

**Status**: DONE

All 35+ JWT validation tests pass.

---

## Dependency Order

```
T001 (strict validation)
  ↓
T002 (update existing test)
  ↓
T003 (add new tests)
  ↓
T004 (verify all pass)
```

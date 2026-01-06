# Tasks: Add Roles Claim to JWT Generation

## Feature 1152 - Phase 1.5.3 RBAC Infrastructure

### T001: Add roles parameter to create_test_jwt()

**Status**: TODO
**File**: `tests/e2e/conftest.py`

Add `roles: list[str] | None = None` parameter to `create_test_jwt()` function.
Default to `["free"]` when None (authenticated user default).

**Acceptance**: Function signature includes roles parameter.

---

### T002: Include roles claim in JWT payload

**Status**: TODO
**File**: `tests/e2e/conftest.py`

Add `"roles": roles` to the payload dict before `jwt.encode()`.

**Acceptance**: Generated JWT contains `roles` claim when decoded.

---

### T003: Add unit tests for roles in test JWT

**Status**: TODO
**File**: `tests/unit/e2e/test_create_test_jwt.py` (new file)

Test cases:
1. Default roles is `["free"]` when not specified
2. Custom roles parameter is included in JWT
3. Empty roles array is valid
4. Roles roundtrip through validate_jwt()

**Acceptance**: All new tests pass.

---

### T004: Verify existing tests pass

**Status**: TODO
**File**: N/A (verification only)

Run full test suite to ensure no regressions.

**Acceptance**: All existing tests pass.

---

## Dependency Order

```
T001 (add parameter)
  ↓
T002 (include in payload)
  ↓
T003 (unit tests)
  ↓
T004 (full test suite)
```

# Tasks: Add RBAC Fields to User Model

## Feature 1151 - Phase 1.5.2 RBAC Infrastructure

### T001: Add RBAC fields to User model class

**Status**: TODO
**File**: `src/lambdas/shared/models/user.py`

Add after `merged_at` field (around line 44):
```python
# Feature 1151 - RBAC fields
subscription_active: bool = False
subscription_expires_at: datetime | None = None
is_operator: bool = False
```

**Acceptance**: User model has 3 new fields with correct types and defaults.

---

### T002: Update to_dynamodb_item() for RBAC fields

**Status**: TODO
**File**: `src/lambdas/shared/models/user.py`

Add serialization in `to_dynamodb_item()`:
- `subscription_active` → boolean
- `subscription_expires_at` → ISO8601 string (if not None)
- `is_operator` → boolean

**Acceptance**: `to_dynamodb_item()` output includes RBAC fields.

---

### T003: Update from_dynamodb_item() for RBAC fields

**Status**: TODO
**File**: `src/lambdas/shared/models/user.py`

Add deserialization in `from_dynamodb_item()`:
- Use `.get(key, default)` for backward compatibility
- Parse datetime from ISO8601 string

**Acceptance**: `from_dynamodb_item()` correctly parses RBAC fields with defaults.

---

### T004: Add unit tests for RBAC fields

**Status**: TODO
**File**: `tests/unit/lambdas/shared/models/test_user.py`

Test cases:
1. New User instance has correct defaults
2. `to_dynamodb_item()` serializes RBAC fields
3. `from_dynamodb_item()` deserializes RBAC fields
4. Legacy item (missing RBAC keys) gets defaults
5. Datetime roundtrip for subscription_expires_at

**Acceptance**: All new tests pass, 100% coverage of RBAC serialization.

---

### T005: Verify get_roles_for_user() integration

**Status**: TODO
**File**: N/A (verification only)

Run existing `get_roles_for_user()` tests to verify they still pass.
The function uses `getattr()` defensively, so it should work with real fields too.

**Acceptance**: All `test_roles.py` tests pass.

---

### T006: Run full test suite

**Status**: TODO
**File**: N/A (verification only)

Run `pytest tests/unit/` to verify no regressions.

**Acceptance**: All 2601+ unit tests pass.

---

## Dependency Order

```
T001 (add fields)
  ↓
T002 (to_dynamodb_item) ──┐
  ↓                       │
T003 (from_dynamodb_item) ├── Can run in parallel after T001
  ↓                       │
T004 (unit tests) ────────┘
  ↓
T005 (verify roles integration)
  ↓
T006 (full test suite)
```

# Tasks: get_roles_for_user Function

**Feature**: 1150-role-enum-get-roles
**Created**: 2026-01-06

## Task List

### T1: Create roles.py module

**File**: `src/lambdas/shared/auth/roles.py`

**Description**: Implement the `get_roles_for_user(user: User) -> list[str]` function.

**Requirements**:
- Import Role enum from constants
- Use getattr() for optional fields (subscription_active, is_operator, subscription_expires_at)
- Handle auth_type="anonymous" → return ["anonymous"]
- Handle authenticated users → return ["free"] + additional roles
- Check subscription expiry if subscription_active and subscription_expires_at set
- Anonymous users cannot have operator role

**Acceptance Criteria**:
- [ ] Function handles all role combinations correctly
- [ ] Uses getattr() for forward compatibility with Feature 1151
- [ ] Proper type hints and docstring

---

### T2: Export function from auth module

**File**: `src/lambdas/shared/auth/__init__.py`

**Description**: Add `get_roles_for_user` to the module's public exports.

**Acceptance Criteria**:
- [ ] Import added
- [ ] Added to `__all__` list
- [ ] Can be imported as `from src.lambdas.shared.auth import get_roles_for_user`

---

### T3: Create unit tests

**File**: `tests/unit/lambdas/shared/auth/test_roles.py`

**Description**: Comprehensive unit tests for all role scenarios.

**Test Cases**:
- [ ] test_anonymous_user_gets_anonymous_role
- [ ] test_email_authenticated_user_gets_free_role
- [ ] test_google_authenticated_user_gets_free_role
- [ ] test_github_authenticated_user_gets_free_role
- [ ] test_paid_user_gets_free_and_paid_roles
- [ ] test_operator_gets_all_roles
- [ ] test_expired_subscription_gets_only_free
- [ ] test_anonymous_cannot_be_operator
- [ ] test_user_without_rbac_fields_defaults_to_free

**Acceptance Criteria**:
- [ ] All tests pass
- [ ] Tests use pytest fixtures
- [ ] Mock User objects to test all scenarios

---

### T4: Verify no regressions

**Description**: Run full test suite to verify no existing tests break.

**Commands**:
```bash
pytest tests/unit -x
make validate
```

**Acceptance Criteria**:
- [ ] All existing unit tests pass
- [ ] make validate passes
- [ ] No type errors

---

## Progress Tracking

| Task | Status | Notes |
|------|--------|-------|
| T1 | Pending | |
| T2 | Pending | |
| T3 | Pending | |
| T4 | Pending | |

# Implementation Plan: get_roles_for_user Function

**Feature**: 1150-role-enum-get-roles
**Created**: 2026-01-06
**Spec**: [spec.md](./spec.md)

## Technical Context

| Aspect | Value |
|--------|-------|
| Feature Scope | Single function implementation |
| Primary File | `src/lambdas/shared/auth/roles.py` (new) |
| Dependencies | Role enum (exists), User model (partial - fields added in 1151) |
| Test Location | `tests/unit/lambdas/shared/auth/test_roles.py` (new) |
| Risk Level | Low - additive change, no breaking changes |

## Constitution Check

- [x] No expensive resources added
- [x] No IAM changes needed
- [x] Unit tests required
- [x] No CI workflow changes
- [x] Uses existing patterns (enum, dataclass)

## Design Decisions

### D1: File Location

**Decision**: Create new file `src/lambdas/shared/auth/roles.py`

**Rationale**:
- Separates role logic from constants (which is just the enum)
- Clean separation of concerns
- Easier to test in isolation

**Alternative**: Add to constants.py
- Rejected: constants.py should remain pure data, no logic

### D2: Handling Missing User Fields

**Decision**: Use `getattr()` with sensible defaults

**Rationale**:
- Feature 1151 will add role fields to User model
- This function must work before AND after 1151
- Defaults: subscription_active=False, is_operator=False, subscription_expires_at=None

### D3: Role Ordering

**Decision**: Return roles in additive order: base role first, then additional roles

**Rationale**:
- Consistent ordering for testing
- Matches documented additive model (anonymous → free → paid → operator)

## Implementation Steps

1. Create `src/lambdas/shared/auth/roles.py` with `get_roles_for_user()` function
2. Export from `src/lambdas/shared/auth/__init__.py`
3. Create unit tests in `tests/unit/lambdas/shared/auth/test_roles.py`
4. Verify all existing tests pass

## Test Strategy

### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| Anonymous user | auth_type="anonymous" | ["anonymous"] |
| Free user (email) | auth_type="email", subscription_active=False | ["free"] |
| Free user (google) | auth_type="google", subscription_active=False | ["free"] |
| Paid user | auth_type="email", subscription_active=True | ["free", "paid"] |
| Operator | is_operator=True | ["free", "paid", "operator"] |
| Expired subscription | subscription_active=True, subscription_expires_at=past | ["free"] |
| Anonymous cannot be operator | auth_type="anonymous", is_operator=True | ["anonymous"] |
| Missing fields | User without RBAC fields | ["free"] (authenticated default) |

## Artifacts

- [ ] `src/lambdas/shared/auth/roles.py` - Function implementation
- [ ] `src/lambdas/shared/auth/__init__.py` - Export added
- [ ] `tests/unit/lambdas/shared/auth/test_roles.py` - Unit tests

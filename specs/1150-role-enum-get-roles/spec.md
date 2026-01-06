# Feature Specification: get_roles_for_user Function

**Feature Branch**: `1150-role-enum-get-roles`
**Created**: 2026-01-06
**Status**: Draft
**Input**: Phase 1.5.1 - Implement get_roles_for_user(user: User) -> list[str] function that returns roles based on user state.
**Parent Spec**: specs/1126-auth-httponly-migration/spec-v2.md (Phase 1.5)

## Context

The Role enum (ANONYMOUS, FREE, PAID, OPERATOR) already exists in `src/lambdas/shared/auth/constants.py` (Feature 1130). This feature implements the `get_roles_for_user()` function that determines which roles a user has based on their state.

**Dependency**: This is a foundation for Features 1151 (User model role fields), 1152 (JWT claims), and 1153 (strict validation).

## User Scenarios & Testing

### User Story 1 - Anonymous User Role Assignment (Priority: P1)

When an anonymous user (not authenticated) accesses the system, they should receive the ANONYMOUS role.

**Why this priority**: Anonymous users are the most common initial state - every user starts as anonymous before authenticating.

**Independent Test**: Create a User with `auth_type="anonymous"` and verify `get_roles_for_user()` returns `["anonymous"]`.

**Acceptance Scenarios**:

1. **Given** a User with `auth_type="anonymous"`, **When** `get_roles_for_user(user)` is called, **Then** it returns `["anonymous"]`
2. **Given** a User with `auth_type="anonymous"` and any other fields set, **When** `get_roles_for_user(user)` is called, **Then** it returns `["anonymous"]` (auth_type takes precedence)

---

### User Story 2 - Authenticated Free User Role Assignment (Priority: P1)

When an authenticated user without a subscription accesses the system, they should receive the FREE role.

**Why this priority**: Free authenticated users are the core user base after anonymous users.

**Independent Test**: Create a User with `auth_type="email"` (or "google", "github") and `subscription_active=False`, verify returns `["free"]`.

**Acceptance Scenarios**:

1. **Given** a User with `auth_type="email"` and `subscription_active=False`, **When** `get_roles_for_user(user)` is called, **Then** it returns `["free"]`
2. **Given** a User with `auth_type="google"` and no subscription fields, **When** `get_roles_for_user(user)` is called, **Then** it returns `["free"]`

---

### User Story 3 - Paid User Role Assignment (Priority: P2)

When a user with an active subscription accesses the system, they should receive the PAID role (which includes FREE).

**Why this priority**: Paid users are a subset of authenticated users, requires subscription infrastructure.

**Independent Test**: Create a User with `auth_type="email"` and `subscription_active=True`, verify returns `["free", "paid"]`.

**Acceptance Scenarios**:

1. **Given** a User with `auth_type="email"` and `subscription_active=True`, **When** `get_roles_for_user(user)` is called, **Then** it returns `["free", "paid"]`
2. **Given** a User with `subscription_active=True` but `subscription_expires_at` in the past, **When** `get_roles_for_user(user)` is called, **Then** it returns `["free"]` (expired subscription)

---

### User Story 4 - Operator Role Assignment (Priority: P2)

When an operator (admin) accesses the system, they should receive the OPERATOR role (which includes FREE and PAID).

**Why this priority**: Operators are rare but critical for system administration.

**Independent Test**: Create a User with `is_operator=True`, verify returns `["free", "paid", "operator"]`.

**Acceptance Scenarios**:

1. **Given** a User with `is_operator=True`, **When** `get_roles_for_user(user)` is called, **Then** it returns `["free", "paid", "operator"]`
2. **Given** a User with `is_operator=True` but `auth_type="anonymous"`, **When** `get_roles_for_user(user)` is called, **Then** it returns `["anonymous"]` (cannot be operator while anonymous)

---

### Edge Cases

- What happens when User model doesn't have subscription fields yet? Function should use defaults (subscription_active=False, is_operator=False).
- What happens when subscription_expires_at is None but subscription_active=True? Treat as active (no expiry).
- What happens when auth_type is an unexpected value? Treat as anonymous for safety.

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a `get_roles_for_user(user: User) -> list[str]` function
- **FR-002**: Function MUST return `["anonymous"]` for users with `auth_type="anonymous"`
- **FR-003**: Function MUST return `["free"]` for authenticated users without active subscription
- **FR-004**: Function MUST return `["free", "paid"]` for users with `subscription_active=True` and valid expiry
- **FR-005**: Function MUST return `["free", "paid", "operator"]` for users with `is_operator=True`
- **FR-006**: Function MUST check `subscription_expires_at` against current time if set
- **FR-007**: Function MUST handle missing User model fields gracefully using defaults
- **FR-008**: Function MUST be exported from `src/lambdas/shared/auth/__init__.py`

### Key Entities

- **User**: The user model with auth_type, and future RBAC fields (role, subscription_active, subscription_expires_at, is_operator)
- **Role**: Enum with ANONYMOUS, FREE, PAID, OPERATOR values (already exists in constants.py)

## Success Criteria

### Measurable Outcomes

- **SC-001**: All unit tests pass for each role assignment scenario
- **SC-002**: Function correctly handles users without RBAC fields (backward compatible)
- **SC-003**: Function is properly exported and importable from `src.lambdas.shared.auth`
- **SC-004**: No existing tests break (zero regression)
- **SC-005**: Function returns roles in consistent order (anonymous/free first, then additive roles)

## Implementation Notes

**Location**: `src/lambdas/shared/auth/roles.py` (new file) or `src/lambdas/shared/auth/constants.py` (extend existing)

**Dependency on Feature 1151**: This function references User model fields that don't exist yet. Implementation must use `getattr()` with defaults:
```python
subscription_active = getattr(user, 'subscription_active', False)
is_operator = getattr(user, 'is_operator', False)
```

This allows the function to work before and after User model is extended in Feature 1151.

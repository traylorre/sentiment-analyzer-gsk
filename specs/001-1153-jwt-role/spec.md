# Feature Specification: Strict Role Validation in JWT

**Feature Branch**: `1153-jwt-role-validation`
**Created**: 2026-01-06
**Status**: Draft
**Phase**: 1.5.4 - RBAC Infrastructure
**Depends On**: Feature 1152 (roles claim in JWT generation)

## ⚠️ BREAKING CHANGE (v3.0)

This feature implements **strict role validation** that REJECTS tokens missing the `roles` claim. This is a v3.0 breaking change that forces users with old tokens to re-login.

**Rationale**: Auto-promoting role-less tokens creates a security gap where an attacker with an old token could be granted implicit roles. Forcing re-login ensures all tokens have explicit role claims.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reject Tokens Without Roles (Priority: P1)

As the auth middleware, I MUST reject JWT tokens that don't have a `roles` claim to prevent security bypass.

**Why this priority**: Security - prevents old tokens from being auto-promoted.

**Independent Test**: Call `validate_jwt()` with token missing `roles`, verify it returns `None`.

**Acceptance Scenarios**:

1. **Given** a JWT without `roles` claim, **When** `validate_jwt()` is called, **Then** it returns `None` (rejected)
2. **Given** a JWT with `roles: []` (empty array), **When** `validate_jwt()` is called, **Then** it returns valid `JWTClaim` (empty is valid)
3. **Given** a JWT with `roles: ["free"]`, **When** `validate_jwt()` is called, **Then** it returns valid `JWTClaim`

---

### User Story 2 - @require_role Decorator Works (Priority: P1)

As a developer, I need `@require_role("paid")` to correctly check the `roles` claim in validated JWTs.

**Why this priority**: RBAC functionality depends on this.

**Independent Test**: Decorate endpoint with `@require_role("paid")`, call with JWT containing `["free", "paid"]`, verify access granted.

**Acceptance Scenarios**:

1. **Given** endpoint with `@require_role("paid")` and JWT with `roles: ["free", "paid"]`, **When** request is made, **Then** access is granted
2. **Given** endpoint with `@require_role("paid")` and JWT with `roles: ["free"]`, **When** request is made, **Then** 403 Forbidden returned
3. **Given** endpoint with `@require_role("operator")` and JWT with `roles: ["free", "paid", "operator"]`, **When** request is made, **Then** access is granted

---

### User Story 3 - Existing Users Force Re-login (Priority: P1)

As a user with an old token (no `roles` claim), I should receive a 401 Unauthorized and be prompted to re-login.

**Why this priority**: User experience for the breaking change.

**Independent Test**: Send request with old-style token, verify 401 response.

**Acceptance Scenarios**:

1. **Given** a user with token generated before v3.0, **When** they make an API request, **Then** they receive 401 Unauthorized
2. **Given** a user who re-logs in, **When** they receive new token, **Then** the token contains `roles` claim

---

### Edge Cases

- **Empty roles array**: `roles: []` is valid - user has no roles, but token format is correct
- **Unknown roles**: `roles: ["beta_tester"]` should be accepted (forward compatibility)
- **Null roles claim**: `"roles": null` should be REJECTED (must be an array)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `validate_jwt()` MUST reject tokens without `roles` claim (return `None`)
- **FR-002**: `validate_jwt()` MUST accept tokens with empty `roles: []` array
- **FR-003**: `validate_jwt()` MUST accept tokens with valid `roles` array
- **FR-004**: `validate_jwt()` MUST log warning when rejecting role-less token
- **FR-005**: All test JWT helpers MUST include `roles` claim (done in Feature 1152)

### Key Entities

- **JWTClaim**: `roles` field changes from optional to effectively required for validation
- **JWT Payload**: `roles` claim becomes mandatory for all new tokens

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tokens without `roles` claim return `None` from `validate_jwt()`
- **SC-002**: Tokens with `roles: []` are accepted
- **SC-003**: `@require_role()` decorator correctly checks roles
- **SC-004**: All existing tests pass (test JWTs now include roles per Feature 1152)

## Technical Notes

### Implementation

In `validate_jwt()` after decoding the payload:

```python
# v3.0 BREAKING CHANGE: Reject tokens without roles claim
roles = payload.get("roles")
if roles is None:
    logger.warning("JWT rejected: missing roles claim (v3.0 requirement)")
    return None
```

### Migration Path

1. Feature 1152 ensures all test JWTs include `roles`
2. This feature enables strict validation
3. Production Cognito tokens need Pre Token Generation Lambda trigger (Future Feature 1157)

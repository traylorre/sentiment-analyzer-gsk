# Feature Specification: Require Role Decorator

**Feature Branch**: `1130-require-role-decorator`
**Created**: 2026-01-05
**Status**: Draft
**Input**: User description: "Phase 0 D6: Create @require_role decorator at src/lambdas/shared/middleware/require_role.py. Syntax: @require_role('operator'). Must prevent role leakage in 403 error responses. REQUIRED by C4/C5 - must be implemented before those fixes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Protect Admin Endpoints (Priority: P1)

An operator (administrative user) needs to access sensitive endpoints like session revocation and user lookup. The system must verify the user has the `operator` role before allowing access. Non-operator users attempting these endpoints receive a generic access denied response that does not reveal what role is required.

**Why this priority**: Security-critical. Without role protection, any authenticated user can perform admin actions like revoking all sessions or enumerating users. This is the core functionality that enables C4/C5 endpoint protection.

**Independent Test**: Can be fully tested by decorating a test endpoint with `@require_role('operator')` and verifying that users without the role receive 403 while operators can access it.

**Acceptance Scenarios**:

1. **Given** a user with `operator` role, **When** they access an endpoint decorated with `@require_role('operator')`, **Then** the request proceeds to the handler and returns the expected response.

2. **Given** a user with `free` role (no operator role), **When** they access an endpoint decorated with `@require_role('operator')`, **Then** they receive a 403 Forbidden response with a generic message that does NOT mention "operator" or any specific role.

3. **Given** an anonymous (unauthenticated) user, **When** they access an endpoint decorated with `@require_role('operator')`, **Then** they receive a 401 Unauthorized response (authentication required before authorization check).

---

### User Story 2 - Support Multiple Role Levels (Priority: P2)

The system supports a hierarchy of roles (anonymous, free, paid, operator) where decorators can require any specific role. This enables tiered feature access where paid features require `paid` role and admin features require `operator` role.

**Why this priority**: Enables future feature gating for subscription tiers. Foundation for monetization but not blocking for initial security fixes.

**Independent Test**: Can be tested by creating endpoints with different role requirements (`@require_role('paid')`, `@require_role('free')`) and verifying correct access control per role.

**Acceptance Scenarios**:

1. **Given** a user with `paid` role, **When** they access an endpoint requiring `paid`, **Then** access is granted.

2. **Given** a user with `free` role (no paid subscription), **When** they access an endpoint requiring `paid`, **Then** they receive 403 Forbidden with generic message.

3. **Given** a user with `operator` role, **When** they access an endpoint requiring `paid`, **Then** access is granted (operators implicitly have all lower roles via role accumulation).

---

### User Story 3 - Composable with Existing Auth (Priority: P3)

The decorator integrates seamlessly with the existing FastAPI dependency injection pattern for authentication. It can be combined with other dependencies and does not conflict with the current `get_authenticated_user_id` or `extract_auth_context_typed` functions.

**Why this priority**: Ensures the decorator fits into the existing architecture without breaking current patterns. Important for maintainability but not blocking for initial implementation.

**Independent Test**: Can be tested by applying decorator to an endpoint that also uses `Depends(get_users_table)` and verifying both work correctly.

**Acceptance Scenarios**:

1. **Given** an endpoint with `@require_role('operator')` and `Depends(get_users_table)`, **When** an operator accesses it, **Then** both the role check passes and the table dependency is injected.

---

### Edge Cases

- What happens when a user's token is valid but missing the `roles` claim? The decorator should reject with 401 (invalid token structure, not authorization failure).
- What happens when the roles claim contains an empty list? Treat as having no roles; 403 if role required.
- What happens when role parameter is invalid (typo like `@require_role('admn')`)? Fail at decoration time (startup) with clear error, not runtime.
- What happens with concurrent role changes (user demoted mid-session)? Role is read from JWT at request time; demotion takes effect on next token refresh.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `@require_role(role: str)` decorator that can be applied to FastAPI route handlers.
- **FR-002**: System MUST return 401 Unauthorized if the request lacks valid authentication (no token or invalid token).
- **FR-003**: System MUST return 403 Forbidden if the authenticated user lacks the required role.
- **FR-004**: System MUST use a generic 403 error message that does NOT reveal the required role (prevent role enumeration).
- **FR-005**: System MUST validate the role parameter against known canonical roles at decoration time (startup), raising an error for unknown roles.
- **FR-006**: System MUST read user roles from the JWT `roles` claim (list of strings).
- **FR-007**: System MUST support the canonical role values: `anonymous`, `free`, `paid`, `operator`.
- **FR-008**: System MUST reject tokens missing the `roles` claim with 401 (malformed token, not authorization failure).
- **FR-009**: Decorator MUST be composable with FastAPI's `Depends()` system without conflicts.
- **FR-010**: Decorator MUST integrate with existing `extract_auth_context_typed()` function for token parsing.

### Key Entities

- **Role**: A string identifier representing a permission level. Canonical values: `anonymous`, `free`, `paid`, `operator`. Roles are additive (a paid user has `['free', 'paid']`).
- **AuthContext**: Existing dataclass containing `user_id`, `auth_type`, `auth_method`. Extended to include `roles: list[str]`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Decorated endpoints return 403 for unauthorized users within 50ms overhead (negligible latency impact).
- **SC-002**: 100% of admin endpoints (revoke, lookup) are protected before Phase 0 completion.
- **SC-003**: Security audit shows zero role information leakage in error responses.
- **SC-004**: Decorator can be applied to existing endpoints with single-line change (no handler refactoring required).
- **SC-005**: Invalid role parameters detected at application startup, preventing runtime failures.

## Assumptions

- JWT tokens will include a `roles` claim (list of strings) as per Phase 1.5 planning. Until Phase 1.5, this decorator will reject all tokens as malformed (acceptable for Phase 0 since admin endpoints shouldn't be accessible yet).
- The canonical role enum (`anonymous`, `free`, `paid`, `operator`) is stable and will not change frequently.
- Role checking is based on exact string matching against the roles list (e.g., `'operator' in roles`).
- The decorator pattern is acceptable even though the codebase currently uses dependency injection; this provides cleaner syntax for role requirements.

## Dependencies

- **Phase 1.5 (role-enum-canonical)**: Defines the canonical role values this decorator validates against.
- **Phase 1.5 (jwt-roles-claim)**: Ensures JWTs contain the `roles` claim this decorator reads.
- **Existing**: `extract_auth_context_typed()` from auth_middleware.py for token parsing.

## Out of Scope

- Role hierarchy/inheritance (operator > paid > free) - this decorator checks for exact role presence; the role assignment logic (handled in Phase 1.5) is responsible for role accumulation.
- Role management UI or API endpoints.
- Database storage for roles (roles are in JWT, not fetched from database per request).

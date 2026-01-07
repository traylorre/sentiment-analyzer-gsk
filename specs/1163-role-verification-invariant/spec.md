# Feature Specification: Role-Verification Invariant Validator

**Feature Branch**: `1163-role-verification-invariant`
**Created**: 2026-01-06
**Status**: Draft
**Input**: Implement role-verification invariant validator on User model to enforce state machine rules

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prevent Invalid Anonymous:Verified State (Priority: P1)

When user data is created or modified, the system must prevent the impossible state where a user has role="anonymous" but verification="verified". This state is logically contradictory because the act of verification inherently upgrades the user from anonymous to a registered role.

**Why this priority**: This is the core invariant that prevents data corruption. An anonymous:verified user would have undefined behavior in authorization checks.

**Independent Test**: Can be fully tested by attempting to create/modify a User with anonymous role and verified status. System rejects with clear error message.

**Acceptance Scenarios**:

1. **Given** a new User object being created, **When** role="anonymous" and verification="verified" are set, **Then** validation fails with error: "Invalid state: anonymous users cannot be verified. Verification upgrades role to 'free'."
2. **Given** an existing anonymous:pending user, **When** verification is changed to "verified" without changing role, **Then** validation fails with the same error.
3. **Given** a User with role="anonymous" and verification="none", **When** saved, **Then** validation passes (valid state).

---

### User Story 2 - Auto-Upgrade Anonymous to Free on Verification (Priority: P2)

When an anonymous user completes email verification or OAuth login, the system should automatically upgrade their role from "anonymous" to "free" as part of the verification completion. This implements the state machine rule that verification IS the role upgrade.

**Why this priority**: This provides the user-friendly behavior where verification automatically grants the user a registered role, rather than leaving them in an invalid state.

**Independent Test**: Can be tested by setting an anonymous user's verification to "verified" and observing the automatic role upgrade to "free".

**Acceptance Scenarios**:

1. **Given** an anonymous:pending user, **When** verification is set to "verified", **Then** role is automatically upgraded to "free" and the User object is valid.
2. **Given** an anonymous:none user, **When** verification is set to "verified" via OAuth flow, **Then** role is automatically upgraded to "free".

---

### User Story 3 - Enforce Verified Status for Non-Anonymous Roles (Priority: P3)

Users with roles above anonymous (free, paid, operator) must always have verification="verified". This ensures that registered users have proven their identity.

**Why this priority**: This is a secondary invariant that maintains consistency. It's less critical than P1 because existing workflows already set verification when upgrading roles.

**Independent Test**: Can be tested by attempting to create a User with role="free" and verification="none" or "pending".

**Acceptance Scenarios**:

1. **Given** a new User object, **When** role="free" and verification="none", **Then** validation fails with error: "Invalid state: non-anonymous roles require verified status."
2. **Given** a User with role="paid", **When** verification is changed to "pending", **Then** validation fails.
3. **Given** a User with role="operator" and verification="verified", **When** saved, **Then** validation passes.

---

### Edge Cases

- What happens when role is set to "free" but verification is missing/None? → Validation fails; verification defaults to "none" per model, so this triggers the invariant.
- How does system handle legacy data loaded from database without verification field? → Model defaults verification="none", role="anonymous", which is a valid state.
- What happens during deserialization from DynamoDB? → Validation runs after model construction; invalid states from corrupted data are caught.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST reject User objects where role="anonymous" and verification="verified" with a clear error message.
- **FR-002**: System MUST automatically upgrade role from "anonymous" to "free" when verification is set to "verified" on an anonymous user, rather than rejecting.
- **FR-003**: System MUST reject User objects where role is non-anonymous (free, paid, operator) and verification is not "verified".
- **FR-004**: System MUST apply validation after all fields are set (post-init validation) to ensure cross-field constraints are checked.
- **FR-005**: System MUST allow valid state combinations: anonymous:none, anonymous:pending, free:verified, paid:verified, operator:verified.

### Key Entities

- **User**: The primary entity containing role and verification fields. Validation enforces that these fields maintain consistent state per the role-verification matrix.
- **RoleType**: Literal type with values "anonymous", "free", "paid", "operator".
- **VerificationType**: Literal type with values "none", "pending", "verified".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of attempts to create anonymous:verified users are rejected with appropriate error message.
- **SC-002**: 100% of anonymous users who complete verification are automatically upgraded to free role.
- **SC-003**: 100% of non-anonymous users with non-verified status are rejected.
- **SC-004**: Zero data corruption from invalid role-verification combinations in production.
- **SC-005**: All existing unit tests continue to pass (no regressions from adding validation).

## Assumptions

- The User model already has role (RoleType) and verification (VerificationType) fields from Feature 1162.
- Pydantic's @model_validator(mode='after') is available and is the appropriate mechanism for cross-field validation.
- Auto-upgrade from anonymous→free is preferred over rejection to provide better user experience.
- The validation applies to all User instantiations including deserialization from DynamoDB.

## Dependencies

- Feature 1162 (User model federation fields) - COMPLETED: Provides the role and verification fields.

## Canonical Source

- specs/1126-auth-httponly-migration/spec-v2.md (role-verification matrix)
- specs/1126-auth-httponly-migration/implementation-gaps.md (lines 122-177)

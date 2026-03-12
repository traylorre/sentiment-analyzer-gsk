# Feature Specification: OAuth Role Advancement

**Feature Branch**: `1170-oauth-role-advancement`
**Created**: 2026-01-07
**Status**: Draft
**Input**: User description: "OAuth users stay role=anonymous. After OAuth success, users should advance from anonymous to free. Set role_assigned_at and role_assigned_by for audit trail."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - OAuth User Gets Free Role (Priority: P1)

A user authenticates via OAuth (Google or GitHub) and receives the "free" role instead of remaining "anonymous". This enables them to access features reserved for authenticated users.

**Why this priority**: Core functionality - without role advancement, OAuth users cannot access any RBAC-protected features despite being authenticated.

**Independent Test**: Can be tested by completing OAuth flow and verifying the user's role field equals "free" in the database.

**Acceptance Scenarios**:

1. **Given** an anonymous user, **When** they complete OAuth authentication via Google, **Then** their role is set to "free"
2. **Given** an anonymous user, **When** they complete OAuth authentication via GitHub, **Then** their role is set to "free"
3. **Given** an existing user with role "anonymous", **When** they link an OAuth provider, **Then** their role advances to "free"

---

### User Story 2 - Audit Trail for Role Assignment (Priority: P1)

When a user's role changes due to OAuth authentication, the system records when the role was assigned and what triggered the assignment for compliance and debugging purposes.

**Why this priority**: Critical for compliance - role changes must be auditable to trace privilege escalation.

**Independent Test**: After OAuth completes, verify `role_assigned_at` contains a valid ISO timestamp and `role_assigned_by` contains "oauth:{provider}".

**Acceptance Scenarios**:

1. **Given** a user completing OAuth, **When** their role is set to "free", **Then** `role_assigned_at` is set to the current UTC timestamp
2. **Given** a user completing OAuth, **When** their role is set to "free", **Then** `role_assigned_by` is set to "oauth:google" or "oauth:github" based on provider

---

### User Story 3 - Preserve Higher Roles (Priority: P2)

If a user already has a role higher than "free" (e.g., "paid" or "operator"), OAuth authentication should not demote them.

**Why this priority**: Prevents accidental privilege loss for existing paid or operator users.

**Independent Test**: Complete OAuth for a user with role="paid" and verify role remains "paid".

**Acceptance Scenarios**:

1. **Given** a user with role "paid", **When** they complete OAuth authentication, **Then** their role remains "paid"
2. **Given** a user with role "operator", **When** they complete OAuth authentication, **Then** their role remains "operator"
3. **Given** a user with role "free", **When** they complete OAuth authentication again, **Then** their role remains "free" (no change needed)

---

### Edge Cases

- What happens when OAuth fails midway? Role should not change (atomic operation).
- What happens if `role_assigned_at` already has a value? Only update if role actually changes.
- What happens for new users created during OAuth? They should get role="free" directly.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST set role to "free" when a user completes OAuth authentication and their current role is "anonymous"
- **FR-002**: System MUST set `role_assigned_at` to current UTC timestamp when role changes
- **FR-003**: System MUST set `role_assigned_by` to "oauth:{provider}" where provider is "google" or "github"
- **FR-004**: System MUST NOT modify role if current role is "free", "paid", or "operator" (higher privilege)
- **FR-005**: System MUST NOT modify `role_assigned_at` or `role_assigned_by` if role does not change
- **FR-006**: System MUST apply role advancement for both new users created during OAuth and existing users linking OAuth

### Key Entities

- **User**: Contains `role` (RoleType), `role_assigned_at` (datetime|None), `role_assigned_by` (str|None)
- **RoleType**: Literal type with values "anonymous", "free", "paid", "operator" in ascending privilege order

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of users completing OAuth with role="anonymous" have role="free" after callback completes
- **SC-002**: 100% of role advancements have both `role_assigned_at` and `role_assigned_by` populated
- **SC-003**: 0% of users with role="paid" or "operator" are demoted after OAuth authentication
- **SC-004**: Role advancement occurs in the same transaction as OAuth completion (no partial states)

## Assumptions

- Role hierarchy is: anonymous < free < paid < operator (ascending privilege)
- OAuth providers are limited to "google" and "github" in current implementation
- The `_link_provider()` function (Feature 1169) handles federation fields; this feature handles role advancement
- Role advancement should integrate into `handle_oauth_callback()` flow, not as a separate operation

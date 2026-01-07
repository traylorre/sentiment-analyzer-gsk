# Feature Specification: User Model Federation Fields

**Feature Branch**: `1162-user-model-federation`
**Created**: 2026-01-07
**Status**: Draft
**Input**: User description: "Add 9 missing federation fields to User model: role, verification, pending_email, primary_email, linked_providers, provider_metadata, last_provider_used, role_assigned_at, role_assigned_by. Also add ProviderMetadata class."
**Canonical Source**: `specs/1126-auth-httponly-migration/spec-v2.md` (lines 4168-4196)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-Provider Account Linking (Priority: P1)

A user who initially signed up anonymously or via email can later link their Google and GitHub accounts to the same user profile. This allows them to sign in using any of their linked providers while maintaining a single identity and preserving their data.

**Why this priority**: This is the core federation value proposition. Without provider linking, users are forced to maintain separate accounts for each authentication method, leading to fragmented data and poor user experience.

**Independent Test**: Can be tested by creating a user, linking a provider, and verifying the user's `linked_providers` list and `provider_metadata` dictionary are correctly populated.

**Acceptance Scenarios**:

1. **Given** an existing user with `linked_providers: ["email"]`, **When** the user authenticates via Google OAuth, **Then** `linked_providers` becomes `["email", "google"]` and `provider_metadata["google"]` contains the OAuth subject claim, email, and avatar URL.
2. **Given** a user with multiple linked providers, **When** the user signs in via any linked provider, **Then** they access the same account and data.
3. **Given** a user signs in via a new provider, **When** the login completes, **Then** `last_provider_used` is updated to reflect the most recent provider.

---

### User Story 2 - Role-Based Access Control (Priority: P1)

The system categorizes users into roles (anonymous, free, paid, operator) that determine their access level. Role transitions are audited with timestamps and attribution for compliance and troubleshooting.

**Why this priority**: Roles are foundational for authorization. Every protected endpoint depends on role checks. Without roles, the system cannot differentiate access levels.

**Independent Test**: Can be tested by creating users with different roles and verifying role values are persisted and retrievable.

**Acceptance Scenarios**:

1. **Given** a new session without authentication, **When** the system creates a user record, **Then** `role` defaults to `"anonymous"`.
2. **Given** a user completes a subscription purchase, **When** a Stripe webhook fires, **Then** `role` is updated to `"paid"`, `role_assigned_at` is set to current time, and `role_assigned_by` is `"stripe_webhook"`.
3. **Given** an operator manually assigns a role via admin interface, **When** the role update completes, **Then** `role_assigned_by` is `"admin:{admin_user_id}"`.

---

### User Story 3 - Email Verification Workflow (Priority: P2)

Users who provide an email address go through a verification workflow. The system tracks verification state (`none`, `pending`, `verified`) and stores both the pending email awaiting verification and the verified primary email.

**Why this priority**: Email verification is required for elevated roles (free, paid, operator). It's a prerequisite for role upgrades but can be implemented after the core role structure.

**Independent Test**: Can be tested by initiating email verification and verifying `verification` state transitions and `pending_email`/`primary_email` field updates.

**Acceptance Scenarios**:

1. **Given** a user with `verification: "none"`, **When** they submit an email for verification, **Then** `verification` becomes `"pending"` and `pending_email` stores the submitted address.
2. **Given** a user with `verification: "pending"`, **When** they confirm the verification link, **Then** `verification` becomes `"verified"`, `primary_email` is set to the confirmed address, and `pending_email` is cleared.
3. **Given** a verified user, **When** they attempt to change their email, **Then** `pending_email` stores the new address and `verification` remains `"verified"` until the new email is confirmed.

---

### User Story 4 - Avatar Selection from Provider (Priority: P3)

When a user has multiple linked providers, the system uses the avatar from the most recently used provider for display purposes.

**Why this priority**: Avatar display is a UI enhancement. The core data model must support it, but it's lower priority than authentication and authorization.

**Independent Test**: Can be tested by linking multiple providers with different avatars and verifying `last_provider_used` drives avatar selection.

**Acceptance Scenarios**:

1. **Given** a user with `linked_providers: ["google", "github"]` and different avatars per provider, **When** querying the display avatar, **Then** the system returns the avatar from `provider_metadata[last_provider_used]`.

---

### Edge Cases

- What happens when a user tries to link a provider that's already linked to another account? (Conflict resolution)
- How does the system handle provider unlinking when it's the only linked provider? (Must keep at least one)
- What happens if OAuth provider returns no email or avatar? (Handle null provider metadata fields)
- How does the system behave if `role_assigned_by` references a deleted admin user? (Preserve audit trail)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store user role as one of: `anonymous`, `free`, `paid`, `operator`
- **FR-002**: System MUST store email verification state as one of: `none`, `pending`, `verified`
- **FR-003**: System MUST store `pending_email` separately from `primary_email` to support verification workflows
- **FR-004**: System MUST maintain a list of linked authentication providers per user
- **FR-005**: System MUST store provider-specific metadata (sub claim, email, avatar, timestamps) for each linked provider
- **FR-006**: System MUST track which provider was most recently used for authentication
- **FR-007**: System MUST record role change audit trail (timestamp and attribution)
- **FR-008**: System MUST preserve backward compatibility with existing user records during migration
- **FR-009**: System MUST define a `ProviderMetadata` entity to structure per-provider data
- **FR-010**: System MUST support the providers: `email`, `google`, `github`

### Key Entities

- **User**: Core identity with role-based access. Key attributes: `role`, `verification`, `pending_email`, `primary_email`, `linked_providers`, `provider_metadata`, `last_provider_used`, role audit fields.
- **ProviderMetadata**: Per-provider OAuth data. Key attributes: `sub` (OAuth subject claim), `email`, `avatar`, `linked_at`, `verified_at` (for email provider).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 9 specified fields are present in the User model and persisted correctly
- **SC-002**: Existing user records continue to function (no breaking migration required for MVP)
- **SC-003**: ProviderMetadata class is defined and usable for storing provider-specific data
- **SC-004**: Unit tests achieve 100% coverage of new fields and ProviderMetadata class
- **SC-005**: User model validation prevents invalid field combinations (enforced in Feature 1163)

## Assumptions

- The existing `auth_type` field will be deprecated but retained for backward compatibility during transition
- The existing `email` field semantics map to `primary_email` (canonical verified email)
- The existing `is_operator` boolean maps to `role: "operator"`
- DynamoDB schema supports the new fields without migration (NoSQL flexibility)
- The role-verification state machine invariant (no `anonymous:verified` state) will be implemented in Feature 1163

## Dependencies

- **Feature 1163**: Role-verification invariant validator (to be implemented after this feature)
- **spec-v2.md**: Canonical specification for field definitions and state machine

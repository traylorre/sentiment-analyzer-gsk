# Feature Specification: OAuth-to-OAuth Link (Federation Flow 5)

**Feature Branch**: `1183-oauth-to-oauth-link`
**Created**: 2026-01-09
**Status**: Draft
**Input**: User description: "Feature 1183: OAuth-to-OAuth Link (Federation Flow 5). Auto-link when user with one OAuth provider tries another OAuth provider."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - OAuth User Links Second OAuth Provider (Priority: P1)

A user authenticated via Google OAuth later signs in via GitHub OAuth. The system automatically links both accounts since both OAuth providers verify their emails.

**Why this priority**: Core feature - enables seamless multi-provider authentication without friction.

**Independent Test**: User with Google account signs in with GitHub, accounts auto-link.

**Acceptance Scenarios**:

1. **Given** a user authenticated via Google OAuth, **When** they sign in via GitHub OAuth with the same verified email, **Then** both providers are linked to the same user account
2. **Given** OAuth-to-OAuth auto-link succeeds, **When** the user views their account, **Then** both providers appear in linked_providers
3. **Given** OAuth-to-OAuth auto-link succeeds, **When** the user logs out, **Then** they can sign in with either Google or GitHub

---

### User Story 2 - Prevent Duplicate OAuth Linking (Priority: P1)

When a user tries to link an OAuth account (`provider:sub`) that already belongs to a different user, the system rejects the link to prevent account hijacking.

**Why this priority**: Critical for security - prevents unauthorized access.

**Independent Test**: Attempt to link OAuth sub already owned by different user, receive error.

**Acceptance Scenarios**:

1. **Given** OAuth sub "github:123" is linked to user A, **When** user B tries to authenticate with the same GitHub account, **Then** AUTH_023 error is returned
2. **Given** AUTH_023 error occurs, **When** the user sees the error, **Then** they receive guidance on account recovery

---

### User Story 3 - Handle Unverified OAuth Email (Priority: P2)

When an OAuth provider returns `email_verified=false`, the system does not auto-link and requires manual verification.

**Why this priority**: Security boundary - prevents email spoofing attacks.

**Independent Test**: OAuth with unverified email triggers prompt/rejection.

**Acceptance Scenarios**:

1. **Given** OAuth provider returns email_verified=false, **When** auto-link is attempted, **Then** AUTH_022 error is returned
2. **Given** OAuth email is not verified, **When** the user sees the error, **Then** they are prompted to verify their email first

---

### Edge Cases

- What happens when user has Google linked and tries GitHub with different email?
  - Auto-link proceeds (OAuth-to-OAuth is trusted regardless of email domain)
- What happens when OAuth sub is already linked to same user?
  - Update last_provider_used, no error
- What happens when OAuth provider doesn't return email at all?
  - Still auto-link based on email_verified claim (email field is optional)

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST auto-link when existing OAuth user authenticates with different OAuth provider
- **FR-002**: System MUST check provider_sub uniqueness before linking to prevent account hijacking
- **FR-003**: System MUST reject auto-link with AUTH_023 if provider_sub belongs to different user
- **FR-004**: System MUST reject auto-link with AUTH_022 if email_verified=false
- **FR-005**: System MUST add new provider to linked_providers on successful auto-link
- **FR-006**: System MUST create provider_metadata entry for new OAuth provider
- **FR-007**: System MUST update last_provider_used to the newly linked provider
- **FR-008**: System MUST log AUTH_METHOD_LINKED audit event with link_type="auto"

### Key Entities

- **User.linked_providers**: List updated to include new OAuth provider (e.g., ["google", "github"])
- **User.provider_metadata**: Dict with metadata for each provider (sub, email, avatar, linked_at)
- **User.last_provider_used**: Updated to most recently used provider
- **provider_sub GSI**: Global secondary index for O(1) provider_sub collision detection

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: OAuth-to-OAuth auto-link completes in under 500ms (P90)
- **SC-002**: 100% of valid OAuth-to-OAuth links succeed without user intervention
- **SC-003**: 0% of invalid provider_sub links succeed (collision prevention)
- **SC-004**: All auto-link events are logged with full audit trail

## Assumptions

- OAuth providers (Google, GitHub) reliably return email_verified claim
- provider_sub GSI exists and is indexed for efficient collision detection
- Existing handle_oauth_callback() function can be extended for Flow 5 logic

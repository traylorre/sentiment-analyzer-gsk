# Feature Specification: OAuth Auto-Link for Email-Verified Users

**Feature Branch**: `1181-oauth-auto-link`
**Created**: 2026-01-09
**Status**: Draft
**Input**: User description: "Implement Federation Flow 3: Free:email → OAuth (Auto-Link Same Domain). When a user with email auth (e.g. user@gmail.com) tries OAuth with same domain (Google), auto-link the accounts."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Same-Domain Auto-Link (Priority: P1)

A user who signed up via magic link with a Gmail address (@gmail.com) decides to use Google OAuth for convenience. Since Google is authoritative for @gmail.com addresses, the system automatically links the OAuth identity to their existing account without requiring confirmation.

**Why this priority**: This is the primary happy path that most users will experience. Gmail users authenticating with Google represent the largest use case and should be seamless.

**Independent Test**: Can be fully tested by authenticating an existing @gmail.com user via Google OAuth and verifying the accounts are automatically linked with no user intervention.

**Acceptance Scenarios**:

1. **Given** a user exists with email "user@gmail.com" (free:email, verified), **When** they authenticate via Google OAuth returning the same email, **Then** the OAuth provider is automatically linked to their account without prompting.
2. **Given** a user exists with email "user@gmail.com" (free:email, verified), **When** Google OAuth is linked, **Then** their `linked_providers` includes both "email" and "google".
3. **Given** auto-linking occurs, **When** the link completes, **Then** an audit event `AUTH_METHOD_LINKED` is logged with `link_type: "auto"`.

---

### User Story 2 - Cross-Domain Manual Linking (Priority: P2)

A user who signed up via magic link with a non-Gmail address (e.g., @hotmail.com) attempts Google OAuth. Since the domains don't match, the system prompts them to choose whether to link the accounts or keep them separate.

**Why this priority**: Cross-domain scenarios are less common but require explicit user consent to prevent accidental account confusion.

**Independent Test**: Can be tested by authenticating a @hotmail.com user via Google OAuth and verifying a prompt appears asking to link or keep separate.

**Acceptance Scenarios**:

1. **Given** a user exists with email "ceo@hotmail.com" (free:email, verified), **When** they authenticate via Google OAuth returning "ceo@gmail.com", **Then** a prompt appears asking "Link accounts or use Google only?"
2. **Given** the user chooses "Link Accounts", **When** the operation completes, **Then** both email addresses are associated with the same user account.
3. **Given** the user chooses "Use Google Only", **When** the operation completes, **Then** a new separate session is created without linking.

---

### User Story 3 - GitHub Always Requires Confirmation (Priority: P3)

Any user attempting GitHub OAuth receives a manual linking prompt, regardless of their email domain. GitHub is considered an "opaque" identity provider where email is not the primary identifier.

**Why this priority**: GitHub users are a smaller segment and the additional confirmation step ensures security for developer accounts.

**Independent Test**: Can be tested by authenticating any email-verified user via GitHub OAuth and verifying a confirmation prompt always appears.

**Acceptance Scenarios**:

1. **Given** a user exists with any email (free:email, verified), **When** they authenticate via GitHub OAuth, **Then** a prompt always appears asking to link or keep separate.
2. **Given** GitHub OAuth email matches the user's existing email, **When** they choose to link, **Then** the audit event shows `link_type: "manual"`.

---

### Edge Cases

- What happens when the OAuth provider returns `email_verified: false`? → Reject linking with AUTH_022 error.
- What happens when the OAuth account is already linked to a different user? → Reject with AUTH_023 error ("This OAuth account is already linked").
- What happens when a user has no existing session? → This is Flow 1/2, not Flow 3; redirect to standard OAuth signup.
- What happens when the user cancels the linking prompt? → Session continues with original identity, no changes made.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement `can_auto_link_oauth(oauth_claims, existing_user)` function to determine if auto-linking is allowed.
- **FR-002**: System MUST auto-link when OAuth provider is Google AND user's existing email ends with `@gmail.com`.
- **FR-003**: System MUST prompt for manual confirmation when OAuth provider is GitHub (any domain).
- **FR-004**: System MUST prompt for manual confirmation when OAuth email domain differs from existing user's email domain.
- **FR-005**: System MUST reject linking if OAuth `email_verified` claim is false (error AUTH_022).
- **FR-006**: System MUST reject linking if OAuth `sub` is already linked to a different user (error AUTH_023) using `get_user_by_provider_sub()`.
- **FR-007**: System MUST implement `link_oauth_to_existing(user, provider, oauth_claims, auto_link)` function.
- **FR-008**: When linking, system MUST update: `linked_providers`, `provider_metadata[provider]`, and `last_provider_used`.
- **FR-009**: System MUST log `AuthEventType.AUTH_METHOD_LINKED` with appropriate `link_type` ("auto" or "manual").
- **FR-010**: System MUST NOT change user role during linking (role remains unchanged).

### Key Entities

- **User**: The existing email-verified user with `linked_providers`, `provider_metadata`, and `last_provider_used` fields.
- **ProviderMetadata**: Per-provider data including `sub`, `email`, `avatar`, and `linked_at` timestamp.
- **OAuthClaims**: External data from OAuth provider including `sub`, `email`, `email_verified`, and profile information.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Gmail users authenticating with Google OAuth complete linking in under 3 seconds with no additional prompts.
- **SC-002**: All linking operations complete with appropriate audit trail entries.
- **SC-003**: Zero instances of OAuth accounts being linked to multiple users (enforced by provider_sub uniqueness).
- **SC-004**: 100% of unverified OAuth emails are rejected with clear error messaging.
- **SC-005**: Manual linking prompts display within 500ms of OAuth callback completion.

## Assumptions

- The `get_user_by_provider_sub()` helper function exists (Feature 1180).
- The `by_provider_sub` GSI exists in DynamoDB for O(1) lookup.
- User model already has `linked_providers`, `provider_metadata`, and `last_provider_used` fields.
- Frontend can render a linking confirmation dialog for manual linking cases.

# Feature Specification: Email-to-OAuth Link (Federation Flow 4)

**Feature Branch**: `1182-email-to-oauth-link`
**Created**: 2026-01-09
**Status**: Draft
**Input**: User description: "Feature 1182: Email-to-OAuth Link (Federation Flow 4). Allow OAuth-authenticated users to add email verification later via magic link."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - OAuth User Initiates Email Linking (Priority: P1)

An OAuth user (e.g., signed in with Google) wants to add email as an additional authentication method so they can sign in with either method in the future.

**Why this priority**: Core feature - without this, OAuth users cannot add email verification to their accounts, blocking multi-provider auth for this flow direction.

**Independent Test**: Can be fully tested by OAuth user clicking "Add Email" button, entering email, and verifying magic link is sent. Delivers the ability to start the linking process.

**Acceptance Scenarios**:

1. **Given** an OAuth user is authenticated (e.g., via Google), **When** they navigate to account settings and click "Add Email", **Then** they see an input field for their email address
2. **Given** an OAuth user has entered a valid email address, **When** they submit the form, **Then** a magic link is sent to that email address
3. **Given** a magic link has been sent, **When** the user checks their email, **Then** they receive an email with a verification link within 2 minutes

---

### User Story 2 - User Completes Email Verification (Priority: P1)

A user who has initiated email linking clicks the magic link in their email to complete the verification and add email as a linked provider.

**Why this priority**: Core feature - completing the link is essential for the feature to deliver any value.

**Independent Test**: Can be tested by clicking a valid magic link and verifying email is added to linked_providers list.

**Acceptance Scenarios**:

1. **Given** a user has received a magic link email, **When** they click the link within the validity window, **Then** email is added to their linked_providers
2. **Given** email linking is completed, **When** the user views their account settings, **Then** email appears as a linked authentication method
3. **Given** email linking is completed, **When** the user logs out and attempts to sign in, **Then** they can choose to sign in with email magic link OR their original OAuth provider

---

### User Story 3 - Error Handling for Invalid Links (Priority: P2)

A user who clicks an expired or already-used magic link receives a clear error message and guidance on how to proceed.

**Why this priority**: Important for user experience but not blocking core functionality.

**Independent Test**: Can be tested by attempting to use expired or reused tokens and verifying error handling.

**Acceptance Scenarios**:

1. **Given** a magic link has expired (past validity window), **When** the user clicks the link, **Then** they see an error message indicating the link is invalid
2. **Given** a magic link has already been used, **When** the user clicks the same link again, **Then** they see an error message indicating the link is invalid
3. **Given** an invalid link error occurs, **When** the user views the error, **Then** they see guidance on requesting a new magic link

---

### Edge Cases

- What happens when a user tries to link an email that is already linked to their account?
  - System rejects with clear error: "Email already linked to this account"
- What happens when a user initiates email linking twice before completing the first?
  - Second request overwrites pending_email, first magic link becomes invalid
- What happens when the user logs out before clicking the magic link?
  - pending_email persists on User object; link remains valid until expiry
- How does system handle concurrent link attempts from same user?
  - Only most recent pending_email is stored; previous magic links become orphaned (still valid tokens but may conflict)

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST allow OAuth-authenticated users to initiate email linking from account settings
- **FR-002**: System MUST send a magic link to the provided email address when linking is initiated
- **FR-003**: System MUST store the pending email address on the User record until verification completes or is abandoned
- **FR-004**: System MUST add "email" to linked_providers when the magic link is successfully verified
- **FR-005**: System MUST create provider_metadata entry for email with linked_at and verified_at timestamps
- **FR-006**: System MUST clear pending_email after successful verification
- **FR-007**: System MUST reject email linking if "email" is already in linked_providers with clear error message
- **FR-008**: System MUST log AUTH_METHOD_LINKED audit event upon successful linking
- **FR-009**: System MUST return generic error (AUTH_010) for invalid, expired, or reused magic links to prevent enumeration attacks

### Key Entities

- **User.pending_email**: String or null - email address awaiting verification via magic link
- **User.linked_providers**: List of provider types - updated to include "email" upon successful linking
- **User.provider_metadata["email"]**: Provider metadata containing email, linked_at, and verified_at timestamps
- **MagicLinkToken**: Verification token containing email claim, user_id context, expiry, and usage status

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: OAuth users can complete email linking flow in under 5 minutes (from initiation to verification)
- **SC-002**: Magic link emails are delivered within 2 minutes of initiation
- **SC-003**: 100% of valid magic link clicks successfully complete email linking
- **SC-004**: Invalid/expired magic link attempts return consistent error responses within 200ms (no timing attacks)
- **SC-005**: All email linking events are logged with full audit trail for security compliance

## Assumptions

- Magic link token validity window follows existing system configuration (typically 15-30 minutes)
- Email uniqueness enforcement is handled at database constraint level, not within this flow
- The "Add Email" UI component exists or will be created as part of a separate UI feature
- Existing magic link generation and verification infrastructure is available and follows established patterns

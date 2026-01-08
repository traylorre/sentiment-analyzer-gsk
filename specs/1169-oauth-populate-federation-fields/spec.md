# Feature Specification: OAuth Populate Federation Fields

**Feature Branch**: `1169-oauth-populate-federation-fields`
**Created**: 2026-01-07
**Status**: Draft
**Input**: OAuth callback missing federation field population. handle_oauth_callback() in auth.py extracts JWT claims (sub, email, picture) but never populates User model fields: linked_providers, provider_metadata[provider], last_provider_used. Must create _link_provider() helper to update these fields when OAuth completes. Critical for multi-provider support.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - First OAuth Sign-In (Priority: P1)

A new user signs in using Google OAuth for the first time. The system should record that Google is now a linked provider and store Google's metadata (subject ID, email, avatar URL).

**Why this priority**: This is the foundational flow - without capturing provider metadata on first sign-in, no federation features can work.

**Independent Test**: Can be fully tested by completing Google OAuth flow and querying the User record to verify linked_providers contains "google" and provider_metadata["google"] contains the expected fields.

**Acceptance Scenarios**:

1. **Given** a new user with no account, **When** they complete Google OAuth sign-in, **Then** their User record has `linked_providers: ["google"]` and `provider_metadata["google"]` populated with sub, email, avatar, linked_at
2. **Given** a new user with no account, **When** they complete Google OAuth sign-in, **Then** `last_provider_used` is set to "google"

---

### User Story 2 - Returning User OAuth Sign-In (Priority: P1)

An existing user signs in again using the same OAuth provider. The system should update `last_provider_used` timestamp and refresh provider metadata if changed.

**Why this priority**: Essential for tracking user activity and keeping provider metadata current.

**Independent Test**: Can be tested by signing in twice with the same provider and verifying provider_metadata timestamps update.

**Acceptance Scenarios**:

1. **Given** an existing user with Google linked, **When** they sign in via Google again, **Then** `last_provider_used` remains "google" and `provider_metadata["google"].linked_at` is updated if metadata changed
2. **Given** an existing user with Google linked, **When** they sign in via Google with a different avatar, **Then** `provider_metadata["google"].avatar` is updated

---

### User Story 3 - Link Additional Provider (Priority: P2)

An existing user who signed up with Google later links their GitHub account. The system should add GitHub to linked_providers while preserving Google.

**Why this priority**: Multi-provider support is the key federation value proposition but depends on basic provider storage working first.

**Independent Test**: Can be tested by signing in with Google, then completing GitHub OAuth, and verifying both providers appear in linked_providers.

**Acceptance Scenarios**:

1. **Given** an existing user with only Google linked, **When** they complete GitHub OAuth flow, **Then** `linked_providers` is `["google", "github"]`
2. **Given** an existing user with only Google linked, **When** they complete GitHub OAuth flow, **Then** `provider_metadata["github"]` is populated and `provider_metadata["google"]` is preserved
3. **Given** an existing user with only Google linked, **When** they complete GitHub OAuth flow, **Then** `last_provider_used` is updated to "github"

---

### Edge Cases

- What happens when provider returns no avatar URL? System should store null for avatar field, not fail.
- What happens when provider email differs from existing primary_email? System should NOT overwrite primary_email; provider email goes only in provider_metadata.
- What happens when the same provider is linked twice (duplicate)? System should update metadata, not create duplicate entry in linked_providers.
- What happens when JWT claims are missing sub claim? System should fail gracefully - sub is required for provider identity.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST extract provider identity (sub claim) from OAuth JWT claims
- **FR-002**: System MUST add the OAuth provider to `linked_providers` if not already present
- **FR-003**: System MUST NOT create duplicate entries in `linked_providers` when user re-authenticates with same provider
- **FR-004**: System MUST create or update `provider_metadata[provider]` with sub, email, avatar, and linked_at fields
- **FR-005**: System MUST set `last_provider_used` to the current OAuth provider
- **FR-006**: System MUST preserve existing linked_providers and provider_metadata when linking additional providers
- **FR-007**: System MUST handle missing optional claims (avatar, email) gracefully by storing null
- **FR-008**: System MUST fail if required claim (sub) is missing from OAuth JWT

### Key Entities

- **User**: The authenticated user account with federation fields (linked_providers, provider_metadata, last_provider_used)
- **ProviderMetadata**: Per-provider OAuth data including sub (provider subject ID), email, avatar, linked_at, verified_at
- **ProviderType**: Enum of supported OAuth providers (google, github, email)

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of successful OAuth sign-ins result in provider being present in `linked_providers`
- **SC-002**: 100% of successful OAuth sign-ins result in `provider_metadata[provider]` containing valid sub and linked_at values
- **SC-003**: 100% of successful OAuth sign-ins result in `last_provider_used` matching the OAuth provider used
- **SC-004**: 0% of OAuth sign-ins create duplicate provider entries in `linked_providers`
- **SC-005**: Users can link up to 3 OAuth providers (google, github, email) to a single account

## Assumptions

- OAuth JWT claims are already being decoded correctly in `handle_oauth_callback()` (existing functionality)
- The User model already has the federation fields defined (Feature 1162 complete)
- DynamoDB serialization/deserialization for federation fields already works (Feature 1162 complete)
- Cognito user pool is configured and returns standard OIDC claims (sub, email, picture)

## Dependencies

- Feature 1162 (User Model Federation Fields) - COMPLETED
- Cognito identity provider configuration - COMPLETED

## Out of Scope

- Role advancement on OAuth (separate feature 1170)
- Email verification marking (separate feature 1171)
- Frontend display of linked providers (Phase 2)
- Provider unlinking (future feature)

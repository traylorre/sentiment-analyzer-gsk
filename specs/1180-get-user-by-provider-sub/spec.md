# Feature Specification: Get User by Provider Sub Helper

**Feature Branch**: `1180-get-user-by-provider-sub`
**Created**: 2026-01-10
**Status**: Draft
**Input**: User description: "Implement get_user_by_provider_sub(provider, sub) helper function for account linking flows"

## Problem Statement

The account linking flows (Features 3-5 in federation) require looking up users by their OAuth provider's subject claim (sub). Currently, there is no way to query users by provider_sub in DynamoDB, which is needed to:

1. Detect if an OAuth account is already linked to a different user
2. Prevent duplicate provider linking across user accounts
3. Enable OAuth-to-OAuth auto-linking

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prevent Duplicate OAuth Linking (Priority: P1)

When a user attempts to link an OAuth provider (Google/GitHub) that is already linked to another user account, the system must detect this and prevent the duplicate linking to maintain account integrity.

**Why this priority**: Duplicate provider linking would break the identity model - one OAuth identity must map to exactly one user account.

**Independent Test**: Can be tested by creating two users, linking Google to user A, then attempting to link the same Google account to user B.

**Acceptance Scenarios**:

1. **Given** user A has Google OAuth linked with sub "123456", **When** user B attempts to link the same Google OAuth, **Then** the system returns the existing user A record indicating a conflict.

2. **Given** an OAuth sub "123456" that has never been linked, **When** the system queries for this sub, **Then** it returns None indicating no existing link.

3. **Given** multiple users with different OAuth providers, **When** querying by provider+sub combination, **Then** only the exact matching user is returned.

---

### User Story 2 - OAuth Auto-Link Detection (Priority: P2)

When a user authenticates via a new OAuth provider, the system must efficiently check if that provider is already linked to detect auto-linking opportunities.

**Why this priority**: Auto-linking improves user experience by seamlessly connecting accounts that share verified identity.

**Independent Test**: Can be tested by querying for provider+sub combinations and verifying correct user lookup.

**Acceptance Scenarios**:

1. **Given** a user with Google linked (sub="google-123"), **When** querying for ("google", "google-123"), **Then** the correct user is returned.

2. **Given** a user with GitHub linked (sub="gh-456"), **When** querying for ("google", "google-123"), **Then** None is returned (different provider).

3. **Given** a query for non-existent sub, **When** querying for ("google", "nonexistent"), **Then** None is returned.

---

### User Story 3 - Efficient Query Performance (Priority: P1)

The provider lookup must complete quickly (sub-100ms) to not impact OAuth callback latency. This requires a GSI-based solution, not a table scan.

**Why this priority**: OAuth callbacks have strict timeout requirements; slow lookups would cause authentication failures.

**Independent Test**: Can be tested by measuring query latency with representative data.

**Acceptance Scenarios**:

1. **Given** a GSI on provider_sub, **When** querying by provider+sub, **Then** the query completes in under 100ms.

2. **Given** 100,000 users in the table, **When** querying by provider+sub, **Then** performance remains constant (O(1) not O(n)).

---

### Edge Cases

- What happens when querying with empty provider or sub?
- How does the system handle malformed provider_sub index values?
- What if a user has multiple providers with the same sub from different providers?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `get_user_by_provider_sub(provider, sub)` function that returns a User or None
- **FR-002**: System MUST use a GSI for O(1) query performance, not table scans
- **FR-003**: System MUST support querying by composite key of provider+sub (e.g., "google:118368473829470293847")
- **FR-004**: System MUST return None when no matching user exists
- **FR-005**: System MUST return the full User object when a match is found
- **FR-006**: System MUST handle invalid inputs gracefully (empty strings, None values)

### Non-Functional Requirements

- **NFR-001**: Query latency MUST be under 100ms at p99
- **NFR-002**: Solution MUST not require full table scans
- **NFR-003**: GSI MUST be added via Terraform (infrastructure as code)

### Key Entities

- **User**: Existing user model with provider_metadata field
- **GSI (by_provider_sub)**: New Global Secondary Index for provider+sub lookups
  - Hash Key: `provider_sub` (composite string: "{provider}:{sub}")
  - Projected: `PK`, `SK`, all user attributes (or keys-only with subsequent get_item)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `get_user_by_provider_sub("google", "123456")` returns correct user when linked
- **SC-002**: `get_user_by_provider_sub("google", "nonexistent")` returns None
- **SC-003**: Query completes in under 100ms (measured in unit tests)
- **SC-004**: Integration tests verify GSI-based lookup works correctly
- **SC-005**: Account linking flows can use this function to detect duplicates

## Assumptions

- The `provider_sub` field will be stored as a composite string "{provider}:{sub}" to enable single-attribute GSI
- The GSI will use on-demand capacity (consistent with existing GSIs)
- The function will be added to `src/lambdas/dashboard/auth.py` alongside existing user lookup functions
- Terraform changes will be applied separately from code changes (standard deployment)

## Out of Scope

- Migration of existing users to populate provider_sub field (they already have provider_metadata)
- Multi-region GSI replication
- Caching of provider_sub lookups
- Backfilling provider_sub for historical users (handled by separate migration if needed)

## Implementation Notes

### Populating provider_sub

When `_link_provider()` is called, it should also update a `provider_sub` attribute on the user record with the composite key "{provider}:{sub}". This enables the GSI to index it.

### GSI Design

```
Index Name: by_provider_sub
Hash Key: provider_sub (String) - format: "{provider}:{sub}"
Projection: KEYS_ONLY (then use get_item for full user)
```

Using KEYS_ONLY projection minimizes GSI storage costs while still enabling the lookup use case.

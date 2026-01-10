# Feature Specification: OAuth State Validation

**Feature Branch**: `1185-oauth-state-validation`
**Created**: 2026-01-10
**Status**: Draft
**Input**: A12-A13: OAuth state must store and validate redirect_uri (prevent redirect attacks) and provider (prevent provider confusion). On callback, assert state.redirect_uri matches and state.provider matches. Security-critical.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prevent OAuth Redirect Attacks (Priority: P1)

An attacker attempts to intercept OAuth flow by modifying the callback redirect_uri. The system validates that the redirect_uri in the state matches the actual callback request, preventing the attack.

**Why this priority**: Security-critical. Open redirect vulnerabilities allow token theft and phishing attacks.

**Independent Test**: Can be tested by attempting callback with mismatched redirect_uri and verifying rejection with 400/401.

**Acceptance Scenarios**:

1. **Given** user initiates OAuth with redirect_uri "https://app.example.com/callback", **When** attacker sends callback with redirect_uri "https://evil.com/steal", **Then** system returns 400 "Invalid OAuth state"
2. **Given** user initiates OAuth with redirect_uri "https://app.example.com/callback", **When** legitimate callback arrives with matching redirect_uri, **Then** authentication succeeds

---

### User Story 2 - Prevent Provider Confusion Attacks (Priority: P1)

An attacker attempts to confuse the system by initiating OAuth with provider "google" but sending callback claiming provider "github". The system validates the provider matches the original request.

**Why this priority**: Security-critical. Provider confusion can lead to account takeover by linking wrong OAuth identity.

**Independent Test**: Can be tested by initiating OAuth for Google but sending callback claiming GitHub, verifying rejection.

**Acceptance Scenarios**:

1. **Given** user initiates OAuth with provider "google", **When** callback claims provider "github", **Then** system returns 400 "Invalid OAuth state"
2. **Given** user initiates OAuth with provider "google", **When** callback claims provider "google", **Then** authentication proceeds

---

### User Story 3 - State Expiration (Priority: P2)

OAuth state tokens expire after a reasonable time window to prevent replay attacks using stale authorization codes.

**Why this priority**: Defense in depth. Limits attack window for intercepted state values.

**Independent Test**: Can be tested by waiting past expiry and attempting callback, verifying rejection.

**Acceptance Scenarios**:

1. **Given** OAuth state was generated 10 minutes ago, **When** callback arrives with that state, **Then** system returns 400 "OAuth state expired"
2. **Given** OAuth state was generated 1 minute ago, **When** callback arrives with that state, **Then** authentication proceeds

---

### Edge Cases

- What happens when state parameter is missing from callback? Return 400 "Missing OAuth state"
- What happens when state is malformed/invalid? Return 400 "Invalid OAuth state" (generic message)
- What happens when state was already used (replay)? Return 400 "OAuth state already used"

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate a cryptographically secure random state value for each OAuth authorization request
- **FR-002**: System MUST store state with associated metadata: redirect_uri, provider, created_at, user_id (if available)
- **FR-003**: System MUST include state parameter in OAuth authorization URL
- **FR-004**: System MUST validate state parameter is present in callback request
- **FR-005**: System MUST validate state.redirect_uri matches callback redirect_uri
- **FR-006**: System MUST validate state.provider matches callback provider
- **FR-007**: System MUST reject states older than 5 minutes (configurable)
- **FR-008**: System MUST mark states as "used" after successful validation (one-time use)
- **FR-009**: System MUST use generic error messages that don't reveal validation details (prevent enumeration)

### Key Entities

- **OAuthState**: Represents a pending OAuth authorization
  - state_id: Cryptographically secure random string (32 bytes, URL-safe base64)
  - provider: The OAuth provider ("google" | "github")
  - redirect_uri: The expected callback redirect URI
  - created_at: When the state was generated
  - user_id: Optional anonymous user ID if linking accounts
  - used: Boolean flag for one-time use enforcement

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All OAuth callback attempts without valid state are rejected with 400 status
- **SC-002**: All OAuth callback attempts with mismatched redirect_uri are rejected
- **SC-003**: All OAuth callback attempts with mismatched provider are rejected
- **SC-004**: All OAuth callback attempts with expired state (>5 min) are rejected
- **SC-005**: All OAuth callback attempts with already-used state are rejected
- **SC-006**: Error messages do not reveal which specific validation failed (enumeration prevention)

## Assumptions

- State will be stored in DynamoDB with TTL for automatic cleanup
- State ID will use `secrets.token_urlsafe(32)` for cryptographic randomness
- CSRF double-submit cookies remain as additional layer but OAuth state provides primary CSRF protection
- The 5-minute expiry is sufficient for normal OAuth flows

## Out of Scope

- PKCE implementation (separate feature)
- OAuth state encryption (not required for this security level)
- Rate limiting on state generation (separate feature)

# Feature Specification: OAuth State/CSRF Validation

**Feature Branch**: `1193-oauth-state-csrf`
**Created**: 2026-01-11
**Status**: Draft
**Input**: Add OAuth state parameter for CSRF protection

## User Scenarios & Testing _(mandatory)_

### User Story 1 - CSRF-Protected OAuth Flow (Priority: P1)

Users complete OAuth authentication with automatic CSRF protection, preventing attackers from initiating OAuth flows on their behalf.

**Why this priority**: CSRF protection is a security requirement. Without state validation, attackers can trick users into linking attacker-controlled OAuth accounts.

**Independent Test**: Can be tested by completing OAuth flow and verifying state parameter matches between authorize URL and callback.

**Acceptance Scenarios**:

1. **Given** user clicks "Continue with Google", **When** redirect to OAuth provider occurs, **Then** authorize URL includes state parameter stored by frontend.
2. **Given** OAuth provider redirects back with code and state, **When** frontend calls callback API, **Then** state from URL is sent to backend for validation.
3. **Given** backend receives state parameter, **When** state is valid and unused, **Then** tokens are issued and state marked as used.

---

### User Story 2 - State Mismatch Protection (Priority: P1)

When state parameter doesn't match or is missing, authentication fails with clear error message.

**Why this priority**: This is the core security feature - detecting CSRF attacks.

**Independent Test**: Can be tested by tampering with state parameter and verifying authentication fails.

**Acceptance Scenarios**:

1. **Given** attacker modifies state in callback URL, **When** frontend sends mismatched state, **Then** backend rejects with "Invalid OAuth state" error.
2. **Given** user opens OAuth link directly (no stored state), **When** callback received without prior state storage, **Then** frontend shows "Authentication session expired" error.

---

### User Story 3 - Provider-Specific State (Priority: P2)

Each OAuth provider (Google, GitHub) uses separate state values to prevent provider confusion attacks.

**Why this priority**: Prevents A13 vulnerability where attacker uses Google state with GitHub callback.

**Independent Test**: Can be tested by verifying different state values for each provider in OAuth URLs response.

**Acceptance Scenarios**:

1. **Given** user requests OAuth URLs, **When** response received, **Then** each provider has unique state value.
2. **Given** user authenticates with Google using Google's state, **When** callback sent with provider="github", **Then** backend rejects (provider mismatch).

---

### Edge Cases

- What happens when state expires (>5 minutes)?
  - Backend rejects with "Invalid OAuth state" error
- What happens when same state is used twice (replay attack)?
  - Backend rejects second attempt (state marked as used)
- What happens when redirect_uri doesn't match?
  - Backend rejects with "Invalid OAuth state" error
- What happens when user has multiple tabs with OAuth flows?
  - Each tab stores its own state in sessionStorage (isolated)

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST extract provider-specific state from `/api/v2/auth/oauth/urls` response
- **FR-002**: System MUST store state in sessionStorage before redirecting to OAuth provider
- **FR-003**: System MUST extract state parameter from OAuth callback URL
- **FR-004**: System MUST send state in callback API request body
- **FR-005**: System MUST send redirect_uri in callback API request body
- **FR-006**: System MUST display "Authentication session expired" when state missing from sessionStorage
- **FR-007**: System MUST display backend error message when state validation fails
- **FR-008**: System MUST update authApi.exchangeOAuthCode to include state and redirect_uri parameters

### Key Entities

- **OAuth State**: 43-character URL-safe base64 string with 5-minute TTL
- **Callback Parameters**: code, state, provider, redirect_uri (all required by backend)
- **Storage**: sessionStorage for cross-tab isolation

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of OAuth callbacks include state parameter in API request
- **SC-002**: State mismatch attacks result in immediate rejection (no token exchange attempted)
- **SC-003**: Each OAuth provider receives unique state value
- **SC-004**: State is cleared from sessionStorage after callback processing

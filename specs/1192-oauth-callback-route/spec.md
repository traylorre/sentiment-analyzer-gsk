# Feature Specification: OAuth Callback Route Handler

**Feature Branch**: `1192-oauth-callback-route`
**Created**: 2026-01-11
**Status**: Draft
**Input**: Create frontend route at /auth/callback to receive authorization codes from OAuth providers

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Google OAuth Completion (Priority: P1)

A user clicks "Continue with Google" on the sign-in page, authenticates with Google, and is redirected back to the application where the OAuth flow completes automatically, landing them on the dashboard.

**Why this priority**: This is the core happy path that enables OAuth authentication to function. Without this, the OAuth flow is broken at the redirect step.

**Independent Test**: Can be fully tested by clicking Google OAuth button, completing Google consent, and verifying automatic redirect to dashboard with authenticated session.

**Acceptance Scenarios**:

1. **Given** user initiated Google OAuth from sign-in page, **When** Google redirects back with authorization code in URL, **Then** the callback page extracts the code and provider, calls the backend token exchange, and redirects user to dashboard.
2. **Given** user has valid authorization code, **When** callback page processes the code, **Then** user sees a loading indicator during the token exchange (no blank screen).
3. **Given** backend successfully exchanges code for tokens, **When** callback receives tokens with federation fields, **Then** user is authenticated with correct role and linkedProviders populated.

---

### User Story 2 - GitHub OAuth Completion (Priority: P1)

A user clicks "Continue with GitHub" on the sign-in page, authenticates with GitHub, and is redirected back to the application where the OAuth flow completes automatically.

**Why this priority**: GitHub is a key alternative OAuth provider; both providers must work for OAuth feature completeness.

**Independent Test**: Can be fully tested by clicking GitHub OAuth button, completing GitHub consent, and verifying automatic redirect to dashboard.

**Acceptance Scenarios**:

1. **Given** user initiated GitHub OAuth from sign-in page, **When** GitHub redirects back with authorization code, **Then** the callback page processes the code identically to Google flow.
2. **Given** GitHub user has email set to private, **When** callback processes response, **Then** user is still authenticated (backend handles email-less GitHub accounts).

---

### User Story 3 - OAuth Error Display (Priority: P2)

When OAuth fails (user denies consent, invalid code, or backend error), the user sees a clear error message with option to retry.

**Why this priority**: Error handling ensures users are not stuck on a broken page when OAuth fails.

**Independent Test**: Can be tested by simulating OAuth denial or network error and verifying error message display.

**Acceptance Scenarios**:

1. **Given** user denied OAuth consent at provider, **When** provider redirects back with error parameter, **Then** callback page displays "Authentication cancelled" message with retry button.
2. **Given** authorization code is expired or invalid, **When** backend returns error during token exchange, **Then** callback page displays error message with retry option.
3. **Given** network error occurs during token exchange, **When** API call fails, **Then** callback page displays "Connection error" with retry button.

---

### User Story 4 - Account Conflict Handling (Priority: P2)

When a user attempts OAuth with an email already registered via different method, the callback displays appropriate conflict information.

**Why this priority**: Federation conflicts must be handled gracefully to guide users to correct sign-in method.

**Independent Test**: Can be tested by creating magic-link account then attempting OAuth with same email.

**Acceptance Scenarios**:

1. **Given** user's OAuth email matches existing magic-link account, **When** backend returns conflict response, **Then** callback displays "This email is already registered" with guidance to use existing method.

---

### Edge Cases

- What happens when callback URL lacks required parameters (code or provider)?
  - Display "Invalid callback" error with link to sign-in page
- What happens when user manually navigates to /auth/callback without OAuth flow?
  - Display "No authentication in progress" message with sign-in link
- What happens when user refreshes the callback page during token exchange?
  - Token exchange should be idempotent or show error if code was already used
- What happens when user has multiple tabs with OAuth flows?
  - Each tab handles its own callback independently

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST create a route handler at `/auth/callback` that receives OAuth provider redirects
- **FR-002**: System MUST extract `code` and `state` parameters from the callback URL query string
- **FR-003**: System MUST determine the OAuth provider (google/github) from the `state` parameter or URL structure
- **FR-004**: System MUST call `handleCallback(code, provider)` from the useAuth hook to exchange code for tokens
- **FR-005**: System MUST display a loading indicator while the token exchange is in progress
- **FR-006**: System MUST redirect to dashboard (`/`) upon successful authentication
- **FR-007**: System MUST display an error message with retry option when OAuth fails
- **FR-008**: System MUST handle missing or malformed URL parameters gracefully
- **FR-009**: System MUST handle backend error responses (4xx, 5xx) with user-friendly messages
- **FR-010**: System MUST handle conflict responses (email already registered) with appropriate guidance

### Key Entities

- **Callback URL Parameters**: `code` (authorization code from provider), `state` (CSRF token with encoded provider info), `error` (provider error if user denied)
- **Auth Response**: User profile with federation fields, access/refresh tokens, session expiry
- **Error States**: Provider denial, invalid code, network error, conflict response

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Users completing OAuth flow are redirected to dashboard within 3 seconds of callback
- **SC-002**: 100% of valid OAuth callbacks result in authenticated session (no silent failures)
- **SC-003**: Users see loading indicator within 100ms of callback page load (no blank screen)
- **SC-004**: All error scenarios display actionable message with retry option within 1 second
- **SC-005**: OAuth callback success rate matches backend OAuth endpoint success rate (no frontend-only failures)

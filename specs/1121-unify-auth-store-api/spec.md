# Feature Specification: Unify Auth-Store API Client

**Feature Branch**: `1121-unify-auth-store-api`
**Created**: 2026-01-03
**Status**: Draft
**Input**: User description: "The auth-store.ts file has a critical bug where some methods use raw fetch() with relative URLs instead of using the authApi client. This causes requests to go to the Next.js frontend server (which returns 404) instead of the Lambda Function URL backend."

## Problem Statement

The frontend authentication store (`auth-store.ts`) has inconsistent API call patterns:
- `signInAnonymous()` correctly uses `authApi.createAnonymousSession()`
- Other methods (`signInWithMagicLink`, `verifyMagicLink`, `signInWithOAuth`, `handleOAuthCallback`, `refreshSession`, `signOut`) use raw `fetch()` with relative URLs like `/api/v2/auth/magic-link`

When using relative URLs with `fetch()`, requests go to the Next.js frontend server instead of the Lambda backend configured via `NEXT_PUBLIC_API_URL`. This causes 404 errors for OAuth URLs, magic link verification, and other auth operations.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - OAuth Sign-In Flow (Priority: P1)

A user clicks "Continue with Google" to sign in with their Google account. The system retrieves OAuth authorization URLs from the backend and redirects them to Google's consent screen.

**Why this priority**: OAuth sign-in is the primary authentication method. Without it working, users cannot authenticate beyond anonymous sessions.

**Independent Test**: Can be fully tested by clicking "Continue with Google" and verifying the redirect to Google's consent screen without 404 errors.

**Acceptance Scenarios**:

1. **Given** a user on the sign-in page, **When** they click "Continue with Google", **Then** the system fetches OAuth URLs from the backend and redirects to Google's authorization endpoint
2. **Given** a user on the sign-in page, **When** the OAuth URLs request fails, **Then** the user sees an error message indicating authentication is unavailable

---

### User Story 2 - OAuth Callback Processing (Priority: P1)

After authenticating with Google/GitHub, the user is redirected back to the application with an authorization code. The system exchanges this code for authentication tokens.

**Why this priority**: This completes the OAuth flow - without it, users cannot finish signing in after authorizing with Google/GitHub.

**Independent Test**: Can be tested by completing an OAuth flow and verifying the callback successfully creates a session without 404 errors.

**Acceptance Scenarios**:

1. **Given** a user returning from Google with an authorization code, **When** the callback is processed, **Then** the system exchanges the code for tokens and establishes a session
2. **Given** an invalid or expired authorization code, **When** the callback is processed, **Then** the user sees an appropriate error message

---

### User Story 3 - Magic Link Authentication (Priority: P2)

A user requests a magic link to their email, receives it, clicks the link, and is authenticated.

**Why this priority**: Magic link is an alternative authentication method, less critical than OAuth but still important for users without social accounts.

**Independent Test**: Can be tested by requesting a magic link, clicking it, and verifying successful authentication.

**Acceptance Scenarios**:

1. **Given** a user on the sign-in page, **When** they enter their email and request a magic link, **Then** the request is sent to the backend without errors
2. **Given** a user clicking a magic link, **When** the link is verified, **Then** the user is authenticated and redirected to the dashboard

---

### User Story 4 - Session Refresh (Priority: P2)

An authenticated user's access token expires. The system automatically refreshes the token using the refresh token.

**Why this priority**: Session refresh prevents users from being unexpectedly logged out during long sessions.

**Independent Test**: Can be tested by waiting for token expiration and verifying automatic refresh without errors.

**Acceptance Scenarios**:

1. **Given** a user with an expiring access token, **When** the token refresh is triggered, **Then** the system obtains new tokens from the backend
2. **Given** an invalid refresh token, **When** refresh is attempted, **Then** the user is gracefully signed out

---

### User Story 5 - Sign Out (Priority: P3)

A user signs out of the application, and their session is invalidated on the server.

**Why this priority**: Sign out is less frequently used but important for security and shared device scenarios.

**Independent Test**: Can be tested by signing out and verifying the session is invalidated server-side.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they click sign out, **Then** the backend is notified and local state is cleared
2. **Given** a network error during sign out, **When** sign out fails, **Then** local state is still cleared (graceful degradation)

---

### Edge Cases

- What happens when network connectivity is lost during OAuth callback processing?
- How does the system handle expired magic link tokens?
- What happens if the backend returns an unexpected response format?
- How are concurrent authentication attempts handled?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All authentication API calls MUST use the `authApi` client from `@/lib/api/auth` instead of raw `fetch()`
- **FR-002**: The `signInWithMagicLink` method MUST use `authApi.requestMagicLink()` for sending magic link requests
- **FR-003**: The `verifyMagicLink` method MUST use `authApi.verifyMagicLink()` for token verification
- **FR-004**: The `signInWithOAuth` method MUST use `authApi.getOAuthUrls()` for fetching OAuth authorization URLs
- **FR-005**: The `handleOAuthCallback` method MUST use `authApi.exchangeOAuthCode()` for exchanging authorization codes
- **FR-006**: The `refreshSession` method MUST use `authApi.refreshToken()` for token refresh
- **FR-007**: The `signOut` method MUST use `authApi.signOut()` for server-side session invalidation
- **FR-008**: Response data from `authApi` methods MUST be properly mapped to the store state (snake_case to camelCase conversion handled by authApi)
- **FR-009**: Error handling MUST be preserved - catch blocks should continue to set error state and propagate errors

### Key Entities

- **AuthStore**: Zustand store managing authentication state (user, tokens, session expiry)
- **authApi**: Centralized API client that routes requests through the configured `NEXT_PUBLIC_API_URL` to the Lambda backend
- **User**: Represents the authenticated user with userId, authType, and profile data
- **AuthTokens**: Contains accessToken, refreshToken, and idToken

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Clicking "Continue with Google" successfully redirects to Google's OAuth consent screen without 404 errors
- **SC-002**: Completing OAuth flow successfully creates an authenticated session
- **SC-003**: Requesting a magic link successfully sends the request to the backend (202 response)
- **SC-004**: Clicking a magic link successfully authenticates the user
- **SC-005**: Token refresh automatically occurs without user-visible errors
- **SC-006**: Sign out successfully clears the session both locally and on the server
- **SC-007**: All authentication operations complete within 5 seconds under normal network conditions

## Assumptions

- The `authApi` client is already correctly configured to use `NEXT_PUBLIC_API_URL`
- The response types in `authApi` match what the auth-store expects (or have proper mapping functions)
- Error handling patterns (try/catch with setError) should be preserved
- The authApi methods handle snake_case to camelCase conversion internally

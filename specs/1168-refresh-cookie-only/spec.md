# Feature Specification: Refresh Token Cookie-Only Request

**Feature Branch**: `1168-refresh-cookie-only`
**Created**: 2026-01-07
**Status**: Draft
**Input**: User description: "Stop sending refresh token in request body - rely on httpOnly cookie only. Frontend auth.ts line 88 should send empty body to /refresh endpoint instead of {refreshToken}. Backend Feature 1160 already extracts from cookie."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Silent Token Refresh (Priority: P1)

When a user's access token expires during a session, the system automatically refreshes it using the httpOnly cookie without exposing the refresh token to JavaScript.

**Why this priority**: Core security improvement - prevents XSS attacks from stealing refresh tokens since the token is never accessible to JavaScript code.

**Independent Test**: Can be fully tested by letting an access token expire and verifying the refresh succeeds without any token in the request body.

**Acceptance Scenarios**:

1. **Given** a user has an expired access token and a valid refresh token cookie, **When** the frontend calls the refresh endpoint, **Then** the request body is empty and authentication succeeds via the cookie.
2. **Given** a user has an expired access token but no refresh token cookie, **When** the frontend calls the refresh endpoint, **Then** the request fails with 401 Unauthorized.

---

### User Story 2 - Secure Cookie Transmission (Priority: P1)

The refresh token is transmitted only via httpOnly cookie, never in request body or headers accessible to JavaScript.

**Why this priority**: Security-critical - ensures the refresh token cannot be exfiltrated via XSS.

**Independent Test**: Verify network requests show empty body and refresh token only in Cookie header.

**Acceptance Scenarios**:

1. **Given** the frontend refresh function is called, **When** inspecting the network request, **Then** the request body is empty or undefined.
2. **Given** the frontend refresh function is called, **When** inspecting the request, **Then** no refresh token appears in any JavaScript-accessible location.

---

### Edge Cases

- What happens when the cookie is missing? → 401 Unauthorized response, user redirected to login.
- What happens when the cookie is expired/invalid? → 401 Unauthorized response, user redirected to login.
- What happens if JavaScript code attempts to read the refresh token? → Token is inaccessible due to httpOnly flag.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Frontend refresh API MUST send an empty request body to `/api/v2/auth/refresh`
- **FR-002**: Frontend refresh function MUST NOT accept a refresh token parameter
- **FR-003**: Frontend MUST NOT store refresh tokens in any JavaScript-accessible storage (localStorage, sessionStorage, memory)
- **FR-004**: Frontend MUST rely on browser's automatic cookie inclusion for authentication
- **FR-005**: Frontend MUST handle 401 responses by redirecting to login flow
- **FR-006**: Unused refresh token interfaces/types MUST be removed to prevent accidental misuse

### Key Entities

- **Refresh Token Cookie**: httpOnly cookie named `refresh_token` set by backend, transmitted automatically by browser
- **Access Token**: Short-lived JWT stored in memory, refreshed via cookie-authenticated endpoint

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero refresh token values appear in request bodies (verifiable via network inspection)
- **SC-002**: Token refresh succeeds when valid cookie present (verifiable via E2E test)
- **SC-003**: Token refresh fails with 401 when cookie absent (verifiable via E2E test)
- **SC-004**: No JavaScript code references refresh token string values (verifiable via code search)

## Assumptions

- Backend Feature 1160 is already deployed and extracts refresh token from cookie
- Browser is configured to send cookies with `credentials: 'include'` (already configured in api client)
- CSRF protection via double-submit pattern (Feature 1158) is already in place

## Scope

### In Scope
- Remove refresh token parameter from frontend refresh API call
- Remove `RefreshTokenRequest` interface if unused
- Update any callers to not pass refresh token argument

### Out of Scope
- Backend changes (already complete in Feature 1160)
- Cookie configuration changes (already complete)
- CSRF protection (already complete in Feature 1158)

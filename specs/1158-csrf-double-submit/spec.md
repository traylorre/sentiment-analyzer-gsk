# Feature Specification: CSRF Double-Submit Cookie Pattern

**Feature Branch**: `1158-csrf-double-submit`
**Created**: 2026-01-06
**Status**: Draft
**Input**: User description: "Implement CSRF double-submit cookie pattern for API security"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - State-Changing Request Protection (Priority: P1)

As an authenticated user making state-changing API requests, I want the system to protect my requests from cross-site request forgery attacks so that malicious websites cannot perform unauthorized actions on my behalf.

**Why this priority**: Core security protection - without this, the entire CSRF defense is ineffective. This is the primary value delivered by the feature.

**Independent Test**: Can be tested by making a POST request with and without valid CSRF token and verifying the appropriate accept/reject behavior.

**Acceptance Scenarios**:

1. **Given** an authenticated user with a valid session, **When** they make a POST request with matching CSRF cookie and header, **Then** the request is processed successfully
2. **Given** an authenticated user with a valid session, **When** they make a POST request with mismatched CSRF cookie and header, **Then** the request is rejected with 403 Forbidden
3. **Given** an authenticated user with a valid session, **When** they make a POST request without CSRF header, **Then** the request is rejected with 403 Forbidden
4. **Given** an authenticated user with a valid session, **When** they make a GET request without CSRF header, **Then** the request is processed successfully (safe methods exempt)

---

### User Story 2 - Frontend Token Integration (Priority: P2)

As a frontend application, I need to read the CSRF token from a non-httpOnly cookie and include it in request headers so that my state-changing requests are authenticated.

**Why this priority**: Enables the frontend to participate in the CSRF protection flow. Required for end-to-end functionality but depends on backend being ready first.

**Independent Test**: Can be tested by verifying the frontend correctly reads the cookie and includes the header in fetch requests.

**Acceptance Scenarios**:

1. **Given** the backend sets a CSRF cookie, **When** the frontend makes a POST request, **Then** it includes the X-CSRF-Token header with the cookie value
2. **Given** the CSRF cookie does not exist, **When** the frontend makes a POST request, **Then** it handles the missing token gracefully (request may fail with 403)

---

### User Story 3 - Token Lifecycle Management (Priority: P3)

As the system, I need to generate, set, and refresh CSRF tokens at appropriate points in the authentication lifecycle so that tokens are always available and valid.

**Why this priority**: Token lifecycle ensures tokens are fresh and available. Important for long sessions but basic protection works without sophisticated lifecycle.

**Independent Test**: Can be tested by verifying tokens are set on login/refresh and remain valid throughout the session.

**Acceptance Scenarios**:

1. **Given** a user completes authentication, **When** the auth response is sent, **Then** a CSRF token cookie is included
2. **Given** a user refreshes their session, **When** the refresh response is sent, **Then** the CSRF token cookie is refreshed

---

### Edge Cases

- What happens when the CSRF cookie is expired or missing?
- How does the system handle clock skew between cookie expiry and session validity?
- What happens when a legitimate user has cookies blocked by browser settings?
- How does the system handle concurrent requests with token refresh?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate cryptographically secure CSRF tokens using 32 bytes of random data
- **FR-002**: System MUST set the CSRF token in a non-httpOnly cookie (so JavaScript can read it)
- **FR-003**: System MUST validate that the X-CSRF-Token header matches the csrf_token cookie value
- **FR-004**: System MUST use constant-time comparison to prevent timing attacks
- **FR-005**: System MUST reject state-changing requests (POST, PUT, PATCH, DELETE) without valid CSRF token with 403 status
- **FR-006**: System MUST allow safe methods (GET, HEAD, OPTIONS) without CSRF validation
- **FR-007**: System MUST exempt specific paths from CSRF validation (/api/v2/auth/refresh, OAuth callbacks)
- **FR-008**: System MUST set CSRF cookie with secure=True, path=/api/v2, max_age=86400

### Key Entities

- **CSRF Token**: A cryptographically random string that proves the request originated from the legitimate frontend
- **CSRF Cookie**: Browser storage for the token, readable by JavaScript (httpOnly=False)
- **CSRF Header**: Request header (X-CSRF-Token) containing the token for server validation

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All state-changing API endpoints reject requests without valid CSRF token
- **SC-002**: CSRF validation adds less than 5ms latency to request processing
- **SC-003**: 100% of authenticated state-changing requests from the legitimate frontend succeed with CSRF protection enabled
- **SC-004**: Zero false positives (legitimate requests incorrectly rejected) in production

## Assumptions

- The refresh endpoint (/api/v2/auth/refresh) is exempt because it uses cookie-only authentication (no JavaScript access needed)
- OAuth callback endpoints are exempt because OAuth state parameter provides equivalent CSRF protection
- The frontend will be updated to include the X-CSRF-Token header in all state-changing requests
- SameSite cookie attribute will be changed from "strict" to "none" to support cross-origin requests (handled by separate feature)

## Dependencies

- **Prerequisite**: This feature MUST be implemented before changing SameSite from "strict" to "none"
- **Frontend Update**: Frontend API client must be updated to read and send CSRF tokens
- **CloudFront**: Cookie forwarding rules must allow csrf_token cookie

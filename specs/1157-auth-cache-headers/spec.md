# Feature Specification: Auth Cache-Control Headers

**Feature Branch**: `1157-auth-cache-headers`
**Created**: 2026-01-06
**Status**: Draft
**Input**: Add Cache-Control headers to auth responses per spec-v2.md line 1091. Add no-store, no-cache, must-revalidate headers to all auth endpoints in router_v2.py. Non-breaking change.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Prevent Browser Caching of Auth Responses (Priority: P1)

As a security-conscious application, auth responses (tokens, session data, user info) must never be cached by browsers or intermediate proxies. This prevents sensitive authentication data from being stored in browser caches where it could be accessed by other users on shared devices or leaked through cache inspection.

**Why this priority**: Security-critical. Cached auth tokens or session data could be replayed or exposed, compromising user accounts.

**Independent Test**: Can be fully tested by making auth requests and verifying response headers contain correct Cache-Control directives. Delivers security hardening without affecting functionality.

**Acceptance Scenarios**:

1. **Given** a user completes magic link verification, **When** the response is returned, **Then** the response includes `Cache-Control: no-store, no-cache, must-revalidate`
2. **Given** a user completes OAuth callback, **When** the response is returned, **Then** the response includes `Cache-Control: no-store, no-cache, must-revalidate`
3. **Given** a user requests token refresh, **When** the response is returned, **Then** the response includes `Cache-Control: no-store, no-cache, must-revalidate`

---

### User Story 2 - Prevent Proxy Caching of Auth Responses (Priority: P1)

As a security measure, auth responses must include headers that prevent intermediate proxies (CDNs, reverse proxies) from caching sensitive authentication data.

**Why this priority**: Security-critical. Even if browser doesn't cache, intermediate proxies might cache responses and serve stale auth data to other users.

**Independent Test**: Can be tested by inspecting response headers for Pragma and Expires directives that work with older HTTP/1.0 proxies.

**Acceptance Scenarios**:

1. **Given** any auth endpoint response, **When** inspecting headers, **Then** response includes `Pragma: no-cache` for HTTP/1.0 compatibility
2. **Given** any auth endpoint response, **When** inspecting headers, **Then** response includes `Expires: 0` to force revalidation

---

### Edge Cases

- What happens when response already has Cache-Control header set by framework? Headers should be explicitly set, overriding any defaults.
- How does system handle streaming responses (SSE)? SSE endpoints are separate from auth endpoints and not affected.
- What if a downstream service adds caching headers? The auth endpoint headers are authoritative; downstream services should not modify them.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST include `Cache-Control: no-store, no-cache, must-revalidate` header on all auth endpoint responses
- **FR-002**: System MUST include `Pragma: no-cache` header on all auth endpoint responses for HTTP/1.0 compatibility
- **FR-003**: System MUST include `Expires: 0` header on all auth endpoint responses
- **FR-004**: System MUST apply cache headers to the following auth endpoints:
  - POST /api/v2/auth/anonymous
  - GET /api/v2/auth/validate
  - POST /api/v2/auth/magic-link
  - GET /api/v2/auth/magic-link/verify
  - GET /api/v2/auth/oauth/urls
  - POST /api/v2/auth/oauth/callback
  - POST /api/v2/auth/refresh
  - POST /api/v2/auth/signout
  - GET /api/v2/auth/session
  - POST /api/v2/auth/check-email
  - POST /api/v2/auth/link-accounts
  - GET /api/v2/auth/merge-status
- **FR-005**: System MUST NOT affect non-auth endpoints with these cache control headers

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of auth endpoint responses include the required Cache-Control header
- **SC-002**: 100% of auth endpoint responses include the required Pragma header
- **SC-003**: 100% of auth endpoint responses include the required Expires header
- **SC-004**: Zero browser cache hits for auth responses when tested with browser developer tools
- **SC-005**: All existing auth functionality continues to work without degradation (non-breaking)

## Assumptions

- The application uses a framework (FastAPI) that allows setting response headers
- CloudFront is already configured with TTL=0 for auth endpoints (infrastructure-level caching already disabled)
- This change addresses browser and proxy caching at the application response level
- HTTP/1.0 compatibility is desired for legacy proxy support

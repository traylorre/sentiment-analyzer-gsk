# Feature Specification: SSE Lambda Bearer Token Authentication

**Feature Branch**: `1154-sse-bearer-token-auth`
**Created**: 2026-01-06
**Status**: Draft
**Input**: User description: "Feature 1154: SSE Lambda Bearer Token Authentication. The SSE Lambda handler does not support Bearer token authentication. Add Bearer token extraction in config_stream() function to align with Dashboard Lambda auth pattern."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Authenticated SSE Connection (Priority: P1)

A user with a valid session token wants to receive real-time sentiment updates via Server-Sent Events (SSE). The user's frontend sends the session token as a Bearer token in the Authorization header, and the SSE endpoint should authenticate the user and establish the streaming connection.

**Why this priority**: This is the primary use case that is currently broken. E2E tests fail because the SSE endpoint doesn't recognize Bearer token authentication, returning 401 Unauthorized. This blocks the entire CI/CD pipeline.

**Independent Test**: Can be tested by creating an anonymous session, getting a token, and connecting to the SSE endpoint with `Authorization: Bearer {token}` header. Success is verified by receiving HTTP 200 and the SSE event stream opening.

**Acceptance Scenarios**:

1. **Given** a user has a valid session token, **When** they connect to `/api/v2/configurations/{config_id}/stream` with `Authorization: Bearer {token}` header, **Then** the system authenticates the user and returns HTTP 200 with an open SSE connection
2. **Given** a user has an invalid or expired token, **When** they connect to the SSE endpoint with that token, **Then** the system returns HTTP 401 Unauthorized with an error message
3. **Given** a user provides no authentication, **When** they connect to the SSE endpoint, **Then** the system returns HTTP 401 Unauthorized

---

### User Story 2 - Backwards Compatibility with X-User-ID Header (Priority: P2)

Some legacy clients may still use the X-User-ID header for authentication. The system should continue to support this method while also accepting Bearer tokens.

**Why this priority**: Maintains backwards compatibility for any existing clients, but Bearer token is the preferred method going forward per Feature 1146.

**Independent Test**: Can be tested by connecting with X-User-ID header (without Bearer token) and verifying the connection is established.

**Acceptance Scenarios**:

1. **Given** a user provides X-User-ID header, **When** they connect to the SSE endpoint, **Then** the system authenticates via the header and establishes the connection
2. **Given** a user provides both Bearer token AND X-User-ID header, **When** they connect, **Then** the system uses the Bearer token (takes precedence)

---

### User Story 3 - Query Parameter Token Support (Priority: P3)

For clients that cannot set custom headers (e.g., EventSource in some browsers), the system should support authentication via query parameter.

**Why this priority**: Fallback mechanism for limited clients. Less common use case.

**Independent Test**: Can be tested by connecting with `?user_token={token}` query parameter.

**Acceptance Scenarios**:

1. **Given** a user provides token via `user_token` query parameter, **When** they connect, **Then** the system authenticates and establishes the connection
2. **Given** Bearer token, X-User-ID header, and query parameter are all provided, **When** connecting, **Then** Bearer token takes highest precedence, then X-User-ID, then query parameter

---

### Edge Cases

- What happens when the Bearer token is malformed (not a valid JWT)?
  - System returns 401 with "Invalid token format" message
- What happens when the Bearer token signature verification fails?
  - System returns 401 with "Token validation failed" message
- What happens when the Bearer token is expired?
  - System returns 401 with "Token expired" message
- How does system handle Bearer token with no "Bearer " prefix?
  - System falls back to checking X-User-ID header and query param

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SSE Lambda MUST accept authentication via `Authorization: Bearer {token}` header
- **FR-002**: SSE Lambda MUST validate Bearer tokens using the same JWT validation mechanism as Dashboard Lambda
- **FR-003**: SSE Lambda MUST extract user_id from the validated JWT claims (sub claim)
- **FR-004**: SSE Lambda MUST maintain backwards compatibility with X-User-ID header authentication
- **FR-005**: SSE Lambda MUST maintain backwards compatibility with `user_token` query parameter authentication
- **FR-006**: SSE Lambda MUST use the following authentication precedence: Bearer token > X-User-ID header > user_token query parameter
- **FR-007**: SSE Lambda MUST return HTTP 401 with descriptive error message when authentication fails
- **FR-008**: SSE Lambda MUST use the JWT_SECRET environment variable for token validation (same as Dashboard Lambda)

### Key Entities

- **Bearer Token**: A JWT containing user session information, passed in Authorization header
- **User ID**: The unique identifier for the user, extracted from JWT sub claim or legacy headers
- **SSE Connection**: The established event stream connection for real-time updates

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 4 SSE E2E tests pass (test_sse_connection_established, test_sse_receives_sentiment_update, test_sse_receives_refresh_event, test_sse_reconnection_with_last_event_id)
- **SC-002**: SSE endpoint accepts Bearer token authentication with 0% authentication failures for valid tokens
- **SC-003**: Backwards compatibility maintained - existing X-User-ID and query param authentication continues to work
- **SC-004**: CI/CD pipeline integration tests pass without 401 errors on SSE endpoints

## Assumptions

- The JWT_SECRET environment variable is already configured in the SSE Lambda (confirmed deployed)
- The JWT validation logic used by Dashboard Lambda can be reused or imported
- The token format is consistent between Dashboard and SSE authentication flows
- PyJWT library is available in the SSE Lambda runtime

# Feature Specification: Fix Anonymous Auth 422 Error

**Feature Branch**: `1119-fix-anonymous-auth-422`
**Created**: 2026-01-02
**Status**: Draft
**Input**: User description: "Fix POST /api/v2/auth/anonymous returning 422 Unprocessable Entity. Root Cause: Frontend sends empty/undefined body, but backend router_v2.py expects Pydantic-validated AnonymousSessionRequest body. The AnonymousSessionRequest model already has defaults (timezone=America/New_York, device_fingerprint=None) so the endpoint should accept empty bodies."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Anonymous Session Creation (Priority: P1)

A new visitor lands on the dashboard for the first time. The system automatically creates an anonymous session so they can use the application without requiring sign-up, providing immediate value and reducing friction.

**Why this priority**: This is the primary entry point for all new users. Without a working anonymous auth, new visitors see errors and cannot use the dashboard at all. This is a blocking issue for all user flows.

**Independent Test**: Can be fully tested by opening the dashboard in an incognito browser window. A successful anonymous session allows the user to interact with the dashboard immediately without any error messages.

**Acceptance Scenarios**:

1. **Given** a new visitor with no existing session, **When** the frontend loads and calls POST /api/v2/auth/anonymous with no request body, **Then** the backend creates a new anonymous session and returns HTTP 201 with user_id, auth_type, created_at, session_expires_at, and storage_hint.

2. **Given** a new visitor with no existing session, **When** the frontend loads and calls POST /api/v2/auth/anonymous with an empty JSON body `{}`, **Then** the backend creates a new anonymous session using default timezone (America/New_York) and returns HTTP 201.

3. **Given** a new visitor, **When** the frontend provides optional parameters (timezone, device_fingerprint), **Then** the backend uses those values instead of defaults.

---

### User Story 2 - Session Persistence (Priority: P2)

After an anonymous session is created, the user's session persists across page refreshes and browser tabs, allowing them to continue their work without interruption.

**Why this priority**: Once anonymous auth works, session persistence ensures users don't lose their work. This is dependent on P1 working first.

**Independent Test**: Can be tested by creating a session, refreshing the page, and verifying the same user_id is returned without creating a new session.

**Acceptance Scenarios**:

1. **Given** a user with an existing anonymous session (X-User-ID header present), **When** the frontend calls POST /api/v2/auth/anonymous, **Then** the backend returns the existing session information without creating a duplicate.

---

### Edge Cases

- What happens when the request body is `null` vs `undefined` vs empty string? All should be treated as "no body provided" and use defaults.
- What happens when the request body contains unknown fields? Should be ignored per standard behavior.
- What happens when timezone is invalid? Should fall back to America/New_York.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept POST /api/v2/auth/anonymous with no request body and create a session using default values.
- **FR-002**: System MUST accept POST /api/v2/auth/anonymous with an empty JSON body `{}` and create a session using default values.
- **FR-003**: System MUST accept POST /api/v2/auth/anonymous with optional parameters (timezone, device_fingerprint) and use provided values.
- **FR-004**: System MUST return HTTP 201 with a valid session response containing user_id, auth_type, created_at, session_expires_at, and storage_hint.
- **FR-005**: System MUST NOT return HTTP 422 when the request body is empty, null, or undefined.
- **FR-006**: System MUST use "America/New_York" as the default timezone when not provided.
- **FR-007**: System MUST use null as the default device_fingerprint when not provided.

### Key Entities

- **AnonymousSession**: Represents a temporary user session with user_id (UUID), auth_type ("anonymous"), timezone, device_fingerprint (optional), created_at, session_expires_at (30 days from creation), storage_hint ("localStorage").

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: New visitors can load the dashboard and begin using it within 3 seconds without seeing any authentication error messages.
- **SC-002**: POST /api/v2/auth/anonymous returns HTTP 201 (not 422) when called with no request body.
- **SC-003**: POST /api/v2/auth/anonymous returns HTTP 201 (not 422) when called with empty JSON body `{}`.
- **SC-004**: The anonymous session response contains all required fields (user_id, auth_type, created_at, session_expires_at, storage_hint).
- **SC-005**: Existing frontend code works without modification (backward compatible fix).

## Assumptions

- The AnonymousSessionRequest model already has sensible defaults defined (timezone="America/New_York", device_fingerprint=None).
- The fix should be in the backend router_v2.py endpoint, not in the frontend code.
- This is a greenfield approach - no backward compatibility concerns with older API versions.
- The session creation logic in auth_service is already working correctly; only the request body parsing needs adjustment.

# Feature Specification: Remove X-User-ID Header Fallback

**Feature Branch**: `1146-remove-xuserid-fallback`
**Created**: 2026-01-05
**Status**: Draft
**Priority**: P0 - Critical Security Fix
**CVSS**: 9.1 (Critical)
**Input**: User description: "Phase 0 D5: Remove X-User-ID header fallback from auth middleware. Backend currently accepts X-User-ID header as fallback identity source, enabling impersonation attacks. Must remove fallback and require authenticated session only. CVSS 9.1 (Critical). Security fix - no new features."

---

## Problem Statement

The authentication middleware currently accepts an `X-User-ID` header as a fallback mechanism for user identification. This creates a critical security vulnerability where any client can impersonate any user by simply setting this header. This bypasses all authentication controls and allows unauthorized access to user accounts and data.

**Attack Vector**: Attacker sends request with `X-User-ID: <victim-user-id>` header → System accepts this as the authenticated user → Attacker gains full access to victim's data.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Security Fix (Priority: P1)

As a **security engineer**, I need the X-User-ID header fallback removed so that users can only be identified through properly authenticated sessions, preventing impersonation attacks.

**Why this priority**: This is a CVSS 9.1 Critical vulnerability that allows complete account takeover. No feature work can proceed until this is fixed.

**Independent Test**: Can be fully tested by sending requests with fake X-User-ID headers and verifying they are rejected. Delivers security by closing the impersonation attack vector.

**Acceptance Scenarios**:

1. **Given** a valid authenticated session, **When** a request is made without X-User-ID header, **Then** the system identifies the user from the authenticated session
2. **Given** a valid authenticated session, **When** a request includes a malicious X-User-ID header, **Then** the system ignores the header and uses only the session identity
3. **Given** no authenticated session, **When** a request includes an X-User-ID header, **Then** the system returns 401 Unauthorized (not accepting the header as identity)
4. **Given** no authenticated session and no X-User-ID header, **When** a request is made to a protected endpoint, **Then** the system returns 401 Unauthorized

---

### User Story 2 - Application Stability (Priority: P2)

As a **user**, I need the system to continue functioning correctly after the security fix so that my normal usage is unaffected.

**Why this priority**: After closing the security hole, the application must still work for legitimate users.

**Independent Test**: Can be fully tested by performing all authentication flows (anonymous, magic link, OAuth) and verifying protected endpoints still work with valid sessions.

**Acceptance Scenarios**:

1. **Given** a user authenticates via magic link, **When** they access protected endpoints, **Then** their requests succeed with proper authorization
2. **Given** a user authenticates via OAuth, **When** they access protected endpoints, **Then** their requests succeed with proper authorization
3. **Given** an anonymous user creates a session, **When** they access anonymous-allowed endpoints, **Then** their requests succeed

---

### Edge Cases

- What happens when legacy clients still send X-User-ID header? System must ignore it silently (no error, just ignored)
- What happens when session cookie is present but expired? System returns 401, does not fall back to X-User-ID
- What happens when both session and X-User-ID header are present with different user IDs? System uses only session identity, completely ignores header
- What happens to anonymous sessions that previously used X-User-ID? Anonymous sessions must use proper session tracking, not header-based identification

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST NOT accept X-User-ID header as an identity source under any circumstances
- **FR-002**: System MUST derive user identity exclusively from authenticated session tokens
- **FR-003**: System MUST return 401 Unauthorized for requests to protected endpoints without valid session
- **FR-004**: System MUST ignore any X-User-ID header silently (no error response for including it, just not used)
- **FR-005**: System MUST maintain backward compatibility for all legitimate authentication flows (magic link, OAuth, anonymous)
- **FR-006**: System MUST NOT break any existing functionality that relies on proper session-based authentication

### Non-Functional Requirements

- **NFR-001**: Change must not increase request latency by more than 1ms
- **NFR-002**: All existing tests must pass after the change (no regression)
- **NFR-003**: Security fix must be atomic - no partial states where header is sometimes accepted

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of requests with fake X-User-ID headers (and no valid session) receive 401 Unauthorized
- **SC-002**: 100% of requests with valid sessions continue to work regardless of X-User-ID header presence
- **SC-003**: All existing authentication flows (magic link, OAuth, anonymous) continue to function with no change in success rate
- **SC-004**: Zero regressions in existing test suite
- **SC-005**: Attack simulation: Requests with `X-User-ID: <other-user>` header cannot access other user's data

---

## Scope

### In Scope

- Remove X-User-ID header fallback from authentication middleware
- Update any code that reads X-User-ID header for identity
- Update tests that relied on X-User-ID header (convert to proper session auth)

### Out of Scope

- New authentication methods
- Changes to session token format
- Changes to OAuth or magic link flows
- Frontend changes (backend-only fix)
- Adding new security features

---

## Assumptions

- The codebase uses middleware-based authentication
- User identity should come exclusively from JWT/session tokens
- The X-User-ID header was a development convenience that should never have been in production
- Anonymous sessions have their own session token mechanism (not X-User-ID based)

---

## Dependencies

- Must be completed after D4 (cookies.ts deletion) - completed
- Blocks C4 and C5 (endpoint protection) which need clean identity model

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking legitimate functionality | Low | High | Comprehensive test coverage before and after |
| Missing some code paths that use X-User-ID | Medium | High | Full codebase search for all references |
| Tests that relied on X-User-ID fail | High | Low | Update tests to use proper auth |

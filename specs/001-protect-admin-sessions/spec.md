# Feature Specification: Protect Admin Sessions Revoke Endpoint

**Feature Branch**: `001-protect-admin-sessions`
**Created**: 2026-01-05
**Status**: Draft
**Input**: User description: "C4: Protect /admin/sessions/revoke endpoint. Add @require_role('admin') decorator to prevent unauthorized session revocation. This is an RBAC Phase 1.5 security fix. The endpoint currently has no role protection - any authenticated user can revoke any session. Location: src/lambdas/dashboard/auth.py - the revoke endpoint handler. Use the existing @require_role decorator from Feature 1130."

## Problem Statement

The `/admin/sessions/revoke` endpoint currently allows any authenticated user to revoke any session. This is a critical security vulnerability - a regular user could revoke admin sessions, causing denial of service, or revoke other users' sessions maliciously. The endpoint must be protected with role-based access control to ensure only administrators can perform session revocation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin Revokes Malicious Session (Priority: P1)

An administrator needs to revoke a user session that shows suspicious activity (e.g., unusual login location, potential compromise).

**Why this priority**: This is the primary use case for session revocation - security incident response. Admins must be able to quickly terminate compromised sessions.

**Independent Test**: Can be fully tested by authenticating as an admin user, calling the revoke endpoint with a valid session ID, and verifying the session is invalidated.

**Acceptance Scenarios**:

1. **Given** an authenticated admin user with `roles: ["admin"]`, **When** they call `/admin/sessions/revoke` with a valid session ID, **Then** the session is revoked and a 200 success response is returned
2. **Given** an authenticated admin user with `roles: ["admin", "user"]`, **When** they call `/admin/sessions/revoke`, **Then** the request succeeds (admin role is present among multiple roles)

---

### User Story 2 - Non-Admin Blocked from Revocation (Priority: P1)

A regular authenticated user attempts to revoke a session (their own or another user's). The system must block this action to prevent unauthorized session termination.

**Why this priority**: Equal to P1 as this is the security-critical path - preventing unauthorized access is as important as allowing authorized access.

**Independent Test**: Can be fully tested by authenticating as a non-admin user and verifying the revoke endpoint returns 403 Forbidden.

**Acceptance Scenarios**:

1. **Given** an authenticated user with `roles: ["user"]`, **When** they call `/admin/sessions/revoke`, **Then** the request is rejected with 403 Forbidden
2. **Given** an authenticated user with no roles, **When** they call `/admin/sessions/revoke`, **Then** the request is rejected with 403 Forbidden
3. **Given** an unauthenticated request, **When** calling `/admin/sessions/revoke`, **Then** the request is rejected with 401 Unauthorized

---

### Edge Cases

- What happens when admin role is revoked mid-request? System MUST validate role at request time; if role check passes, operation completes.
- What happens when admin tries to revoke their own session? System MUST allow this (admin may need to invalidate their own compromised session).
- What happens when session ID doesn't exist? System MUST return appropriate error (404 or 400) without revealing whether the session ever existed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST require the `admin` role to access the `/admin/sessions/revoke` endpoint
- **FR-002**: System MUST return 403 Forbidden when a non-admin authenticated user attempts session revocation
- **FR-003**: System MUST return 401 Unauthorized when an unauthenticated user attempts session revocation
- **FR-004**: System MUST log all session revocation attempts (both successful and blocked) as security events
- **FR-005**: System MUST use the existing `@require_role` decorator from Feature 1130 for role enforcement

### Key Entities

- **Session**: User authentication session that can be revoked by administrators
- **Role**: User permission level (specifically `admin` role for this endpoint)
- **Security Event Log**: Record of authorization decisions for audit trail

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of non-admin requests to `/admin/sessions/revoke` are blocked with 403 Forbidden
- **SC-002**: 100% of unauthenticated requests are blocked with 401 Unauthorized
- **SC-003**: Admin users can successfully revoke sessions with no change to existing functionality
- **SC-004**: Security audit logs capture all revocation attempts (success and failure)

## Assumptions

- The `@require_role` decorator from Feature 1130 is already implemented and working
- Admin users have `admin` in their JWT `roles` claim
- The revoke endpoint handler already exists in `src/lambdas/dashboard/auth.py`
- No changes to the session revocation logic itself are needed - only adding the role protection decorator

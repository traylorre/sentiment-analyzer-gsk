# Feature Specification: Remove Auth Store persist() Middleware

**Feature Branch**: `1165-remove-auth-store-persist`
**Created**: 2026-01-06
**Status**: Draft
**Input**: Phase 2 C6 Security Fix - Remove localStorage from auth flow

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Eliminate localStorage Attack Surface (Priority: P1)

As a security engineer, I need the zustand persist() middleware removed from the auth store so that there is zero authentication data in localStorage, eliminating XSS attack vectors for token theft.

**Why this priority**: This is a security hardening requirement (CVSS 8.6). Even though tokens are currently not persisted, the persist infrastructure creates risk: developer confusion, future accidental token storage, and unnecessary localStorage footprint.

**Independent Test**: After removal, verify `localStorage.getItem('sentiment-auth-tokens')` returns null after authentication.

**Acceptance Scenarios**:

1. **Given** the auth store uses persist() middleware, **When** this feature is complete, **Then** the persist() wrapper is completely removed from the store creation.
2. **Given** localStorage contains 'sentiment-auth-tokens' from previous sessions, **When** the user visits the site, **Then** the old data is ignored (store starts fresh).
3. **Given** a user is authenticated, **When** they check localStorage, **Then** no authentication-related keys exist.

---

### User Story 2 - Session Restoration via Cookies (Priority: P2)

As a user, when I refresh the page or open a new tab, I want my session to be restored automatically via the httpOnly cookie mechanism, without relying on localStorage.

**Why this priority**: This ensures the HTTPOnly cookie model works correctly - session persistence comes from server-side cookies, not client-side storage.

**Independent Test**: Log in, refresh page, verify session is restored via /refresh endpoint.

**Acceptance Scenarios**:

1. **Given** a user has an active session (httpOnly refresh cookie), **When** they refresh the page, **Then** useSessionInit calls /refresh and restores the session.
2. **Given** a user opens a new tab, **When** the app loads, **Then** the session is restored via /refresh (not localStorage).
3. **Given** a user's session has expired, **When** they refresh, **Then** /refresh returns 401 and they see login prompt.

---

### User Story 3 - Clean Up Hydration Logic (Priority: P3)

As a developer, I want the unnecessary hydration tracking removed since there's nothing to hydrate from localStorage anymore.

**Why this priority**: Code simplification - removes complexity that's no longer needed.

**Independent Test**: Verify _hasHydrated flag and related hooks are removed or simplified.

**Acceptance Scenarios**:

1. **Given** the store had _hasHydrated tracking, **When** persist() is removed, **Then** the hydration tracking is simplified or removed.
2. **Given** useSessionInit waited for hydration, **When** there's nothing to hydrate, **Then** it initializes immediately.

---

### Edge Cases

- What happens to existing localStorage data from previous versions? → Ignored; store initializes fresh. Users re-authenticate via cookie.
- What happens in private browsing mode? → Works identically since we no longer depend on localStorage.
- What happens if /refresh fails on page load? → User sees login prompt (anonymous session or auth required).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST NOT use zustand persist() middleware for the auth store.
- **FR-002**: System MUST NOT write any authentication data to localStorage.
- **FR-003**: System MUST restore sessions via /refresh endpoint using httpOnly cookies.
- **FR-004**: System MUST initialize auth store with default empty state on every page load.
- **FR-005**: System MUST remove or simplify the _hasHydrated tracking since there's nothing to hydrate.
- **FR-006**: System MUST maintain all existing auth functionality (login, logout, token refresh).

### Key Entities

- **AuthStore**: Zustand store holding authentication state (user, tokens, flags) - now memory-only.
- **httpOnly Cookie**: Server-managed refresh token cookie - the ONLY persistence mechanism.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero authentication-related keys in localStorage after any user action.
- **SC-002**: Session restoration works via /refresh endpoint on page refresh.
- **SC-003**: All existing auth tests pass after changes.
- **SC-004**: Code reduction: persist() wrapper and related hydration code removed.
- **SC-005**: No regression in user experience - sessions still persist across page refreshes via cookies.

## Assumptions

- The /refresh endpoint correctly handles httpOnly cookies and returns access tokens.
- The backend sets proper httpOnly, Secure, SameSite=None cookies.
- Frontend tests can be updated to not rely on localStorage hydration.

## Dependencies

- Backend /refresh endpoint must work with httpOnly cookies (already implemented).
- CORS and cookie settings must be correct (already configured).

## Canonical Source

- specs/1126-auth-httponly-migration/spec-v2.md (lines 2894-2909, 2620-2698)
- specs/1126-auth-httponly-migration/implementation-gaps.md (Phase 2 C6)

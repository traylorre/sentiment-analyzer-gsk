# Feature Specification: Remove Zustand Persist Middleware

**Feature Branch**: `1131-remove-zustand-persist`
**Created**: 2026-01-05
**Status**: Draft
**Input**: User description: "Phase 0 D1: Remove zustand persist() middleware from frontend/src/stores/auth-store.ts:279-306. Current code writes tokens to localStorage enabling XSS attacks. Require memory-only storage. CVSS 8.6."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Secure Token Storage (Priority: P1)

As a security team member, I need authentication tokens to be stored only in memory so that XSS attacks cannot steal user credentials from localStorage.

**Why this priority**: This is a CVSS 8.6 security vulnerability. Tokens stored in localStorage can be exfiltrated by any malicious script running on the page, leading to session hijacking.

**Independent Test**: After implementation, inspect browser localStorage using DevTools and verify no `tokens` (accessToken, refreshToken, idToken) appear. Verify the application still functions correctly for authenticated users.

**Acceptance Scenarios**:

1. **Given** a user logs in successfully, **When** I inspect localStorage in browser DevTools, **Then** no authentication tokens (accessToken, refreshToken, idToken) are present
2. **Given** a user is authenticated, **When** I refresh the page, **Then** the user session may require re-authentication (acceptable security tradeoff)
3. **Given** a malicious XSS script runs on the page, **When** it attempts to read localStorage, **Then** no sensitive tokens are accessible

---

### User Story 2 - Preserve Non-Sensitive Session State (Priority: P2)

As a user, I want my non-sensitive session preferences to persist across browser refreshes so that I don't lose my session state unnecessarily.

**Why this priority**: While tokens must not persist, non-sensitive flags like `isAuthenticated` and `isAnonymous` can still be persisted to improve UX without security risk.

**Independent Test**: Verify that after page refresh, the application correctly identifies whether the user was previously authenticated (even if they need to re-authenticate).

**Acceptance Scenarios**:

1. **Given** a user is authenticated, **When** I refresh the page, **Then** the application shows appropriate loading state while re-validating session
2. **Given** a user was anonymous, **When** I refresh the page, **Then** the anonymous session state is restored from persistence

---

### Edge Cases

- What happens when a user refreshes the page mid-session?
  - User may need to re-authenticate since tokens are not persisted
  - httpOnly cookies (if implemented) can provide session continuity
- What happens when localStorage is unavailable (private browsing)?
  - Behavior unchanged - memory fallback already exists in codebase
- What happens to existing localStorage data from before this fix?
  - Existing tokens in localStorage should be cleared on first load

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST NOT persist authentication tokens (accessToken, refreshToken, idToken) to localStorage
- **FR-002**: System MUST store authentication tokens in memory only during the browser session
- **FR-003**: System MAY persist non-sensitive session flags (isAuthenticated, isAnonymous, sessionExpiresAt) to localStorage for UX continuity
- **FR-004**: System MUST clear any existing tokens from localStorage on application initialization (migration cleanup)
- **FR-005**: System MUST continue to function correctly for authenticated users after this change
- **FR-006**: System MUST continue to sync tokens to httpOnly cookies via existing `setAuthCookies()` mechanism

### Key Entities

- **AuthState**: Contains user profile, tokens, and session flags
  - `tokens` field: Must remain in-memory only
  - `user` field: Non-sensitive profile data, can be persisted
  - Session flags: `isAuthenticated`, `isAnonymous`, `sessionExpiresAt`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero authentication tokens appear in localStorage after user login (verified via DevTools inspection)
- **SC-002**: Application functions correctly for 100% of existing authentication flows (login, logout, refresh)
- **SC-003**: Security scanners report no localStorage token storage vulnerability
- **SC-004**: Existing unit and E2E tests continue to pass without modification (or with minimal updates for expected behavior changes)

## Assumptions

- httpOnly cookie mechanism exists and is the preferred secure token transport
- The existing `setAuthCookies()` function handles secure token transmission to the backend
- Memory-only token storage is acceptable even though page refresh requires re-authentication
- The zustand persist middleware can be partially configured to exclude specific fields

## Out of Scope

- Implementing httpOnly cookie-based token refresh (handled by separate feature)
- Backend changes to support token-less localStorage
- Migration of existing user sessions - they will simply need to re-login once

## Security Considerations

- **Vulnerability addressed**: CWE-922 (Insecure Storage of Sensitive Information)
- **CVSS Score**: 8.6 (High)
- **Attack vector**: XSS script reading localStorage to steal tokens
- **Mitigation**: Remove tokens from persist() partialize function, store in memory only

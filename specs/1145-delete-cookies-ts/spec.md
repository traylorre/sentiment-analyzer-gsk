# Feature Specification: Delete Cookies.ts Security Fix

**Feature Branch**: `1145-delete-cookies-ts`
**Created**: 2026-01-05
**Status**: Draft
**Input**: User description: "Phase 0 D4: Delete frontend/src/lib/cookies.ts entirely. File sets non-httpOnly cookies that XSS can read. Complete file deletion required - no refactoring. CVSS 8.6. Security fix blocking all other auth work."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Security Vulnerability Remediation (Priority: P1)

A security auditor identifies that the application stores authentication tokens in JavaScript-accessible cookies, making them vulnerable to XSS attacks. By deleting the cookies.ts file, we eliminate the attack vector where malicious scripts could steal user tokens.

**Why this priority**: CVSS 8.6 critical security vulnerability. Token theft via XSS could lead to complete account takeover. This blocks all other authentication improvements.

**Independent Test**: Can be verified by confirming no JavaScript-accessible auth cookies exist in the browser after user authentication.

**Acceptance Scenarios**:

1. **Given** a user is authenticated, **When** malicious JavaScript attempts to read cookies via `document.cookie`, **Then** no authentication tokens are accessible
2. **Given** the cookies.ts file existed, **When** the fix is deployed, **Then** the file no longer exists in the codebase
3. **Given** components previously imported from cookies.ts, **When** the fix is deployed, **Then** those imports are removed and the application compiles successfully

---

### User Story 2 - Application Stability After Removal (Priority: P1)

The application must continue to function correctly after the cookies.ts file is removed. All authentication flows must work without the client-side cookie management.

**Why this priority**: Equal priority to the security fix - breaking the app is not acceptable.

**Independent Test**: Full authentication flow (anonymous, magic link, logout) continues to work after deployment.

**Acceptance Scenarios**:

1. **Given** a new user visits the site, **When** they start an anonymous session, **Then** the session works correctly without client-side cookie utilities
2. **Given** an authenticated user, **When** they perform any action, **Then** authentication continues to work via backend httpOnly cookies
3. **Given** the auth-store.ts imports cookies.ts, **When** cookies.ts is deleted, **Then** auth-store.ts is updated to remove the import and any calls to deleted functions

---

### Edge Cases

- What happens if a user has existing non-httpOnly cookies from before the fix? They will be ignored; backend httpOnly cookies take precedence.
- How does the system handle the auth-store.ts dependency? The import and function calls must be removed from auth-store.ts.
- What happens to the cookies.test.ts test file? It must be deleted since it tests deleted functionality.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST delete the file `frontend/src/lib/cookies.ts` entirely
- **FR-002**: System MUST remove all imports of cookies.ts from dependent files (auth-store.ts)
- **FR-003**: System MUST remove all calls to `setAuthCookies()` and `clearAuthCookies()` functions
- **FR-004**: System MUST delete the test file `frontend/tests/unit/lib/cookies.test.ts`
- **FR-005**: System MUST compile successfully after all deletions (no TypeScript errors)
- **FR-006**: System MUST pass all remaining tests after the deletion

### Key Entities

- **cookies.ts**: The file to be deleted - contains `setAuthCookies`, `clearAuthCookies`, `getAuthCookie`, `getIsAnonymousCookie` functions
- **auth-store.ts**: Consumer of cookies.ts - imports `setAuthCookies` and `clearAuthCookies`
- **cookies.test.ts**: Test file for cookies.ts - must also be deleted

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The file `frontend/src/lib/cookies.ts` does not exist in the repository
- **SC-002**: No JavaScript code in the frontend can access authentication tokens via `document.cookie`
- **SC-003**: The application builds without TypeScript compilation errors
- **SC-004**: All frontend unit tests pass (excluding deleted test file)
- **SC-005**: Authentication flows (anonymous session, magic link login, logout) continue to function correctly
- **SC-006**: CVSS 8.6 XSS token theft vulnerability is eliminated

## Assumptions

- Backend httpOnly cookie authentication is already in place and working
- The removal of client-side cookie management does not break any backend functionality
- The `auth-store.ts` calls to `setAuthCookies` and `clearAuthCookies` are no longer needed because the backend handles cookie management
- No other files depend on cookies.ts beyond what was identified (auth-store.ts, cookies.test.ts)

## Dependencies

- This fix depends on httpOnly cookie authentication being functional on the backend
- This fix blocks Phase 0 C4, C5 and all subsequent authentication phases

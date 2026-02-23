# Feature Specification: Multi-User Session Consistency

**Feature Branch**: `014-session-consistency`
**Created**: 2025-12-01
**Status**: Draft
**Input**: User description: "Session consistency audit - ensure user sessions work correctly across frontend/backend, fix race conditions for multi-user scenarios, follow industry best practices"

## Problem Statement

The authentication system has critical race conditions and consistency issues that prevent reliable multi-user operation:

1. **Frontend-Backend Session Mismatch**: The dashboard frontend cannot display data because it lacks a valid user session, even after the traffic generator successfully warms the API
2. **Magic Link Token Race Condition**: Two concurrent users can verify the same magic link token, creating duplicate accounts
3. **User Creation Race Condition**: Concurrent OAuth/magic link flows can create multiple accounts for the same email address
4. **Session Storage Divergence**: Frontend localStorage and backend DynamoDB can have inconsistent session states

## Clarifications

### Session 2025-12-01

- Q: Which authentication header strategy should be used? → A: Hybrid approach - backend accepts both `X-User-ID` and `Authorization: Bearer` for anonymous sessions. Backward compatible, gradual migration path, no breaking changes.
- Q: When should anonymous session be auto-created? → A: On app load - create session immediately when React app mounts, before any user interaction. Ensures session exists for all API calls, zero perceived latency.
- Q: Should all sessions support server-side revocation? → A: Yes, server-side revocation for all sessions (anonymous + authenticated). Integrate with existing andon cord/feature flag system for rapid incident response during attacks.
- Q: Where should email uniqueness be enforced? → A: Database constraint via GSI + conditional write (`attribute_not_exists(email)`). Guaranteed atomic, no race conditions possible.
- Q: How should partial merge failures be handled? → A: Tombstone + idempotency keys - mark source items with `merged_to` field before copying. Retry skips already-merged items. No item limit, audit trail preserved, self-healing on partial failures.
- Q: How should race conditions be tested? → A: Async concurrency with pytest-asyncio using `asyncio.gather()` to fire concurrent requests. Matches existing E2E patterns, provides true I/O parallelism.
- Q: What test coverage categories are required? → A: Full pyramid (unit + integration + contract + e2e) for each FR. Must meet 80% coverage threshold enforced by CI.
- Q: How should tests be marked? → A: New feature marker `@pytest.mark.session_consistency` plus story sub-markers `@pytest.mark.session_us1` through `session_us6`. Clear namespace, no conflicts with existing markers.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Single User Gets Consistent Session Across Tabs (Priority: P1)

A user opens the sentiment dashboard in their browser. They should be automatically authenticated (anonymously if no prior session) and see their data immediately. If they open another tab, both tabs should share the same session and see the same data.

**Why this priority**: This is the core user experience - users cannot use the product at all if sessions don't work consistently. The current bug (dashboard shows "No sentiment data") is caused by this failure.

**Independent Test**: Open dashboard in browser, verify anonymous session is created automatically, verify data loads in the chart. Open second tab, verify same session is used.

**Acceptance Scenarios**:

1. **Given** a new user visits the dashboard, **When** the page loads, **Then** an anonymous session is automatically created and stored in localStorage before any user interaction
2. **Given** a user has an active session in Tab A, **When** they open Tab B, **Then** Tab B uses the same session from localStorage
3. **Given** a user's session exists in localStorage, **When** they make API requests, **Then** the correct authentication header is sent to the backend (either `X-User-ID` or `Authorization: Bearer` accepted)
4. **Given** a user's session token, **When** the backend validates it, **Then** it returns the user's data without errors

---

### User Story 2 - Concurrent Magic Link Verifications Are Safe (Priority: P1)

Two users should not be able to use the same magic link token to create accounts. The first verification wins; subsequent attempts fail gracefully.

**Why this priority**: This is a critical security vulnerability - duplicate accounts with the same email breaks the authentication model and could lead to data exposure.

**Independent Test**: Simulate two concurrent verification requests with the same token. Verify only one succeeds and the other fails with "token already used" error.

**Acceptance Scenarios**:

1. **Given** a valid magic link token, **When** User A verifies it first, **Then** User A's account is created and the token is marked used atomically
2. **Given** a token already verified by User A, **When** User B tries to verify the same token, **Then** User B receives "token already used" error
3. **Given** two simultaneous verification requests, **When** they race to verify, **Then** exactly one succeeds and one fails (no duplicates)

---

### User Story 3 - User Email Uniqueness Is Guaranteed (Priority: P1)

Each email address should map to exactly one user account. Concurrent OAuth and magic link flows for the same email should not create duplicate accounts.

**Why this priority**: Duplicate accounts per email causes data fragmentation, auth flow confusion, and potential security issues.

**Independent Test**: Trigger concurrent OAuth and magic link authentication for the same email. Verify only one account is created.

**Acceptance Scenarios**:

1. **Given** no existing account for alice@example.com, **When** OAuth login completes, **Then** exactly one account is created (enforced by database constraint)
2. **Given** an existing OAuth account for alice@example.com, **When** magic link verification completes for the same email, **Then** the existing account is linked (not duplicated)
3. **Given** two concurrent OAuth logins for bob@example.com, **When** they race, **Then** exactly one account is created and both sessions reference it (database rejects second write)

---

### User Story 4 - Session Refresh Keeps User Logged In (Priority: P2)

Active users should not be unexpectedly logged out. The session should be refreshed as they use the application, and the frontend should sync with backend session state.

**Why this priority**: Users losing their session during active use creates a poor experience, but it's less critical than the security/correctness issues in P1.

**Independent Test**: User makes requests over multiple days. Verify session doesn't expire while actively using the app. Verify frontend session state matches backend.

**Acceptance Scenarios**:

1. **Given** a user with a 30-day session created on Day 1, **When** they make a request on Day 20, **Then** the session expiry is extended by 30 days from Day 20
2. **Given** a user's backend session is valid, **When** the frontend checks session status, **Then** the frontend receives and stores the updated expiry time
3. **Given** a user's session has expired, **When** they try to make a request, **Then** they are redirected to re-authenticate (not silently failing)
4. **Given** a security incident requiring immediate logout, **When** the andon cord/feature flag is triggered, **Then** all affected sessions are invalidated server-side immediately

---

### User Story 5 - Account Merge Is Atomic and Idempotent (Priority: P2)

When an anonymous user authenticates, their anonymous account data should be merged into their authenticated account without data loss or duplication.

**Why this priority**: Data loss during merge is serious but affects fewer users than the basic auth flows.

**Independent Test**: Create anonymous session with configurations. Authenticate with magic link. Verify all anonymous configurations appear under authenticated account.

**Acceptance Scenarios**:

1. **Given** anonymous user A with 3 configurations, **When** they authenticate as alice@example.com, **Then** all 3 configurations are transferred to the authenticated account
2. **Given** a merge operation in progress, **When** it fails halfway, **Then** it can be retried without creating duplicate configurations (tombstone markers track progress)
3. **Given** two concurrent merge operations for the same user, **When** they race, **Then** the final state is consistent (no duplicates, no data loss)
4. **Given** a partially merged account, **When** an operator investigates, **Then** the `merged_to` field on source items shows exactly where data was transferred

---

### User Story 6 - Email Lookup Is Fast and Consistent (Priority: P3)

Looking up users by email should be efficient and return consistent results, even under high load.

**Why this priority**: Performance optimization - the system works without this but at reduced efficiency.

**Independent Test**: Query user by email 100 times. Verify all queries complete within acceptable time and return consistent results.

**Acceptance Scenarios**:

1. **Given** 10,000 users in the system, **When** looking up a user by email, **Then** the lookup completes within 100ms (via GSI query, not table scan)
2. **Given** concurrent email lookups, **When** a new user is being created with that email, **Then** the lookup returns a consistent result (either exists or doesn't)

---

### Edge Cases

- What happens when a user's localStorage is cleared mid-session?
  - Frontend detects missing session on app load and creates new anonymous session immediately
- What happens when the backend session expires but frontend localStorage still has old token?
  - Backend returns 401, frontend clears localStorage and creates new anonymous session
- What happens when two devices try to authenticate the same account simultaneously?
  - Both should succeed and share the same user ID (session tokens may differ)
- What happens when magic link token expires during verification?
  - Return "token expired" error, user must request new link
- What happens when the database is temporarily unavailable?
  - Return 503, frontend shows "temporarily unavailable" message
- What happens during a security incident requiring mass logout?
  - Andon cord triggers server-side session invalidation for all affected users immediately

## Requirements *(mandatory)*

### Functional Requirements

#### Authentication Header Consistency
- **FR-001**: Backend MUST accept both `X-User-ID` header and `Authorization: Bearer` token for user authentication (hybrid approach)
- **FR-002**: Backend MUST validate the authentication header and extract user ID consistently regardless of header format used
- **FR-003**: Frontend MUST automatically create anonymous session on app load (React mount), before any user interaction

#### Session Security
- **FR-016**: All sessions (anonymous and authenticated) MUST support server-side revocation
- **FR-017**: Session revocation MUST integrate with existing andon cord/feature flag system for rapid incident response

#### Atomic Token Verification
- **FR-004**: Magic link token verification MUST be atomic - check and mark-used in single operation
- **FR-005**: Concurrent verification attempts for the same token MUST result in exactly one success
- **FR-006**: Token verification MUST fail gracefully if token is already used, expired, or invalid

#### User Uniqueness
- **FR-007**: System MUST prevent creation of multiple user accounts with the same email address via database constraint
- **FR-008**: User creation MUST use email GSI with conditional write (`attribute_not_exists`) to ensure uniqueness atomically
- **FR-009**: Email lookup MUST use GSI query (not full table scan) for production-scale efficiency

#### Session Lifecycle
- **FR-010**: Session expiry MUST be extended on user activity (sliding window)
- **FR-011**: Frontend MUST sync session state with backend periodically
- **FR-012**: Expired sessions MUST result in clear re-authentication flow (not silent failures)

#### Account Merge
- **FR-013**: Account merge MUST use tombstone markers (`merged_to` field) on source items before copying
- **FR-014**: Merge operations MUST be idempotent - retries skip items already marked with `merged_to`
- **FR-015**: Concurrent merge operations MUST not create duplicate data (tombstone prevents double-copy)

### Key Entities

- **User**: Represents an authenticated or anonymous user. Key attributes: user_id (unique), email (unique for authenticated users via GSI), auth_type, session_expires_at, revoked (boolean for server-side invalidation)
- **Session Token**: Represents an active session. Used for authentication. Has expiry time. Can be invalidated server-side.
- **Magic Link Token**: One-time use token for passwordless authentication. Has expiry, used flag, associated email.
- **Configuration**: User-owned data that must be preserved during merge operations. Includes `merged_to` field for idempotent merge tracking.

## Testing Requirements *(mandatory)*

### Test Strategy

All changes MUST include tests following the repository's full test pyramid:

1. **Unit Tests** (`tests/unit/`) - Isolated component tests with moto/responses mocking
2. **Integration Tests** (`tests/integration/`) - Multi-component workflows with AWS mocking
3. **Contract Tests** (`tests/contract/`) - API schema validation
4. **E2E Tests** (`tests/e2e/`) - Full pipeline tests against real AWS preprod

### Race Condition Testing

Race conditions MUST be tested using async concurrency with `pytest-asyncio`:
- Use `asyncio.gather()` to fire concurrent requests
- Test at least 10 concurrent operations per race condition scenario
- Verify exactly one success for mutually exclusive operations (token verification, user creation)

### Pytest Markers

Tests MUST use the following markers (to be added to `pytest.ini`):

```ini
session_consistency: Feature 014 - Session consistency tests
session_us1: User Story 1 - Consistent session across tabs
session_us2: User Story 2 - Concurrent magic link verification
session_us3: User Story 3 - Email uniqueness guarantee
session_us4: User Story 4 - Session refresh
session_us5: User Story 5 - Atomic account merge
session_us6: User Story 6 - Fast email lookup
```

### Test Coverage Requirements

- **Minimum Coverage**: 80% (enforced by CI)
- **Race Condition Coverage**: Every FR involving concurrency (FR-005, FR-008, FR-015) MUST have dedicated race condition tests
- **Frontend Coverage**: Auth store and session hooks MUST have vitest coverage

### Test File Structure

```
tests/
├── unit/
│   └── lambdas/
│       └── shared/
│           └── auth/
│               ├── test_session_consistency.py      # FR-001, FR-002, FR-003
│               ├── test_atomic_token_verification.py # FR-004, FR-005, FR-006
│               ├── test_email_uniqueness.py         # FR-007, FR-008, FR-009
│               └── test_merge_idempotency.py        # FR-013, FR-014, FR-015
├── integration/
│   └── test_session_race_conditions.py              # Concurrent operation tests
├── contract/
│   └── test_session_api_v2.py                       # API schema validation
└── e2e/
    └── test_session_consistency_preprod.py          # Real AWS validation
```

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users see their data within 3 seconds of opening the dashboard (no "no data" errors for authenticated users)
- **SC-002**: Zero duplicate accounts created per email address under concurrent load (100 simultaneous auth attempts)
- **SC-003**: Magic link tokens can only be used exactly once, verified by audit log
- **SC-004**: Session refresh maintains user authentication for 30+ days of active use without re-login
- **SC-005**: Email lookup completes in under 100ms for tables with 10,000+ users
- **SC-006**: Account merge preserves 100% of user data with zero duplicates
- **SC-007**: System handles 100 concurrent authentication requests without race condition failures
- **SC-008**: Mass session revocation via andon cord completes within 30 seconds for all affected users
- **SC-009**: All tests pass with 80%+ coverage before merge to main

## Assumptions

- UUID v4 generation is sufficiently random to prevent collisions in user IDs
- Conditional writes in the database provide the atomicity needed for race condition prevention
- localStorage is available in all supported browsers
- Network latency between frontend and backend is under 500ms for typical users
- Users typically have at most 5 concurrent browser tabs/devices
- Existing andon cord/feature flag infrastructure is available for session revocation integration
- pytest-asyncio is available for concurrent test execution

## Out of Scope

- OAuth provider-side rate limiting or security
- Multi-region session replication
- Session hijacking detection/prevention (beyond token validation)
- Browser extension or native app authentication flows
- SSO/SAML enterprise authentication

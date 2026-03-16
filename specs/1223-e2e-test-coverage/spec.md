# Feature Specification: E2E Test Coverage Expansion

**Feature Branch**: `1223-e2e-test-coverage`
**Created**: 2026-03-16
**Status**: Draft
**Input**: Expand E2E test coverage for authentication flows, account linking, alert management, session lifecycle, and cross-browser testing

## User Scenarios & Testing *(mandatory)*

### User Story 1 - OAuth Login Flow Verification (Priority: P1)

As a quality engineer, I need end-to-end tests that verify the complete OAuth login flow (Google and GitHub) works correctly, including authorization redirect, callback handling, session creation, and token issuance. Tests must cover both successful login and error scenarios without requiring real OAuth provider credentials.

**Why this priority**: OAuth login is the primary authentication method for paying users. The current test suite only covers callback error handling — the actual success flow is completely untested. A regression here silently breaks user acquisition.

**Independent Test**: Can be tested by mocking the OAuth provider response at the callback level and verifying the full session lifecycle from redirect to authenticated dashboard access.

**Acceptance Scenarios**:

1. **Given** a user clicks "Continue with Google", **When** the authorization redirect is initiated, **Then** the redirect URL contains valid state, PKCE code_challenge, and correct scopes.
2. **Given** a valid OAuth callback with authorization code, **When** the callback is processed, **Then** the user receives a valid session with appropriate role and the dashboard loads in authenticated state.
3. **Given** an OAuth callback where the provider denies access, **When** the callback is processed, **Then** the user sees a friendly error message with a "Try again" link.
4. **Given** an OAuth callback with a stale or replayed state parameter, **When** the callback is processed, **Then** the system rejects the request and logs the attempt.

---

### User Story 2 - Magic Link Authentication Verification (Priority: P1)

As a quality engineer, I need end-to-end tests that verify the complete magic link flow: email request, token generation, email delivery confirmation, token verification, and session creation. Tests must verify that used tokens cannot be reused and expired tokens are rejected.

**Why this priority**: Magic link auth is the passwordless flow for users who don't use OAuth. The current tests only check the form UI — token generation and verification are completely untested end-to-end.

**Independent Test**: Can be tested by requesting a magic link, extracting the token from the API response (or test email service), then navigating to the verification URL.

**Acceptance Scenarios**:

1. **Given** a user enters a valid email and clicks "Continue with Email", **When** the magic link is requested, **Then** the system confirms the email was sent and a token record is created.
2. **Given** a valid magic link token, **When** the user clicks the verification link, **Then** the user is authenticated with a valid session and redirected to the dashboard.
3. **Given** a magic link token that has already been used, **When** the user clicks the link again, **Then** the system shows "This link has already been used" and prompts for a new link.
4. **Given** a magic link token older than 1 hour, **When** the user clicks the link, **Then** the system shows "This link has expired" and prompts for a new link.

---

### User Story 3 - Alert Management CRUD (Priority: P2)

As a quality engineer, I need end-to-end tests that verify the complete alert lifecycle: creating alerts, viewing alert list, updating alert thresholds, deleting alerts, and verifying quota enforcement.

**Why this priority**: Alert management is a premium feature with no E2E test coverage. The page loads are tested but no CRUD operations are verified. A regression could break the entire alert feature silently.

**Independent Test**: Can be tested by creating an authenticated session, performing alert CRUD operations, and verifying the UI reflects each change.

**Acceptance Scenarios**:

1. **Given** an authenticated user on the alerts page, **When** the user creates a new alert for ticker AAPL with a price threshold, **Then** the alert appears in the list with correct details.
2. **Given** an alert exists, **When** the user updates the threshold, **Then** the alert list reflects the updated value.
3. **Given** an alert exists, **When** the user deletes it, **Then** the alert disappears from the list.
4. **Given** a user at their alert quota limit, **When** they attempt to create another alert, **Then** the system displays a quota exceeded message.

---

### User Story 4 - Session Lifecycle and Refresh (Priority: P2)

As a quality engineer, I need end-to-end tests that verify session management: token refresh, session extension, session expiry, concurrent session limits, and sign-out behavior.

**Why this priority**: Session management is critical for user experience and security. No tests currently cover token refresh, session timeout, or sign-out. Users could experience silent session loss without any automated detection.

**Independent Test**: Can be tested by creating a session, manipulating token expiry via test utilities, and verifying refresh and timeout behaviors.

**Acceptance Scenarios**:

1. **Given** an authenticated user with a session approaching expiry, **When** the system performs a background token refresh, **Then** the session continues without interruption.
2. **Given** an authenticated user, **When** the user clicks "Sign Out", **Then** the session is invalidated, the user is redirected to the login page, and stored tokens are cleared.
3. **Given** a user with 5 active sessions (the maximum), **When** they log in from a 6th device, **Then** the oldest session is evicted and the new session succeeds.
4. **Given** a session that has expired without refresh, **When** the user makes any API request, **Then** they receive a 401 and are prompted to re-authenticate.

---

### User Story 5 - Account Linking Flow (Priority: P2)

As a quality engineer, I need end-to-end tests that verify account linking: anonymous-to-authenticated migration, adding a second OAuth provider, and data preservation during merges.

**Why this priority**: Account linking is a complex flow that touches authentication, data migration, and session management. Zero E2E coverage exists. A regression could cause data loss during account merges.

**Independent Test**: Can be tested by creating an anonymous session with data, authenticating via magic link, and verifying all data transfers to the authenticated account.

**Acceptance Scenarios**:

1. **Given** an anonymous user with saved configurations and alerts, **When** they complete email verification via magic link, **Then** all their data migrates to the authenticated account.
2. **Given** an authenticated user with Google linked, **When** they link their GitHub account, **Then** they can log in with either provider and see the same data.
3. **Given** an anonymous user, **When** they authenticate with an email that already has an account, **Then** the accounts merge and no data is lost.

---

### User Story 6 - Cross-Browser Compatibility (Priority: P3)

As a quality engineer, I need the existing Playwright test suite to run against Firefox and Desktop Safari (WebKit) in addition to Chromium, ensuring cross-browser compatibility.

**Why this priority**: Currently only Chromium-based browsers are tested. Firefox and Safari have different rendering engines that may expose CSS, JavaScript, or CORS issues invisible in Chromium.

**Independent Test**: Can be tested by adding Firefox and WebKit projects to the Playwright configuration and running the existing sanity test suite.

**Acceptance Scenarios**:

1. **Given** the existing sanity test suite, **When** run against Firefox, **Then** all tests pass with the same assertions as Chromium.
2. **Given** the existing sanity test suite, **When** run against WebKit (Safari), **Then** all tests pass with the same assertions as Chromium.
3. **Given** a browser-specific CSS issue, **When** detected by cross-browser tests, **Then** the failure clearly identifies the browser and the rendering difference.

---

### Edge Cases

- What happens when OAuth providers return different email formats (uppercase, with dots, with plus-addressing)? Tests should normalize and verify.
- What happens when magic link email delivery fails? Tests should verify the UI shows a retry option.
- What happens when the user's browser blocks third-party cookies? SSE streaming and session management must degrade gracefully.
- What happens when multiple Playwright tests run concurrently against the same preprod environment? Tests must use unique user identifiers to prevent data collision.
- What happens when the E2E test itself times out during a cold Lambda start? Tests should have appropriate timeout budgets for cold start scenarios.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Test suite MUST include OAuth login flow tests covering authorization redirect, callback success, callback errors, and session creation.
- **FR-002**: Test suite MUST include magic link flow tests covering email request, token verification, token reuse rejection, and token expiry.
- **FR-003**: Test suite MUST include alert CRUD tests covering create, read, update, delete, and quota enforcement.
- **FR-004**: Test suite MUST include session lifecycle tests covering token refresh, sign-out, session eviction, and expired session handling.
- **FR-005**: Test suite MUST include account linking tests covering anonymous-to-authenticated migration, multi-provider linking, and data preservation.
- **FR-006**: Test suite MUST run against Firefox and WebKit in addition to Chromium, with failures attributed to the specific browser.
- **FR-007**: All new tests MUST use unique, isolated test data (prefixed identifiers) to prevent collision with other concurrent test runs.
- **FR-008**: All new tests MUST clean up test data after execution, or use TTL-based data that auto-expires.
- **FR-009**: Test suite MUST produce structured reports (JUnit XML or similar) compatible with CI artifact upload.
- **FR-010**: OAuth flow tests MUST use mocked provider responses at the callback boundary — no real OAuth provider credentials required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Authentication flow coverage increases from 2 tested flows (anonymous session, callback errors) to 6 tested flows (adding OAuth success, magic link full flow, session refresh, sign-out).
- **SC-002**: Alert management goes from 0 CRUD operations tested to full lifecycle coverage (create, read, update, delete, quota).
- **SC-003**: Account linking goes from 0 tested scenarios to 3 tested scenarios (anonymous migration, multi-provider, email merge).
- **SC-004**: Cross-browser testing covers 3 browser engines (Chromium, Firefox, WebKit) with 90%+ of existing tests passing on all three.
- **SC-005**: All new E2E tests run in CI within the existing pipeline timeout budget (no new infrastructure needed).
- **SC-006**: Test skip rate remains below 15% after enabling previously skipped test groups.
- **SC-007**: Zero false positives — new tests must be deterministic (no flaky behavior over 10 consecutive runs).

## Assumptions

- Preprod environment is available and stable for E2E testing against real Lambda functions.
- OAuth provider mocking will be done at the callback URL level (intercepting the redirect), not by standing up a fake OAuth server.
- Magic link token extraction for E2E tests will use the API directly (request link → extract token from response or DynamoDB query) rather than actual email delivery.
- Cross-browser tests may need browser-specific timeout adjustments for WebKit cold starts.
- The existing Playwright configuration (mobile Chrome, mobile Safari, desktop Chrome) will be extended, not replaced.

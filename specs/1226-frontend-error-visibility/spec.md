# Feature Specification: Frontend Error Visibility

**Feature Branch**: `1226-frontend-error-visibility`
**Created**: 2026-03-19
**Status**: Draft
**Input**: User description: "Frontend error visibility — distinguish API errors from empty results in ticker search, add global connectivity health check banner, surface auth degradation instead of silently swallowing errors"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ticker Search Distinguishes Errors from Empty Results (Priority: P1)

A customer types a ticker symbol into the dashboard search. Currently, both "the API returned no results" and "the API is unreachable" display the same message: "No tickers found." The customer cannot tell whether they misspelled a symbol or the entire system is down. This masked a 3-day outage (dead API URL) because every search appeared to return empty results rather than signaling an infrastructure failure.

After this feature, the customer sees distinct messages for each situation: empty results show "No tickers found," while API errors show a clear error state explaining that something went wrong, with a retry option.

**Why this priority**: This is the exact failure mode that caused 3 days of silent breakage. It's the most impactful change and the simplest to validate.

**Independent Test**: Can be fully tested by simulating a network error on the search endpoint and verifying the customer sees a different message than when the search returns zero results.

**Acceptance Scenarios**:

1. **Given** the API is healthy and a ticker symbol has no matches, **When** the customer searches for "XYZNOTREAL", **Then** the dropdown shows "No tickers found for 'XYZNOTREAL'" (current behavior, unchanged).
2. **Given** the API is unreachable (network error, 500, 502, 503, timeout), **When** the customer searches for "AAPL", **Then** the dropdown shows a distinct error state: a warning message (e.g., "Unable to search. Check your connection or try again.") with a retry action.
3. **Given** the API returns 429 (rate limited), **When** the customer searches, **Then** the dropdown shows "Too many requests. Please wait a moment." distinct from the empty-results message.
4. **Given** the search API was failing and then recovers, **When** the customer retries or types a new query, **Then** the search returns results normally with no stale error state persisting.

---

### User Story 2 — Global API Health Banner (Priority: P1)

A customer visits the dashboard while the backend API is completely unreachable (dead URL, network outage, prolonged 5xx errors). Currently, the dashboard loads its shell (sidebar, search bar, empty chart area) but every interaction fails silently — search says "no tickers found," chart stays on the empty state, and no message explains what's wrong.

After this feature, when the API is unreachable, a persistent banner appears at the top of the page indicating the system is experiencing connectivity issues. The banner auto-dismisses when connectivity is restored. This gives the customer immediate context that failures are systemic, not specific to their query.

**Why this priority**: Equal to P1 because it addresses the systemic case — when everything is broken but nothing says so. The ticker search fix (US1) addresses a single interaction; this addresses the dashboard-wide experience.

**Independent Test**: Can be tested by blocking the API URL, performing 3+ interactions (search, chart load), and verifying the banner appears after sustained failures. Then unblocking and verifying it dismisses after a successful request.

**Acceptance Scenarios**:

1. **Given** the API is unreachable, **When** the customer's first interaction (e.g., search, chart load) fails, **Then** a prominent banner appears indicating connectivity issues (e.g., "We're having trouble connecting to the server. Some features may be unavailable."). The banner appears after sustained failure (3+ failures in 60 seconds), not on the first failed request.
2. **Given** the banner is showing, **When** the customer's next interaction succeeds (API is reachable again), **Then** the banner dismisses automatically on that first successful response.
3. **Given** the API is healthy, **When** the customer uses the dashboard normally, **Then** no banner is shown and the health detection does not degrade the user experience (no visible spinners, no flash of banner).
4. **Given** the API is intermittently failing (some requests succeed, some fail), **When** the customer is using the dashboard, **Then** the banner appears only after sustained failure (not on a single transient error), avoiding false alarms.

---

### User Story 3 — Auth Degradation Surfaced to Customer (Priority: P2)

A customer's session is silently degrading — session refresh fails, profile data goes stale, or the authentication state becomes inconsistent. Currently, these failures are caught and discarded. The customer's session may expire without warning, leading to a sudden "please sign in" experience mid-workflow with no explanation.

After this feature, auth degradation is surfaced via a non-blocking notification. If session refresh fails repeatedly, the customer is told their session may expire soon and offered the option to re-authenticate proactively.

**Why this priority**: Less visible than search/banner because auth degradation is gradual and doesn't affect anonymous users (the majority in preprod). But it will be critical once authenticated users are the norm.

**Independent Test**: Can be tested by simulating a session refresh failure and verifying the customer sees a notification before being forcibly signed out.

**Acceptance Scenarios**:

1. **Given** a logged-in customer whose session refresh fails, **When** the refresh has failed 2 or more consecutive times, **Then** a non-blocking notification appears (e.g., "Your session may expire soon. Please save your work.") with a "Sign in again" action.
2. **Given** a logged-in customer whose profile refresh fails, **When** the failure is transient (single occurrence), **Then** no notification is shown (existing behavior, unchanged).
3. **Given** a logged-in customer who receives a session expiration notification, **When** they click "Sign in again", **Then** they are taken to the sign-in flow with their current page preserved for return after re-authentication.
4. **Given** an anonymous customer, **When** session-related errors occur, **Then** no auth degradation notifications are shown (anonymous sessions are inherently ephemeral).

---

### Edge Cases

- What happens when the API returns an unexpected content type (e.g., HTML error page instead of JSON)? The error should be treated as an API failure, not parsed as results.
- How does the system behave when the API responds slowly (2-5 seconds) but doesn't timeout? Slow but successful responses are not treated as failures; only timeouts and error status codes contribute to the failure counter.
- What if some endpoints fail but others succeed (partial outage)? The banner threshold tracks all request outcomes together. If search fails but auth succeeds, failures still accumulate toward the threshold. Individual endpoint failures are also surfaced by their respective components (search dropdown, chart overlay).
- What happens if the customer has no internet connection at all? The health detection tracks network errors the same as API unreachability. The banner message should not assume the server is at fault (e.g., "Unable to connect" rather than "Server error").
- How does the banner interact with existing error overlays on the chart component? If the banner is showing, the chart error overlay should still appear but should not duplicate the connectivity message. The banner addresses "why" (system-wide); the chart overlay addresses "what" (this chart failed).
- What if the customer dismisses the banner manually? The banner should not reappear until the next failure cycle (i.e., after the API recovers and fails again).

## Clarifications

### Session 2026-03-19

- Q: Should the health banner be driven by a dedicated /health poll, real request outcomes, or both? → A: Request outcomes only. No dedicated health endpoint polling from the frontend. The banner is derived from the customer's own authenticated request failures. Operational health monitoring is handled separately by an authenticated backend canary (out of scope for this feature). This eliminates the DDoS surface of a public health endpoint and avoids false positives from auth/health endpoint mismatches.
- Q: Should error state occurrences be tracked for operational visibility? → A: Structured console logging only (no server-side reporting). Each error state transition (banner shown/dismissed, search error, auth degradation) emits a structured console warning. This provides zero-cost test observability — Playwright and chaos injection tests can intercept console events to assert error states programmatically. Server-side client error visibility (CloudWatch RUM or equivalent) is deferred as a separate feature due to the circular dependency problem (client can't report "API down" to the API).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ticker search dropdown MUST display a distinct visual state for API errors versus empty results. The error state MUST include a retry mechanism.
- **FR-002**: The dashboard MUST track the outcomes of the customer's own API requests and display a persistent banner when sustained failures indicate connectivity loss. No dedicated health endpoint polling from the frontend.
- **FR-003**: The health detection MUST auto-recover — the banner MUST dismiss automatically on the first successful user-triggered request after connectivity is restored, without requiring a page reload.
- **FR-004**: The health banner MUST use a debounce/threshold mechanism — it MUST NOT appear on a single transient failure, only after sustained connectivity loss (3 or more request failures within a 60-second window).
- **FR-005**: Auth session refresh failures MUST be tracked. After 2 or more consecutive failures, the customer MUST receive a non-blocking notification with a re-authentication action.
- **FR-006**: Auth profile refresh failures MUST be logged but MUST NOT be surfaced for single transient failures (preserving current graceful degradation for one-off errors).
- **FR-007**: Error states MUST NOT persist after the underlying issue resolves. Stale error messages MUST be cleared when the next successful response is received.
- **FR-008**: The health banner, search error state, and chart error overlay MUST NOT produce duplicate or conflicting messages for the same underlying failure.
- **FR-009**: All new error UI MUST be consistent with the existing dark-theme dashboard design language.
- **FR-010**: The health detection MUST NOT introduce any additional API requests. It MUST be derived entirely from requests the customer already triggers through normal interaction.
- **FR-011**: Each error state transition (banner shown, banner dismissed, search error displayed, auth degradation notification) MUST emit a structured console warning with event name, timestamp, and relevant context (e.g., failure count, endpoint). This enables automated test assertions without DOM scraping.

### Key Entities

- **API Health State**: Represents the current connectivity status of the backend (healthy, unreachable). Derived exclusively from the outcomes of the customer's own API requests (no dedicated polling). Transitions to "unreachable" after 3+ failures in 60 seconds; transitions back to "healthy" on first successful request.
- **Error Context**: Distinguishes the cause of a failed interaction (network error, timeout, HTTP error status, empty result) so the UI can display an appropriate message.
- **Auth Session Health**: Tracks consecutive session refresh failures to determine when to notify the customer of impending session expiration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When the API is unreachable, 100% of customers who interact with the dashboard see a connectivity banner after their initial failed requests, compared to 0% today.
- **SC-002**: Ticker search shows a distinct error message (not "No tickers found") for API failures, verifiable by automated browser test.
- **SC-003**: The connectivity banner auto-dismisses on the first successful user-triggered request after API recovery, without page reload.
- **SC-004**: Auth degradation notification appears after 2 consecutive session refresh failures, verifiable by simulating refresh errors.
- **SC-005**: Zero additional API requests from health detection — the feature introduces no polling, no background requests, and no dedicated health calls. All detection is passive, derived from existing user-triggered requests.
- **SC-006**: No false-positive banners during normal operation — a single transient 500 error does not trigger the connectivity banner.
- **SC-007**: All error state transitions are detectable by automated tests via structured console events, without relying on DOM selectors or screenshots.

## Assumptions

- The frontend does NOT poll any health endpoint. Health detection is purely passive, derived from user-triggered request outcomes. Operational health monitoring is a separate concern handled by an authenticated backend canary (out of scope).
- Anonymous users are the majority of current traffic; auth degradation notifications primarily benefit authenticated users.
- The existing toast notification library is suitable for non-blocking auth notifications. The health banner is a separate persistent element (not a toast) because it represents a sustained state, not a momentary event.
- A "sustained failure" for the health banner is defined as 3 or more request failures within a 60-second window.
- The feature does not require backend changes — all detection is based on existing API response behavior (status codes, network errors, timeouts).
- A separate feature should address: (1) moving `/health` behind authentication, and (2) creating an authenticated backend canary for operational monitoring.

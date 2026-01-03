# Feature Specification: Fix Double-Slash URL in API Requests

**Feature Branch**: `1118-fix-api-url-double-slash`
**Created**: 2026-01-02
**Status**: Draft
**Input**: User description: "Frontend dashboard making POST requests to //api/v2/auth/anonymous endpoint (double-slash URL) resulting in HTTP 422 errors. Fix requires URL normalization strategy."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Anonymous Authentication Succeeds (Priority: P1)

As a user visiting the dashboard for the first time, I want to be automatically authenticated as an anonymous user so that I can immediately access the dashboard without any errors or login prompts.

**Why this priority**: Authentication is the gateway to all dashboard functionality. If anonymous auth fails, users see errors and cannot use the application at all. This is a complete blocker for the demo-able dashboard goal.

**Independent Test**: Can be fully tested by opening a fresh browser session, navigating to the dashboard URL, and verifying that the page loads without 422 errors and displays dashboard content.

**Acceptance Scenarios**:

1. **Given** a user opens the dashboard in a new browser session, **When** the page loads, **Then** the authentication request completes successfully with HTTP 200/201 status
2. **Given** a user is not logged in, **When** the dashboard attempts anonymous authentication, **Then** the request URL is properly formatted without double slashes
3. **Given** a user accesses the dashboard, **When** checking browser DevTools Network tab, **Then** all API requests show single-slash URL paths (e.g., `/api/v2/auth/anonymous` not `//api/v2/auth/anonymous`)

---

### User Story 2 - All API Requests Use Correct URLs (Priority: P2)

As a user interacting with the dashboard, I want all API requests to be properly formatted so that every feature works reliably without mysterious errors.

**Why this priority**: While auth is the most visible failure, the double-slash issue could affect any API call. Ensuring all requests are properly formatted prevents future issues across the application.

**Independent Test**: Can be tested by exercising multiple dashboard features (searching tickers, viewing sentiment data) and verifying all API requests in Network tab have properly formatted URLs.

**Acceptance Scenarios**:

1. **Given** a user performs any action that triggers an API request, **When** the request is sent, **Then** the URL contains no double slashes between the base URL and path
2. **Given** the API base URL may or may not have a trailing slash, **When** endpoint paths are appended, **Then** the final URL is always correctly formatted

---

### Edge Cases

- What happens when the API base URL already has a trailing slash? The URL construction should still produce a valid URL without double slashes.
- What happens when an endpoint path doesn't start with a slash? The URL construction should still produce a valid URL with proper path separation.
- How does the system handle empty or undefined API base URL? Should display a clear error message indicating misconfiguration rather than making requests to invalid URLs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST construct API request URLs without double slashes between base URL and endpoint path
- **FR-002**: System MUST normalize URL construction regardless of whether base URL has trailing slash
- **FR-003**: System MUST normalize URL construction regardless of whether endpoint path has leading slash
- **FR-004**: URL normalization MUST be applied consistently across all API client methods (GET, POST, PUT, DELETE)
- **FR-005**: System MUST use a single, canonical URL construction pattern (no fallbacks or backwards compatibility layers)

### Key Entities

- **API Base URL**: The root URL for all API requests, configured via environment variable, may or may not have trailing slash
- **Endpoint Path**: The specific API route being called, may or may not have leading slash
- **Constructed URL**: The final URL formed by combining base URL and endpoint path, must never contain double slashes in the path portion

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Anonymous authentication requests return HTTP 200/201 status (not 422) on dashboard load
- **SC-002**: Zero API requests in browser Network tab contain double-slash URLs (`//api/`)
- **SC-003**: Dashboard loads successfully and displays content without authentication errors
- **SC-004**: URL normalization handles edge cases: trailing slash on base URL, missing leading slash on path, both conditions together

## Assumptions

- **Greenfield approach**: Implement the correct solution without backwards compatibility layers or fallbacks
- The URL normalization fix should be implemented in the frontend API client layer
- The fix should handle both cases: base URL with/without trailing slash and paths with/without leading slash
- Normalization happens at URL construction time in the API client
- The Lambda Function URL format (no trailing slash by default) is the expected base URL format
- If tests fail after implementation, debug the mismatch rather than adding workarounds

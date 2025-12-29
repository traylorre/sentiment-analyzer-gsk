# Feature Specification: SSE Runtime URL Discovery

**Feature Branch**: `1100-sse-runtime-url`
**Created**: 2025-12-29
**Status**: Draft
**Input**: User description: "Frontend SSE 502: Fetch /api/v2/runtime to get correct SSE Lambda URL"

## Problem Statement

The dashboard shows a 502 Bad Gateway error when connecting to the Server-Sent Events (SSE) stream. This occurs because the frontend attempts to connect to the SSE endpoint on the Dashboard Lambda (which uses BUFFERED mode and cannot stream), instead of the dedicated SSE Lambda (which uses RESPONSE_STREAM mode and supports true streaming).

**Root Cause**: The frontend uses `NEXT_PUBLIC_API_URL` for SSE connections, but this points to the Dashboard Lambda. The backend already exposes a `/api/v2/runtime` endpoint that returns the correct SSE Lambda URL, but the frontend doesn't fetch or use this configuration.

**Evidence**:
- `/api/v2/runtime` returns: `{"sse_url": "https://lenmswrtbk7aoeot2p75rwhvmq0jcvjz.lambda-url.us-east-1.on.aws/", "environment": "preprod"}`
- SSE Lambda health check works: `GET /health` returns `{"status":"healthy","environment":"preprod"}`
- Dashboard Lambda cannot stream SSE due to BUFFERED invoke mode

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Real-time Dashboard Updates (Priority: P1)

As a user viewing the sentiment analyzer dashboard, I want to see real-time updates to sentiment data so that I can monitor market sentiment as it changes.

**Why this priority**: This is the core value proposition of the SSE feature - without real-time updates, users must manually refresh the page to see new data.

**Independent Test**: Open the dashboard, observe that the "Connecting..." status changes to "Connected", and verify that sentiment updates appear automatically when new data is available.

**Acceptance Scenarios**:

1. **Given** I am on the dashboard page, **When** the page loads, **Then** the SSE connection status shows "Connecting..." followed by "Connected" within 5 seconds
2. **Given** I am connected to the SSE stream, **When** new sentiment data is available, **Then** the dashboard updates automatically without page refresh
3. **Given** the SSE connection drops, **When** the system detects the disconnection, **Then** it automatically attempts to reconnect with exponential backoff

---

### User Story 2 - Graceful Fallback (Priority: P2)

As a user on a network with SSE restrictions, I want the dashboard to remain functional even if the SSE connection cannot be established.

**Why this priority**: Some corporate networks block SSE connections. Users should still be able to use the dashboard with manual refresh.

**Independent Test**: Block the SSE Lambda URL in browser dev tools and verify the dashboard loads and functions with manual refresh.

**Acceptance Scenarios**:

1. **Given** the SSE Lambda is unreachable, **When** the frontend fails to fetch runtime config, **Then** the dashboard functions normally with a "Live updates unavailable" indicator
2. **Given** the SSE connection fails after multiple retries, **When** max reconnection attempts are reached, **Then** a user-friendly message is displayed with option to manually retry

---

### Edge Cases

- What happens when `/api/v2/runtime` returns a null or empty `sse_url`?
  - System falls back to Dashboard Lambda URL and continues attempting connection
- What happens when the SSE Lambda URL is returned but the Lambda is down?
  - EventSource error handling triggers reconnection with exponential backoff
- What happens when the runtime config endpoint is slow (>5s)?
  - Show "Initializing..." state, do not block dashboard rendering
- What happens on mobile/low-bandwidth connections?
  - SSE should work; connection drops handled by reconnection logic

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Frontend MUST fetch `/api/v2/runtime` on application initialization before attempting SSE connection
- **FR-002**: Frontend MUST store the `sse_url` from runtime config in application state
- **FR-003**: Frontend MUST use the `sse_url` (when available) as the base URL for all EventSource connections
- **FR-004**: Frontend MUST fall back to `NEXT_PUBLIC_API_URL` if `sse_url` is null, empty, or fetch fails
- **FR-005**: Frontend MUST NOT block initial page render while fetching runtime config
- **FR-006**: System MUST preserve existing reconnection logic (exponential backoff with jitter)
- **FR-007**: Frontend MUST show appropriate connection status to users (Connecting, Connected, Disconnected, Error)

### Key Entities

- **RuntimeConfig**: Application configuration fetched from backend including `sse_url` and `environment`
- **SSEClient**: Client class managing EventSource connections with reconnection logic
- **ConfigStore**: Application state store holding runtime configuration

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 502 errors on SSE stream endpoint are eliminated (0 occurrences in browser Network tab)
- **SC-002**: SSE connection successfully establishes within 5 seconds on page load (when network is available)
- **SC-003**: Dashboard remains functional even when SSE Lambda is unreachable (no blank pages or JavaScript errors)
- **SC-004**: Real-time updates are visible in the dashboard when sentiment data changes

## Assumptions

- The backend `/api/v2/runtime` endpoint is already implemented and returns the correct SSE Lambda URL
- The SSE Lambda (RESPONSE_STREAM mode) is deployed and operational
- The frontend uses React/Next.js with a centralized configuration store pattern
- EventSource API is available in all target browsers (modern browsers, no IE11 requirement)

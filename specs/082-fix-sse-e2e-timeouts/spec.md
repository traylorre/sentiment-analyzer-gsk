# Feature Specification: Fix SSE E2E Integration Test Timeouts

**Feature Branch**: `082-fix-sse-e2e-timeouts`
**Created**: 2025-12-10
**Status**: Draft
**Input**: User description: "Fix SSE E2E Integration Test Timeouts - SSE streaming endpoints return timeout instead of streaming responses in preprod"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnose SSE Streaming Failures (Priority: P1)

As a developer, I need to identify why SSE streaming endpoints timeout in preprod E2E tests so that I can fix the root cause and unblock the pipeline.

**Why this priority**: The pipeline is blocked by failing SSE E2E tests. Without diagnosis, we cannot identify the correct fix.

**Independent Test**: Can be tested by examining CI logs, Lambda configurations, and streaming endpoint behavior to produce a root cause analysis document.

**Acceptance Scenarios**:

1. **Given** the failing pipeline run 20098880625, **When** analyzing the test failures, **Then** the root cause is identified and documented (infra vs code vs test)
2. **Given** the SSE Lambda configuration, **When** reviewing streaming mode settings, **Then** any misconfiguration is identified
3. **Given** the test client implementation, **When** reviewing stream_sse() method, **Then** any client-side issues are identified

---

### User Story 2 - Fix SSE Streaming Endpoint Response (Priority: P1)

As a dashboard user, I need SSE streaming endpoints to return real-time events so that I receive live sentiment updates without refreshing the page.

**Why this priority**: SSE is a core user-facing feature. Non-streaming endpoints defeat the purpose of real-time updates.

**Independent Test**: Can be tested by connecting to `/api/v2/stream` and verifying that events are received within the timeout window.

**Acceptance Scenarios**:

1. **Given** the SSE Lambda is deployed with streaming mode, **When** GET `/api/v2/stream` is called, **Then** response returns `text/event-stream` content type within 10 seconds
2. **Given** an authenticated user with a configuration, **When** GET `/api/v2/configurations/{id}/stream` is called, **Then** SSE connection is established with streaming response
3. **Given** an established SSE connection, **When** events occur, **Then** events are pushed to the client in real-time

---

### User Story 3 - Verify E2E Test Suite Passes (Priority: P2)

As a CI/CD system, I need all SSE E2E tests to pass so that the deploy pipeline completes successfully and changes can be deployed.

**Why this priority**: Without passing tests, the pipeline remains blocked and no features can be deployed.

**Independent Test**: Can be tested by running the full E2E test suite in preprod and verifying all 6 SSE tests pass.

**Acceptance Scenarios**:

1. **Given** the SSE fix is deployed, **When** running `pytest tests/e2e/test_sse.py`, **Then** all 6 tests pass
2. **Given** the full E2E suite, **When** running preprod integration tests, **Then** no timeouts occur on streaming endpoints
3. **Given** a successful test run, **When** the pipeline completes, **Then** the workflow status is "success"

---

### Edge Cases

- What happens when SSE Lambda cold starts during test execution?
- How does the system handle connection drops mid-stream?
- What happens if the test timeout is shorter than Lambda cold start time?
- How does the system behave with multiple concurrent SSE connections?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SSE streaming endpoints MUST return `text/event-stream` content type
- **FR-002**: SSE Lambda MUST be configured for RESPONSE_STREAM invoke mode
- **FR-003**: SSE streaming responses MUST begin within 10 seconds of request
- **FR-004**: Test client MUST properly handle streaming responses without blocking
- **FR-005**: Non-streaming status endpoint (`/api/v2/stream/status`) MUST continue to work independently
- **FR-006**: SSE endpoints MUST support authenticated requests with valid session tokens

### Key Entities

- **SSE Lambda**: Handles streaming responses for real-time events
- **Dashboard Lambda**: Handles BUFFERED responses for REST API calls
- **Test Client**: PreprodAPIClient with stream_sse() method for E2E testing
- **SSE Event**: Server-sent event with event type, data, and optional ID

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 6 SSE E2E tests in `tests/e2e/test_sse.py` pass in preprod (0 failures)
- **SC-002**: SSE streaming endpoints respond within 10 seconds (no timeouts)
- **SC-003**: Pipeline deploy workflow completes with status "success"
- **SC-004**: Non-SSE tests continue to pass (no regression)

## Assumptions

- The SSE Lambda is a separate Lambda from the dashboard Lambda
- The current test timeout of 10 seconds should be sufficient for SSE connection establishment
- The issue is either infrastructure configuration or endpoint implementation, not network connectivity
- The non-streaming `/api/v2/stream/status` endpoint passing indicates the SSE Lambda is reachable

# Feature Specification: SSE Endpoint Implementation

**Feature Branch**: `015-sse-endpoint-fix`
**Created**: 2025-12-02
**Status**: Draft
**Input**: User description: "Fix SSE endpoint, add comprehensive tests. Goal: stop failing preprod pipeline. Consider adding mechanism for testing SSE locally."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard Real-Time Connection (Priority: P1)

An operator viewing the dashboard expects to see a "Connected" status indicator and receive real-time updates without page refreshes. Currently, the dashboard shows "Disconnected" because the SSE endpoint returns 404.

**Why this priority**: This is the core functionality that drives the entire feature. Without a working SSE endpoint, the dashboard cannot establish real-time connections, forcing fallback to polling and showing misleading "Disconnected" status.

**Independent Test**: Can be fully tested by opening the dashboard in a browser and verifying the connection status shows "Connected" and metrics update automatically. Delivers immediate visual feedback to operators.

**Acceptance Scenarios**:

1. **Given** a deployed dashboard, **When** an operator opens the dashboard page, **Then** the connection status indicator shows "Connected" within 5 seconds
2. **Given** an active SSE connection, **When** new data becomes available, **Then** the dashboard updates without requiring a page refresh
3. **Given** an SSE connection, **When** the server sends a heartbeat, **Then** the connection remains open and status shows "Connected"

---

### User Story 2 - Graceful Connection Recovery (Priority: P2)

When network issues occur or the server temporarily becomes unavailable, the dashboard should automatically reconnect without operator intervention.

**Why this priority**: Network interruptions are common in real-world deployments. Automatic recovery ensures operators don't need to manually refresh the page, maintaining operational continuity.

**Independent Test**: Can be tested by simulating a network interruption (e.g., temporarily blocking the connection) and verifying the dashboard automatically reconnects and restores "Connected" status.

**Acceptance Scenarios**:

1. **Given** an active SSE connection, **When** the connection is lost, **Then** the dashboard attempts to reconnect with increasing delays (exponential backoff)
2. **Given** a lost connection, **When** reconnection attempts exceed the maximum retries, **Then** the dashboard falls back to polling mode
3. **Given** a reconnection in progress, **When** the SSE endpoint becomes available again, **Then** the dashboard establishes a new connection and shows "Connected"

---

### User Story 3 - Configuration-Specific Streaming (Priority: P3)

Users with specific configurations need to receive updates relevant to their selected tickers and settings, not all system data.

**Why this priority**: While the global metrics stream (P1) provides dashboard-wide data, configuration-specific streaming enables targeted updates for individual user configurations, improving efficiency and user experience.

**Independent Test**: Can be tested by creating a configuration, connecting to its stream endpoint, and verifying only events relevant to that configuration are received.

**Acceptance Scenarios**:

1. **Given** an authenticated user with a configuration, **When** they request the configuration stream, **Then** they receive events specific to that configuration's tickers
2. **Given** an unauthenticated request to a configuration stream, **When** the request is processed, **Then** the server returns 401 Unauthorized
3. **Given** an invalid configuration ID, **When** a stream is requested, **Then** the server returns 404 Not Found

---

### User Story 4 - Local Development Testing (Priority: P4)

Developers need to test SSE functionality locally without deploying to preprod, enabling faster iteration and debugging.

**Why this priority**: Development efficiency is important but not critical for production functionality. This supports the development workflow rather than end-user features.

**Independent Test**: Can be tested by running the local development server and verifying SSE connections work identically to the deployed environment.

**Acceptance Scenarios**:

1. **Given** a local development environment, **When** a developer starts the server, **Then** SSE endpoints are available and functional
2. **Given** a local SSE connection, **When** test events are generated, **Then** the developer sees events in real-time in their browser/test client
3. **Given** unit tests for SSE, **When** tests run locally, **Then** all SSE behavior can be validated without network dependencies

---

### Edge Cases

- What happens when the server restarts while clients are connected? (Clients should detect disconnection and reconnect)
- How does the system handle clients that never disconnect? (Heartbeat mechanism keeps connections alive; stale connections timeout)
- What happens when a client reconnects with a Last-Event-ID that no longer exists? (Server starts from current state)
- How does the system behave under high connection counts? (Connection limits and graceful degradation)
- What happens when the event generator produces events faster than clients can consume? (Events are dropped or buffered based on configuration)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a global SSE endpoint at `/api/v2/stream` that broadcasts dashboard-wide metrics and events
- **FR-002**: System MUST provide a configuration-specific SSE endpoint at `/api/v2/configurations/{config_id}/stream` that broadcasts events for that configuration
- **FR-003**: SSE endpoints MUST return `Content-Type: text/event-stream` header for successful connections
- **FR-004**: System MUST send periodic heartbeat events to keep connections alive (recommended interval: 15-30 seconds)
- **FR-005**: System MUST support the `Last-Event-ID` header for reconnection resilience
- **FR-006**: Configuration-specific SSE endpoints MUST require authentication (X-User-ID header or Bearer token)
- **FR-007**: System MUST return 401 Unauthorized for unauthenticated requests to protected SSE endpoints
- **FR-008**: System MUST return 404 Not Found for invalid configuration IDs
- **FR-009**: System MUST emit `metrics` events containing aggregated dashboard metrics (total, sentiment counts, tag distribution)
- **FR-010**: System MUST emit `new_item` events when new analyzed items are available
- **FR-011**: System MUST include event IDs with each event for reconnection support
- **FR-012**: Unit tests MUST be able to test SSE behavior without establishing actual network connections
- **FR-013**: E2E tests MUST validate SSE endpoint availability and correct response headers
- **FR-014**: All existing E2E SSE tests (T095-T099) MUST pass without skipping due to 404
- **FR-015**: System MUST support at least 100 concurrent SSE connections and gracefully reject new connections when limit is reached
- **FR-016**: System MUST log SSE connection open and close events with client identifiers
- **FR-017**: System MUST emit metrics for active SSE connection count

### Key Entities

- **SSE Connection**: A persistent HTTP connection from a client that receives server-pushed events. Has a connection ID, client identifier, and optional Last-Event-ID for reconnection.
- **SSE Event**: A message pushed to connected clients. Contains event type (metrics, new_item, heartbeat), event ID, and JSON data payload.
- **Heartbeat**: A periodic keep-alive event sent to all connections to prevent timeout. Contains timestamp and connection status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dashboard shows "Connected" status within 5 seconds of page load in preprod environment
- **SC-002**: All E2E SSE tests (T095-T099) pass without skipping, achieving 100% pass rate
- **SC-003**: Preprod pipeline completes successfully without SSE-related failures
- **SC-004**: Dashboard receives at least one metrics update event within 60 seconds of establishing connection
- **SC-005**: After simulated disconnection, dashboard successfully reconnects within 30 seconds
- **SC-006**: Unit tests achieve 80% or higher code coverage for SSE endpoint implementation
- **SC-007**: Local development server supports SSE testing without external dependencies

## Clarifications

### Session 2025-12-02

- Q: What is the maximum concurrent SSE connections the system should support? → A: 100 concurrent connections (small team/department scale)
- Q: What level of SSE observability is required? → A: Standard (lifecycle + metrics) - Log connection open/close, emit connection count metrics

## Assumptions

- The `sse-starlette` library (already a project dependency) provides adequate SSE functionality for FastAPI
- Dashboard polling fallback (already implemented) serves as acceptable degradation if SSE fails
- Heartbeat interval of 15-30 seconds is sufficient to keep connections alive through typical proxy timeouts
- Lambda Function URLs support long-lived SSE connections (AWS documentation confirms streaming response support)
- Event history for `Last-Event-ID` reconnection can be limited to recent events (last 100 or 5 minutes) without impact

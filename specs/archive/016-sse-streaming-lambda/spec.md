# Feature Specification: SSE Streaming Lambda

**Feature Branch**: `016-sse-streaming-lambda`
**Created**: 2025-12-02
**Status**: Draft
**Input**: User description: "Deploy dedicated SSE streaming Lambda with AWS Lambda Web Adapter to coexist with Mangum-based dashboard Lambda"

## Clarifications

### Session 2025-12-02

- Q: How does SSE Lambda receive sentiment data to broadcast? → A: Poll DynamoDB on fixed interval (same method as existing dashboard Lambda)
- Q: What level of observability is required for SSE Lambda? → A: Enhanced (CloudWatch logs + X-Ray tracing + latency/throughput metrics)

## Problem Statement

The current architecture uses a single Lambda function with Mangum (ASGI adapter) to serve both REST API endpoints and SSE streaming endpoints. However, Mangum does not support Lambda's `RESPONSE_STREAM` invoke mode, creating a fundamental incompatibility:

- **BUFFERED mode**: Works with Mangum for REST APIs, but buffers SSE responses (breaking real-time streaming)
- **RESPONSE_STREAM mode**: Enables true streaming, but Mangum returns wrapped Lambda proxy responses that don't get unwrapped

This feature introduces a two-Lambda architecture where each Lambda is optimized for its use case.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Real-Time Dashboard Updates (Priority: P1)

Dashboard users want to receive real-time sentiment updates without page refresh. When new sentiment data is available, the dashboard should automatically display it within seconds.

**Why this priority**: Real-time updates are the core value proposition of SSE streaming. Without working SSE, users must manually refresh to see new data.

**Independent Test**: Can be fully tested by connecting to the SSE endpoint and verifying events stream in real-time when sentiment data changes.

**Acceptance Scenarios**:

1. **Given** a user has the dashboard open, **When** new sentiment data is ingested, **Then** the dashboard displays the update within 5 seconds without page refresh
2. **Given** a user connects to the SSE stream, **When** the connection is established, **Then** they receive a heartbeat event confirming the connection is alive
3. **Given** a user has an active SSE connection, **When** the server sends a sentiment_update event, **Then** the client receives the event with properly formatted data

---

### User Story 2 - REST API Reliability (Priority: P1)

Existing REST API consumers (frontend, mobile apps, third-party integrations) must continue to work without any changes. The introduction of SSE streaming must not break existing functionality.

**Why this priority**: Breaking existing APIs would cause immediate user-facing issues. This is a non-negotiable requirement.

**Independent Test**: Run the full E2E test suite against REST endpoints; all existing tests must pass without modification.

**Acceptance Scenarios**:

1. **Given** the two-Lambda architecture is deployed, **When** a client calls any REST API endpoint, **Then** the response format matches the existing API contract exactly
2. **Given** the dashboard Lambda uses BUFFERED mode, **When** any endpoint returns a response, **Then** the response body is properly unwrapped (not wrapped in Lambda proxy format)
3. **Given** all existing E2E tests, **When** run against the new deployment, **Then** 100% of tests pass without modification

---

### User Story 3 - Graceful Connection Handling (Priority: P2)

Users on unstable networks should experience graceful degradation. If the SSE connection drops, the client should automatically reconnect and resume receiving updates.

**Why this priority**: Network reliability varies; graceful handling improves user experience on mobile and poor connections.

**Independent Test**: Simulate network interruption and verify automatic reconnection with event resumption.

**Acceptance Scenarios**:

1. **Given** an active SSE connection, **When** the network connection drops, **Then** the client automatically attempts to reconnect with exponential backoff
2. **Given** a reconnecting client sends Last-Event-ID header, **When** the server receives the reconnection request, **Then** it resumes from the specified event (if within buffer window)
3. **Given** multiple reconnection attempts fail, **When** max retries is reached, **Then** the client falls back to polling mode and notifies the user

---

### User Story 4 - Configuration-Specific Streams (Priority: P3)

Users with saved configurations want to receive updates only for their configured tickers, not all global updates. This reduces noise and bandwidth.

**Why this priority**: Personalization improves relevance but is not essential for MVP. Global stream satisfies basic needs.

**Independent Test**: Connect to a config-specific stream and verify only events for configured tickers are received.

**Acceptance Scenarios**:

1. **Given** a user has a saved configuration with specific tickers, **When** they connect to the config stream endpoint, **Then** they only receive events for those tickers
2. **Given** a user's configuration changes, **When** the change is saved, **Then** the SSE stream immediately reflects the new ticker list

---

### Edge Cases

- What happens when the SSE Lambda reaches its 15-minute execution limit? Client must reconnect seamlessly.
- How does the system handle 100+ concurrent SSE connections? Connection limits must be enforced with clear error messages.
- What if the SSE Lambda is cold-started? First connection may take 2-3 seconds longer; heartbeat confirms readiness.
- What happens if sentiment data ingestion fails? SSE continues sending heartbeats; no false-positive updates sent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST deploy a dedicated SSE Lambda function separate from the dashboard REST Lambda
- **FR-002**: SSE Lambda MUST use RESPONSE_STREAM invoke mode for true streaming capability
- **FR-003**: Dashboard Lambda MUST continue using BUFFERED invoke mode for REST APIs
- **FR-004**: SSE Lambda MUST expose a global stream endpoint at `/api/v2/stream` accessible via Function URL
- **FR-005**: SSE Lambda MUST expose a configuration-specific stream endpoint at `/api/v2/configurations/{id}/stream`
- **FR-006**: SSE Lambda MUST send heartbeat events every 30 seconds to keep connections alive
- **FR-007**: SSE Lambda MUST support Last-Event-ID header for reconnection resumption
- **FR-008**: SSE Lambda MUST enforce a maximum of 100 concurrent connections per Lambda instance
- **FR-009**: SSE Lambda MUST return 503 Service Unavailable when connection limit is reached
- **FR-010**: All SSE events MUST include event type, unique event ID, and JSON-formatted data payload
- **FR-011**: System MUST expose SSE Lambda via a dedicated Function URL (separate from dashboard)
- **FR-012**: Frontend MUST be updated to use the SSE Function URL for streaming and dashboard URL for REST
- **FR-013**: SSE Lambda MUST require valid authentication (X-User-ID header) for config-specific streams
- **FR-014**: Global stream MUST NOT require authentication (public metrics)
- **FR-015**: SSE Lambda MUST poll DynamoDB at a configurable interval (default: 5 seconds) to detect new sentiment data
- **FR-016**: SSE Lambda MUST enable X-Ray tracing for distributed request tracing
- **FR-017**: SSE Lambda MUST emit custom CloudWatch metrics for connection count, event throughput, and latency
- **FR-018**: SSE Lambda MUST log connection lifecycle events (connect, disconnect, errors) at INFO level

### Key Entities

- **SSE Connection**: Represents an active streaming connection; tracks connection ID, user ID (if authenticated), connected ticker filters, last event ID sent
- **SSE Event**: A single event in the stream; contains event type (metrics/sentiment_update/heartbeat), unique ID, timestamp, and data payload
- **Connection Pool**: Per-Lambda-instance tracking of active connections; enforces limits and manages lifecycle

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive real-time updates within 5 seconds of data ingestion (end-to-end latency)
- **SC-002**: System supports 100 concurrent SSE connections per Lambda instance without degradation
- **SC-003**: 100% of existing REST API E2E tests pass without modification after deployment
- **SC-004**: SSE connection establishment completes in under 3 seconds (including cold start)
- **SC-005**: Reconnection after network interruption succeeds within 10 seconds (with backoff)
- **SC-006**: SSE Lambda cold start time is under 2 seconds
- **SC-007**: Zero breaking changes to existing API contracts (all endpoints return identical response formats)

## Assumptions

- Docker-based Lambda deployment is acceptable for the SSE Lambda (may be required for certain adapters)
- The existing frontend already has SSE reconnection logic with exponential backoff
- CloudFront is not required for SSE routing in MVP; clients can connect directly to Function URLs
- The 15-minute Lambda timeout is acceptable for SSE connections (clients handle reconnection)

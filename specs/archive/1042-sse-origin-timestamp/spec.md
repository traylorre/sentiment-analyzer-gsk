# Feature Specification: SSE Origin Timestamp for Latency Measurement

**Feature Branch**: `1042-sse-origin-timestamp`
**Created**: 2025-12-23
**Status**: Draft
**Input**: Add origin_timestamp field to SSE events for end-to-end latency measurement

## Context

Feature 1019 (Validate Live Update Latency) defines E2E tests that measure the latency from SSE event origin to client receipt. These tests expect an `origin_timestamp` field in SSE event data to calculate latency. However, the current SSE implementation uses a `timestamp` field instead, causing test failures because the client-side JavaScript cannot find the expected field name.

**Problem Evidence**:
- `tests/e2e/test_live_update_latency.py` line 163: `if (data.origin_timestamp)`
- `src/lambdas/dashboard/sse.py` line 80: `timestamp: datetime = Field(...)`
- Pipeline failure: 3 tests failing with "No SSE events received with latency metrics"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard Latency Monitoring (Priority: P1)

As a dashboard user, I expect real-time updates to arrive within a measurable time window so that I can trust the data freshness displayed on my screen.

**Why this priority**: This is the core user value - users need confidence that displayed data is current, not stale. The latency measurement validates this promise.

**Independent Test**: Can be fully tested by connecting to the SSE stream, receiving events, and verifying each event contains the `origin_timestamp` field with a valid ISO8601 timestamp.

**Acceptance Scenarios**:

1. **Given** a browser connected to the SSE stream, **When** a heartbeat event is received, **Then** the event data contains an `origin_timestamp` field in ISO8601 format
2. **Given** a browser connected to the SSE stream, **When** a metrics event is received, **Then** the event data contains an `origin_timestamp` field in ISO8601 format
3. **Given** an `origin_timestamp` in the event, **When** the client calculates latency as (receive_time - origin_time), **Then** the result is a positive millisecond value representing actual network latency

---

### User Story 2 - SLA Validation (Priority: P2)

As a platform operator, I need to validate that live updates meet our p95 < 3 second SLA requirement so that I can ensure service quality.

**Why this priority**: SLA validation depends on having measurable latency data. Without origin_timestamp, we cannot validate the SLA.

**Independent Test**: Can be tested by collecting 50+ SSE events with origin_timestamp, calculating p95 latency, and asserting < 3000ms.

**Acceptance Scenarios**:

1. **Given** 50+ SSE events with `origin_timestamp`, **When** p95 latency is calculated, **Then** the value is less than 3000 milliseconds
2. **Given** SSE events with `origin_timestamp`, **When** client-side metrics are exposed via `window.lastLatencyMetrics`, **Then** the object includes latency_ms, event_type, origin_timestamp, and receive_timestamp fields

---

### Edge Cases

- **Clock skew**: What happens when server and client clocks are not synchronized? The latency may appear negative. System should detect and flag clock skew events.
- **Missing field**: What if origin_timestamp parsing fails? Client should gracefully skip latency calculation rather than crash.
- **Timezone handling**: ISO8601 timestamps must include timezone information (UTC preferred) to prevent incorrect latency calculations.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SSE heartbeat events MUST include an `origin_timestamp` field containing the server's current time when the event was generated
- **FR-002**: SSE metrics events MUST include an `origin_timestamp` field containing the server's current time when the event was generated
- **FR-003**: The `origin_timestamp` field MUST be in ISO8601 format with timezone indicator (e.g., `2025-12-23T12:00:00Z` or `2025-12-23T12:00:00+00:00`)
- **FR-004**: The `origin_timestamp` field name MUST match exactly what the client-side latency tracking code expects (lowercase with underscore)
- **FR-005**: Existing `timestamp` field MAY be retained for backward compatibility, but `origin_timestamp` takes precedence for latency measurement

### Key Entities

- **SSE Event**: Real-time event sent from server to client containing type (heartbeat/metrics), data payload, and origin_timestamp
- **Latency Metrics**: Client-side calculated metrics including latency_ms, event_type, origin_timestamp, receive_timestamp, and is_clock_skew flag

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 3 tests in `test_live_update_latency.py` pass (test_live_update_p95_under_3_seconds, test_sse_events_include_origin_timestamp, test_latency_metrics_exposed_to_window)
- **SC-002**: Pipeline passes with no integration test failures related to SSE latency
- **SC-003**: p95 end-to-end latency remains under 3 seconds (existing SLA maintained)
- **SC-004**: No breaking changes to existing SSE consumers (timestamp field preserved if used elsewhere)

## Assumptions

- The client-side latency tracking JavaScript is correct and only needs the field name to match
- Server and client clocks are reasonably synchronized (within seconds, not minutes)
- Renaming `timestamp` to `origin_timestamp` or adding `origin_timestamp` as an alias will not break existing functionality

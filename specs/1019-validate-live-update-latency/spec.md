# Feature Specification: Validate Live Update Latency

**Feature Branch**: `1019-validate-live-update-latency`
**Created**: 2024-12-22
**Status**: Draft
**Input**: User description: "T065: Validate <3s live update latency (SC-003) with CloudWatch metrics. Measure time from sentiment analysis completion to dashboard display. Add timestamp to SSE events, calculate client-side latency. Create CloudWatch dashboard or metric alarm for p95 latency. Document end-to-end latency breakdown in docs/performance-validation.md."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate End-to-End Latency Target (Priority: P1)

As a platform operator, I need to verify that sentiment updates reach the dashboard within 3 seconds of analysis completion, so that I can ensure the system meets its performance SLA and users see timely data.

**Why this priority**: This is the core validation - proving SC-003 is met. Without this measurement, we cannot claim the system meets its latency requirements.

**Independent Test**: Trigger a sentiment analysis completion event, measure time until dashboard receives SSE event, verify p95 is under 3 seconds.

**Acceptance Scenarios**:

1. **Given** a sentiment analysis job completes, **When** the SSE event reaches the dashboard, **Then** the total elapsed time is under 3 seconds for 95% of events
2. **Given** multiple sentiment updates in rapid succession, **When** measuring latency for each, **Then** p95 latency remains under 3 seconds even under load
3. **Given** the CloudWatch metrics are collecting latency data, **When** querying p95 latency, **Then** the value matches the validated target

---

### User Story 2 - Instrument SSE Events with Timestamps (Priority: P1)

As a developer, I need SSE events to include the timestamp when sentiment analysis completed (origin timestamp), so that clients can calculate end-to-end latency accurately.

**Why this priority**: Without origin timestamps, client-side latency calculation is impossible. This is a prerequisite for US1.

**Independent Test**: Connect to SSE stream, receive an event, verify the event payload includes `origin_timestamp` field with ISO8601 format.

**Acceptance Scenarios**:

1. **Given** a sentiment bucket update event, **When** the SSE event is serialized, **Then** it includes an `origin_timestamp` field representing when the data was generated
2. **Given** a heartbeat event, **When** the SSE event is serialized, **Then** it includes a `server_timestamp` for latency monitoring
3. **Given** an SSE event with `origin_timestamp`, **When** client receives it, **Then** client can calculate `receive_time - origin_timestamp` as end-to-end latency

---

### User Story 3 - CloudWatch Latency Metrics (Priority: P2)

As an operations engineer, I need latency metrics published to CloudWatch so that I can monitor system performance over time, set up alarms, and create dashboards.

**Why this priority**: Important for ongoing monitoring but can be added after basic latency validation works.

**Independent Test**: Trigger sentiment updates, query CloudWatch Logs Insights for latency metrics, verify p95 calculation is accurate.

**Acceptance Scenarios**:

1. **Given** SSE events are being sent, **When** the streaming Lambda logs latency, **Then** CloudWatch Logs contain structured latency metrics (JSON format)
2. **Given** latency logs are available, **When** running CloudWatch Logs Insights query, **Then** p50, p90, p95, p99 percentiles are calculated correctly
3. **Given** a CloudWatch alarm is configured, **When** p95 latency exceeds 3 seconds, **Then** an alert is triggered

---

### User Story 4 - Document Latency Breakdown (Priority: P3)

As a new team member, I need documentation explaining how latency is measured and what contributes to end-to-end latency, so that I can troubleshoot performance issues.

**Why this priority**: Documentation enhances maintainability but doesn't block validation.

**Independent Test**: Follow docs/performance-validation.md instructions to run latency validation and understand each latency component.

**Acceptance Scenarios**:

1. **Given** the documentation exists, **When** reading the latency breakdown section, **Then** all latency components are explained (analysis time, SNS/SQS, Lambda cold start, SSE delivery)
2. **Given** the documentation explains how to run tests, **When** following the instructions, **Then** latency validation tests run successfully
3. **Given** the documentation includes troubleshooting, **When** encountering high latency, **Then** the guide helps identify which component is slow

---

### Edge Cases

- What happens when CloudWatch is unavailable? (Latency logging should not block SSE event delivery)
- How does latency behave during Lambda cold starts? (First event may exceed target; measure warm invocation separately)
- What if client clock is significantly skewed? (Document that NTP sync is assumed; provide server-side validation alternative)
- How to handle network latency variations between client and server? (Measure server-side latency separately from client-side)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SSE bucket update events MUST include an `origin_timestamp` field indicating when the sentiment data was generated
- **FR-002**: SSE heartbeat events MUST include a `server_timestamp` field for client clock synchronization reference
- **FR-003**: Streaming Lambda MUST log latency metrics in structured JSON format to CloudWatch Logs
- **FR-004**: Latency metrics MUST include: event_type, origin_timestamp, send_timestamp, and calculated latency_ms
- **FR-005**: A CloudWatch Logs Insights query MUST be provided to calculate p50, p90, p95, p99 latency percentiles
- **FR-006**: Documentation MUST explain the end-to-end latency breakdown with all contributing components
- **FR-007**: E2E test MUST validate that p95 latency is under 3 seconds (SC-003)
- **FR-008**: Client-side JavaScript MUST calculate and optionally log receive latency using `origin_timestamp`

### Key Entities

- **LatencyMetric**: Represents a single latency measurement with origin_timestamp, send_timestamp, receive_timestamp, event_type, latency_ms
- **SSEEvent**: Existing event structure extended with origin_timestamp and server_timestamp fields
- **CloudWatch Log Entry**: JSON-structured log entry containing latency metrics for Logs Insights queries

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: p95 end-to-end latency (analysis completion to dashboard display) is under 3 seconds
- **SC-002**: Latency metrics are available in CloudWatch Logs within 1 minute of event delivery
- **SC-003**: CloudWatch Logs Insights query returns accurate percentile calculations for at least 24 hours of data
- **SC-004**: Documentation enables new team members to run latency validation within 15 minutes of reading

## Assumptions

- NTP time synchronization is in place on all systems (client, Lambda, origin)
- CloudWatch Logs retention is set to at least 7 days for metrics analysis
- SSE streaming Lambda is already deployed and functional
- Sentiment analysis completion triggers SNS/SQS notifications that reach the streaming Lambda
- Standard web application latency expectations apply (sub-second server processing)

## Canonical Sources

- [CS-001]: [MDN Performance API](https://developer.mozilla.org/en-US/docs/Web/API/Performance) - Client timing
- [CS-002]: [CloudWatch Logs Insights Query Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)
- [CS-003]: [SSE Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [CS-004]: Parent spec `specs/1009-realtime-multi-resolution/spec.md` SC-003 defines the 3s target

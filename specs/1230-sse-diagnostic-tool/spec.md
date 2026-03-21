# Feature Specification: SSE Diagnostic Tool

**Feature Branch**: `1230-sse-diagnostic-tool`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "Lightweight tool to connect to SSE stream and report events. Curl can't test SSE properly."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect and Display Live Events (Priority: P1)

A developer or on-call engineer wants to verify the SSE stream is working by connecting to it and seeing events as they arrive in real time. They run the diagnostic tool, point it at the stream URL, and immediately see parsed, formatted events in their terminal — heartbeats, sentiment updates, and partial bucket updates — with timestamps and event types clearly labeled.

**Why this priority**: This is the core value proposition. Without a way to see live SSE events in a readable format, debugging SSE issues requires browser DevTools or reading raw curl output with embedded JSON. A formatted terminal view is the fastest path to "is the stream working?"

**Independent Test**: Can be fully tested by running the tool against the local dev server or preprod SSE endpoint and verifying that events appear within the heartbeat interval (30 seconds).

**Acceptance Scenarios**:

1. **Given** a running SSE stream, **When** the user runs the tool with the stream URL, **Then** the tool connects and displays each event with its type, timestamp, and formatted payload.
2. **Given** a stream emitting heartbeat events every 30 seconds, **When** the tool is connected, **Then** the user sees heartbeat events appearing at the expected interval.
3. **Given** a stream emitting sentiment_update events, **When** the tool is connected, **Then** each event shows the ticker, score, label, and source in a human-readable format.

---

### User Story 2 - Filter Events by Type and Ticker (Priority: P2)

A developer debugging a specific issue wants to see only certain event types (e.g., only `sentiment_update`) or only events for a specific ticker (e.g., `AAPL`). They pass filter options to the tool and the output shows only matching events, reducing noise.

**Why this priority**: Filtering is essential for targeted debugging. Without it, the tool floods the terminal with heartbeats and metrics when the developer only cares about sentiment updates for one ticker.

**Independent Test**: Can be tested by running the tool with `--event-type sentiment_update --ticker AAPL` and verifying that only matching events are displayed.

**Acceptance Scenarios**:

1. **Given** a stream emitting multiple event types, **When** the user filters by `sentiment_update`, **Then** only sentiment_update events are displayed (heartbeats and metrics are hidden).
2. **Given** a stream emitting events for multiple tickers, **When** the user filters by `AAPL`, **Then** only events containing AAPL data are displayed.
3. **Given** the user specifies both event type and ticker filters, **When** events arrive, **Then** only events matching both criteria are shown.

---

### User Story 3 - Connection Health Summary (Priority: P3)

After disconnecting (Ctrl+C), the tool prints a summary of the session: total events received, events per type, connection duration, any reconnection attempts, and whether the stream appears healthy based on heartbeat regularity.

**Why this priority**: The summary turns a debugging session into actionable data. Instead of scrolling through output, the engineer gets a quick health report.

**Independent Test**: Can be tested by connecting for 2+ minutes, pressing Ctrl+C, and verifying the summary includes event counts and duration.

**Acceptance Scenarios**:

1. **Given** a completed diagnostic session, **When** the user disconnects, **Then** a summary is printed showing total events, count per event type, and session duration.
2. **Given** heartbeats arriving irregularly (gap > 2x expected interval), **When** the summary is printed, **Then** it flags "heartbeat gap detected" as a warning.

---

### Edge Cases

- What happens when the SSE endpoint is unreachable? The tool prints a clear connection error with the URL attempted and suggests checking the endpoint is running.
- What happens when the connection drops mid-stream? The tool attempts automatic reconnection (up to 3 retries with backoff) and reports each attempt.
- What happens when the stream returns 401 (unauthorized)? The tool prints "Authentication required" and suggests providing a token.
- What happens when the stream returns 503 (connection limit)? The tool prints the Retry-After value and waits before retrying.
- What happens when no events arrive for an extended period? The tool shows a "no events received" warning after 60 seconds of silence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST connect to an SSE endpoint and display each received event in real time, formatted for human readability.
- **FR-002**: Each displayed event MUST show: event type, timestamp, and a formatted summary of the payload (not raw JSON).
- **FR-003**: The tool MUST support filtering by event type (heartbeat, metrics, sentiment_update, partial_bucket, deadline).
- **FR-004**: The tool MUST support filtering by ticker symbol to show only events related to specified tickers.
- **FR-005**: The tool MUST accept the SSE endpoint URL as a required argument.
- **FR-006**: The tool MUST support authentication for config-specific streams via three methods: bearer token (`--token`), user ID (`--user-id`), or query parameter (appended automatically). The global stream requires no authentication.
- **FR-007**: The tool MUST handle connection failures gracefully with clear error messages and automatic retry (up to 3 attempts with exponential backoff).
- **FR-008**: On disconnect (Ctrl+C), the tool MUST print a session summary with event counts per type, total duration, and health warnings.
- **FR-009**: The tool MUST support a `--json` output mode that prints each event as a single JSON line (for piping to other tools like jq).
- **FR-010**: The tool MUST respect the `Last-Event-ID` protocol for resuming streams after reconnection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can connect to the SSE stream and see the first event within 35 seconds (heartbeat interval + 5s connection overhead).
- **SC-002**: The tool can be started with a single command (URL as argument) with no configuration file required.
- **SC-003**: Filtered output shows only matching events with 100% accuracy (no false positives or missed matches).
- **SC-004**: The session summary correctly counts all received events by type with zero discrepancy.
- **SC-005**: Connection errors produce actionable messages that identify the specific failure (auth, network, limit) in 100% of cases.

## Assumptions

- The SSE endpoint is already deployed and accessible (preprod or local dev server).
- The tool is a developer utility run from the command line, not a production service.
- Authentication tokens can be obtained separately (via anonymous auth endpoint or existing session).
- The SSE event format follows the existing protocol: `event: {type}\ndata: {json}\n\n`.

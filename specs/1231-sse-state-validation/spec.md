# Feature Specification: SSE In-Memory State Validation

**Feature Branch**: `1231-sse-state-validation`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "Resolution mismatch during partial failure — if the SSE Lambda process is reused after a fault injection that corrupts in-memory state, module-level singletons could be stale. Add per-connection state validation and a health check for in-memory consistency."

## Adversarial Review Finding

The original concern — `valid_resolutions` being cached at module level — is **already mitigated**. As of Feature 1229, `valid_resolutions` is computed as `{r.value for r in Resolution}` inside `_handle_global_stream()`, meaning it is derived fresh on every request. No module-level caching of resolution values exists.

However, three real risks remain for Lambda process reuse after fault injection:

1. **Connection Manager singleton** (`connection_manager` at module level in `connection.py`) — the `_connections` dict could reference stale/phantom connections after an unclean restart. If a previous invocation's `finally` block never ran (e.g., Lambda freeze during streaming), connections leak and the pool appears full.
2. **Stream Generator singleton** (`_stream_generator` lazy global in `stream.py`) — contains `EventBuffer`, `Debouncer`, and `CacheMetricsLogger` instances that accumulate state across invocations. A corrupted `_event_buffer` could replay garbage events on reconnection. A corrupted `_debouncer` could suppress legitimate event emissions.
3. **No health check** — there is no endpoint or per-connection check that validates whether in-memory state is internally consistent before serving a new connection.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Per-Connection State Consistency Validation (Priority: P1)

When a new SSE connection is established (global or config-specific), the handler validates that all module-level singletons are in a consistent state before streaming begins. If any invariant is violated (e.g., connection pool count is negative, event buffer contains entries older than Lambda uptime, debouncer timestamps are in the future), the handler logs a warning, resets the corrupted state, and continues serving the connection with clean state rather than propagating corruption.

**Why this priority**: This is the core defense against stale state propagation. Without it, a single corrupted invocation can silently serve wrong data to all subsequent connections for the lifetime of the Lambda instance.

**Independent Test**: Unit test with a deliberately corrupted `ConnectionManager` (negative count, phantom connections) and `EventBuffer` (events with timestamps before Lambda start). Verify the validation detects corruption, resets state, and the connection proceeds normally.

**Acceptance Scenarios**:

1. **Given** a Lambda instance with phantom connections in the connection pool (connections that were never properly released), **When** a new connection is established, **Then** the handler detects phantom connections older than a configurable threshold (default 15 minutes), removes them, and logs a warning.
2. **Given** an `EventBuffer` containing events with IDs that cannot be parsed or timestamps from before the Lambda instance started, **When** a client reconnects with `Last-Event-ID`, **Then** the corrupted buffer entries are purged before replay.
3. **Given** a `Debouncer` with last-emit timestamps in the future (clock skew from corrupted state), **When** a bucket update arrives, **Then** the debouncer resets the invalid entry and allows the emission.

---

### User Story 2 - Health Endpoint Reports State Consistency (Priority: P2)

The existing `/api/v2/stream/status` endpoint is extended to include an `integrity` section that reports the consistency of all module-level singletons. This allows monitoring systems and the SSE diagnostic tool (Feature 1230) to detect state corruption without establishing a streaming connection.

**Why this priority**: Observability is essential for chaos engineering. Without a health signal, operators cannot distinguish between "stream is slow" and "stream state is corrupted" — they look identical from the client side.

**Independent Test**: Call `/api/v2/stream/status` after injecting corrupted state into `ConnectionManager` and `EventBuffer`. Verify the response includes `integrity.status: "degraded"` with specific violation details.

**Acceptance Scenarios**:

1. **Given** a healthy Lambda instance with no state corruption, **When** `/api/v2/stream/status` is called, **Then** the response includes `integrity: { status: "healthy", checks: { connection_pool: "ok", event_buffer: "ok", debouncer: "ok" } }`.
2. **Given** phantom connections exist in the pool, **When** `/api/v2/stream/status` is called, **Then** the response includes `integrity: { status: "degraded", checks: { connection_pool: "phantom_connections_detected", count: N } }`.
3. **Given** the event buffer contains unparseable entries, **When** `/api/v2/stream/status` is called, **Then** `integrity.checks.event_buffer` reports `"corrupted_entries_detected"` with count.

---

### Edge Cases

- What happens when all connections are phantom (pool full, zero real clients)? The validation resets the entire pool, emits a `connection_pool_reset` CloudWatch metric, and allows the new connection.
- What happens when the Lambda is frozen and resumed by AWS? The `_start_time` in `ConnectionManager` and `SSEStreamGenerator` may be stale. The health check compares `_start_time` against the current invocation time to detect freeze/thaw gaps.
- What happens when state corruption is detected mid-stream (not just at connection time)? The heartbeat cycle includes a lightweight invariant check. If corruption is detected mid-stream, the connection emits a `state_reset` event and resets affected singletons.
- What happens when `_stream_generator` is `None` (cold start)? No validation needed — `get_stream_generator()` creates fresh state. Validation only applies when state already exists.
- What happens when the Debouncer has thousands of stale keys from a long-running instance? The health check trims keys older than 2x the heartbeat interval.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: On each new SSE connection, the handler MUST validate connection pool integrity before acquiring a connection slot. Phantom connections (connected_at older than 15 minutes with no recent heartbeat) MUST be purged.
- **FR-002**: On each new SSE connection, the handler MUST validate the event buffer integrity. Buffer entries that cannot be parsed or have event IDs inconsistent with the current Lambda instance MUST be purged.
- **FR-003**: The Debouncer MUST validate timestamps on each `should_emit()` call. Entries with last-emit timestamps in the future (relative to `time.time()`) MUST be reset.
- **FR-004**: The `/api/v2/stream/status` endpoint MUST include an `integrity` field in its response reporting the state of connection pool, event buffer, and debouncer.
- **FR-005**: State validation MUST complete in under 5ms to avoid impacting connection establishment latency. If validation exceeds 5ms, it MUST be logged as a warning and skipped rather than blocking the connection.
- **FR-006**: All state resets triggered by validation MUST emit a CloudWatch metric (`StateValidation/{component}`) for monitoring and alerting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After fault injection that leaves phantom connections, the next real connection is served within the normal connection time (no pool-full rejection due to phantom connections).
- **SC-002**: The `/api/v2/stream/status` endpoint correctly reports `degraded` state when any singleton has corruption, verified by integration test.
- **SC-003**: State validation adds less than 5ms overhead to connection establishment, measured via CloudWatch `StateValidation/DurationMs` metric.
- **SC-004**: Zero false positives — healthy state is never flagged as corrupted during normal operation, verified by running the health check every heartbeat cycle for 1 hour without false alarms.

## Assumptions

- The SSE Lambda uses Lambda Function URL with RESPONSE_STREAM invoke mode (custom runtime with process reuse).
- Module-level singletons (`connection_manager`, `_stream_generator`) persist across invocations within the same Lambda execution environment.
- The `Resolution` enum is stable and does not change at runtime — the original `valid_resolutions` concern is already mitigated.
- Phantom connection threshold (15 minutes) is appropriate because Lambda timeout is 15 minutes maximum.

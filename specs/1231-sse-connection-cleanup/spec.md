# Feature Specification: SSE Connection Leak Cleanup

**Feature Branch**: `1231-sse-connection-cleanup`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "SSE connection leak under chaos -- If the SSE Lambda is killed mid-stream (force-killed, not graceful shutdown), the connection manager should decrement the connection count. But if the Lambda process is force-killed, the deadline event may not fire and the count may stay elevated, eventually hitting the 100-connection limit."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stale Connections Auto-Expire (Priority: P1)

An SSE Lambda instance is serving 40 active connections when a force-kill (SIGKILL) or OOM kills the process. The Lambda runtime spins up a new instance with the same in-memory `ConnectionManager`. The global `connection_manager` still shows 40 active connections, but none of them have sent a heartbeat in over 60 seconds. New connection attempts are rejected at 100, even though no real clients are connected. With this fix, connections that haven't had activity in 2x the heartbeat interval (default 60s) are automatically marked as stale and eligible for eviction, so the connection pool self-heals.

**Why this priority**: This is the core fix. Without TTL-based expiry, a single force-kill event permanently reduces capacity by the number of orphaned connections. Under repeated chaos, the pool eventually reaches 100 and all new clients are rejected with 503.

**Independent Test**: Create a `ConnectionManager`, acquire connections without updating their `last_activity`, advance time past the TTL, and verify `count` reflects only active connections after a sweep.

**Acceptance Scenarios**:

1. **Given** a connection with no activity for longer than 2x the heartbeat interval, **When** a cleanup sweep runs, **Then** the connection is removed from the pool and the count decrements.
2. **Given** a connection that has received a heartbeat within the TTL window, **When** a cleanup sweep runs, **Then** the connection is retained.
3. **Given** the heartbeat interval is changed via `SSE_HEARTBEAT_INTERVAL`, **When** the TTL is computed, **Then** it equals 2x the current heartbeat interval (not a hardcoded value).

---

### User Story 2 - New Connections Trigger Cleanup (Priority: P2)

When a new client connects (calls `acquire()`), the connection manager first sweeps stale connections before checking the capacity limit. This means that after a force-kill, the very first new connection attempt reclaims orphaned slots, preventing unnecessary 503 errors without requiring a background thread or timer.

**Why this priority**: The TTL mechanism from US1 defines *what* is stale, but without a trigger to actually remove stale entries, the pool still appears full until something invokes the sweep. Triggering on `acquire()` is zero-cost (no background threads) and guarantees cleanup happens exactly when it matters -- when a new client needs a slot.

**Independent Test**: Fill a `ConnectionManager` to capacity with stale connections, then call `acquire()` for a new connection. The stale entries should be swept and the new connection should succeed.

**Acceptance Scenarios**:

1. **Given** a connection manager at capacity (100/100) with all connections stale, **When** a new `acquire()` is called, **Then** stale connections are swept first and the new connection succeeds.
2. **Given** a connection manager at capacity with 50 active and 50 stale, **When** a new `acquire()` is called, **Then** only the 50 stale connections are removed, the 50 active remain, and the new connection succeeds (total: 51).
3. **Given** a connection manager with no stale connections at capacity, **When** a new `acquire()` is called, **Then** no connections are swept and `acquire()` returns None (503).

---

### User Story 3 - Status Endpoint Reports Stale Connections (Priority: P3)

The `/api/v2/stream/status` endpoint adds two new fields to its response: `stale_connections` (count of connections past TTL) and `connection_ttl_seconds` (the configured TTL). This gives on-call engineers visibility into whether the pool is healthy or contaminated by orphaned connections.

**Why this priority**: Observability is essential for validating the fix works in production. Without stale connection visibility, an engineer seeing "connections: 95, available: 5" can't distinguish between 95 real clients and 90 stale + 5 real.

**Independent Test**: Create a `ConnectionManager` with a mix of active and stale connections, call `get_status()`, and verify the response includes accurate `stale_connections` count.

**Acceptance Scenarios**:

1. **Given** a connection manager with 5 active and 10 stale connections, **When** `/api/v2/stream/status` is called, **Then** the response includes `connections: 15`, `stale_connections: 10`, `connection_ttl_seconds: 60`.
2. **Given** a connection manager with 0 stale connections, **When** `/api/v2/stream/status` is called, **Then** `stale_connections` is 0.
3. **Given** a custom heartbeat interval of 15 seconds, **When** `/api/v2/stream/status` is called, **Then** `connection_ttl_seconds` is 30 (2x heartbeat interval).

---

### Edge Cases

- What happens when the Lambda is force-killed and a new invocation starts on the SAME warm container? The in-memory `connection_manager` global retains the orphaned entries. The next `acquire()` call sweeps them because their `last_activity` hasn't been updated. This is the primary scenario.
- What happens when ALL connections are stale and the pool is full? The sweep on `acquire()` removes all 100 stale entries, then the new connection succeeds. The pool goes from 100 to 1.
- What happens when a heartbeat is delayed but the connection is still alive? The TTL of 2x heartbeat interval (default 60s) provides a safety margin. A heartbeat that's 5 seconds late (35s instead of 30s) won't trigger false expiry. Only connections silent for 60+ seconds are swept.
- What happens when `last_activity` is updated by non-heartbeat events? Any event dispatch (sentiment_update, partial_bucket, metrics) updates `last_activity`. Only truly inactive connections are evicted.
- What happens with concurrent `acquire()` calls triggering simultaneous sweeps? The sweep runs under the existing `_lock`, so concurrent calls are serialized. No double-sweep or race condition.
- What happens if the connection TTL is set very low (e.g., 1 second)? The TTL is derived from the heartbeat interval (2x), which has a minimum of 1 second. A 1-second heartbeat with 2-second TTL is aggressive but correct -- connections must send events at least every 2 seconds or be swept.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `SSEConnection` dataclass MUST include a `last_activity` field (datetime, UTC) that is set on creation and updated on every event dispatch (heartbeat, sentiment_update, partial_bucket, metrics).
- **FR-002**: The `ConnectionManager` MUST accept a `connection_ttl_seconds` parameter (default: 2x `SSE_HEARTBEAT_INTERVAL`, falling back to 60 seconds).
- **FR-003**: The `ConnectionManager` MUST provide a `sweep_stale()` method that removes connections whose `last_activity` is older than `connection_ttl_seconds` from now, operating under the existing `_lock`.
- **FR-004**: The `ConnectionManager.acquire()` method MUST call `sweep_stale()` before checking the capacity limit, so that stale connections are reclaimed before rejecting new clients.
- **FR-005**: The `ConnectionManager.update_last_event_id()` method MUST also update `last_activity` on the connection, since it is called on every event dispatch.
- **FR-006**: The `ConnectionManager.get_status()` method MUST include `stale_connections` (int) and `connection_ttl_seconds` (int) in its return dict.
- **FR-007**: The `StreamStatus` pydantic model MUST include `stale_connections` (int) and `connection_ttl_seconds` (int) fields.
- **FR-008**: The `sweep_stale()` method MUST log each connection it removes, including the `connection_id` and how long it has been inactive, at WARNING level.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a simulated force-kill (connections with `last_activity` > TTL), the next `acquire()` call succeeds instead of returning None.
- **SC-002**: The `/api/v2/stream/status` endpoint reports accurate `stale_connections` counts (verified by unit test).
- **SC-003**: Active connections (with recent `last_activity`) are never swept -- zero false positives in unit tests.
- **SC-004**: Thread-safety is preserved -- concurrent acquire/release/sweep operations produce consistent counts (existing thread-safety test pattern extended).
- **SC-005**: The connection pool self-heals from 100/100 stale to accepting new connections within a single `acquire()` call (no delay, no background process).

## Assumptions

- Force-kill scenarios primarily affect warm Lambda containers where the global `connection_manager` instance persists across invocations.
- The heartbeat interval (default 30s) is a reliable proxy for connection liveness -- a connection that hasn't participated in any event dispatch for 2x the interval is presumed dead.
- The existing `_lock` (threading.Lock) is sufficient for thread-safety -- no need for async-safe locks since the ConnectionManager runs in the sync handler context.
- This fix does not address Lambda cold start scenarios (new container = fresh ConnectionManager with zero connections).

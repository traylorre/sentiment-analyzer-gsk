# Research: SSE Connection Leak Cleanup

**Date**: 2026-03-21

## Decision 1: Connection Liveness Tracking

**Decision**: Add `last_activity` field to `SSEConnection`, updated on every event dispatch via `update_last_event_id()`.

**Rationale**: The existing `update_last_event_id()` is already called on every heartbeat and event dispatch in `stream.py` (lines 397, 431, 444, 501). Piggybacking on this call is zero-cost and requires no changes to the streaming logic -- only the `update_last_event_id()` method gains a single additional line.

**Alternatives considered**:
- Separate `touch()` method called from stream.py -- more explicit but requires changes in 8+ locations in stream.py instead of 1 change in connection.py
- Background heartbeat thread in ConnectionManager -- heavyweight, introduces complexity, and doesn't solve the root cause (force-kill prevents cleanup regardless of how it's triggered)
- External health check (e.g., DynamoDB TTL) -- adds dependency and latency; in-memory is sufficient since the ConnectionManager is per-Lambda-instance

## Decision 2: Sweep Trigger Strategy

**Decision**: Sweep stale connections at the beginning of `acquire()`, before capacity check.

**Rationale**: This is the simplest approach with zero infrastructure:
1. No background thread (which would itself be killed on SIGKILL)
2. No timer/cron (Lambda doesn't have persistent timers)
3. Cleanup happens exactly when needed -- when a new client wants a slot
4. Under the existing `_lock` -- no new synchronization needed

The sweep runs in O(n) where n is the number of connections (max 100). At 100 connections, this is a trivial dictionary scan.

**Alternatives considered**:
- Periodic background sweep via `threading.Timer` -- killed on SIGKILL just like the connections; doesn't solve the problem
- Sweep on every `get_status()` call -- status endpoint is read-only; side effects on read are surprising
- Sweep on `release()` -- too late; the whole problem is that release never happens

## Decision 3: TTL Derivation

**Decision**: TTL = 2x heartbeat interval, configurable via `SSE_CONNECTION_TTL` env var with fallback to `2 * SSE_HEARTBEAT_INTERVAL`.

**Rationale**: The heartbeat interval (default 30s) is the guaranteed minimum event frequency for any connection. A connection that hasn't had activity in 2x that interval (60s) has definitively missed at least one heartbeat cycle. The 2x multiplier provides safety margin for:
- Network jitter (heartbeat arrives 5s late)
- Event loop delays under high load
- Clock skew between measurements

The env var override allows operators to tune for specific environments (e.g., shorter TTL in chaos testing, longer TTL in production with variable load).

## Decision 4: Status Endpoint Extension

**Decision**: Add `stale_connections` and `connection_ttl_seconds` to `get_status()` and `StreamStatus` model.

**Rationale**: The existing `/api/v2/stream/status` endpoint already returns connection pool metrics. Adding stale connection visibility is essential for:
1. On-call engineers diagnosing "connection limit reached" alerts
2. Dashboard monitoring of pool health
3. Validating the fix works in production (stale count should drop after sweep)

The `stale_connections` count is computed lazily (scan connections dict, compare timestamps) rather than maintained as a counter, to avoid consistency issues between the counter and actual stale state.

## Decision 5: Logging Strategy

**Decision**: Log swept connections at WARNING level.

**Rationale**: A swept connection represents an abnormal condition -- a connection that was not cleanly released. WARNING level ensures it's visible in CloudWatch without flooding logs. Each swept connection logs:
- `connection_id`: for correlation with prior "Connection acquired" log
- `inactive_seconds`: how long the connection has been idle
- `user_id`: for identifying affected users (sanitized)

This creates a queryable trail in CloudWatch Logs Insights:
```
filter @message like /Swept stale connection/
| stats count() as stale_sweeps by bin(5m)
```

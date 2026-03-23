# Research: SSE In-Memory State Validation

**Date**: 2026-03-21

## Decision 1: Validation Trigger Point

**Decision**: Validate state on each new connection establishment, not on every event or on a timer.

**Rationale**: The corruption window is between Lambda invocations. Once a connection is streaming, state is actively being used and any corruption would manifest as an exception (which the existing error handling catches). The risk is at connection time: stale state from a previous invocation silently affecting a new connection. Per-connection validation also naturally scales — zero connections means zero overhead; high-connection periods get proportional validation.

**Alternatives considered**:
- Per-event validation — too expensive, would violate the 5ms budget on high-throughput streams
- Timer-based validation (every N seconds) — adds complexity with background threads, and misses the window if corruption happens between timer ticks and a new connection
- On cold start only — misses the primary risk: warm start with stale state from a crashed previous invocation

## Decision 2: Phantom Connection Detection Strategy

**Decision**: Use `connected_at` timestamp comparison against a configurable threshold (default 15 minutes = Lambda max timeout).

**Rationale**: Lambda Function URL invocations have a maximum timeout of 15 minutes. Any `SSEConnection` object with `connected_at` older than 15 minutes is definitively a phantom — the Lambda invocation that created it has ended (cleanly or not). The `ConnectionManager._connections` dict is the only place connections live, and the `release()` method is called in a `finally` block. Phantoms only occur when the `finally` block doesn't execute (Lambda freeze, process crash, OOM kill).

**Why not heartbeat tracking**: Adding a "last seen" timestamp to each connection would require modifying the streaming hot path to update timestamps on every heartbeat. This adds lock contention to the connection pool for a problem that only manifests in exceptional cases.

## Decision 3: Event Buffer Corruption Detection

**Decision**: Check event buffer entries for parseable event IDs and discard entries that predate the current Lambda instance's `_start_time`.

**Rationale**: The `EventBuffer` is used for `Last-Event-ID` replay on client reconnection. If the buffer contains events from a previous Lambda invocation (which is impossible in normal operation but possible if `_stream_generator` global survives a partial crash), those events reference stale state. Event IDs use the format `evt_{uuid}`, so unparseable IDs indicate corruption. Events with timestamps before `SSEStreamGenerator._start_time` indicate cross-invocation leakage.

## Decision 4: Debouncer Self-Healing

**Decision**: Add a timestamp sanity check to `Debouncer.should_emit()` that resets entries with future timestamps.

**Rationale**: The `Debouncer._last_emit` dict stores `time.time()` values. If the Lambda process is frozen and resumed (AWS Lambda execution environment freeze/thaw), `time.time()` jumps forward, which is fine — the debouncer will naturally un-suppress. But if in-memory state is corrupted (bit flip, memory pressure), a future timestamp would permanently suppress emissions for that key. A simple `if last_emit > current_time: reset` guard costs almost nothing and prevents this edge case.

## Decision 5: Health Check Response Model

**Decision**: Extend the existing `StreamStatus` pydantic model with an `integrity` field using a new `IntegrityReport` model.

**Rationale**: The `/api/v2/stream/status` endpoint already returns a `StreamStatus` model. Adding an `integrity` field is backwards-compatible (new field with a default value). The `IntegrityReport` model provides structured data that monitoring systems can alert on. Using pydantic ensures the integrity data is always well-formed.

**Schema**:
```json
{
  "connections": 5,
  "max_connections": 100,
  "available": 95,
  "uptime_seconds": 3600,
  "integrity": {
    "status": "healthy",
    "checks": {
      "connection_pool": "ok",
      "event_buffer": "ok",
      "debouncer": "ok"
    },
    "last_validated": "2026-03-21T10:30:00Z",
    "resets_since_start": 0
  }
}
```

## Decision 6: CloudWatch Metric Strategy

**Decision**: Use the existing `MetricsEmitter` pattern with a new metric namespace prefix `StateValidation/`.

**Rationale**: Consistent with existing metrics (`ConnectionCount`, `EventsSent`, etc.). Separate namespace prefix allows independent alerting and dashboard widgets. Metrics emitted:
- `StateValidation/DurationMs` — validation latency per connection
- `StateValidation/PhantomConnectionsPurged` — count of phantom connections removed
- `StateValidation/BufferEntriesPurged` — count of corrupted buffer entries removed
- `StateValidation/DebouncerKeysReset` — count of stale debouncer keys reset
- `StateValidation/PoolReset` — binary (0/1) when full pool reset occurs

# Quickstart: SSE Connection Leak Cleanup

**Branch**: `1231-sse-connection-cleanup`

## Problem

When a Lambda is force-killed (SIGKILL, OOM), the `finally` block in `handler.py` that calls `connection_manager.release()` never executes. The orphaned connections remain in the in-memory `ConnectionManager`, permanently reducing capacity. Under repeated chaos, the pool fills to 100 and rejects all new clients with 503.

## Fix Summary

1. **Connection TTL**: Each connection tracks `last_activity` (updated on every event dispatch). Connections idle for > 2x heartbeat interval (default 60s) are considered stale.
2. **Sweep on acquire**: `acquire()` sweeps stale connections before checking capacity, so the first new client after a force-kill reclaims orphaned slots.
3. **Status endpoint**: `/api/v2/stream/status` now reports `stale_connections` and `connection_ttl_seconds` for observability.

## Verification

```bash
# Run unit tests
pytest tests/unit/sse_streaming/test_connection.py tests/unit/sse_streaming/test_connection_cleanup.py -v

# Check status endpoint (local dev)
curl http://localhost:8000/api/v2/stream/status | jq '.stale_connections'

# CloudWatch Logs query for stale connection sweeps
# filter @message like /Swept stale connection/
# | stats count() as stale_sweeps by bin(5m)
```

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `SSE_HEARTBEAT_INTERVAL` | `30` | Heartbeat interval in seconds |
| `SSE_CONNECTION_TTL` | `2 * SSE_HEARTBEAT_INTERVAL` | Connection TTL in seconds (override) |

## Files Changed

| File | Change |
|------|--------|
| `src/lambdas/sse_streaming/connection.py` | Add `last_activity`, `sweep_stale()`, TTL config |
| `src/lambdas/sse_streaming/models.py` | Add `stale_connections`, `connection_ttl_seconds` to `StreamStatus` |
| `tests/unit/sse_streaming/test_connection.py` | Extend for `last_activity` and status changes |
| `tests/unit/sse_streaming/test_connection_cleanup.py` | New: stale sweep tests |

## Key Design Decisions

1. **No background thread**: Sweep runs on `acquire()` only -- background threads would be killed by SIGKILL too.
2. **TTL = 2x heartbeat**: Provides safety margin for late heartbeats while catching truly dead connections.
3. **`update_last_event_id()` updates `last_activity`**: This method is already called on every event dispatch in `stream.py`. Zero changes needed in stream.py.

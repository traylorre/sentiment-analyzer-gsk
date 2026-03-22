# Quickstart: SSE In-Memory State Validation

**Branch**: `1231-sse-state-validation`

## What Changed

The original concern about `valid_resolutions` being cached at module level was **already fixed** by Feature 1229 — it's now computed fresh per request. This feature addresses the remaining risks: module-level singletons (`connection_manager`, `_stream_generator`) that can hold stale state after Lambda process reuse following a fault.

## Files to Modify

| File | Change |
|------|--------|
| `src/lambdas/sse_streaming/state_validator.py` | **NEW**: `StateValidator` class with `validate_state()`, `get_integrity()` |
| `src/lambdas/sse_streaming/handler.py` | Call `validate_state()` before `connection_manager.acquire()` in both stream handlers; extend `_handle_stream_status()` to include integrity |
| `src/lambdas/sse_streaming/connection.py` | Add `purge_phantom_connections(threshold_seconds)` and `get_connection_ages()` methods to `ConnectionManager` |
| `src/lambdas/sse_streaming/stream.py` | Add `check_buffer_integrity()` to `EventBuffer`; add `check_debouncer_integrity()` to `Debouncer`; add `get_integrity()` to `SSEStreamGenerator` |
| `src/lambdas/sse_streaming/models.py` | Add `IntegrityCheck`, `IntegrityReport` pydantic models; extend `StreamStatus` with optional `integrity` field |
| `tests/unit/test_state_validator.py` | **NEW**: Unit tests for all validation paths |

## Implementation Order

1. **Models first**: Add `IntegrityCheck` and `IntegrityReport` to `models.py`
2. **Introspection methods**: Add `purge_phantom_connections()` to `ConnectionManager`, `check_buffer_integrity()` to `EventBuffer`, future-timestamp guard to `Debouncer.should_emit()`
3. **StateValidator**: Create `state_validator.py` that orchestrates component checks
4. **Wire into handler**: Call `validate_state()` before acquire in both stream handlers; extend status endpoint
5. **Tests**: Unit tests for each validation path (phantom detection, buffer purge, debouncer reset, health endpoint)
6. **Metrics**: Emit `StateValidation/*` CloudWatch metrics on each reset

## Key Pattern: StateValidator

```python
class StateValidator:
    def __init__(self, conn_manager, stream_generator, metrics_emitter):
        self._conn_manager = conn_manager
        self._stream_generator = stream_generator
        self._metrics = metrics_emitter
        self._resets_since_start = 0
        self._last_validated = None

    def validate_state(self, timeout_ms: float = 5.0) -> bool:
        """Validate all singletons. Returns True if any resets occurred."""
        start = time.perf_counter()
        resets = False

        resets |= self._check_connection_pool()
        resets |= self._check_event_buffer()
        resets |= self._check_debouncer()

        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > timeout_ms:
            logger.warning("State validation exceeded budget",
                          extra={"elapsed_ms": elapsed_ms})

        self._last_validated = datetime.now(UTC)
        if resets:
            self._resets_since_start += 1
        return resets

    def get_integrity(self) -> IntegrityReport:
        """Get current integrity status for health endpoint."""
        ...
```

## Validation Rules

| Component | Check | Reset Action |
|-----------|-------|-------------|
| ConnectionManager | Connections with `connected_at` > 15min ago | Remove phantom connections |
| EventBuffer | Events with unparseable IDs or pre-start timestamps | Clear corrupted entries |
| Debouncer | `_last_emit` timestamps in the future | Reset affected keys |
| Debouncer | Keys older than 2x heartbeat interval | Trim stale keys |

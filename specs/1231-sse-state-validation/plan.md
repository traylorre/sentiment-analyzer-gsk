# Implementation Plan: SSE In-Memory State Validation

**Branch**: `1231-sse-state-validation` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1231-sse-state-validation/spec.md`

## Summary

Add per-connection state validation and integrity reporting to the SSE streaming Lambda. Before each new connection, validate that module-level singletons (ConnectionManager, EventBuffer, Debouncer) are internally consistent. Extend the `/api/v2/stream/status` endpoint with an `integrity` section. Reset corrupted state automatically with CloudWatch metrics for observability.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: No new packages. Uses existing `time`, `logging`, `datetime` (stdlib), `pydantic` (existing), `boto3` (existing CloudWatch metrics)
**Storage**: None (in-memory validation only)
**Testing**: pytest with moto mocks for CloudWatch metrics
**Target Platform**: AWS Lambda (custom runtime, RESPONSE_STREAM)
**Project Type**: Enhancement to existing SSE streaming module
**Performance Goals**: Validation completes in under 5ms
**Constraints**: Must not break existing SSE protocol behavior or connection flow
**Scale/Scope**: 1 new module + modifications to 4 existing files + 1 test file

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Implementation accompaniment (unit tests) | PASS | Tests for each validation function + integration test for handler |
| Deterministic time handling in tests | PASS | Mock `time.time()` for phantom detection and debouncer validation |
| External dependency mocking | PASS | Mock CloudWatch for metric emission in tests |
| GPG-signed commits | PASS | Standard workflow |
| Feature branch workflow | PASS | Branch `1231-sse-state-validation` |
| SAST/lint pre-push | PASS | `make validate` |

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/1231-sse-state-validation/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── tasks.md
└── checklists/
    └── requirements.md
```

### Source Code

```text
src/lambdas/sse_streaming/
├── state_validator.py          # NEW: StateValidator class with per-component checks
├── handler.py                  # MODIFY: Call validate_state() before connection acquire
├── connection.py               # MODIFY: Add purge_phantom_connections() method
├── stream.py                   # MODIFY: Add integrity_check() to SSEStreamGenerator
└── models.py                   # MODIFY: Add IntegrityReport model to StreamStatus

tests/unit/
└── test_state_validator.py     # NEW: Unit tests for state validation
```

**Structure Decision**: New `state_validator.py` module keeps validation logic isolated from connection/streaming concerns. Modifications to existing modules are minimal (adding introspection methods that the validator calls).

## Architecture

### Validation Flow (per connection)

```
New connection arrives
    │
    ▼
handler._handle_global_stream() or _handle_config_stream()
    │
    ├── state_validator.validate_state()    # <5ms budget
    │       ├── check_connection_pool()     # Purge phantom connections
    │       ├── check_event_buffer()        # Purge corrupted entries
    │       └── check_debouncer()           # Reset future timestamps
    │
    ├── (log warnings + emit metrics if resets occurred)
    │
    └── connection_manager.acquire()        # Normal flow continues
```

### Health Endpoint Extension

```
GET /api/v2/stream/status
    │
    ├── connection_manager.get_status()     # Existing
    └── state_validator.get_integrity()     # NEW
            ├── connection_pool: "ok" | "phantom_connections_detected"
            ├── event_buffer: "ok" | "corrupted_entries_detected"
            └── debouncer: "ok" | "stale_keys_detected"
```

## Key Design Decisions

1. **Validate on connection, not on every event**: Per-event validation would violate the 5ms budget. Connection-time validation catches corruption before it propagates.

2. **Reset, don't reject**: When corruption is detected, reset the affected state and continue. Rejecting connections due to internal state issues would make the Lambda appear down when it can self-heal.

3. **Phantom threshold = Lambda timeout**: 15 minutes matches the maximum Lambda execution time. Any connection older than that is guaranteed to be a phantom from a previous invocation that never cleaned up.

4. **Heartbeat-cycle lightweight check**: A minimal check during heartbeat emission catches mid-stream corruption without impacting event throughput.

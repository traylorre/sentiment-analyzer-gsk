# Feature Specification: 097-sse-content-type-header

**Branch**: `main` | **Date**: 2025-12-12

## Problem Statement

SSE E2E test `test_global_stream_available` fails with:
```
AssertionError: Expected text/event-stream, got: application/octet-stream
```

The SSE Lambda returns `application/octet-stream` instead of `text/event-stream`.

## Root Cause

The stream generators in `src/lambdas/sse_streaming/stream.py` yield pre-formatted SSE strings via `event.to_sse_format()`:

```python
async def generate_global_stream(...) -> AsyncGenerator[str]:
    ...
    yield heartbeat.to_sse_format()  # Returns formatted string
```

However, `EventSourceResponse` from `sse-starlette` expects dictionaries:
```python
# Expected format
yield {"event": "heartbeat", "id": "evt_xxx", "data": "..."}
```

When given raw strings, `sse-starlette` may not correctly set the Content-Type header.

## Solution

Modify stream generators to yield dictionaries instead of formatted strings. `EventSourceResponse` will handle SSE formatting and set the correct Content-Type.

### Before
```python
yield heartbeat.to_sse_format()
```

### After
```python
yield heartbeat.to_sse_dict()
```

## Scope

| In Scope | Out of Scope |
|----------|--------------|
| Fix stream generator yield format | Lambda infrastructure changes |
| Add `to_sse_dict()` method to SSEEvent | Test assertion fixes (lenient tests) |

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | test_global_stream_available passes | Pipeline Preprod Integration Tests |
| SC-002 | All other SSE tests still pass | Pipeline Preprod Integration Tests |
| SC-003 | Content-Type is text/event-stream | E2E test assertion |

## Technical Details

**Files Modified**:
1. `src/lambdas/sse_streaming/models.py` - Add `to_sse_dict()` method
2. `src/lambdas/sse_streaming/stream.py` - Change yields from `to_sse_format()` to `to_sse_dict()`

## References

- [sse-starlette documentation](https://github.com/sysid/sse-starlette)
- [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter)

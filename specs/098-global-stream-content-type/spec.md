# Feature Specification: 098-global-stream-content-type

**Branch**: `main` | **Date**: 2025-12-12

## Problem Statement

After feature 097 (dict yields), `test_global_stream_available` still fails with wrong Content-Type.
Config-specific stream tests pass due to lenient assertion, but all SSE endpoints return
`application/octet-stream` instead of `text/event-stream`.

## Root Cause Analysis

### Test Assertion Difference
- **test_global_stream_available** (strict): `"text/event-stream" in content_type`
- **test_sse_connection_established** (lenient): `"text/event-stream" in content_type OR "stream" in content_type.lower()`

`"application/octet-stream"` passes the lenient check because it contains `"stream"`.

### Actual Issue
The EventSourceResponse was not explicitly setting `media_type`. While sse-starlette
defaults to `text/event-stream`, something in the Lambda Web Adapter response chain
may be overriding it when not explicitly set.

## Solution

Explicitly set `media_type="text/event-stream"` in both EventSourceResponse calls.

### Before
```python
return EventSourceResponse(
    event_generator(),
    headers={...},
)
```

### After
```python
return EventSourceResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={...},
)
```

## Scope

| In Scope | Out of Scope |
|----------|--------------|
| Add explicit media_type to EventSourceResponse | Fix lenient test assertions |
| Both global and config stream endpoints | |

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | test_global_stream_available passes | Pipeline |
| SC-002 | Content-Type is text/event-stream | E2E assertion |
| SC-003 | All SSE tests continue to pass | Pipeline |

## Technical Details

**File**: `src/lambdas/sse_streaming/handler.py`
**Changes**: 2 lines (lines 154 and 295)

## References

- [sse-starlette](https://github.com/sysid/sse-starlette)
- [AWS Lambda Web Adapter response streaming](https://aws.amazon.com/blogs/compute/using-response-streaming-with-aws-lambda-web-adapter-to-optimize-performance/)

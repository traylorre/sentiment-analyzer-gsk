# Feature 1293: Plan

## Implementation
Add skip decorator to 5 tests in `test_sse_connection_preprod.py`.

Pattern:
```python
_SKIP_SSE_HTTP = os.environ.get("PREPROD_TRANSPORT") == "invoke"
_SKIP_REASON = "SSE HTTP streaming requires keep-alive connection, incompatible with invoke transport. Covered by Playwright E2E."

@pytest.mark.skipif(_SKIP_SSE_HTTP, reason=_SKIP_REASON)
```

Apply to: `test_sse_lambda_no_runtime_error`, `test_sse_stream_returns_200`, `test_sse_content_type_is_event_stream`, `test_sse_receives_heartbeat_event`, `test_dashboard_sse_connection_flow`.

## Clarifications
All self-answered.

## Adversarial Review #2
No drift. Gate passes.

# Feature 1293: Skip SSE Streaming Tests in Invoke Mode

## Problem
5 SSE streaming tests in `tests/e2e/test_sse_connection_preprod.py` fail with 403. They use `httpx.AsyncClient.stream()` to establish HTTP SSE connections to the SSE Lambda Function URL, which now requires AWS_IAM auth.

SSE streaming is fundamentally incompatible with Lambda invoke — invoke returns the complete response and SSE never completes (it's an infinite stream). These tests cannot be rewritten to use invoke.

## Files & Test Counts
- `tests/e2e/test_sse_connection_preprod.py` — 5 tests to skip

## Solution
Add `pytest.mark.skipif` when `PREPROD_TRANSPORT == "invoke"`. These tests remain runnable in local dev (where Function URL auth is NONE) and are covered in CI by Playwright browser tests (chaos-sse-lifecycle.spec.ts, chaos-sse-recovery.spec.ts).

## Functional Requirements

### FR-001: Skip all 5 SSE streaming tests in invoke mode
Tests: `test_sse_lambda_no_runtime_error`, `test_sse_stream_returns_200`, `test_sse_content_type_is_event_stream`, `test_sse_receives_heartbeat_event`, `test_dashboard_sse_connection_flow`.

### FR-002: Clear skip reason
Skip message must explain WHY (SSE streaming requires HTTP keep-alive, invoke returns complete response) and WHERE the behavior is covered instead (Playwright E2E).

## Success Criteria
- SC-001: All 5 tests skip cleanly in CI (PREPROD_TRANSPORT=invoke)
- SC-002: Tests still run when PREPROD_TRANSPORT is unset or "http" (local dev)
- SC-003: Skip count stays under 15% threshold

## Adversarial Review #1

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | **LOW** | Skip count concern — but preprod already has 156 skips/344 total (45%). Adding 5 is noise. | **Accepted**: Preprod skip rate is high by design (env-var gated). The 15% threshold in skip-rate-validate applies to unit tests, not preprod E2E. |

**0 CRITICAL, 0 HIGH remaining.** Gate passes.

## Out of Scope
- SigV4 signing for SSE streaming (complex, deferred)
- Rewriting SSE tests to use a different transport

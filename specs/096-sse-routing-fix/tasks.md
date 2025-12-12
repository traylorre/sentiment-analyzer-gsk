# 096: SSE Routing Fix - Tasks

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 3 |
| Parallelizable | 0 |
| File Changes | 1 (`api_client.py`) |
| Estimated Changes | 1 line modification |

## Phase 1: Implementation

### Goal
Fix SSE URL routing to catch all streaming endpoints.

### Tasks

- [x] T001 Update routing condition in `tests/e2e/helpers/api_client.py` line 312-314
  - Change: `path.startswith("/api/v2/stream")`
  - To: `"/stream" in path`

## Phase 2: Commit & Push

### Goal
Commit and push to trigger pipeline.

### Tasks

- [ ] T002 Commit changes with GPG signature and push to main

## Verification Checklist

Post-push verification:

- [ ] V001: SSE tests pass (test_global_stream_available, test_sse_connection_established, etc.)
- [ ] V002: Preprod Integration Tests job succeeds
- [ ] V003: Full Deploy Pipeline passes

## Dependencies

```
T001 ─> T002
```

## Success Criteria Mapping

| Success Criteria | Verification Task |
|-----------------|-------------------|
| SC-001: SSE tests pass | V001, V002 |
| SC-002: Config stream routes to SSE Lambda | V001 |
| SC-003: Non-stream routes unchanged | V002 |

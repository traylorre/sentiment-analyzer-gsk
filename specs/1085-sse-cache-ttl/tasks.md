# Implementation Tasks: Fix SSE 429 Rate Limit

**Branch**: `1085-sse-cache-ttl` | **Created**: 2025-12-28

## Phase 1: Implementation

- [X] T001 [US1] Change METRICS_CACHE_TTL default from "60" to "300"
- [X] T002 [US1] Add Feature 1085 comment for traceability

## Phase 2: Testing

- [X] T003 Verify existing metrics tests pass with new TTL (23/23 SSE tests pass)

## Phase 3: Verification

- [ ] T004 Deploy and verify SSE runs without 429 errors

## Dependencies

```text
T001 → T002 → T003 → T004
```

## Notes

- Single line change: `"60"` to `"300"` in metrics.py
- Environment variable override still works for custom configuration

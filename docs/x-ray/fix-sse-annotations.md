# Task 8: Add SSE Connection and Polling Annotations

**Priority:** P2
**Spec FRs:** FR-008, FR-009
**Status:** TODO
**Depends on:** Task 5 (SSE OTel spans via ADOT Extension must exist)
**Blocks:** Nothing

> **Round 3 Update:** All SSE streaming annotations attach as OTel span attributes on spans created by the ADOT Lambda Extension (Task 5), not as X-Ray subsegment annotations. The ADOT Extension exports these to X-Ray where they appear as annotations. References to "subsegments" below refer to OTel spans during the streaming phase.

---

## Problem

Even with subsegments (task 5), operators need queryable business context. Connection pool pressure and DynamoDB polling performance need to be searchable annotations, not just timing data.

---

## Annotations to Add

### Connection Lifecycle (FR-008)

Attach to `connection_acquire` and `connection_release` subsegments from task 5:

| Annotation Key | Source | Type | On Subsegment |
|---------------|--------|------|---------------|
| `connection_id` | `ConnectionManager.acquire()` return value | String | `connection_acquire` |
| `current_count` | `ConnectionManager._connections` length | Number | `connection_acquire`, `connection_release` |
| `max_connections` | `ConnectionManager._max_connections` | Number | `connection_acquire` |

### DynamoDB Polling (FR-009)

Attach to `dynamodb_poll` and `dynamodb_query_sentiment` subsegments from task 5:

| Annotation Key | Source | Type | On Subsegment |
|---------------|--------|------|---------------|
| `item_count` | Query result count | Number | `dynamodb_poll` |
| `changed_count` | Items that changed since last poll | Number | `dynamodb_poll` |
| `poll_duration_ms` | Elapsed time of poll operation | Number | `dynamodb_poll` |
| `sentiment_type` | GSI query parameter | String | `dynamodb_query_sentiment` |

---

## Files to Modify

| File | Change |
|------|--------|
| `src/lambdas/sse_streaming/connection.py` | Add annotations in acquire/release methods |
| `src/lambdas/sse_streaming/polling.py` | Add annotations in poll/query methods |

---

## Success Criteria

- [ ] `connection_acquire` subsegment has `connection_id`, `current_count`, `max_connections`
- [ ] `connection_release` subsegment has `current_count`
- [ ] `dynamodb_poll` subsegment has `item_count`, `changed_count`, `poll_duration_ms`
- [ ] `dynamodb_query_sentiment` subsegment has `sentiment_type`
- [ ] Operators can filter traces by `current_count > 90` (pool pressure) or `poll_duration_ms > 500`
- [ ] Total annotations per subsegment stays under 50 (X-Ray limit)

---

## Blind Spots

1. **Annotation cardinality**: `connection_id` is high-cardinality (UUID). Annotating it is acceptable because it enables trace-to-connection correlation, but it shouldn't be used as a group-by dimension in X-Ray analytics.
2. **Poll duration double-counting**: `poll_duration_ms` as an annotation duplicates the subsegment duration. It's kept because subsegment duration includes X-Ray overhead, while `poll_duration_ms` is the pure DynamoDB operation time.

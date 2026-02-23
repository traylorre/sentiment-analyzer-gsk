# Task 6: Replace latency_logger with X-Ray Annotations

**Priority:** P2
**Spec FRs:** FR-006, FR-022
**Status:** TODO
**Depends on:** Task 5 (SSE subsegments/segments must exist for annotations to attach to), Task 14 (tracer standardization)
**Blocks:** Task 12 (downstream consumer audit)

---

## Problem

`latency_logger.py` emits custom structured JSON logs for CloudWatch Logs Insights `pctile()` queries. This data should be X-Ray subsegment annotations instead, so operators can query latency directly in X-Ray without switching to Logs Insights.

---

## Current State

**File:** `src/lambdas/sse_streaming/latency_logger.py` (99 lines)

Emits structured log with fields:
- `event_type`: "bucket_update", "partial_bucket", "heartbeat"
- `origin_timestamp`: When sentiment data was created
- `send_timestamp`: When SSE event was serialized
- `latency_ms`: Time delta (milliseconds)
- `is_cold_start`: Boolean
- `is_clock_skew`: Boolean (negative latency detection)
- `connection_count`: Active SSE connections

**Called from:** `stream.py:_create_partial_bucket_event()` (and similar event creation paths)

---

## Files to Modify

| File | Change |
|------|--------|
| `src/lambdas/sse_streaming/latency_logger.py` | **DELETE** entire module |
| `src/lambdas/sse_streaming/stream.py` | Replace `log_latency_metric()` calls with X-Ray annotations on the `sse_event_dispatch` subsegment (from task 5) |
| Any other files importing `latency_logger` | Remove imports and calls |

---

## What to Change

At each point where `log_latency_metric()` is currently called:
1. Get the current X-Ray subsegment (should be `sse_event_dispatch` from task 5)
2. Add annotations: `event_type`, `latency_ms`, `is_cold_start`, `is_clock_skew`, `connection_count`
3. Remove the `log_latency_metric()` call
4. After all call sites are migrated, delete `latency_logger.py`

---

## Annotation Mapping

| Log Field | X-Ray Annotation Key | Type | Indexed/Searchable |
|-----------|---------------------|------|-------------------|
| `event_type` | `event_type` | String | YES |
| `latency_ms` | `latency_ms` | Number | YES |
| `is_cold_start` | `is_cold_start` | Boolean | YES |
| `is_clock_skew` | `is_clock_skew` | Boolean | YES |
| `connection_count` | `connection_count` | Number | YES |
| `origin_timestamp` | (subsegment start_time) | — | Automatic |
| `send_timestamp` | (subsegment end_time) | — | Automatic |

Note: `origin_timestamp` and `send_timestamp` are captured by the subsegment timing itself. `latency_ms` is the derived delta and is explicitly annotated for direct querying.

---

## RESPONSE_STREAM Constraint (Round 3 — Revised)

Event dispatch happens during SSE streaming — AFTER the Lambda runtime's X-Ray segment has closed (see Task 5). This means annotations cannot be added to standard X-Ray subsegments. Instead:

- Annotations attach as **OTel span attributes** on `sse_event_dispatch` spans created via the ADOT Lambda Extension (Task 5)
- The ADOT Extension exports these spans to X-Ray, where attributes appear as annotations
- OTel span attributes support `str`, `int`, `float`, `bool` — `None` should be omitted
- The ADOT Extension runs as an independent process that survives after the handler returns, ensuring spans are exported during streaming

---

## Success Criteria

- [ ] `latency_logger.py` deleted from repository
- [ ] Zero remaining imports of `latency_logger` in codebase
- [ ] `sse_event_dispatch` subsegments contain all 5 annotations
- [ ] Operators can filter traces by `latency_ms > 3000` in X-Ray
- [ ] No operational log entries removed (only tracing-specific structured logs)

---

## Blind Spots

1. **CloudWatch Logs Insights saved queries**: Any saved queries using `pctile()` on latency_logger fields will break. Task 12 must audit these.
2. **Dashboard widgets**: If any CloudWatch dashboard widget queries latency_logger JSON fields, it will break.
3. **Clock skew detection**: The `is_clock_skew` field detects negative latency (event claims to arrive before it was created). This edge case detection must transfer to the X-Ray annotation.
4. **RESPONSE_STREAM streaming phase (Round 3)**: Annotations attach as OTel span attributes on spans created via the ADOT Lambda Extension (Task 5), not to Lambda subsegments. If no OTel span is active when the attribute write is attempted, the attribute is silently dropped. Ensure annotations are written within an active OTel span context.
5. **Annotation type validation**: All annotation values must be `str`, `int`, `float`, or `bool`. If `latency_ms` is `None` (e.g., missing timestamp), omit the annotation rather than passing `None`.

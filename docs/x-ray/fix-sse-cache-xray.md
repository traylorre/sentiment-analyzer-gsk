# Task 7: Replace cache_logger with X-Ray Annotations

**Priority:** P2
**Spec FRs:** FR-007, FR-023
**Status:** TODO
**Depends on:** Task 5 (SSE subsegments/segments must exist for annotations to attach to), Task 14 (tracer standardization)
**Blocks:** Task 12 (downstream consumer audit)

---

## Problem

`cache_logger.py` (237 lines) emits custom structured JSON logs for cache hit rate validation (FR-003, FR-004 from Feature 1020). This data should be X-Ray annotations instead.

---

## Current State

**File:** `src/lambdas/sse_streaming/cache_logger.py` (237 lines)

`CacheMetricsLogger` class with `maybe_log()` method. Emits structured log with fields:
- `event_type`: "cache_metrics"
- `trigger`: "periodic", "threshold", "cold_start"
- `hits`: Cache hits count
- `misses`: Cache misses count
- `hit_rate`: Float (0.0-1.0)
- `entry_count`: Current cache size
- `max_entries`: Cache capacity (256)
- `is_cold_start`: Boolean
- `connection_count`: Active SSE connections
- `ticker`, `resolution` (optional context)

**Triggers:**
- Periodic: Every N seconds
- Threshold: When hit rate drops below configured threshold
- Cold start: On first invocation

---

## Files to Modify

| File | Change |
|------|--------|
| `src/lambdas/sse_streaming/cache_logger.py` | **DELETE** entire module |
| Files that call `CacheMetricsLogger.maybe_log()` | Replace with X-Ray annotations on current subsegment |
| Any imports of `cache_logger` | Remove |

---

## Annotation Mapping

| Log Field | X-Ray Annotation Key | Type | Indexed/Searchable |
|-----------|---------------------|------|-------------------|
| `hit_rate` | `cache_hit_rate` | Number | YES |
| `entry_count` | `cache_entry_count` | Number | YES |
| `max_entries` | `cache_max_entries` | Number | YES |
| `trigger` | `cache_trigger` | String | YES |
| `is_cold_start` | `is_cold_start` | Boolean | YES |
| `hits` | (metadata, not annotation) | Number | No (detail data) |
| `misses` | (metadata, not annotation) | Number | No (detail data) |
| `ticker` | (metadata, not annotation) | String | No (high cardinality) |
| `resolution` | (metadata, not annotation) | String | No (detail data) |

Note: `hits`, `misses`, `ticker`, and `resolution` go to X-Ray metadata (non-indexed) because they are detail fields, not primary filter dimensions. `ticker` is high-cardinality and would bloat annotation indexes.

---

## RESPONSE_STREAM Constraint (Round 3 — Revised)

Cache metrics are emitted during SSE streaming — AFTER the Lambda runtime's X-Ray segment has closed (see Task 5). This means annotations cannot be added to standard X-Ray subsegments. Instead:

- Annotations attach as **OTel span attributes** on spans created via the ADOT Lambda Extension (Task 5)
- The periodic trigger must fire within an active OTel span context
- OTel span attributes support `str`, `int`, `float`, `bool` — `None` should be omitted
- `hit_rate` (float) and `entry_count` (int) are confirmed valid attribute types
- The ADOT Extension exports these spans to X-Ray, where attributes appear as annotations

---

## Success Criteria

- [ ] `cache_logger.py` deleted from repository
- [ ] Zero remaining imports of `cache_logger` in codebase
- [ ] Current subsegment contains cache annotations when trigger fires
- [ ] Operators can filter traces by `cache_hit_rate < 0.8` in X-Ray
- [ ] Cache threshold alerts visible as annotations (not just logs)

---

## Blind Spots

1. **Periodic trigger timing**: `CacheMetricsLogger` uses a timer-based trigger. X-Ray annotations attach to the subsegment active at the time of the trigger. If no subsegment is active (between poll cycles), the annotation has nowhere to attach. Must ensure annotations are written within a subsegment context.
2. **Feature 1020 validation**: Feature 1020 validates cache hit rate >80%. If any automated check queries cache_logger's structured logs to verify this, it will break.
3. **Threshold alerts**: cache_logger logs a threshold alert when hit rate drops. This alerting behavior needs to transfer to X-Ray (perhaps as an error annotation on the subsegment).
4. **RESPONSE_STREAM streaming phase (Round 3)**: Annotations attach as OTel span attributes on spans created via the ADOT Lambda Extension (Task 5). If the periodic trigger fires between poll cycles (no active OTel span), the attribute has nowhere to attach. Must ensure trigger evaluation happens within a poll cycle's OTel span context.
5. **Annotation type validation**: All annotation values must be `str`, `int`, `float`, or `bool`. `hit_rate` is a float (valid). If `hit_rate` is `None` (e.g., zero cache operations), omit the annotation rather than passing `None`.

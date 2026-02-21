# Task 9: Consolidate Correlation IDs onto X-Ray Trace IDs

**Priority:** P3
**Spec FRs:** FR-010, FR-011, FR-012, FR-024
**Status:** TODO
**Depends on:** Tasks 2, 4, 5 (all subsegments should exist before changing the correlation system)
**Blocks:** Task 12 (downstream consumer audit)

---

## Problem

Two custom correlation ID systems exist in parallel with X-Ray:

1. `get_correlation_id()` in `src/lib/metrics.py:296-316` — format: `{source_id}-{lambda_request_id}`
2. `generate_correlation_id()` in `src/lib/deduplication.py:199-223` — identical format

Operators must know to search BOTH X-Ray traces AND CloudWatch Logs with two different ID formats. The custom IDs should be replaced by X-Ray trace IDs as the universal correlation key.

---

## Current State

**`get_correlation_id(source_id, context)`** — `src/lib/metrics.py:296-316`
- Takes `source_id` (e.g., `article#abc123`) and Lambda `context`
- Extracts `aws_request_id` from context
- Returns: `article#abc123-req-123-456`
- Fallback: `"unknown"` if request_id missing

**`generate_correlation_id(source_id, request_id)`** — `src/lib/deduplication.py:199-223`
- Same format, explicit parameters
- Duplicate implementation

**Usage sites** (from grep):
- `src/lib/metrics.py` (definition)
- `src/lib/deduplication.py` (definition)
- `src/lambdas/shared/schemas.py:279-281` (SchemaInconsistency model field)
- `tests/unit/test_metrics.py:136-156` (TestGetCorrelationId class)
- `tests/unit/test_deduplication.py:257-277` (test_generate_correlation_id)

**Critical finding:** The correlation ID is defined in schemas but NOT actively propagated through the pipeline in handler code. It exists but is underutilized.

---

## Files to Modify

| File | Change |
|------|--------|
| `src/lib/metrics.py` | Remove `get_correlation_id()` function; add `get_xray_trace_id()` helper that retrieves active trace ID |
| `src/lib/deduplication.py` | Remove `generate_correlation_id()` function |
| `src/lambdas/shared/schemas.py` | Update `SchemaInconsistency.correlation_id` to use X-Ray trace ID format |
| `src/lib/metrics.py` (StructuredLogger) | Add X-Ray trace ID as top-level field in all log entries (FR-012) |
| `tests/unit/test_metrics.py` | Remove `TestGetCorrelationId` class; add test for `get_xray_trace_id()` |
| `tests/unit/test_deduplication.py` | Remove `test_generate_correlation_id` tests |

---

## What to Change

### 1. New helper function (replaces both old functions)

A thin helper that retrieves the active X-Ray trace ID from the current segment. When X-Ray is active (all Lambdas after tasks 1-5), this returns the trace ID in format `1-{hex_timestamp}-{24_hex_digits}`.

### 2. Structured log enrichment (FR-012)

The `StructuredLogger` class in `metrics.py` must automatically include the X-Ray trace ID as a top-level field (`xray_trace_id`) in every log entry. This enables CloudWatch Logs Insights queries to join with X-Ray traces:

```
fields @timestamp, @message, xray_trace_id
| filter xray_trace_id = "1-abc123-def456"
```

### 3. Schema update

`SchemaInconsistency.correlation_id` field type/validation should accept X-Ray trace ID format.

---

## Success Criteria

- [ ] `get_correlation_id()` function deleted from `metrics.py`
- [ ] `generate_correlation_id()` function deleted from `deduplication.py`
- [ ] Zero remaining call sites for either function
- [ ] All structured log entries include `xray_trace_id` top-level field
- [ ] `SchemaInconsistency.correlation_id` accepts X-Ray trace ID format
- [ ] Tests updated: old tests removed, new tests added for trace ID retrieval
- [ ] CloudWatch Logs Insights query `filter xray_trace_id = "..."` works

---

## Blind Spots

1. **X-Ray context availability**: The trace ID retrieval will return `None` or raise when no active segment exists (e.g., during unit tests, local development without X-Ray). The helper must handle this — but NOT with a fallback to the old format. If X-Ray is not active, the field should be `null`/absent, making the gap visible.
2. **Test mocking**: Unit tests that don't run under X-Ray will need to mock the trace ID retrieval. The existing `tests/e2e/helpers/xray.py` has patterns for this.
3. **Log volume**: Adding `xray_trace_id` to every log entry increases log size slightly. This is acceptable — the field is a fixed-length string (~36 chars).

# Quickstart: SSE Origin Timestamp

## Overview

This feature renames the `timestamp` field to `origin_timestamp` in SSE event models to enable client-side latency measurement.

## Files Changed

1. `src/lambdas/dashboard/sse.py` - Rename field in 2 Pydantic models

## How to Test

### Run E2E Tests (after implementation)

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk
pytest tests/e2e/test_live_update_latency.py -v
```

### Expected Results

All 3 tests should pass:
- `test_live_update_p95_under_3_seconds` - Collects 50+ samples, validates p95 < 3000ms
- `test_sse_events_include_origin_timestamp` - Verifies `origin_timestamp` field present
- `test_latency_metrics_exposed_to_window` - Verifies `window.lastLatencyMetrics` populated

## Verification

Before:
```json
{"event": "heartbeat", "data": {"timestamp": "2025-12-23T12:00:00Z", "connections": 5}}
```

After:
```json
{"event": "heartbeat", "data": {"origin_timestamp": "2025-12-23T12:00:00Z", "connections": 5}}
```

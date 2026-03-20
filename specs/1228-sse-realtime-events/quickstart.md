# Quickstart: Wire SSE Real-Time Events

**Feature**: 1228-sse-realtime-events
**Date**: 2026-03-20

## Overview

This feature wires two dead-code event types in the SSE Lambda to live data:
1. `sentiment_update` — emitted when per-ticker aggregate sentiment changes
2. `partial_bucket` — emitted when timeseries OHLC buckets change

## Files to Modify

| File | Change | Why |
|------|--------|-----|
| `src/lambdas/sse_streaming/polling.py` | Add per-ticker aggregate tracking + timeseries polling | FR-001, FR-002, FR-003, FR-004 |
| `src/lambdas/sse_streaming/stream.py` | Wire events into both stream generators | FR-006, FR-007, FR-008 |
| `src/lambdas/sse_streaming/models.py` | Update SSEEvent validator to accept PartialBucketEvent | Validation fix |

## Implementation Order

### Step 1: Fix Pre-existing Bug in polling.py

Change `item.get("ticker")` to iterate `item.get("matched_tickers", [])` in `_aggregate_metrics()`. This fixes the empty `by_tag` dict.

### Step 2: Extend PollingService for Per-Ticker Aggregates + Timeseries

Extend `PollingService.poll()` to return three things: (metrics, per_ticker_aggregates, timeseries_buckets).

- Add `_compute_per_ticker_aggregates(items)` — computes score/label/count per ticker from already-fetched items
- Add `_fetch_timeseries_buckets(tickers)` — uses `BatchGetItem` against TIMESERIES_TABLE for current buckets of discovered tickers × 8 resolutions
- Ticker list derived from sentiment items (no hardcoded list needed)

**Key**: The `PollingService` returns raw data. Change detection happens **per-connection** in the stream generators, not in the shared polling service.

### Step 3: Wire Events into generate_global_stream()

Add per-connection local state: `local_last_per_ticker`, `local_last_buckets`, `local_is_baseline`.

In the main event loop (after metrics handling):
- Diff per-ticker aggregates against local snapshot → emit `sentiment_update` for changed tickers
- Diff timeseries buckets against local snapshot → emit `partial_bucket` for changed buckets (via debouncer)
- Skip all change events on first poll (baseline establishment)

### Step 4: Wire Events into generate_config_stream()

Replace the heartbeat-only loop with a polling loop (same as global stream). Each config stream connection maintains its own local snapshots. Apply `connection.matches_ticker()` filter before yielding sentiment_update and partial_bucket events.

### Step 5: Increase Event Buffer

Change `EventBuffer(max_size=100)` to `EventBuffer(max_size=500)`.

### Step 6: Baseline Establishment

Each generator coroutine starts with `local_is_baseline = True`. First poll populates snapshots, no events emitted. Per-connection state means each new connection independently establishes its baseline.

## Testing Strategy

- **Unit tests**: Mock DynamoDB responses. Test change detection logic, ticker filtering, debouncer behavior, baseline establishment.
- **Deterministic time**: Use `freezegun` for `progress_pct` calculations.
- **No integration tests needed**: All DynamoDB interactions are through existing, tested boto3 patterns.

## Verification

```bash
# Run unit tests
cd ~/projects/sentiment-analyzer-gsk
python -m pytest tests/unit/test_sse_sentiment_events.py tests/unit/test_sse_timeseries_polling.py tests/unit/test_sse_stream_wiring.py -v

# Live verification (after deploy)
curl -N "https://4dhyo52gjpp3dzmkrxgr2gktqm0vpksw.lambda-url.us-east-1.on.aws/api/v2/stream" | head -50
```

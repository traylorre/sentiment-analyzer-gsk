# Future Work: Real-Time OHLC Two-Zone Architecture

**Status:** Future Work (Not In Scope for CACHE-001)
**Created:** 2026-02-04
**Related Spec:** `ohlc-cache-remediation.md` (CACHE-001)
**Source:** Claude Desktop analysis of `write-through-pubsub-design.md`

---

## Overview

This document captures future architectural direction for real-time OHLC data. The current spec (CACHE-001) focuses on **filled/locked buckets only**. This document describes how that work will integrate with future **partial/in-progress bucket** support.

---

## Two-Zone Data Model

OHLC data has two fundamentally different freshness profiles:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         OHLC DATA ZONES                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ZONE 1: LOCKED/FILLED BUCKETS              ZONE 2: IN-PROGRESS BUCKET  │
│  ════════════════════════════               ══════════════════════════  │
│                                                                          │
│  • Immutable once interval closes           • Mutable until close       │
│  • Safe to cache aggressively               • Changes every tick        │
│  • Source: DynamoDB → Cache → API           • Source: WebSocket stream  │
│  • Read pattern: Query by range             • Read pattern: Subscribe   │
│  • One per resolution per ticker            • Exactly ONE per resolution│
│                                                                          │
│  Example (AAPL at 2:47 PM):                 Example (AAPL at 2:47 PM):  │
│  ┌─────┬─────┬─────┬─────┬─────┐           ┌─────┐                      │
│  │2:42 │2:43 │2:44 │2:45 │2:46 │           │2:47 │  ← forming          │
│  │ ✓   │ ✓   │ ✓   │ ✓   │ ✓   │           │ ... │                      │
│  └─────┴─────┴─────┴─────┴─────┘           └─────┘                      │
│      Locked (cacheable)                     In-progress (live)          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Resolution Buckets

At any given time, there are **6 in-progress buckets** (one per resolution):

| Resolution | Bucket Duration | Example (at 2:47:32 PM) |
|------------|-----------------|-------------------------|
| 1min       | 60 seconds      | 2:47:00 - 2:47:59 (forming) |
| 5min       | 5 minutes       | 2:45:00 - 2:49:59 (forming) |
| 15min      | 15 minutes      | 2:45:00 - 2:59:59 (forming) |
| 30min      | 30 minutes      | 2:30:00 - 2:59:59 (forming) |
| 1h         | 1 hour          | 2:00:00 - 2:59:59 (forming) |
| 1day       | Market day      | 9:30:00 - 16:00:00 (forming) |

---

## Current Work: Filled Buckets (CACHE-001)

The `ohlc-cache-remediation.md` spec addresses **Zone 1 only**:

```
Dashboard Request → OHLC Endpoint
                        ↓
                  In-Memory Cache (1hr TTL)
                        ↓ miss
                  DynamoDB Cache (90-day TTL)
                        ↓ miss
                  Tiingo/Finnhub REST API
                        ↓
                  Write-through to DynamoDB
                        ↓
                  Return filled buckets
```

**Design Decisions for Reusability:**

1. **Cache key includes resolution**: `ohlc:{ticker}:{resolution}:{range}:{date}`
   - Future: Same key structure works for partial bucket metadata

2. **`is_closed` attribute planned**: DynamoDB schema can store `is_closed: bool`
   - Current: All stored data is closed (true)
   - Future: Partial buckets stored with `is_closed: false`

3. **Separate read/write functions**: `_read_from_dynamodb()`, `_write_through_to_dynamodb()`
   - Future: Partial bucket writes use same `_write_through_to_dynamodb()`

4. **Resolution enum**: `OHLCResolution` already supports all intervals
   - Future: No changes needed for partial bucket support

---

## Future Work: Partial Buckets (Post CACHE-001)

### Phase 1: WebSocket Ingestion (Fargate)

```
Tiingo/Finnhub WebSocket
        ↓
Fargate Ingestion Service (persistent connection)
        ↓
    ┌───┴───┐
    ↓       ↓
DynamoDB    SNS (ticker-updates)
(ticker-    ↓
prices)     SQS → Broadcast Lambda
            ↓
        API Gateway WebSocket
            ↓
        Dashboard (partial bucket updates)
```

**Key Components:**
- `src/ingestion/` - New Fargate service for WebSocket connections
- `ticker-prices` DynamoDB table - Stores both locked and forming bars
- SNS topic for real-time fan-out

### Phase 2: Dashboard Integration

Dashboard displays combined view:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OHLC Chart Display                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [===== Filled Buckets (from DDB/cache) =====][Partial]             │
│                                                                      │
│  Source: OHLC REST endpoint                   Source: WebSocket     │
│  Updates: On page load / range change         Updates: Real-time    │
│  Latency: ~100ms (cache hit)                  Latency: ~100-500ms   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 3: Unified Query Layer

Eventually, OHLC endpoint could serve both:

```python
async def get_ohlc_data(ticker: str, resolution: str, start: date, end: date):
    """Query OHLC data, combining locked and partial buckets."""

    # Zone 1: Locked buckets (current CACHE-001 implementation)
    locked_candles = await _read_from_dynamodb(ticker, resolution, start, end)

    # Zone 2: Partial bucket (future - from real-time table or memory)
    if end >= date.today():
        partial_candle = await _get_partial_bucket(ticker, resolution)
        if partial_candle:
            locked_candles.append(partial_candle)

    return locked_candles
```

---

## Data Source Consolidation (Future Decision)

### Option A: Two Tables (Recommended for MVP)

| Table | Purpose | Populated By |
|-------|---------|--------------|
| `ohlc-cache` | Historical filled buckets | OHLC endpoint write-through |
| `ticker-prices` | Real-time + recent | Fargate WebSocket ingestion |

**Pros:** No migration, parallel development
**Cons:** Query complexity, potential data inconsistency

### Option B: Single Table (Future Consolidation)

| Table | Purpose | Populated By |
|-------|---------|--------------|
| `ticker-prices` | All OHLC data | Fargate (real-time) + Backfill job (historical) |

**Pros:** Single source of truth, simpler queries
**Cons:** Migration effort, schema alignment

### Option C: Hybrid (Recommended Long-Term)

- `ticker-prices` for recent data (last 7 days) - populated by Fargate
- `ohlc-cache` for historical data (>7 days) - populated on-demand from Tiingo
- OHLC endpoint queries both, merges results

---

## Compatibility Notes

### Current SSE Lambda

The existing SSE Lambda (`/api/v2/stream`) serves **sentiment data**, not OHLC:
- Protocol: HTTP Server-Sent Events
- Data: Sentiment metrics (positive/neutral/negative counts)
- Update: Polls DynamoDB every 5 seconds

**Decision:** Keep SSE for sentiment, add WebSocket for OHLC prices.
- Sentiment is lower-frequency, SSE is sufficient
- Price data needs lower latency, WebSocket preferred

### Existing Infrastructure Reuse

| Component | Current Use | Future Use |
|-----------|-------------|------------|
| `ohlc-cache` DynamoDB | Filled buckets (CACHE-001) | Historical data (>7 days) |
| `OHLCResolution` enum | Resolution parsing | Same |
| `PriceCandle` model | Candle representation | Same + `is_forming` field |
| CloudWatch metrics | Cache hit/miss | + WebSocket connection count |
| Circuit breaker | DynamoDB failures | Same pattern for WebSocket |

---

## Blind Spots Identified

From analysis session (2026-02-04):

1. **Data gap on Fargate restart** - Need backfill mechanism
2. **SNS → SQS latency** - 50-500ms delay (acceptable for most users)
3. **WebSocket connection limits** - API Gateway defaults (request increase)
4. **Popular ticker fan-out** - AAPL subscribed by thousands
5. **Two tables with different schemas** - Query layer abstraction needed
6. **Forming bar race condition** - Out-of-order message handling

---

## Open Questions (To Address in Future Spec)

1. Should partial buckets be stored in DynamoDB or only held in memory?
2. What happens to partial bucket data if Fargate restarts mid-bar?
3. Should we publish partial bucket updates to SNS, or only closed bars?
4. How do we handle market close (4 PM ET) - when does daily bar "close"?
5. Cost comparison: Fargate WebSocket vs current EventBridge polling

---

## References

- `ohlc-cache-remediation.md` - Current filled bucket implementation
- `write-through-pubsub-design.md` - Original architecture proposal (Claude Desktop)
- SSE Lambda analysis - Agent exploration (2026-02-04)
- Tiingo WebSocket API: https://api.tiingo.com/documentation/websockets
- Finnhub WebSocket API: https://finnhub.io/docs/api/websocket-trades

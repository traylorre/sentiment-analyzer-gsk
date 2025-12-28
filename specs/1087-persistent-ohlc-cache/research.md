# Research: Persistent OHLC Cache

**Feature**: 1087-persistent-ohlc-cache
**Date**: 2025-12-28
**Status**: Complete

## Research Questions

1. DynamoDB key design for time-series OHLC data
2. Write-through cache implementation pattern
3. Market hours detection for freshness logic
4. Range query optimization for pan/zoom

---

## 1. DynamoDB Key Design

### Decision
**Composite key**: `PK = {ticker}#{source}`, `SK = {resolution}#{timestamp}`

### Rationale
- Enables single Query operation for all candles of a ticker+source+resolution within time range
- ISO8601 timestamps sort lexicographically → efficient `BETWEEN` queries
- Aligns with existing `sentiment-timeseries` table pattern in codebase
- Source tracking allows data provenance (Tiingo vs Finnhub)

### Alternatives Considered
| Pattern | Rejected Because |
|---------|------------------|
| `PK = {ticker}#{resolution}` | Loses source provenance |
| `PK = {ticker}`, `SK = {timestamp}` | Can't filter by resolution efficiently |
| GSI on timestamp | Wrong access pattern, reads all symbols |

### Example
```
PK: "AAPL#tiingo"
SK: "5m#2025-12-27T10:30:00Z"
Attributes: { open: 195.50, high: 196.00, low: 195.25, close: 195.75, volume: 1234567 }
```

---

## 2. Write-Through Cache Pattern

### Decision
**Synchronous write-through** with conditional writes to prevent duplicates

### Rationale
- External API data is fetched → immediately written to DynamoDB → returned to client
- Conditional `PutItem` with `attribute_not_exists(SK)` prevents redundant writes
- No async queues = simpler architecture, guaranteed cache population
- Historical data is immutable → write once, read forever

### Alternatives Considered
| Pattern | Rejected Because |
|---------|------------------|
| Write-behind (async) | Adds latency, complexity, potential data loss on Lambda timeout |
| Read-through only | Still makes API call, just caches response after |
| Client-side cache | No shared benefit across users |

### Implementation Flow
```
Request → Check L1 (Lambda memory)
       → Check L2 (DynamoDB)
       → Fetch from External API
       → Write-through to L2
       → Populate L1
       → Return
```

---

## 3. Market Hours Detection

### Decision
**Hardcoded NYSE schedule** with simple weekday/time check (no external API)

### Rationale
- NYSE trading hours: 9:30 AM - 4:00 PM Eastern, Monday-Friday
- Historical data requests don't need market hours logic (data is permanent)
- Only "current candle" freshness needs market hours check
- Holidays are edge cases (~10/year) and can return stale data gracefully
- Avoids external API dependency for calendar data

### Alternatives Considered
| Pattern | Rejected Because |
|---------|------------------|
| External holiday API | Adds latency, API key management, rate limits |
| Holiday table in DynamoDB | Operational overhead, needs manual updates |
| Always fetch latest | Wastes API quota, unnecessary for historical |

### Freshness Rules
| Scenario | Behavior |
|----------|----------|
| Historical candle (>1 hour old) | Always serve from cache |
| Current candle during market hours | Fetch fresh, write-through |
| Current candle outside market hours | Serve from cache |

---

## 4. Range Query Optimization

### Decision
**Single Query with `BETWEEN` on sort key** using ISO8601 timestamp prefix

### Rationale
- DynamoDB Query is single-partition, O(log n) seek + O(k) scan for k items
- ISO8601 sorts lexicographically → `BETWEEN "5m#2025-12-01" AND "5m#2025-12-31"` works
- Resolution prefix ensures we only get matching resolution (no post-filter needed)
- Pagination via `LastEvaluatedKey` if >1MB response

### Alternatives Considered
| Pattern | Rejected Because |
|---------|------------------|
| Scan with FilterExpression | Reads entire table, expensive |
| Separate table per resolution | Multiplies operational overhead |
| GSI on timestamp | Wrong access pattern |

### Query Example
```python
# 2-hour window of 5m candles (24 records)
response = table.query(
    KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
    ExpressionAttributeValues={
        ":pk": "AAPL#tiingo",
        ":start": "5m#2025-12-28T10:00:00Z",
        ":end": "5m#2025-12-28T12:00:00Z"
    },
    ProjectionExpression="SK, #o, high, low, #c, volume",
    ExpressionAttributeNames={"#o": "open", "#c": "close"}
)
```

### Performance Expectations
| Query | Items | Expected Latency |
|-------|-------|------------------|
| 2-hour window @ 5m | ~24 | <50ms |
| 1-day window @ 1m | ~390 | <100ms |
| 1-month window @ 1h | ~160 | <50ms |

---

## Alignment with Existing Codebase

### Existing Cache Layers
1. **L1 (Lambda memory)**: `src/lambdas/dashboard/ohlc.py` lines 44-163
   - Max 256 entries, TTL 5m-1h by resolution
   - Cache key: `ohlc:{TICKER}:{RESOLUTION}:{TIME_RANGE}`

2. **L2 (Adapter memory)**: `src/lambdas/shared/adapters/tiingo.py`, `finnhub.py`
   - Per-adapter cache, 30min-1h TTL
   - Not persistent across Lambda cold starts

### Existing Table Pattern (Reference)
`sentiment-timeseries` table uses:
```
PK: {ticker}#{resolution}
SK: ISO8601 timestamp
```

OHLC cache follows similar pattern with source addition.

---

## Decisions Summary

| Question | Decision |
|----------|----------|
| Key design | `PK = {ticker}#{source}`, `SK = {resolution}#{timestamp}` |
| Cache pattern | Synchronous write-through with conditional writes |
| Market hours | Hardcoded NYSE schedule (9:30-16:00 ET weekdays) |
| Range queries | `BETWEEN` on ISO8601-prefixed sort keys |

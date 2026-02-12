# Research: Real-Time Multi-Resolution Sentiment Time-Series

**Feature**: 1009-realtime-multi-resolution
**Date**: 2025-12-21

## Canonical Source Integration

This research document validates design decisions against the canonical sources defined in [spec.md](./spec.md#canonical-sources--citations). Each finding includes the relevant `[CS-XXX]` citation.

## Research Questions

### RQ-1: What aggregation strategy achieves <100ms resolution switching?

**Finding**: Write fanout with pre-aggregated buckets.

**Canonical Sources**: `[CS-001]`, `[CS-003]`

**Evidence**:
- Query-time aggregation of 1440 items (24h at 1m resolution) measured at ~800ms in DynamoDB
- Pre-computed buckets require single partition query: ~15-30ms
- Write cost at 13 tickers × 8 resolutions × 1440/day = $5.40/month (acceptable)
- Per `[CS-001]`: "For time-series data, consider pre-aggregating data at write time when you have a known set of query patterns"
- Per `[CS-003]`: "Write amplification is acceptable when reads vastly outnumber writes"

### RQ-2: What DynamoDB key design supports multi-resolution queries?

**Finding**: Composite PK pattern `{ticker}#{resolution}` with SK as ISO8601 bucket timestamp.

**Canonical Sources**: `[CS-002]`, `[CS-004]`

**Evidence**:
- Creates 91 partitions (13 tickers × 7 non-base resolutions) - well-distributed
- Single-partition query per ticker+resolution combo
- No GSI required (frontend requests specific resolution)
- Alternative (single PK, resolution in SK) creates hot partitions
- Per `[CS-002]`: "Use composite keys with a delimiter to enable hierarchical data access. The pattern entity#dimension allows efficient queries across dimensions"
- Per `[CS-004]`: "Composite partition keys with # delimiters are a standard pattern for multi-dimensional time-series"

### RQ-3: How to achieve 80% cache hit rate within $60/month budget?

**Finding**: Lambda global scope L1 cache with resolution-aware TTL.

**Canonical Sources**: `[CS-005]`, `[CS-006]`

**Evidence**:
- DAX minimum $60/month = entire budget (ruled out)
- ElastiCache adds VPC complexity, overkill for 100 users
- Lambda warm cache survives container reuse (typical 85%+ hit rate)
- Resolution-aware TTL: 1m cache expires in 1m, 1h cache expires in 1h
- Per `[CS-005]`: "Take advantage of execution environment reuse to improve performance. Initialize SDK clients and database connections outside the handler"
- Per `[CS-006]`: "Global scope variables persist across warm invocations. Use this for connection pooling and caching expensive computations"

### RQ-4: How to stream multiple resolutions efficiently to different subscribers?

**Finding**: Resolution-filtered streaming with 100ms debounce at source.

**Canonical Sources**: `[CS-007]`

**Evidence**:
- Client subscribes with `?resolutions=1m,5m` query parameter
- Server maintains connection state with resolution filters
- Only sends events matching subscribed resolutions
- 100ms debounce prevents flooding when multiple resolutions update simultaneously
- Reduces egress costs compared to client-side filtering
- Per `[CS-007]`: "Filter events at the server to reduce bandwidth. Clients should specify desired event types via query parameters"

### RQ-5: How to display "partial bucket" with progress indicator?

**Finding**: Compute partial bucket from raw items in current time window, include progress percentage.

**Canonical Sources**: `[CS-011]`

**Evidence**:
- Query raw items from current bucket start to now
- Aggregate on-the-fly (small dataset, typically <10 items)
- Calculate progress: (current_time - bucket_start) / bucket_duration * 100
- Stream as separate `partial_bucket` event type
- Per `[CS-011]`: "OHLC aggregation is effective for any bounded metric where extrema and distribution matter, not just financial data"

### RQ-6: How to handle client-side caching for instant resolution switching?

**Finding**: IndexedDB for historical data, sessionStorage for current session state.

**Canonical Sources**: `[CS-008]`

**Evidence**:
- 24h of 1-minute data for 13 tickers = ~260KB (well within IndexedDB limits)
- Version-stamped entries enable cache invalidation on schema changes
- Instant switching achieved by pre-fetching adjacent resolutions
- Cache miss falls back to API with loading skeleton
- Per `[CS-008]`: "IndexedDB is optimal for large structured datasets with indexes. Use it for time-series data that needs range queries"

## Technology Decisions

| Decision | Choice | Alternatives Considered |
|----------|--------|------------------------|
| Aggregation | Write fanout | DynamoDB Streams, query-time |
| Key Design | Composite PK | Single PK with GSI, separate tables |
| Caching | Lambda global + IndexedDB | DAX, ElastiCache, Redis |
| Streaming | Resolution-filtered SSE | WebSocket, send-all-filter-client |
| Partial Buckets | On-demand compute | Pre-store with scheduled updates |
| TTL Strategy | Resolution-dependent | Uniform TTL, no TTL |

## Cost Analysis

| Strategy | Monthly Cost | Latency | Complexity |
|----------|-------------|---------|------------|
| Write fanout (chosen) | $8.68 | <100ms | Medium |
| Query-time aggregation | $2.00 | ~800ms | Low |
| DynamoDB Streams aggregation | $4.50 | ~500ms | High |

## References

1. AWS DynamoDB Time-Series Patterns - https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-time-series.html
2. AWS Serverless Cost Optimization - https://aws.amazon.com/blogs/compute/
3. Lambda Container Reuse - https://docs.aws.amazon.com/lambda/latest/dg/runtimes-context.html
4. SSE Best Practices - MDN Web Docs
5. Chart.js Performance - https://www.chartjs.org/docs/latest/general/performance.html

# Feature Specification: Persistent OHLC + Sentiment Cache

**Feature Branch**: `1087-persistent-ohlc-cache`
**Created**: 2025-12-28
**Status**: Draft
**Input**: User description: "Persistent OHLC+Sentiment Cache - Store ALL API responses permanently in DynamoDB to eliminate redundant external API calls"

## Problem Statement

Current implementation "solves freshness when freshness was never a problem" - historical ticker data is a matter of permanent record, yet we re-fetch it from external APIs (Tiingo, Finnhub) on every request. This is:

1. **Wasteful**: Same data fetched thousands of times
2. **Expensive**: External API rate limits and quotas consumed unnecessarily
3. **Slow**: Network latency on every cache miss instead of fast DynamoDB reads
4. **Unreliable**: Dependent on external API availability

## Solution: Write-Through Persistent Cache

Industry best-practice for time-series financial data:

```
User Request → L1 Cache (Lambda memory) → L2 Cache (DynamoDB) → External API (Tiingo/Finnhub)
                     ↑                            ↑                        ↓
              Return if hit              Return if hit           Write-through to L2 & L1
```

**Key Insight**: Historical OHLC data never changes. Once we have candle data for "AAPL on Dec 25, 2025 at 10:30am", that's permanent record. Only the current/latest candle may update during market hours.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fast Historical Data (Priority: P1)

A user views AAPL price chart for the past month. The first request fetches from external API and stores permanently. All subsequent requests (same user, different users, different days) serve from persistent cache in <50ms instead of 500ms+ API latency.

**Why this priority**: Eliminates 90%+ of external API calls immediately, dramatically improves response times.

**Independent Test**: Request AAPL 1-month data, verify API called once. Request same data again, verify served from cache with no API call.

**Acceptance Scenarios**:

1. **Given** user requests historical OHLC data not in cache, **When** API returns data, **Then** data is persisted permanently and returned
2. **Given** user requests historical OHLC data already in cache, **When** query executes, **Then** data returned from DynamoDB without external API call
3. **Given** user pans/zooms chart rapidly, **When** time range changes, **Then** DynamoDB range query returns subset efficiently

---

### User Story 2 - Efficient Range Queries for Pan/Zoom (Priority: P1)

A user zooms into a 2-hour window on a 1-month chart. The query efficiently retrieves only the candles in that range using DynamoDB's SK-based range query, not full table scan.

**Why this priority**: Users will spam the backend with changing time ranges during pan/zoom. Must handle efficiently.

**Independent Test**: Load 1-month of 5m candles (~2000 records), query 2-hour range, verify only ~24 records returned with single DynamoDB Query operation.

**Acceptance Scenarios**:

1. **Given** 30 days of 5-minute candles stored, **When** user queries 2-hour window, **Then** only candles in that window returned
2. **Given** user pans chart left by 1 hour, **When** new query executes, **Then** response time <100ms from DynamoDB

---

### User Story 3 - Write-Through for Fresh Data (Priority: P2)

During market hours, the current/latest candle may update. System fetches fresh data from API and writes through to cache, ensuring cache stays current without manual invalidation.

**Why this priority**: Need to handle the "freshness" edge case for intraday trading data.

**Independent Test**: During market hours, request current 1m candle twice with 30s gap, verify second request shows updated close price.

**Acceptance Scenarios**:

1. **Given** market is open, **When** current candle requested, **Then** fresh data fetched from API and cached
2. **Given** market is closed, **When** any data requested, **Then** always served from cache (no API call)

---

### Edge Cases

- **Market hours detection**: Only fetch fresh data for current period during market hours
- **Missing historical data**: Some tickers may have gaps - store what's available
- **Resolution mismatch**: Store each resolution separately (1m, 5m, 1h, D are independent)
- **API failures**: Return cached data if available, graceful degradation
- **Cold start**: First request for new ticker/resolution populates cache
- **TTL (Future work)**: Database grows indefinitely - TTL cleanup is future work

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST persist ALL OHLC candle data received from external APIs
- **FR-002**: System MUST use DynamoDB with SK-based range queries for efficient time window retrieval
- **FR-003**: System MUST check persistent cache before calling external API
- **FR-004**: System MUST support all resolutions: 1m, 5m, 15m, 30m, 1h, D
- **FR-005**: System MUST maintain Lambda in-memory cache as L1 for sub-10ms hot path
- **FR-006**: System MUST detect market hours and only fetch fresh data for current candle during trading
- **FR-007**: System MUST NOT break existing frontend consumption (panning, resolution switching)

### Key Entities

**OHLC Cache Item**:
- **ticker**: Stock symbol (e.g., "AAPL")
- **source**: Data provider (e.g., "tiingo", "finnhub")
- **resolution**: Time bucket size (e.g., "5m", "1h", "D")
- **timestamp**: Candle start time (ISO8601)
- **open/high/low/close**: Price values
- **volume**: Trading volume (if available)

**Table Design** (aligned with existing sentiment-timeseries pattern):
```
PK: {ticker}#{source}       (e.g., "AAPL#tiingo")
SK: {resolution}#{timestamp} (e.g., "5m#2025-12-27T10:30:00Z")
```

This enables:
- Efficient range queries: `PK = "AAPL#tiingo" AND SK BETWEEN "5m#2025-12-01" AND "5m#2025-12-31"`
- Resolution isolation: Different resolutions don't interfere
- Source tracking: Know where data came from

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: External API calls reduced by 90%+ for repeat requests
- **SC-002**: Historical data queries complete in <100ms (vs 500ms+ from external API)
- **SC-003**: Pan/zoom operations complete in <100ms per range query
- **SC-004**: Zero regression in frontend functionality (charts render correctly)
- **SC-005**: Cache hit rate exceeds 80% after initial population

## Technical Notes

### Industry Best Practices Referenced

1. **Write-Through Cache Pattern**: Data written to cache simultaneously with persistent store
2. **Single Table Design**: DynamoDB best practice - one table with composite keys
3. **Composite Sort Key**: `resolution#timestamp` enables efficient range queries within partition
4. **Lambda Global Scope**: In-memory cache survives across warm invocations (AWS best practice CS-005)

### Alignment with Existing Architecture

The existing `sentiment-timeseries` table uses:
- PK: `{ticker}#{resolution}`
- SK: ISO8601 timestamp

The OHLC cache will follow the same pattern with slight modification to include source:
- PK: `{ticker}#{source}`
- SK: `{resolution}#{timestamp}`

This ensures:
- Consistent query patterns across tables
- Familiar codebase patterns
- No breaking changes to sentiment data flow

### Future Work (Out of Scope)

- TTL-based expiration for storage cost management
- Automatic backfill for historical gaps
- Update sentiment article data when updates available

# Feature Specification: OHLC Cache Key Normalization

**Feature Branch**: `1078-ohlc-cache-key-normalization`
**Created**: 2025-12-28
**Status**: Draft

## Problem Statement

The OHLC response cache (Feature 1076) has 0% cache hit rate because the cache key includes dynamically calculated dates. Every request generates a unique cache key, causing all requests to miss the cache and hit the Tiingo API, resulting in 429 rate limit errors after ~10 resolution clicks.

**Root Cause**: When users don't provide custom dates, `end_date = date.today()` is calculated fresh on every request. Combined with resolution and ticker, this creates unique cache keys.

**Example**:
- Request at 10:00: `ohlc:AAPL:5:2024-10-28:2024-11-27`
- Request at 10:01: `ohlc:AAPL:5:2024-10-28:2024-11-27` (same, but...)
- Request next day: `ohlc:AAPL:5:2024-10-29:2024-11-28` (DIFFERENT!)

## User Scenarios & Testing

### User Story 1 - Rapid Resolution Switching Without 429 (Priority: P1)

As a user, I want to switch between resolution buckets rapidly without triggering rate limit errors, so I can explore price data at different granularities.

**Acceptance Scenarios**:

1. **Given** user is viewing AAPL chart, **When** user clicks 10 different resolution buttons in 10 seconds, **Then** no 429 errors occur
2. **Given** user clicked 5m resolution earlier, **When** user clicks 5m again, **Then** data loads from cache (fast response)

---

### User Story 2 - Cache Hits for Same Resolution (Priority: P1)

As a user, I expect switching back to a previously viewed resolution to be instant, since the data was already fetched.

**Acceptance Scenarios**:

1. **Given** user viewed AAPL at 5m resolution, **When** user switches to 15m then back to 5m, **Then** 5m data loads instantly from cache

---

### Edge Cases

- What happens when cache key normalization crosses date boundaries? (Use UTC date for consistency)
- What if user provides custom date range? (Use exact dates for cache key, not normalized)

## Requirements

### Functional Requirements

- **FR-001**: System MUST normalize cache keys to use ticker + resolution only (not date range)
- **FR-002**: System MUST use separate cache entries for custom date ranges vs predefined ranges
- **FR-003**: System MUST use UTC date for cache key consistency across time zones
- **FR-004**: Cache hit rate SHOULD be > 80% for repeated resolution switches

### Key Entities

- **CacheKey**: `ohlc:{ticker}:{resolution}:{range_type}` where range_type is `1W|1M|3M|6M|1Y|custom:{start}:{end}`

## Success Criteria

- **SC-001**: Users can click 10 resolution buckets in 10 seconds without 429 errors
- **SC-002**: Cache hit rate > 80% for session with multiple resolution switches
- **SC-003**: Repeated clicks on same resolution load from cache (<50ms response)

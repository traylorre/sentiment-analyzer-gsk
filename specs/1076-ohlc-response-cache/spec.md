# Feature Specification: OHLC Response Cache

**Feature Branch**: `1076-ohlc-response-cache`
**Created**: 2025-12-27
**Status**: Draft
**Input**: User description: "Add module-level OHLC response cache in Dashboard Lambda to eliminate 429 rate limit errors when users rapidly click resolution buckets"

## Problem Statement

When users rapidly click resolution buckets on the Price Chart (e.g., switching between 1m, 5m, 15m, 1h), they trigger 429 (Too Many Requests) errors. The root cause is that each resolution change calls the Tiingo external API directly, with only a 5-minute adapter-level cache that's lost on Lambda cold starts.

**Comparison with Sentiment API**: The Sentiment API doesn't have this issue because it queries internal DynamoDB data, which has no rate limits. The OHLC API calls external Tiingo API, which has aggressive rate limiting.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolution Switching Without Errors (Priority: P1)

As a user viewing the Price Chart, I want to switch between resolution buckets (1m, 5m, 15m, etc.) without encountering rate limit errors, so that I can explore price data at different granularities.

**Why this priority**: Core functionality - users cannot explore price data if they hit 429 errors after 3-5 clicks.

**Independent Test**: Can be tested by clicking 10 resolution buckets in rapid succession and verifying no 429 errors occur.

**Acceptance Scenarios**:

1. **Given** user is viewing AAPL at 1-minute resolution, **When** user clicks 5-minute, 15-minute, 1-hour, 1-day resolution buttons in quick succession (within 5 seconds), **Then** all resolution changes succeed without 429 errors
2. **Given** a previously viewed ticker+resolution combination exists in cache, **When** user switches back to that combination, **Then** data loads instantly from cache without external API call

---

### User Story 2 - Warm Lambda Response Time (Priority: P2)

As a user, I want repeated chart views to load faster than initial views, so that my experience feels responsive.

**Why this priority**: User experience improvement - cached responses should be noticeably faster.

**Independent Test**: Can be tested by measuring response time for first vs second request for same ticker+resolution.

**Acceptance Scenarios**:

1. **Given** AAPL 5-minute data is already cached from previous request, **When** user requests same ticker+resolution, **Then** response completes in under 50ms (vs 500-2000ms for external API)
2. **Given** cache is near capacity (256 entries), **When** new data needs caching, **Then** oldest entries are evicted without affecting response time

---

### User Story 3 - Cache Staleness Handling (Priority: P3)

As a user, I expect fresh price data when market conditions change, so that cached data doesn't become misleading.

**Why this priority**: Data freshness matters for informed decisions but less critical than preventing errors.

**Independent Test**: Can be tested by verifying cache entry timestamps and TTL expiration.

**Acceptance Scenarios**:

1. **Given** 1-minute resolution cache entry is older than 5 minutes, **When** user requests that data, **Then** fresh data is fetched from external API
2. **Given** daily resolution cache entry is older than 1 hour, **When** user requests that data, **Then** fresh data is fetched from external API

---

### Edge Cases

- What happens when cache is full and new data arrives? (LRU eviction)
- How does system handle concurrent requests for same ticker+resolution? (deduplicate or allow through)
- What happens when external API is temporarily down? (serve stale cache if available)
- How does system handle different date ranges for same ticker+resolution? (different cache keys)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST cache OHLC responses at the Lambda module level (similar to sentiment.py pattern)
- **FR-002**: System MUST use cache key format: `{ticker}#{resolution}#{start_date}#{end_date}`
- **FR-003**: System MUST enforce resolution-specific TTLs:
  - 1-minute: 5 minutes TTL
  - 5-minute to 30-minute: 15 minutes TTL
  - Hourly: 30 minutes TTL
  - Daily: 1 hour TTL
- **FR-004**: System MUST limit cache to 256 entries maximum
- **FR-005**: System MUST evict oldest entries when cache reaches capacity (LRU eviction)
- **FR-006**: System MUST track cache hit/miss statistics for observability
- **FR-007**: System MUST log cache state periodically for debugging

### Key Entities

- **OHLCCacheEntry**: Represents a cached response with key, value, timestamp, and TTL
- **CacheStats**: Tracks hits, misses, evictions for monitoring

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can switch between 10 resolution buckets in 5 seconds without any 429 errors
- **SC-002**: Cached responses load in under 50ms (vs 500-2000ms for external API)
- **SC-003**: Cache hit rate exceeds 80% for typical user session (switching between 5-6 resolutions)
- **SC-004**: External API call volume reduced by at least 50% for warm Lambda invocations

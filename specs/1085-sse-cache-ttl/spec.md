# Feature Specification: Fix SSE 429 Rate Limit

**Feature Branch**: `1085-sse-cache-ttl`
**Created**: 2025-12-28
**Status**: Draft
**Input**: User description: "Fix SSE 429 Rate Limit by increasing METRICS_CACHE_TTL. Current TTL (60s) equals METRICS_INTERVAL (60s), causing cache to expire right before SSE needs it. Increase TTL to 300s to ensure cache serves multiple SSE intervals."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Real-Time Updates (Priority: P1)

A user viewing the dashboard receives real-time metric updates via SSE without seeing 429 errors in the console or experiencing connection drops. The dashboard updates smoothly every 60 seconds with the latest sentiment metrics.

**Why this priority**: User reported this as "TOTALLY UNACCEPTABLE" - 429 errors cause the SSE stream to fail, breaking real-time updates which are a core dashboard feature.

**Independent Test**: Open dashboard, watch network tab for 5+ minutes. Verify no 429 errors and metrics events arrive every 60 seconds.

**Acceptance Scenarios**:

1. **Given** dashboard is connected via SSE, **When** 5 minutes pass, **Then** all metrics events are received without 429 errors
2. **Given** multiple browser tabs have SSE connections, **When** they all request metrics, **Then** cache serves shared data without exceeding rate limits

---

### Edge Cases

- Cache expires during high traffic - should gracefully handle one refresh per 300s
- Lambda cold start with empty cache - first request populates cache for subsequent requests
- Multiple Lambda instances - each has independent cache (acceptable for this fix)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST cache metrics query results for at least 5 minutes (300 seconds)
- **FR-002**: System MUST serve cached metrics to all SSE connections within TTL window
- **FR-003**: System MUST reduce database queries by at least 5x (from every 60s to every 300s)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero 429 errors in SSE connections over 30 minute observation period
- **SC-002**: Metrics cache hit rate exceeds 80% during normal operation
- **SC-003**: Database read capacity consumption reduced by 80%
- **SC-004**: Dashboard receives metrics updates every 60 seconds without interruption

## Technical Notes

Root cause: `METRICS_CACHE_TTL = 60` and `METRICS_INTERVAL = 60` are equal. When SSE requests metrics at T=60s, cache expired at T=60s, forcing a new DB query. With multiple connections, this causes rate limiting.

Fix: Increase `METRICS_CACHE_TTL` from 60 to 300 seconds. This ensures:
- 5 SSE metrics intervals (60s each) served from single cache entry
- Reduces DB queries from 1/minute to 1/5minutes per Lambda instance
- Cache hit rate improves from ~0% to ~80%

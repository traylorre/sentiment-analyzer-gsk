# Dashboard Resolution Config

Feature-1021 | Parent: [1009-realtime-multi-resolution](../1009-realtime-multi-resolution/spec.md) | Task: T068

## Purpose

Add resolution configuration to the dashboard's config.js to enable multi-resolution timeseries functionality on the client side. The dashboard currently lacks configuration for the 8 resolution levels needed by the realtime multi-resolution feature.

## Context

The backend timeseries library (`src/lib/timeseries/models.py`) defines 8 resolution levels (1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h) with corresponding duration_seconds and ttl_seconds values. The dashboard needs matching configuration to:

1. Display resolution options in the UI
2. Request appropriate endpoints with resolution parameters
3. Configure client-side cache TTLs aligned with server TTLs

## User Stories

### US1: Resolution Selector Display

**As a** dashboard user
**I want to** see all 8 resolution options in the time selector
**So that** I can choose the granularity of sentiment data to view

**Acceptance Criteria:**
- [ ] AC-1.1: All 8 resolutions visible: 1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h
- [ ] AC-1.2: Display names are human-readable: "1 min", "5 min", etc.
- [ ] AC-1.3: Default resolution is 5m (per FR-002)

### US2: Timeseries API Configuration

**As a** dashboard developer
**I want to** have configured timeseries endpoints
**So that** API calls include the correct resolution parameter

**Acceptance Criteria:**
- [ ] AC-2.1: TIMESERIES endpoint configured: /api/v2/timeseries/{ticker}
- [ ] AC-2.2: STREAM endpoint already exists, ensure resolution support
- [ ] AC-2.3: Resolution passed as query parameter: ?resolution=5m

### US3: Client Cache Alignment

**As a** dashboard
**I want to** cache timeseries data with appropriate TTLs
**So that** cache invalidation matches server-side TTLs

**Acceptance Criteria:**
- [ ] AC-3.1: Each resolution has a matching cache TTL
- [ ] AC-3.2: TTLs match server values from Resolution.ttl_seconds
- [ ] AC-3.3: Cache configuration is immutable (Object.freeze)

## Functional Requirements

| ID | Requirement | Source |
|----|-------------|--------|
| FR-001 | RESOLUTIONS object with all 8 resolution levels | T068 |
| FR-002 | Each resolution has: key, displayName, durationSeconds, ttlSeconds | T068 |
| FR-003 | TIMESERIES endpoint template: /api/v2/timeseries/{ticker} | T068 |
| FR-004 | Default resolution constant: DEFAULT_RESOLUTION = '5m' | FR-002 |
| FR-005 | RESOLUTION_ORDER array for UI display order | T068 |
| FR-006 | Object.freeze on RESOLUTIONS to prevent mutation | T068 |

## Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-001 | Config file size increase < 2KB | < 2KB |
| NFR-002 | No runtime API calls for config | Zero API calls |
| NFR-003 | Backwards compatible with existing code | No breaking changes |

## Success Criteria

| ID | Criterion | Validation Method |
|----|-----------|-------------------|
| SC-001 | All 8 resolutions defined in config | Code review |
| SC-002 | TTL values match server Resolution.ttl_seconds | Unit test |
| SC-003 | TIMESERIES endpoint returns 200 with resolution param | E2E test |
| SC-004 | Existing CONFIG.ENDPOINTS unchanged | Regression test |
| SC-005 | Config is frozen/immutable | Unit test |

## Out of Scope

- Resolution selector UI component (T069)
- Timeseries chart rendering
- IndexedDB cache implementation
- SSE stream resolution switching

## Dependencies

- `src/lib/timeseries/models.py` - Source of truth for resolution values
- `src/dashboard/config.js` - File to modify
- Existing ENDPOINTS configuration must remain unchanged

## Technical Notes

### Resolution Value Mapping

From `Resolution.ttl_seconds` in models.py:

| Resolution | Duration (s) | TTL (s) | Display Name |
|------------|-------------|---------|--------------|
| 1m | 60 | 21600 | 1 min |
| 5m | 300 | 43200 | 5 min |
| 10m | 600 | 86400 | 10 min |
| 1h | 3600 | 604800 | 1 hour |
| 3h | 10800 | 1209600 | 3 hours |
| 6h | 21600 | 2592000 | 6 hours |
| 12h | 43200 | 5184000 | 12 hours |
| 24h | 86400 | 7776000 | 24 hours |

### Endpoint Format

```javascript
ENDPOINTS: {
    // Existing endpoints (unchanged)
    SENTIMENT: '/api/v2/sentiment',
    TRENDS: '/api/v2/trends',
    ARTICLES: '/api/v2/articles',
    METRICS: '/api/v2/metrics',
    STREAM: '/api/v2/stream',

    // New endpoint
    TIMESERIES: '/api/v2/timeseries'  // Append /{ticker}?resolution=5m
}
```

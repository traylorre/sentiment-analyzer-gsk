# Research: Validate Resolution Switching Performance

**Feature**: 1018-validate-resolution-switching-perf
**Date**: 2025-12-22

## Research Questions Resolved

### RQ-001: How to measure perceived resolution switch latency?

**Decision**: Use browser Performance API with `performance.mark()` and `performance.measure()`

**Rationale**:
- Performance API provides sub-millisecond precision (DOMHighResTimeStamp)
- Designed specifically for user-perceived timing measurements
- Already partially implemented in `switchResolution()` at line 188 of timeseries.js (`performance.now()`)
- W3C standard [CS-002], widely supported in all modern browsers

**Alternatives Considered**:
| Alternative | Reason Rejected |
|-------------|-----------------|
| `Date.now()` | Millisecond precision only, not designed for performance |
| `console.time()` | Output to console only, not programmatically accessible |
| Third-party RUM libraries | Overkill for single-feature validation |

### RQ-002: How to run 100+ automated resolution switches in Playwright?

**Decision**: Use Playwright's `page.click()` on resolution buttons with timing captured via `page.evaluate()`

**Rationale**:
- Playwright is already used for E2E tests in this project (pytest-playwright)
- `page.evaluate()` allows reading JavaScript variables from browser context
- Built-in wait mechanisms for DOM stability
- Headless mode for CI execution

**Alternatives Considered**:
| Alternative | Reason Rejected |
|-------------|-----------------|
| Selenium | Slower setup, less maintained Python bindings |
| Puppeteer | Chromium-only, Playwright has broader browser support |
| Manual scripting | Not reproducible in CI |

### RQ-003: How to calculate percentiles (p50, p90, p95, p99)?

**Decision**: Use Python `statistics.quantiles()` (stdlib) or `numpy.percentile()` in test assertions

**Rationale**:
- Python stdlib `statistics` module available without additional dependencies
- `statistics.quantiles()` added in Python 3.8, project uses 3.13
- pytest assertions integrate naturally with Python calculation
- numpy available if more advanced stats needed (already in requirements)

**Implementation Pattern**:
```python
import statistics

measurements = [m['duration_ms'] for m in switch_metrics]
p95 = statistics.quantiles(measurements, n=100)[94]  # 95th percentile
assert p95 < 100, f"p95 latency {p95}ms exceeds 100ms threshold"
```

### RQ-004: How to differentiate cache-hit vs cache-miss switches?

**Decision**: Tag each switch measurement with `cache_hit: boolean` based on IndexedDB lookup result

**Rationale**:
- Cache misses involve network fetch (variable latency)
- 100ms target applies to cache-hit scenarios (instant switching)
- Tagging allows separate analysis of cache-hit vs cache-miss performance
- Existing `switchResolution()` code already tracks cache path

**Implementation**:
- Check if `timeseriesCache.get()` returned data
- Set `cache_hit = true` if data came from cache
- Set `cache_hit = false` if API fetch was required
- Report separate p95 for cache-hit subset

### RQ-005: What is the definition of "switch complete"?

**Decision**: Switch complete when chart renders with new resolution data (DOM updated)

**Rationale**:
- "Perceived latency" = user sees the result, not just data fetched
- Chart.js `update()` callback indicates visual completion
- Captures full user experience (data fetch + render)
- Matches spec requirement: "chart updates within 100 milliseconds"

**Measurement Points**:
1. **Start**: Resolution button click handler begins
2. **End**: Chart.js canvas updated with new data

## Existing Code Analysis

### Current Instrumentation (timeseries.js:188)

```javascript
async switchResolution(resolution) {
    const startTime = performance.now();
    // ... switch logic ...
    console.log(`Resolution switch completed in ${performance.now() - startTime}ms`);
}
```

**Finding**: Basic timing exists but:
- Only logs to console (not accessible to tests)
- Doesn't capture metadata (from/to resolution, cache hit)
- Uses `performance.now()` not `performance.mark()` (less precise for browser timing)

### Enhancement Plan

Replace inline timing with Performance API marks/measures:
1. Add `performance.mark('resolution-switch-start')` at function entry
2. Add `performance.mark('resolution-switch-end')` after chart update
3. Create measure: `performance.measure('resolution-switch', 'start', 'end')`
4. Expose `window.lastSwitchMetrics` object for Playwright access

## Key Sources Referenced

- [CS-002] W3C Performance Timeline API specification
- [CS-003] W3C User Timing API Level 2
- [CS-005] MDN Performance.measure() documentation
- Parent spec 1009-realtime-multi-resolution SC-002

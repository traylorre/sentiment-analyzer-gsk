# Implementation Plan: Validate Resolution Switching Performance

**Branch**: `1018-validate-resolution-switching-perf` | **Date**: 2025-12-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1018-validate-resolution-switching-perf/spec.md`

## Summary

Validate that resolution switching meets the <100ms p95 latency target (SC-002 from parent spec 1009). This involves:
1. Adding instrumentation to capture switch timing metrics using the browser Performance API
2. Creating a Playwright-based performance test that executes 100+ resolution switches
3. Implementing statistical analysis (min/max/mean/p50/p90/p95/p99) on captured timings
4. Documenting the measurement methodology in `docs/performance-validation.md`

## Technical Context

**Language/Version**: JavaScript (ES6+) for dashboard instrumentation, Python 3.13 for E2E test
**Primary Dependencies**: Performance API (browser), Playwright, pytest, numpy/statistics
**Storage**: N/A (metrics collected in-memory during test run)
**Testing**: Playwright E2E test against preprod, pytest for test runner
**Target Platform**: Chrome/Chromium (headless for CI)
**Project Type**: Web application (frontend instrumentation + E2E test)
**Performance Goals**: p95 < 100ms for resolution switching
**Constraints**: Test must complete 100 switches within 2 minutes total
**Scale/Scope**: Single-user performance test (not load testing)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Deterministic Time Handling | PASS | Uses Performance API which measures wall-clock deltas (valid for performance tests) |
| Unit Test Accompaniment | PASS | Will include unit tests for statistical calculation functions |
| E2E Synthetic Data | PASS | Uses existing preprod with synthetic ticker data |
| External API Mocking | PASS | No external APIs called during resolution switch (uses cached data) |
| TDD Pattern | PASS | Write performance test assertions before measuring actual behavior |
| Implementation Accompaniment | PASS | All new code will have tests |

## Project Structure

### Documentation (this feature)

```text
specs/1018-validate-resolution-switching-perf/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research findings
├── data-model.md        # Data structures for timing metrics
├── quickstart.md        # How to run performance validation
├── checklists/
│   └── requirements.md  # Validation checklist
└── contracts/
    └── metrics-schema.yaml  # Schema for timing output
```

### Source Code (repository root)

```text
src/dashboard/
├── timeseries.js        # MODIFY: Add Performance API instrumentation
└── perf-metrics.js      # NEW: Timing capture and reporting utilities

tests/e2e/
└── test_resolution_switch_perf.py  # NEW: 100+ switch performance test

tests/unit/
└── test_perf_statistics.py  # NEW: Unit tests for stats calculation

docs/
└── performance-validation.md  # NEW: Methodology documentation
```

**Structure Decision**: Minimal additions to existing web application structure. Performance test added to E2E suite, instrumentation added to existing timeseries.js module.

## Phase 0: Research

### RQ-001: How to measure perceived resolution switch latency?

**Decision**: Use browser Performance API with `performance.mark()` and `performance.measure()`
**Rationale**: Performance API provides sub-millisecond precision and is designed for user-perceived timing. Already partially implemented in `switchResolution()` at line 188 of timeseries.js.
**Alternatives**:
- Date.now() - Less precise (millisecond only), not designed for performance measurement
- console.time() - Not programmatically accessible
- Third-party RUM libraries - Overkill for this validation

### RQ-002: How to run 100+ automated resolution switches in Playwright?

**Decision**: Use Playwright's `page.click()` on resolution buttons with timing captured via `page.evaluate()`
**Rationale**: Playwright provides excellent browser automation and can execute JavaScript to read Performance API measurements.
**Alternatives**:
- Selenium - Slower, more complex setup
- Puppeteer - Chromium-only, Playwright is more maintained
- Manual scripting - Not reproducible in CI

### RQ-003: How to calculate percentiles (p50, p90, p95, p99)?

**Decision**: Use Python `numpy.percentile()` or `statistics.quantiles()` in test assertions
**Rationale**: Standard library or numpy provide efficient, well-tested percentile calculations.
**Alternatives**:
- Manual sorting and calculation - Error-prone
- JavaScript-side calculation - Harder to integrate with pytest assertions

### RQ-004: How to differentiate cache-hit vs cache-miss switches?

**Decision**: Tag each switch measurement with `cacheHit: boolean` based on whether data was in IndexedDB
**Rationale**: Cache misses require network fetch and will be slower; must validate p95 for cache-hit scenarios specifically.
**Alternatives**:
- Ignore cache state - Would conflate network latency with switch latency
- Warm cache before test - Doesn't capture real-world first-switch behavior

### RQ-005: What is the definition of "switch complete"?

**Decision**: Switch complete when chart renders with new resolution data (DOM updated)
**Rationale**: "Perceived latency" means user sees the result, not just data fetched.
**Alternatives**:
- Data fetch complete - Doesn't account for render time
- Button click processed - Too early, user hasn't seen result

## Phase 1: Design

### Instrumentation Design

Add to `timeseries.js`:
```javascript
// At start of switchResolution()
performance.mark('resolution-switch-start');

// After chart.update() completes
performance.mark('resolution-switch-end');
performance.measure('resolution-switch', 'resolution-switch-start', 'resolution-switch-end');

// Capture metadata
const entry = performance.getEntriesByName('resolution-switch').pop();
window.lastSwitchMetrics = {
    duration_ms: entry.duration,
    from_resolution: previousResolution,
    to_resolution: newResolution,
    cache_hit: dataFromCache,
    timestamp: Date.now()
};
```

### Performance Test Design

Playwright test flow:
1. Navigate to dashboard with warm cache (pre-fetch all resolutions)
2. For each of 100+ iterations:
   - Record current resolution
   - Click next resolution button
   - Wait for render complete
   - Capture `window.lastSwitchMetrics`
3. Collect all metrics
4. Calculate statistics (min, max, mean, p50, p90, p95, p99)
5. Assert p95 < 100ms

### Output Schema

```yaml
performance_report:
  test_name: "resolution_switching_performance"
  timestamp: "2025-12-22T10:30:00Z"
  sample_count: 100
  statistics:
    min_ms: 12.5
    max_ms: 145.2
    mean_ms: 42.3
    p50_ms: 38.1
    p90_ms: 78.4
    p95_ms: 92.1
    p99_ms: 118.5
  passed: true
  threshold_ms: 100
  measurements:
    - duration_ms: 12.5
      from_resolution: "1m"
      to_resolution: "5m"
      cache_hit: true
      timestamp: 1703240000000
    # ... 99 more entries
```

## Complexity Tracking

No violations requiring justification. Feature is a focused validation/testing addition.

## Phase 2: Tasks

*Created by `/speckit.tasks` command - not part of /speckit.plan output*

## Next Steps

1. Run `/speckit.tasks` to generate implementation tasks
2. Run `/speckit.implement` to execute tasks
3. Merge PR with validated performance results

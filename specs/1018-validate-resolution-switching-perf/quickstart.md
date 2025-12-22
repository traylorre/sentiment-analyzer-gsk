# Quickstart: Validate Resolution Switching Performance

**Feature**: 1018-validate-resolution-switching-perf
**Date**: 2025-12-22

## Prerequisites

1. Preprod environment deployed with multi-resolution dashboard
2. Python 3.13+ with pytest and playwright
3. Playwright browsers installed (`playwright install chromium`)

## Running the Performance Test

### Quick validation (local)

```bash
# Install dependencies if not already done
pip install pytest-playwright numpy

# Install Playwright browsers
playwright install chromium

# Run performance validation test
pytest tests/e2e/test_resolution_switch_perf.py -v --headed

# Run headless (CI mode)
pytest tests/e2e/test_resolution_switch_perf.py -v
```

### CI execution

The test runs automatically as part of E2E test suite in GitHub Actions:

```bash
make test-e2e  # Includes performance validation
```

## Interpreting Results

### Successful output

```
tests/e2e/test_resolution_switch_perf.py::test_resolution_switch_p95_under_100ms PASSED

Performance Report:
  sample_count: 100
  min_ms: 12.5
  max_ms: 87.3
  mean_ms: 35.2
  p50_ms: 32.1
  p90_ms: 58.4
  p95_ms: 72.3  ← Target: <100ms ✓
  p99_ms: 84.1
  passed: True
```

### Failure output

```
tests/e2e/test_resolution_switch_perf.py::test_resolution_switch_p95_under_100ms FAILED

AssertionError: p95 latency 112.5ms exceeds 100ms threshold

Performance breakdown:
  Cache-hit switches (n=78): p95 = 45.2ms ✓
  Cache-miss switches (n=22): p95 = 185.3ms ✗  ← Investigate API latency
```

## Troubleshooting

### Test takes too long

- Normal execution: 100 switches in ~60 seconds
- If taking >2 minutes: Check network latency, browser performance
- Solution: Run on faster machine or reduce sample count for debugging

### High p95 on cache misses

Cache misses require API fetch. If p95 is high:
1. Check preprod API response times
2. Verify IndexedDB cache is warming correctly
3. Consider pre-fetching all resolutions before test loop

### Flaky results

Performance tests can vary based on:
- Browser warmup (first few switches may be slower)
- Network conditions (for cache misses)
- Machine load

Solution: Test discards first 5 warm-up switches from statistics.

## Manual verification

Open browser console and trigger resolution switch manually:

```javascript
// In browser dev tools console
timeseriesManager.switchResolution('1h');

// Check timing
console.log(window.lastSwitchMetrics);
// { duration_ms: 42.5, from_resolution: "5m", to_resolution: "1h", cache_hit: true, ... }
```

## Documentation

Full methodology documented at `docs/performance-validation.md`

## Related

- Parent spec: `specs/1009-realtime-multi-resolution/spec.md` (SC-002)
- Dashboard code: `src/dashboard/timeseries.js`
- Cache implementation: `src/dashboard/cache.js`

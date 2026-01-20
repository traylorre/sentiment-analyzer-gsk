# Performance Validation Methodology

This document describes how performance is measured and validated for the Sentiment Analyzer dashboard.

## Performance Targets

| Metric | Target | Spec |
|--------|--------|------|
| Resolution switching | p95 < 100ms | SC-002 |
| Live update latency | p95 < 3000ms | SC-003 |

---

## Part 1: Resolution Switching Performance

Resolution switching latency measures the time from when a user clicks a resolution button to when the chart is visually updated.

### Instrumentation

The dashboard JavaScript (`src/dashboard/timeseries.js`) includes Performance API instrumentation:

```javascript
// At start of switchResolution()
performance.mark('resolution-switch-start');

// After chart.update() completes
performance.mark('resolution-switch-end');
performance.measure('resolution-switch', 'start', 'end');

// Metrics exposed for testing
window.lastSwitchMetrics = {
    duration_ms: entry.duration,
    from_resolution: previousResolution,
    to_resolution: newResolution,
    cache_hit: cacheHit,
    timestamp: Date.now()
};
```

### What "Perceived Latency" Means

The measurement captures **user-perceived latency**:

1. **Start**: When the user clicks a resolution button
2. **End**: When the chart is visually updated with new data

This includes:
- Cache lookup time
- API fetch time (if cache miss)
- Chart rendering time

This excludes:
- SSE reconnection (happens after switch completes)
- Subsequent live updates

### Running Resolution Switching Tests

#### Prerequisites

1. Playwright installed: `pip install pytest-playwright && playwright install chromium`
2. Preprod environment deployed with multi-resolution dashboard

#### Run Locally (with browser visible)

```bash
pytest tests/e2e/test_resolution_switch_perf.py -v --headed
```

#### Run Headless (CI mode)

```bash
pytest tests/e2e/test_resolution_switch_perf.py -v
```

#### Run Specific Test

```bash
# Just the main p95 validation
pytest tests/e2e/test_resolution_switch_perf.py::TestResolutionSwitchPerformance::test_resolution_switch_p95_under_100ms -v
```

### Interpreting Resolution Switching Results

#### Successful Output

```
Performance Report:
{
  "test_name": "resolution_switching_performance",
  "sample_count": 105,
  "statistics": {
    "min_ms": 12.5,
    "max_ms": 87.3,
    "mean_ms": 35.2,
    "p50_ms": 32.1,
    "p90_ms": 58.4,
    "p95_ms": 72.3,    ← Target: <100ms ✓
    "p99_ms": 84.1
  },
  "passed": true,
  "threshold_ms": 100
}
```

**Key metrics:**
- **p95_ms**: The 95th percentile latency - 95% of switches complete faster than this
- **cache_hit**: Whether data came from IndexedDB (faster) or API (slower)
- **sample_count**: Should be 100+ for statistical significance

#### Failure Output

```
AssertionError: p95 latency 112.5ms exceeds 100ms threshold.
Statistics: min=15.2ms, max=245.3ms, mean=68.4ms, p95=112.5ms
```

**Common causes:**
1. Cache not warming properly
2. API latency higher than expected
3. Browser performance issues
4. Network latency to preprod

### Resolution Switching Troubleshooting

#### High p95 on Cache Misses

Cache misses require API fetch. If p95 is high:

1. **Check preprod API latency**: `curl -w "%{time_total}" <API_URL>`
2. **Verify cache is working**: Check browser IndexedDB has data
3. **Consider warming cache**: Test pre-fetches all resolutions before measuring

#### Flaky Results

Performance tests can vary based on:
- Browser warmup (first switches may be slower)
- Network conditions
- Machine load

**Solutions:**
- Test discards first 5 "warmup" switches from statistics
- Run tests multiple times and compare p95 trends
- Ensure consistent test environment

---

## Part 2: Live Update Latency

Live update latency measures the end-to-end time from when sentiment data is created (`origin_timestamp`) to when the client receives the event via SSE.

### Latency Breakdown

The end-to-end latency consists of 5 components:

| Component | Typical Range | Notes |
|-----------|---------------|-------|
| Analysis Lambda | 50-200ms | ML model inference time |
| SNS Publish | 10-50ms | Publish to notification topic |
| SQS Delivery | 50-100ms | Message visibility and polling |
| SSE Lambda Processing | 5-10ms | Event serialization |
| Network (client) | 50-500ms | Variable by client location |

**Total Budget**: < 3000ms for p95 (SC-003)

### Running the E2E Latency Test

#### Prerequisites

1. Install Playwright: `pip install playwright && playwright install chromium`
2. Set environment variable: `export PREPROD_DASHBOARD_URL=https://dashboard.preprod.example.com`

#### Run the Test

```bash
# Run latency validation test
pytest tests/e2e/test_live_update_latency.py -v -m preprod

# Run with detailed output
pytest tests/e2e/test_live_update_latency.py::TestLiveUpdateLatency::test_live_update_p95_under_3_seconds -v -s
```

#### Expected Output

```
Latency Report: {
  "min_ms": 89,
  "max_ms": 1523,
  "mean_ms": 312.45,
  "p50_ms": 234.0,
  "p90_ms": 567.0,
  "p95_ms": 890.0,
  "p99_ms": 1234.0,
  "sample_count": 52,
  "clock_skew_count": 0
}
```

#### Test Pass Criteria

- `p95_ms < 3000` (SC-003)
- `sample_count >= 10` (statistical validity)

### CloudWatch Logs Insights Queries

The SSE streaming Lambda logs latency metrics in structured JSON format. Use these queries to analyze production latency.

#### Overall Percentiles

```sql
fields @timestamp, latency_ms
| filter event_type = "bucket_update"
| stats pctile(latency_ms, 50) as p50,
        pctile(latency_ms, 90) as p90,
        pctile(latency_ms, 95) as p95,
        pctile(latency_ms, 99) as p99,
        count(*) as sample_count
```

#### Percentiles by Ticker

```sql
fields @timestamp, latency_ms, ticker
| filter event_type = "bucket_update"
| stats pctile(latency_ms, 95) as p95, count(*) as count by ticker
| sort p95 desc
```

#### Hourly Latency Trend

```sql
fields @timestamp, latency_ms
| filter event_type = "bucket_update"
| stats pctile(latency_ms, 95) as p95,
        avg(latency_ms) as avg_ms,
        count(*) as count
  by bin(1h)
| sort @timestamp
```

#### Cold Start Impact

```sql
fields @timestamp, latency_ms, is_cold_start
| filter event_type = "bucket_update"
| stats pctile(latency_ms, 95) as p95,
        avg(latency_ms) as avg_ms,
        count(*) as count
  by is_cold_start
```

#### Find High Latency Events

```sql
fields @timestamp, latency_ms, ticker, resolution, is_cold_start
| filter event_type = "bucket_update" and latency_ms > 2000
| sort latency_ms desc
| limit 50
```

### Live Update Latency Troubleshooting

#### Symptom: p95 > 3000ms

**Check cold starts**:
- Run cold start impact query
- If cold start latency significantly higher, consider provisioned concurrency

**Check by ticker**:
- Run percentiles by ticker query
- High-volume tickers may have different latency profiles

#### Symptom: Many clock skew events

**Cause**: Client clock is behind server clock

**Resolution**:
- Client should enable NTP synchronization
- Latency samples with negative values are excluded from statistics

#### Symptom: Increasing latency over time

**Check hourly trend query**:
- Identify when latency started increasing
- Correlate with deployment events or traffic spikes

**Potential causes**:
- Lambda memory pressure (increase memory allocation)
- DynamoDB throttling (check consumed capacity)
- SQS backlog (check ApproximateNumberOfMessagesVisible)

### Client-Side Metrics

The dashboard exposes latency metrics via `window.lastLatencyMetrics`:

```javascript
// In browser console
console.log(window.lastLatencyMetrics);
// Output:
// {
//   latency_ms: 234,
//   event_type: "bucket_update",
//   ticker: "AAPL",
//   origin_timestamp: "2024-12-22T10:35:47.123Z",
//   receive_timestamp: "2024-12-22T10:35:47.357Z",
//   is_clock_skew: false
// }

// Get all latency samples
console.log(window.latencySamples);
// Output: [234, 189, 312, ...]
```

---

## Adding New Performance Validations

To add a new performance metric:

### 1. Add Instrumentation

In the relevant JavaScript file:

```javascript
const switchId = `your-metric-${Date.now()}`;
performance.mark(`${switchId}-start`);

// ... code being measured ...

performance.mark(`${switchId}-end`);
performance.measure(switchId, `${switchId}-start`, `${switchId}-end`);

const entry = performance.getEntriesByName(switchId, 'measure')[0];
window.yourMetric = { duration_ms: entry.duration, ... };

// Clean up
performance.clearMarks(`${switchId}-start`);
performance.clearMarks(`${switchId}-end`);
performance.clearMeasures(switchId);
```

### 2. Add E2E Test

Create `tests/e2e/test_your_metric_perf.py`:

```python
def capture_metrics(page: Page) -> dict:
    return page.evaluate("() => window.yourMetric")

def test_your_metric_p95_under_threshold(self, page: Page):
    measurements = []
    for _ in range(100):
        # Trigger action
        metrics = capture_metrics(page)
        measurements.append(metrics['duration_ms'])

    p95 = calculate_percentile(measurements, 95)
    assert p95 < YOUR_THRESHOLD_MS
```

### 3. Document

Add section to this document explaining:
- What metric measures
- How to run the test
- How to interpret results
- Troubleshooting steps

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PREPROD_DASHBOARD_URL` | `https://preprod.sentiment.example.com` | Dashboard URL for E2E tests |

## Related Files

- **Resolution Switching Instrumentation**: `src/dashboard/timeseries.js`
- **Resolution Switching Test**: `tests/e2e/test_resolution_switch_perf.py`
- **Latency Test**: `tests/e2e/test_live_update_latency.py`
- **Parent Spec**: `specs/1009-realtime-multi-resolution/spec.md` (SC-002, SC-003)
- **Resolution Switching Spec**: `specs/1018-validate-resolution-switching-perf/spec.md`
- **Latency Validation Spec**: `specs/1019-validate-live-update-latency/spec.md`
- [CloudWatch Logs Insights Query Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)

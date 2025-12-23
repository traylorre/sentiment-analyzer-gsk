# Performance Validation: Live Update Latency

This document describes how to validate the live update latency SLA (SC-003: p95 < 3 seconds) for the sentiment analysis dashboard.

## Overview

The dashboard receives real-time sentiment updates via Server-Sent Events (SSE). End-to-end latency is measured from when sentiment data is created (`origin_timestamp`) to when the client receives the event.

## Latency Breakdown

The end-to-end latency consists of 5 components:

| Component | Typical Range | Notes |
|-----------|---------------|-------|
| Analysis Lambda | 50-200ms | ML model inference time |
| SNS Publish | 10-50ms | Publish to notification topic |
| SQS Delivery | 50-100ms | Message visibility and polling |
| SSE Lambda Processing | 5-10ms | Event serialization |
| Network (client) | 50-500ms | Variable by client location |

**Total Budget**: < 3000ms for p95 (SC-003)

## Running the E2E Latency Test

### Prerequisites

1. Install Playwright: `pip install playwright && playwright install chromium`
2. Set environment variable: `export PREPROD_DASHBOARD_URL=https://dashboard.preprod.example.com`

### Run the Test

```bash
# Run latency validation test
pytest tests/e2e/test_live_update_latency.py -v -m preprod

# Run with detailed output
pytest tests/e2e/test_live_update_latency.py::TestLiveUpdateLatency::test_live_update_p95_under_3_seconds -v -s
```

### Expected Output

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

### Test Pass Criteria

- `p95_ms < 3000` (SC-003)
- `sample_count >= 10` (statistical validity)

## CloudWatch Logs Insights Queries

The SSE streaming Lambda logs latency metrics in structured JSON format. Use these queries to analyze production latency.

### Overall Percentiles

```sql
fields @timestamp, latency_ms
| filter event_type = "bucket_update"
| stats pctile(latency_ms, 50) as p50,
        pctile(latency_ms, 90) as p90,
        pctile(latency_ms, 95) as p95,
        pctile(latency_ms, 99) as p99,
        count(*) as sample_count
```

### Percentiles by Ticker

```sql
fields @timestamp, latency_ms, ticker
| filter event_type = "bucket_update"
| stats pctile(latency_ms, 95) as p95, count(*) as count by ticker
| sort p95 desc
```

### Hourly Latency Trend

```sql
fields @timestamp, latency_ms
| filter event_type = "bucket_update"
| stats pctile(latency_ms, 95) as p95,
        avg(latency_ms) as avg_ms,
        count(*) as count
  by bin(1h)
| sort @timestamp
```

### Cold Start Impact

```sql
fields @timestamp, latency_ms, is_cold_start
| filter event_type = "bucket_update"
| stats pctile(latency_ms, 95) as p95,
        avg(latency_ms) as avg_ms,
        count(*) as count
  by is_cold_start
```

### Find High Latency Events

```sql
fields @timestamp, latency_ms, ticker, resolution, is_cold_start
| filter event_type = "bucket_update" and latency_ms > 2000
| sort latency_ms desc
| limit 50
```

## Troubleshooting High Latency

### Symptom: p95 > 3000ms

**Check cold starts**:
- Run cold start impact query
- If cold start latency significantly higher, consider provisioned concurrency

**Check by ticker**:
- Run percentiles by ticker query
- High-volume tickers may have different latency profiles

### Symptom: Many clock skew events

**Cause**: Client clock is behind server clock

**Resolution**:
- Client should enable NTP synchronization
- Latency samples with negative values are excluded from statistics

### Symptom: Increasing latency over time

**Check hourly trend query**:
- Identify when latency started increasing
- Correlate with deployment events or traffic spikes

**Potential causes**:
- Lambda memory pressure (increase memory allocation)
- DynamoDB throttling (check consumed capacity)
- SQS backlog (check ApproximateNumberOfMessagesVisible)

## Client-Side Metrics

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

## References

- [Parent Spec SC-003](../specs/1009-realtime-multi-resolution/spec.md) - Defines 3s latency target
- [Feature 1019 Spec](../specs/1019-validate-live-update-latency/spec.md) - Latency validation requirements
- [CloudWatch Logs Insights Query Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)

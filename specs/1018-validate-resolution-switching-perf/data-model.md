# Data Model: Validate Resolution Switching Performance

**Feature**: 1018-validate-resolution-switching-perf
**Date**: 2025-12-22

## Entities

### SwitchTiming

A single resolution switch measurement captured by browser instrumentation.

| Field | Type | Description |
|-------|------|-------------|
| `duration_ms` | float | Time from click to render complete (milliseconds) |
| `from_resolution` | string | Starting resolution key (e.g., "1m", "5m") |
| `to_resolution` | string | Target resolution key |
| `cache_hit` | boolean | True if data came from IndexedDB cache |
| `timestamp` | integer | Unix timestamp (milliseconds) when switch occurred |

**Example**:
```json
{
  "duration_ms": 42.5,
  "from_resolution": "1m",
  "to_resolution": "5m",
  "cache_hit": true,
  "timestamp": 1703240000000
}
```

### PerformanceReport

Aggregated statistics from a complete performance test run.

| Field | Type | Description |
|-------|------|-------------|
| `test_name` | string | Identifier for the test (e.g., "resolution_switching_performance") |
| `timestamp` | string | ISO 8601 timestamp when test completed |
| `sample_count` | integer | Number of switches measured |
| `statistics` | StatsSummary | Calculated percentiles and averages |
| `passed` | boolean | True if p95 < threshold |
| `threshold_ms` | float | Target threshold (100ms) |
| `measurements` | array[SwitchTiming] | Raw timing data |

### StatsSummary

Statistical summary of timing measurements.

| Field | Type | Description |
|-------|------|-------------|
| `min_ms` | float | Minimum observed latency |
| `max_ms` | float | Maximum observed latency |
| `mean_ms` | float | Arithmetic mean |
| `p50_ms` | float | 50th percentile (median) |
| `p90_ms` | float | 90th percentile |
| `p95_ms` | float | 95th percentile (key threshold) |
| `p99_ms` | float | 99th percentile |

## Resolution Values

Valid resolution keys used in `from_resolution` and `to_resolution` fields:

| Key | Label | Duration (seconds) |
|-----|-------|-------------------|
| `1m` | 1 Min | 60 |
| `5m` | 5 Min | 300 |
| `10m` | 10 Min | 600 |
| `1h` | 1 Hour | 3600 |
| `3h` | 3 Hour | 10800 |
| `6h` | 6 Hour | 21600 |
| `12h` | 12 Hour | 43200 |
| `24h` | 24 Hour | 86400 |

## State Transitions

```
[Resolution A] --click--> [Switching] --render complete--> [Resolution B]
                  |                            |
                  +-- start timer              +-- stop timer
                                               +-- record SwitchTiming
```

## Validation Rules

1. `duration_ms` must be > 0
2. `from_resolution` and `to_resolution` must be valid resolution keys
3. `from_resolution` != `to_resolution` (switching to same resolution is no-op)
4. `sample_count` must match length of `measurements` array
5. `p95_ms` <= `threshold_ms` for test to pass

# Quickstart: Validate Live Update Latency

**Feature**: 1019-validate-live-update-latency
**Purpose**: Validate that live updates reach the dashboard within 3 seconds (SC-003)

## Prerequisites

- AWS CLI configured with preprod credentials
- Python 3.13 with pytest-playwright installed
- Access to CloudWatch Logs for SSE streaming Lambda

## Running Latency Validation

### 1. Run E2E Latency Test

```bash
# Run the latency validation test
pytest tests/e2e/test_live_update_latency.py -v

# Expected output:
# test_live_update_p95_under_3_seconds PASSED
# Latency Report:
#   p50: 127ms
#   p90: 456ms
#   p95: 890ms
#   p99: 1523ms
#   samples: 100
```

### 2. Query CloudWatch Logs

```bash
# Get p95 latency for last 24 hours
aws logs start-query \
  --log-group-name "/aws/lambda/sse-streaming-lambda" \
  --start-time $(date -d '24 hours ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, latency_ms
    | filter event_type = 'bucket_update'
    | stats pctile(latency_ms, 50) as p50,
            pctile(latency_ms, 90) as p90,
            pctile(latency_ms, 95) as p95,
            pctile(latency_ms, 99) as p99,
            count(*) as sample_count
  "

# Get query results (use query ID from previous command)
aws logs get-query-results --query-id <query-id>
```

### 3. Verify Client-Side Metrics

Open browser console on dashboard and check:

```javascript
// After receiving an SSE event
console.log(window.lastLatencyMetrics);
// Expected: { latency_ms: <number>, event_type: "bucket_update", ... }
```

## Interpreting Results

### Success Criteria

| Metric | Target | Action if Exceeded |
|--------|--------|-------------------|
| p95 latency | < 3000ms | Investigate high latency events |
| p99 latency | < 5000ms | Check for cold starts |
| Sample count | > 100 | Wait for more data |

### Latency Breakdown

| Component | Typical | Budget |
|-----------|---------|--------|
| Analysis Lambda | 50-200ms | 500ms |
| SNS/SQS delivery | 50-150ms | 300ms |
| SSE Lambda | 5-10ms | 100ms |
| Network (client) | 50-500ms | 2000ms |
| **Total** | ~300-800ms | **3000ms** |

## Troubleshooting

### High Latency (> 3s)

1. **Check cold starts**:
   ```bash
   # Query cold start impact
   aws logs start-query --query-string "
     fields latency_ms, is_cold_start
     | filter event_type = 'bucket_update'
     | stats pctile(latency_ms, 95) by is_cold_start
   "
   ```
   - If cold starts are the issue, consider provisioned concurrency

2. **Check by ticker**:
   ```bash
   # Find slow tickers
   aws logs start-query --query-string "
     fields latency_ms, ticker
     | filter event_type = 'bucket_update'
     | stats pctile(latency_ms, 95) as p95 by ticker
     | sort p95 desc
   "
   ```

3. **Check connection count**:
   - High connection count may indicate resource contention

### Negative Latency (Clock Skew)

If `latency_ms < 0` is logged:
1. Client clock is behind server time
2. Document assumption: NTP sync required
3. Use `is_clock_skew: true` to filter these in analysis

### Missing Metrics

If no latency metrics appear:
1. Verify SSE Lambda is deployed with updated code
2. Check CloudWatch Logs for errors
3. Verify `origin_timestamp` field is present in events

## CI Integration

The latency test is included in E2E test suite:

```yaml
# .github/workflows/deploy.yml
- name: Run E2E Tests
  run: |
    pytest tests/e2e/ -v --timeout=300
```

## Related Documentation

- [Performance Validation Guide](../../../docs/performance-validation.md)
- [SSE Streaming Architecture](../../../docs/ARCHITECTURE_DECISIONS.md)
- [Parent Spec SC-003](../1009-realtime-multi-resolution/spec.md)

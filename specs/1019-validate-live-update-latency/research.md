# Research: Validate Live Update Latency

**Feature**: 1019-validate-live-update-latency
**Date**: 2024-12-22

## Research Questions

### RQ1: How to add origin_timestamp without breaking existing clients?

**Context**: SSE events currently have a `timestamp` field representing when the event was generated. We need to add `origin_timestamp` to track when the sentiment data was originally created.

**Decision**: Add `origin_timestamp` as an optional field with default=now. Existing clients ignore unknown fields.

**Rationale**:
- Pydantic models serialize to JSON which is forward-compatible
- The existing `timestamp` field serves different purpose (event generation time)
- `origin_timestamp` represents when sentiment analysis completed
- No breaking change to existing consumers

**Alternatives Rejected**:
| Alternative | Reason Rejected |
|-------------|-----------------|
| Rename `timestamp` to `origin_timestamp` | Breaking change for all clients |
| Send separate timing event | Doubles event count, complex correlation |
| Use HTTP headers for timing | Not applicable to SSE |

---

### RQ2: How to log latency without blocking event delivery?

**Context**: Latency metrics must be logged to CloudWatch for monitoring, but logging should not impact event delivery performance.

**Decision**: Use synchronous structlog logging immediately after event serialization but before network send.

**Rationale**:
- Lambda stdout is automatically captured by CloudWatch Logs
- structlog produces JSON that CloudWatch Logs Insights can query
- Logging is fast (~1ms) and runs within Lambda execution time
- No additional network calls or IAM permissions needed

**Alternatives Rejected**:
| Alternative | Reason Rejected |
|-------------|-----------------|
| CloudWatch Metrics API | Adds ~50-100ms latency per PutMetricData call |
| Background async logging | Complex, Lambda may terminate before flush |
| X-Ray subsegments | Good for tracing, but not for percentile queries |

---

### RQ3: What CloudWatch Logs Insights query calculates percentiles?

**Context**: Need to calculate p50, p90, p95, p99 latency from log entries.

**Decision**: Use `pctile()` aggregation function:

```sql
fields @timestamp, latency_ms
| filter event_type = "bucket_update"
| stats pctile(latency_ms, 50) as p50,
        pctile(latency_ms, 90) as p90,
        pctile(latency_ms, 95) as p95,
        pctile(latency_ms, 99) as p99
```

**Rationale**:
- CloudWatch Logs Insights has native percentile support
- No custom metric infrastructure or cost
- Can query arbitrary time ranges
- Results include count for statistical validity

**Query Variations**:
- By ticker: Add `| group by ticker`
- By time window: Add `| bin(1h)` for hourly buckets
- Exclude cold starts: Add `| filter is_cold_start = false`

---

### RQ4: How should client calculate receive latency?

**Context**: Client-side JavaScript needs to calculate latency when receiving SSE events.

**Decision**: Calculate `Date.now() - Date.parse(origin_timestamp)` and expose via `window.lastLatencyMetrics`.

**Implementation Pattern**:
```javascript
// In SSE event handler
const originTime = Date.parse(event.data.origin_timestamp);
const receiveTime = Date.now();
const latencyMs = receiveTime - originTime;

window.lastLatencyMetrics = {
    latency_ms: latencyMs,
    event_type: event.data.event_type,
    origin_timestamp: event.data.origin_timestamp,
    receive_timestamp: new Date().toISOString()
};
```

**Rationale**:
- Matches T064 pattern (window.lastSwitchMetrics)
- Simple, no external dependencies
- E2E test can read via `page.evaluate(() => window.lastLatencyMetrics)`

**Assumptions**:
- Client clock is NTP-synchronized (within ~1 second of server)
- If clock skew detected (negative latency), log warning

---

### RQ5: What components contribute to end-to-end latency?

**Context**: Understanding latency breakdown helps identify optimization targets.

**Decision**: Document 5 latency components:

| Component | Typical Range | Notes |
|-----------|---------------|-------|
| Analysis Lambda | 50-200ms | Model inference time |
| SNS Publish | 10-50ms | Publish to topic |
| SQS Delivery | 50-100ms | Message visibility |
| SSE Lambda Processing | 5-10ms | Event serialization |
| Network (client) | 50-500ms | Variable by client location |

**Total Budget**: < 3000ms for p95

**Rationale**:
- Each component has different optimization strategies
- Network latency is client-dependent and harder to optimize
- Server-side budget: ~300ms leaves room for network variability

**Optimization Priorities**:
1. Lambda cold starts (use provisioned concurrency if needed)
2. Analysis batch size (smaller = lower latency)
3. SQS visibility timeout tuning

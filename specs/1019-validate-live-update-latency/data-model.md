# Data Model: Validate Live Update Latency

**Feature**: 1019-validate-live-update-latency
**Date**: 2024-12-22

## Extended SSE Event Models

### HeartbeatData (extended)

```python
class HeartbeatData(BaseModel):
    """Heartbeat event with server timestamp for clock sync reference."""

    timestamp: datetime  # Event generation time (existing)
    server_timestamp: datetime  # Alias, same as timestamp (FR-002)
    connections: int
    uptime_seconds: int
```

**Notes**:
- `server_timestamp` is an alias for `timestamp` for explicit client reference
- Clients can use heartbeat to detect clock skew

### BucketUpdateEvent (extended)

```python
class BucketUpdateEvent(BaseModel):
    """Bucket update event with origin timestamp for latency tracking."""

    ticker: str
    resolution: Resolution
    bucket: dict[str, Any]
    timestamp: datetime       # When SSE event was generated
    origin_timestamp: datetime  # NEW: When sentiment data was created (FR-001)
```

**Fields**:
- `timestamp`: When the SSE Lambda serialized the event (existing)
- `origin_timestamp`: When the sentiment analysis completed (new)

### PartialBucketEvent (extended)

```python
class PartialBucketEvent(BucketUpdateEvent):
    """Inherits origin_timestamp from BucketUpdateEvent."""

    progress_pct: float
    is_partial: bool = True
```

---

## LatencyMetric Log Entry

### Schema

```json
{
    "event_type": "bucket_update",
    "ticker": "AAPL",
    "resolution": "5m",
    "origin_timestamp": "2024-12-22T10:35:47.123Z",
    "send_timestamp": "2024-12-22T10:35:47.250Z",
    "latency_ms": 127,
    "is_cold_start": false,
    "connection_count": 5
}
```

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| event_type | string | Event type: "bucket_update", "partial_bucket", "heartbeat" |
| ticker | string | Stock ticker symbol (null for heartbeat) |
| resolution | string | Resolution name: "1m", "5m", etc. (null for heartbeat) |
| origin_timestamp | ISO8601 | When sentiment data was created |
| send_timestamp | ISO8601 | When SSE event was serialized |
| latency_ms | int | Difference: send_timestamp - origin_timestamp |
| is_cold_start | bool | True if this is first event after Lambda init |
| connection_count | int | Active SSE connections when event sent |

### Log Level

Use `INFO` level for latency metrics. Use `WARNING` if latency_ms > 2500 (approaching 3s limit).

---

## Client-Side Latency Metrics

### window.lastLatencyMetrics

```typescript
interface LatencyMetrics {
    latency_ms: number;           // End-to-end latency
    event_type: string;           // Event type received
    ticker: string | null;        // Ticker (null for heartbeat)
    origin_timestamp: string;     // ISO8601 from server
    receive_timestamp: string;    // ISO8601 when client received
    is_clock_skew: boolean;       // True if latency_ms < 0
}
```

### Usage in E2E Test

```python
# Get latency metrics from browser
metrics = await page.evaluate("() => window.lastLatencyMetrics")
assert metrics["latency_ms"] < 3000
```

---

## CloudWatch Logs Entry

### Log Group

`/aws/lambda/sse-streaming-lambda` (existing)

### Filter Pattern for Insights

```
{ $.event_type = "bucket_update" && $.latency_ms > 0 }
```

### Sample Log Entry

```json
{
    "level": "INFO",
    "message": "SSE event latency",
    "event_type": "bucket_update",
    "ticker": "AAPL",
    "resolution": "5m",
    "origin_timestamp": "2024-12-22T10:35:47.123Z",
    "send_timestamp": "2024-12-22T10:35:47.250Z",
    "latency_ms": 127,
    "is_cold_start": false,
    "connection_count": 5,
    "timestamp": "2024-12-22T10:35:47.251Z"
}
```

---

## Validation Rules

| Rule | Constraint |
|------|------------|
| origin_timestamp format | ISO 8601 with timezone (UTC) |
| origin_timestamp freshness | Must be within last 60 seconds |
| latency_ms range | 0-60000 (0 to 60 seconds) |
| latency_ms negative | Log warning, set is_clock_skew=true |

# Data Model: SSE Events

**Date**: 2025-12-23

## SSE Event Types

### HeartbeatEventData

Sent every 30 seconds to keep SSE connections alive.

| Field | Type | Description |
|-------|------|-------------|
| origin_timestamp | datetime (ISO8601) | Server time when event was generated |
| connections | int | Number of active SSE connections |

**Before**:
```python
class HeartbeatEventData(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    connections: int = Field(ge=0)
```

**After**:
```python
class HeartbeatEventData(BaseModel):
    origin_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    connections: int = Field(ge=0)
```

### MetricsEventData

Sent every 60 seconds with aggregated dashboard metrics.

| Field | Type | Description |
|-------|------|-------------|
| total | int | Total items analyzed |
| positive | int | Positive sentiment count |
| neutral | int | Neutral sentiment count |
| negative | int | Negative sentiment count |
| by_tag | dict[str, int] | Counts by tag |
| rate_last_hour | int | Analysis rate (last hour) |
| rate_last_24h | int | Analysis rate (last 24h) |
| origin_timestamp | datetime (ISO8601) | Server time when event was generated |

**Before**:
```python
class MetricsEventData(BaseModel):
    # ... other fields ...
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**After**:
```python
class MetricsEventData(BaseModel):
    # ... other fields ...
    origin_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

## Client-Side Latency Calculation

The client calculates latency as:

```javascript
const originTime = new Date(data.origin_timestamp).getTime();
const receiveTime = Date.now();
const latencyMs = receiveTime - originTime;
```

This requires `origin_timestamp` to be present in the JSON payload.

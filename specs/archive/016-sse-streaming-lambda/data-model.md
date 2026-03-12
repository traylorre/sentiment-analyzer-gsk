# Data Model: SSE Streaming Lambda

**Feature**: 016-sse-streaming-lambda
**Date**: 2025-12-02

## Entities

### SSE Connection

Represents an active streaming connection to the SSE Lambda.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| connection_id | string | Unique identifier for this connection | UUID v4, generated on connect |
| user_id | string | null | User ID from X-User-ID header | Required for config streams, null for global |
| config_id | string | null | Configuration ID for filtered streams | Null for global stream |
| ticker_filters | list[string] | Tickers to filter events for | Derived from config, max 5 |
| last_event_id | string | Last event ID sent to this connection | Updated after each event |
| connected_at | datetime | Connection establishment timestamp | UTC, ISO8601 |

**Lifecycle**:
- Created: When client establishes SSE connection
- Active: While streaming events
- Destroyed: On disconnect, timeout, or Lambda shutdown

**Notes**:
- Stored in-memory only (not persisted to DynamoDB)
- Per-Lambda-instance tracking
- Max 100 connections per instance (FR-008)

---

### SSE Event

A single event in the SSE stream.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| event | string | Event type identifier | One of: metrics, sentiment_update, heartbeat |
| id | string | Unique event identifier | Format: evt_{uuid} |
| data | object | Event payload (JSON) | Structure varies by event type |
| retry | integer | null | Reconnection delay in ms | Optional, default 3000 |

**Event Types**:

1. **metrics**: Aggregated dashboard metrics
2. **sentiment_update**: Individual ticker sentiment update
3. **heartbeat**: Keep-alive signal

---

### Connection Pool

Tracks all active connections for a Lambda instance.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| connections | dict[str, SSEConnection] | Active connections by ID | Max 100 entries |
| count | integer | Current connection count | 0-100, thread-safe |
| max_connections | integer | Connection limit | Default 100 (FR-008) |

**Thread Safety**:
- Uses threading.Lock for atomic operations
- Acquire/release operations are synchronized

---

## Event Payloads

### MetricsEventData

```python
class MetricsEventData:
    total: int               # Total items analyzed
    positive: int            # Positive sentiment count
    neutral: int             # Neutral sentiment count
    negative: int            # Negative sentiment count
    by_tag: dict[str, int]   # Counts per ticker tag
    rate_last_hour: int      # Items in last hour
    rate_last_24h: int       # Items in last 24 hours
    timestamp: datetime      # When metrics were computed
```

### SentimentUpdateData

```python
class SentimentUpdateData:
    ticker: str              # Stock ticker symbol
    score: float             # Sentiment score (-1.0 to 1.0)
    label: str               # positive/neutral/negative
    confidence: float        # Model confidence (0.0 to 1.0)
    source: str              # Data source (tiingo/finnhub)
    timestamp: datetime      # When sentiment was computed
```

### HeartbeatData

```python
class HeartbeatData:
    timestamp: datetime      # Current server time
    connections: int         # Active connection count
    uptime_seconds: int      # Lambda uptime
```

---

## State Transitions

### Connection Lifecycle

```
[New Request] → CONNECTING → [Auth Check] → CONNECTED → [Streaming] → DISCONNECTED
                    ↓                            ↓
              [Auth Failed]              [Limit Reached]
                    ↓                            ↓
               REJECTED (401)            REJECTED (503)
```

### Event Flow

```
[DynamoDB Poll] → [Compute Delta] → [Filter by Config] → [Format SSE] → [Send to Client]
       ↑                                                        ↓
       └────────────────── [Wait Interval] ←────────────────────┘
```

---

## DynamoDB Access (Read-Only)

The SSE Lambda reads from existing DynamoDB tables but does not write.

### Tables Accessed

| Table | Access Pattern | Purpose |
|-------|----------------|---------|
| sentiment-data | Query by timestamp | Fetch recent sentiment items |
| configurations | GetItem by config_id | Validate config access |

### Query Patterns

1. **Metrics Aggregation**: Same as dashboard Lambda's `aggregate_dashboard_metrics()`
2. **Config Lookup**: GetItem with pk=USER#{user_id}, sk=CONFIG#{config_id}

---

## Notes

- No new DynamoDB tables required
- All state is ephemeral (in-memory)
- Connection data is not persisted across Lambda invocations
- Clients must handle reconnection after Lambda timeout/restart

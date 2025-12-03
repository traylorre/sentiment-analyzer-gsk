# Data Model: SSE Endpoint Implementation

**Feature**: 015-sse-endpoint-fix
**Date**: 2025-12-02

## Entities

### SSEEvent

Base model for all SSE events sent to clients.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| event | string | Yes | Event type: "metrics", "new_item", "heartbeat" |
| id | string | Yes | Unique event ID for reconnection (UUID or incrementing) |
| data | string (JSON) | Yes | JSON-encoded payload specific to event type |

**Validation Rules**:
- `event` must be one of: "metrics", "new_item", "heartbeat"
- `id` must be unique per stream (used for Last-Event-ID reconnection)
- `data` must be valid JSON string

---

### MetricsEventData

Payload for `metrics` events (FR-009).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| total | integer | Yes | Total items analyzed |
| positive | integer | Yes | Count with positive sentiment |
| neutral | integer | Yes | Count with neutral sentiment |
| negative | integer | Yes | Count with negative sentiment |
| by_tag | object | Yes | Map of tag → count |
| rate_last_hour | integer | Yes | Items analyzed in last hour |
| rate_last_24h | integer | Yes | Items analyzed in last 24 hours |
| timestamp | string (ISO8601) | Yes | When metrics were computed |

---

### NewItemEventData

Payload for `new_item` events (FR-010).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| item_id | string | Yes | Unique identifier for the item |
| ticker | string | Yes | Stock ticker symbol |
| sentiment | string | Yes | "positive", "neutral", or "negative" |
| score | float | Yes | Sentiment score (0.0 to 1.0) |
| timestamp | string (ISO8601) | Yes | When item was analyzed |

---

### HeartbeatEventData

Payload for `heartbeat` events (FR-004).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| timestamp | string (ISO8601) | Yes | Current server time |
| connections | integer | Yes | Active connection count |

---

### ConnectionManager

In-memory manager for tracking active SSE connections (FR-015, FR-016, FR-017).

| Field | Type | Description |
|-------|------|-------------|
| _count | integer | Current active connections |
| _lock | Lock | Thread-safe access |
| max_connections | integer | Maximum allowed (default: 100) |

**Methods**:
- `acquire() -> bool`: Increment count if under limit, return success
- `release()`: Decrement count
- `count -> int`: Current connection count (for metrics)

---

## State Transitions

### SSE Connection Lifecycle

```
[Client Request]
    → VALIDATING (check auth for config-specific)
    → CONNECTING (acquire connection slot)
    → CONNECTED (streaming events)
    → DISCONNECTED (client close or error)
    → release connection slot
```

### Event Generation Flow

```
[Timer/Trigger]
    → Generate event (metrics/new_item/heartbeat)
    → Serialize to SSE format
    → Broadcast to connected clients
    → Log event sent
```

---

## Relationships

```
ConnectionManager (1) ←→ (*) SSEConnection
    - Tracks count, enforces limit

SSEConnection (1) → (*) SSEEvent
    - Each connection receives stream of events

SSEEvent → MetricsEventData | NewItemEventData | HeartbeatEventData
    - Event type determines payload schema
```

---

## Pydantic Models (Implementation Reference)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class MetricsEventData(BaseModel):
    total: int
    positive: int
    neutral: int
    negative: int
    by_tag: dict[str, int]
    rate_last_hour: int
    rate_last_24h: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class NewItemEventData(BaseModel):
    item_id: str
    ticker: str
    sentiment: Literal["positive", "neutral", "negative"]
    score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HeartbeatEventData(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    connections: int = Field(ge=0)

class SSEEvent(BaseModel):
    event: Literal["metrics", "new_item", "heartbeat"]
    id: str
    data: str  # JSON-encoded payload
```

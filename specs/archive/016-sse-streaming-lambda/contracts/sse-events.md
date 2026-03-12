# SSE Events Contract

**Feature**: 016-sse-streaming-lambda
**Date**: 2025-12-02

## Endpoints

### GET /api/v2/stream

**Description**: Global metrics stream (public, no authentication)

**Request**:
```http
GET /api/v2/stream HTTP/1.1
Accept: text/event-stream
Last-Event-ID: evt_abc123  (optional, for reconnection)
```

**Response**:
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

**Events Sent**:
- `heartbeat` every 30 seconds
- `metrics` every 60 seconds (or on change)

---

### GET /api/v2/configurations/{config_id}/stream

**Description**: Configuration-specific stream (requires authentication)

**Request**:
```http
GET /api/v2/configurations/{config_id}/stream HTTP/1.1
Accept: text/event-stream
X-User-ID: user_abc123  (required)
Last-Event-ID: evt_abc123  (optional)
```

**Response** (Success):
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

**Response** (Unauthorized):
```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{"detail": "Missing user identification"}
```

**Response** (Not Found):
```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{"detail": "Configuration not found"}
```

**Events Sent**:
- `heartbeat` every 30 seconds
- `sentiment_update` when matching ticker sentiment changes

---

### GET /api/v2/stream/status

**Description**: Connection status endpoint (non-streaming)

**Request**:
```http
GET /api/v2/stream/status HTTP/1.1
```

**Response**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "connections": 15,
  "max_connections": 100,
  "available": 85,
  "uptime_seconds": 3600
}
```

---

## Event Schemas

### heartbeat

```json
{
  "event": "heartbeat",
  "id": "evt_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "data": {
    "timestamp": "2025-12-02T10:30:00.000Z",
    "connections": 15,
    "uptime_seconds": 3600
  }
}
```

**SSE Format**:
```text
event: heartbeat
id: evt_a1b2c3d4-e5f6-7890-abcd-ef1234567890
data: {"timestamp":"2025-12-02T10:30:00.000Z","connections":15,"uptime_seconds":3600}

```

---

### metrics

```json
{
  "event": "metrics",
  "id": "evt_b2c3d4e5-f6a7-8901-bcde-f23456789012",
  "data": {
    "total": 150,
    "positive": 80,
    "neutral": 45,
    "negative": 25,
    "by_tag": {
      "AAPL": 50,
      "MSFT": 40,
      "GOOGL": 30,
      "TSLA": 30
    },
    "rate_last_hour": 12,
    "rate_last_24h": 150,
    "timestamp": "2025-12-02T10:30:00.000Z"
  }
}
```

**SSE Format**:
```text
event: metrics
id: evt_b2c3d4e5-f6a7-8901-bcde-f23456789012
data: {"total":150,"positive":80,"neutral":45,"negative":25,"by_tag":{"AAPL":50,"MSFT":40,"GOOGL":30,"TSLA":30},"rate_last_hour":12,"rate_last_24h":150,"timestamp":"2025-12-02T10:30:00.000Z"}

```

---

### sentiment_update

```json
{
  "event": "sentiment_update",
  "id": "evt_c3d4e5f6-a7b8-9012-cdef-345678901234",
  "data": {
    "ticker": "AAPL",
    "score": 0.85,
    "label": "positive",
    "confidence": 0.92,
    "source": "tiingo",
    "timestamp": "2025-12-02T10:30:00.000Z"
  }
}
```

**SSE Format**:
```text
event: sentiment_update
id: evt_c3d4e5f6-a7b8-9012-cdef-345678901234
data: {"ticker":"AAPL","score":0.85,"label":"positive","confidence":0.92,"source":"tiingo","timestamp":"2025-12-02T10:30:00.000Z"}

```

---

## Error Responses

### 503 Service Unavailable (Connection Limit)

```http
HTTP/1.1 503 Service Unavailable
Content-Type: application/json
Retry-After: 30

{
  "detail": "Connection limit reached. Try again later.",
  "max_connections": 100,
  "retry_after": 30
}
```

---

## Client Implementation Notes

### JavaScript EventSource

```javascript
const eventSource = new EventSource('https://sse-lambda-url.on.aws/api/v2/stream');

eventSource.addEventListener('heartbeat', (event) => {
  const data = JSON.parse(event.data);
  console.log('Heartbeat:', data.timestamp);
});

eventSource.addEventListener('metrics', (event) => {
  const data = JSON.parse(event.data);
  updateDashboard(data);
});

eventSource.onerror = (error) => {
  // EventSource automatically reconnects with Last-Event-ID
  console.log('Connection error, reconnecting...');
};
```

### Reconnection Behavior

1. Client sends `Last-Event-ID` header on reconnection
2. Server resumes from that event ID if within buffer window
3. If event ID not found, stream starts from current state
4. Default retry interval: 3000ms (sent via SSE `retry:` field)

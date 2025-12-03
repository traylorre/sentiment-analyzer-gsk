# API Contracts: SSE Endpoints

**Feature**: 015-sse-endpoint-fix
**Date**: 2025-12-02

## Endpoints

### GET /api/v2/stream

**Description**: Global metrics stream for dashboard real-time updates (FR-001)

**Authentication**: Optional (public metrics)

**Headers**:
| Header | Required | Description |
|--------|----------|-------------|
| Last-Event-ID | No | Resume from specific event ID (FR-005) |

**Response**:
- **Status**: 200 OK
- **Content-Type**: `text/event-stream` (FR-003)
- **Cache-Control**: `no-cache`
- **Connection**: `keep-alive`

**SSE Event Stream**:
```
event: metrics
id: evt_001
data: {"total":150,"positive":80,"neutral":45,"negative":25,"by_tag":{"AAPL":50},"rate_last_hour":12,"rate_last_24h":150,"timestamp":"2025-12-02T10:30:00Z"}

event: heartbeat
id: evt_002
data: {"timestamp":"2025-12-02T10:30:15Z","connections":15}

event: new_item
id: evt_003
data: {"item_id":"item_xyz","ticker":"AAPL","sentiment":"positive","score":0.85,"timestamp":"2025-12-02T10:30:20Z"}
```

**Error Responses**:
| Status | Condition |
|--------|-----------|
| 503 | Connection limit reached (100 max) |

---

### GET /api/v2/configurations/{config_id}/stream

**Description**: Configuration-specific event stream (FR-002)

**Authentication**: Required (FR-006)

**Headers**:
| Header | Required | Description |
|--------|----------|-------------|
| Authorization | Yes | `Bearer {token}` or X-User-ID |
| Last-Event-ID | No | Resume from specific event ID |

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| config_id | string (UUID) | Configuration identifier |

**Response**:
- **Status**: 200 OK
- **Content-Type**: `text/event-stream`

**SSE Event Stream**: Same format as global stream, filtered to configuration's tickers

**Error Responses**:
| Status | Condition | Body |
|--------|-----------|------|
| 401 | Missing/invalid authentication (FR-007) | `{"detail": "Missing user identification"}` |
| 404 | Configuration not found (FR-008) | `{"detail": "Configuration not found"}` |
| 503 | Connection limit reached | `{"detail": "Maximum connections reached"}` |

---

## SSE Protocol Compliance

### Event Format (per W3C SSE spec)

```
event: <event-type>\n
id: <event-id>\n
data: <json-payload>\n
\n
```

### Heartbeat Behavior (FR-004)

- Sent every 15-30 seconds
- Prevents connection timeout through proxies
- Contains current timestamp and connection count

### Reconnection Support (FR-005, FR-011)

- Every event includes unique `id` field
- Clients send `Last-Event-ID` header on reconnect
- Server resumes from last known event or current state if ID expired

---

## Test Scenarios

### T095: SSE Endpoint Availability
```gherkin
Given a deployed preprod environment
When client requests GET /api/v2/stream
Then response status is 200
And Content-Type is "text/event-stream"
```

### T096: SSE Heartbeat
```gherkin
Given an active SSE connection
When 30 seconds elapse
Then client receives heartbeat event
And event contains timestamp and connections count
```

### T097: SSE Config Stream Authentication
```gherkin
Given a valid configuration exists
When unauthenticated client requests /api/v2/configurations/{id}/stream
Then response status is 401
```

### T098: SSE Config Stream Not Found
```gherkin
Given an authenticated user
When requesting stream for non-existent config
Then response status is 404
```

### T099: SSE Connection Limit
```gherkin
Given 100 active SSE connections
When new client attempts to connect
Then response status is 503
And body contains "Maximum connections reached"
```

# Research: SSE Endpoint Implementation

**Feature**: 015-sse-endpoint-fix
**Date**: 2025-12-02

## Research Tasks

### 1. sse-starlette Integration with FastAPI

**Decision**: Use `sse-starlette` library's `EventSourceResponse` for SSE endpoints

**Rationale**:
- Already a project dependency (sse-starlette==3.0.3)
- Native FastAPI integration via `EventSourceResponse`
- Handles SSE protocol (Content-Type, keep-alive, event formatting)
- Supports async generators for event streaming

**Implementation Pattern**:
```python
from sse_starlette.sse import EventSourceResponse

async def event_generator():
    while True:
        # Yield events as dicts
        yield {
            "event": "metrics",
            "id": str(uuid4()),
            "data": json.dumps({"total": 100, "positive": 60})
        }
        await asyncio.sleep(30)  # Heartbeat interval

@app.get("/api/v2/stream")
async def stream_metrics():
    return EventSourceResponse(event_generator())
```

**Alternatives Considered**:
- Raw `StreamingResponse`: More manual work, doesn't handle SSE protocol
- WebSockets: Bidirectional (overkill for one-way server push)

---

### 2. AWS Lambda Function URL Streaming Support

**Decision**: Lambda Function URLs support streaming responses, compatible with SSE

**Rationale**:
- AWS added response streaming support for Lambda Function URLs in 2023
- Requires `RESPONSE_STREAM` invoke mode (already default for Function URLs)
- Maximum response payload: 20 MB (sufficient for SSE)
- No special configuration needed for existing deployment

**Constraints**:
- Lambda has a 15-minute maximum execution time
- Long-running connections may be terminated; clients must implement reconnection
- Dashboard already has reconnection logic with exponential backoff

**Verification**: Existing dashboard frontend at `src/dashboard/app.js` already implements:
- SSE connection via EventSource API
- Exponential backoff on connection failure
- Fallback to polling after max retries

---

### 3. Connection Management Strategy

**Decision**: Use in-memory connection tracking with atomic counter

**Rationale**:
- Simple implementation for 100 concurrent connections
- No external state store needed (Lambda handles per-instance)
- Connection count metric exposed via CloudWatch

**Implementation Pattern**:
```python
import threading

class ConnectionManager:
    def __init__(self, max_connections: int = 100):
        self._count = 0
        self._lock = threading.Lock()
        self.max_connections = max_connections

    def acquire(self) -> bool:
        with self._lock:
            if self._count >= self.max_connections:
                return False
            self._count += 1
            return True

    def release(self):
        with self._lock:
            self._count = max(0, self._count - 1)

    @property
    def count(self) -> int:
        return self._count
```

**Alternatives Considered**:
- DynamoDB connection tracking: Overkill for demo, adds latency
- Redis: Not in current stack, unnecessary complexity

---

### 4. Event Types and Payload Design

**Decision**: Three event types: `metrics`, `new_item`, `heartbeat`

**Rationale**:
- Matches FR-009, FR-010 requirements
- Consistent with dashboard `app.js` expectations
- Heartbeat keeps connection alive through proxies

**Event Schemas**:

```json
// metrics event (FR-009)
{
  "event": "metrics",
  "id": "evt_abc123",
  "data": {
    "total": 150,
    "positive": 80,
    "neutral": 45,
    "negative": 25,
    "by_tag": {"AAPL": 50, "MSFT": 40, "GOOGL": 30, "TSLA": 30},
    "rate_last_hour": 12,
    "rate_last_24h": 150
  }
}

// new_item event (FR-010)
{
  "event": "new_item",
  "id": "evt_def456",
  "data": {
    "item_id": "item_xyz",
    "ticker": "AAPL",
    "sentiment": "positive",
    "score": 0.85,
    "timestamp": "2025-12-02T10:30:00Z"
  }
}

// heartbeat event (FR-004)
{
  "event": "heartbeat",
  "id": "evt_ghi789",
  "data": {
    "timestamp": "2025-12-02T10:30:00Z",
    "connections": 15
  }
}
```

---

### 5. Testing Strategy

**Decision**: Dual approach - unit tests with mocked generators, E2E tests with real HTTP

**Rationale**:
- FR-012: Unit tests must work without network
- FR-013: E2E tests validate endpoint availability
- FR-014: Existing E2E tests must pass (not skip)

**Unit Testing Pattern**:
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_event_generator_yields_heartbeat():
    from src.lambdas.dashboard.sse import create_event_generator

    gen = create_event_generator(heartbeat_interval=0.1)
    event = await gen.__anext__()

    assert event["event"] == "heartbeat"
    assert "timestamp" in json.loads(event["data"])
```

**E2E Testing Pattern** (from existing `tests/e2e/test_sse.py`):
```python
@pytest.mark.asyncio
async def test_stream_endpoint_returns_sse_content_type(api_client, preprod_base_url):
    response = await api_client.get(f"{preprod_base_url}/api/v2/stream", timeout=5.0)

    # Should NOT return 404 anymore
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
```

---

### 6. Local Development Testing

**Decision**: Add test script and uvicorn support for local SSE testing

**Rationale**:
- FR-012/SC-007: Enable local testing without deployment
- Developers can verify SSE behavior before pushing

**Implementation**:
1. Add `scripts/test_sse_local.py` for manual browser testing
2. Document `uvicorn` local server setup in `quickstart.md`
3. Add pytest fixtures for SSE streaming tests

---

## Summary

| Topic | Decision | Confidence |
|-------|----------|------------|
| SSE Library | sse-starlette EventSourceResponse | High |
| Lambda Streaming | Supported via Function URLs | High |
| Connection Tracking | In-memory with thread lock | High |
| Event Types | metrics, new_item, heartbeat | High |
| Testing | Unit (mocked) + E2E (HTTP) | High |
| Local Dev | uvicorn + test script | High |

All research complete. No NEEDS CLARIFICATION items remain.

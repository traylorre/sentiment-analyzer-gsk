# Quickstart: SSE Endpoint Testing

**Feature**: 015-sse-endpoint-fix
**Date**: 2025-12-02

## Local Development

### 1. Start Local Server

```bash
# From repository root
cd /home/traylorre/projects/sentiment-analyzer-gsk

# Install dependencies (if not already)
pip install -r requirements.txt

# Start uvicorn with the dashboard handler
DYNAMODB_TABLE=dev-sentiment-analyzer \
ENVIRONMENT=dev \
uvicorn src.lambdas.dashboard.handler:app --reload --port 8000
```

### 2. Test SSE Endpoint with curl

```bash
# Global metrics stream
curl -N -H "Accept: text/event-stream" http://localhost:8000/api/v2/stream

# Expected output (events stream continuously):
# event: heartbeat
# id: evt_001
# data: {"timestamp":"2025-12-02T10:30:00Z","connections":1}
#
# event: metrics
# id: evt_002
# data: {"total":0,"positive":0,"neutral":0,"negative":0,...}
```

### 3. Test in Browser

Open browser developer console and run:

```javascript
const source = new EventSource('http://localhost:8000/api/v2/stream');

source.onopen = () => console.log('Connected!');
source.onerror = (e) => console.error('Error:', e);

source.addEventListener('heartbeat', (e) => {
    console.log('Heartbeat:', JSON.parse(e.data));
});

source.addEventListener('metrics', (e) => {
    console.log('Metrics:', JSON.parse(e.data));
});
```

### 4. Test Configuration-Specific Stream

```bash
# First create an anonymous session
curl -X POST http://localhost:8000/api/v2/auth/anonymous -H "Content-Type: application/json" -d '{}'
# Note the token from response

# Create a configuration
curl -X POST http://localhost:8000/api/v2/configurations \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "tickers": [{"symbol": "AAPL"}]}'
# Note the config_id from response

# Stream configuration events
curl -N \
  -H "Accept: text/event-stream" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v2/configurations/YOUR_CONFIG_ID/stream
```

---

## Running Tests

### Unit Tests

```bash
# Run SSE unit tests
PYTHONPATH=. pytest tests/unit/dashboard/test_sse.py -v

# Run with coverage
PYTHONPATH=. pytest tests/unit/dashboard/test_sse.py -v --cov=src/lambdas/dashboard/sse
```

### E2E Tests (Preprod)

```bash
# Set preprod environment
export PREPROD_API_URL="https://your-preprod-url.lambda-url.us-east-1.on.aws"

# Run SSE E2E tests
PYTHONPATH=. pytest tests/e2e/test_sse.py -v -m preprod
```

---

## Troubleshooting

### Connection Immediately Closes

**Symptom**: SSE connection opens then immediately closes
**Cause**: Usually missing `Content-Type: text/event-stream` header
**Fix**: Verify endpoint returns correct headers

```bash
curl -v http://localhost:8000/api/v2/stream 2>&1 | grep -i content-type
# Should show: content-type: text/event-stream
```

### No Events Received

**Symptom**: Connection stays open but no events
**Cause**: Event generator not yielding or heartbeat interval too long
**Fix**: Check logs for errors, reduce heartbeat interval for testing

### 503 Service Unavailable

**Symptom**: Connection rejected with 503
**Cause**: Connection limit (100) reached
**Fix**: Close other connections or increase limit for testing

```python
# In sse.py, for testing only:
connection_manager = ConnectionManager(max_connections=1000)
```

### 404 Not Found

**Symptom**: `/api/v2/stream` returns 404
**Cause**: SSE router not included in app
**Fix**: Verify `include_routers(app)` includes SSE router in handler.py

---

## Dashboard Integration

The dashboard at `src/dashboard/` already expects SSE:

1. `config.js` defines `ENDPOINTS.STREAM: '/api/v2/stream'`
2. `app.js` connects via `EventSource` API
3. Reconnection with exponential backoff is implemented
4. Fallback to polling after 3 failed reconnection attempts

To test dashboard integration:

```bash
# Serve dashboard locally
cd src/dashboard
python -m http.server 8080

# Open http://localhost:8080 in browser
# Check "Connected" status indicator
```

# Quickstart: SSE Diagnostic Tool

**Branch**: `1230-sse-diagnostic-tool`

## Usage

```bash
# Global stream (no auth)
python scripts/sse_diagnostic.py https://FUNCTION_URL/api/v2/stream

# Config-specific stream (with auth)
python scripts/sse_diagnostic.py https://FUNCTION_URL/api/v2/configurations/CONFIG_ID/stream --token TOKEN

# Filter by event type
python scripts/sse_diagnostic.py URL --event-type sentiment_update

# Filter by ticker
python scripts/sse_diagnostic.py URL --ticker AAPL

# JSON output for piping
python scripts/sse_diagnostic.py URL --json | jq '.score'

# Local dev server
python scripts/sse_diagnostic.py http://localhost:8000/api/v2/stream
```

## Implementation Order

1. **SSE parser**: Line-based parser that reads `event:`, `data:`, `id:` prefixes and dispatches events
2. **Event formatters**: Per-type formatting (heartbeat, metrics, sentiment_update, partial_bucket, deadline)
3. **CLI interface**: argparse with URL, --token, --user-id, --event-type, --ticker, --json options
4. **Connection handling**: HTTP connection with retry logic, Last-Event-ID header
5. **Session summary**: Signal handler for Ctrl+C, event counter, duration, health warnings
6. **Tests**: Mock HTTP responses, verify parsing, filtering, and summary output

## Key SSE Protocol Pattern

```python
# SSE parsing is line-based
for line in response:
    line = line.decode().rstrip('\n')
    if line.startswith('event:'):
        event_type = line[6:].strip()
    elif line.startswith('data:'):
        data_buffer += line[5:].strip()
    elif line.startswith('id:'):
        last_event_id = line[3:].strip()
    elif line == '':
        # Empty line = dispatch event
        dispatch(event_type, json.loads(data_buffer), last_event_id)
        event_type, data_buffer = 'message', ''
```

## Event Format Examples

```
[10:35:00] ❤ heartbeat  connections=42 uptime=3600s
[10:35:15] 📊 metrics    total=1234 +12/h positive=678 neutral=345 negative=211
[10:35:16] 📈 sentiment  AAPL +0.6500 positive (tiingo) confidence=0.85
[10:35:17] 🔄 partial    AAPL#5m 45.2% open=0.55 high=0.72 low=0.41 close=0.65 count=8
[10:35:18] ⏰ deadline   Lambda timeout approaching
```

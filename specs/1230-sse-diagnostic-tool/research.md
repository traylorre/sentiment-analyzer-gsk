# Research: SSE Diagnostic Tool

**Date**: 2026-03-21

## Decision 1: Implementation Approach

**Decision**: Single Python script using standard library only

**Rationale**: The tool needs to parse SSE protocol (trivial: read lines, split on `event:` / `data:` / `id:` prefixes) and format JSON. Python's `urllib.request` handles HTTP streaming, `json` parses payloads, `argparse` handles CLI. No need for external SSE client libraries.

**Alternatives considered**:
- `aiohttp` + `aiohttp-sse-client` — async, but overkill for a single-connection diagnostic tool
- Node.js `eventsource` — would require Node.js runtime; team uses Python
- Bash + curl — curl can't parse SSE events properly (the whole reason for this tool)

## Decision 2: SSE Protocol Parsing

**Decision**: Line-based parser following the SSE specification (W3C EventSource)

**Rationale**: SSE protocol is simple:
- Lines starting with `event:` set the event type
- Lines starting with `data:` append to the data buffer
- Lines starting with `id:` set the last event ID
- Empty lines dispatch the event
- Lines starting with `:` are comments (often used for keepalive)

Standard library `urllib.request.urlopen` with streaming read handles this.

## Decision 3: Authentication for Config Streams

**Decision**: Support `--token` and `--user-id` CLI options

**Rationale**: The SSE handler accepts three auth methods in precedence order:
1. `Authorization: Bearer {token}` header
2. `X-User-ID: {user_id}` header
3. `?user_token={token}` query parameter

CLI options `--token` and `--user-id` map to methods 1 and 2. Query parameter is auto-appended as fallback if `--token` is provided and header auth fails. Global stream (`/api/v2/stream`) requires no auth.

## Decision 4: Output Formatting

**Decision**: Colored terminal output with event-type-specific formatting, plus `--json` mode for piping

**Rationale**: Human-readable output should show:
- `[HH:MM:SS]` timestamp prefix
- Event type in color (green=heartbeat, yellow=metrics, blue=sentiment, cyan=partial_bucket, red=deadline)
- Key fields extracted and formatted (not raw JSON dump)
- `--json` mode outputs one JSON object per line (JSONL) for `jq` piping

## Decision 5: Reconnection Strategy

**Decision**: Exponential backoff (1s, 2s, 4s) with max 3 retries, sending Last-Event-ID

**Rationale**: Matches the frontend SSE client behavior. The handler supports Last-Event-ID with a 500-event replay buffer. After 3 failed retries, exit with clear error message.

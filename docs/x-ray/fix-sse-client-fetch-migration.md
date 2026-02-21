# Task 15: Migrate Frontend SSE Client to fetch()+ReadableStream

**Priority:** P2
**Status:** TODO
**Spec FRs:** FR-032, FR-033, FR-048
**Depends on:** Task 10 (CORS headers must include X-Amzn-Trace-Id before this deploys)
**Blocks:** None (but completes SC-015)

---

## Problem

The frontend SSE client uses the `EventSource` API to receive live sentiment updates. The `EventSource` API does **not support custom HTTP headers** — this is defined in the WHATWG HTML Living Standard, Section 9.2. The constructor signature is `EventSource(url, eventSourceInitDict)` where `eventSourceInitDict` only supports `withCredentials: boolean`.

This means:
- CloudWatch RUM's automatic `X-Amzn-Trace-Id` header injection (which patches `window.fetch()`) does NOT apply to `EventSource`
- There is no mechanism to propagate trace context from the browser to the SSE Lambda via `EventSource`
- Browser-to-backend trace linking for SSE connections is impossible with the current client

---

## Solution

Replace `EventSource` with `fetch()` + `ReadableStream` for SSE consumption. This enables:
- CloudWatch RUM auto-injection of `X-Amzn-Trace-Id` on the `fetch()` call
- Manual header attachment when RUM trace context is available
- Full control over request headers, including `Last-Event-ID` for reconnection

The trade-off: `EventSource`'s built-in auto-reconnection is lost and must be reimplemented.

---

## Changes Required

### 1. Replace EventSource with fetch()+ReadableStream

The SSE client must:
- Use `fetch()` with `Accept: text/event-stream` header
- Consume the response body via `response.body.getReader()`
- Parse SSE frames (`data:`, `event:`, `id:`, `retry:`) from the text stream
- Handle partial frame buffering across chunks

### 2. Implement Reconnection Logic (FR-033)

Must match or exceed `EventSource` auto-reconnection guarantees:
- **Exponential backoff** with jitter on connection failure (initial: 1s, max: 30s)
- **`Last-Event-ID` header propagation** — track the last received `id:` field and send it on reconnection for stream resumption
- **Connection state management** — CONNECTING, OPEN, CLOSED states matching `EventSource.readyState`
- **`retry:` field handling** — server-sent `retry:` directives update the reconnection delay
- **Abort controller** — clean connection teardown on component unmount

### 3. Trace Header Propagation

When CloudWatch RUM is active with `addXRayTraceIdHeader: true`:
- RUM automatically injects `X-Amzn-Trace-Id` on the `fetch()` call
- No additional code needed for RUM-instrumented requests

When RUM is not active (90% of production sessions at 10% RUM sampling):
- The client MUST still generate a valid `X-Amzn-Trace-Id` header using the RUM SDK's trace context API
- If no RUM context exists, omit the header — let the Lambda runtime assign the trace ID

---

## Files to Modify

| File | Change |
|------|--------|
| SSE client module (frontend) | Replace EventSource constructor with fetch()+ReadableStream |
| SSE client module (frontend) | Add SSE frame parser (data/event/id/retry field handling) |
| SSE client module (frontend) | Add reconnection logic with backoff+jitter+Last-Event-ID |
| SSE client module (frontend) | Add connection state management (CONNECTING/OPEN/CLOSED) |
| SSE client module (frontend) | Add AbortController for clean teardown |

---

## Verification

1. **Basic streaming:** Verify SSE events are received and parsed correctly via fetch()+ReadableStream
2. **Reconnection:** Kill the SSE connection and verify the client reconnects with exponential backoff and sends `Last-Event-ID`
3. **Trace propagation:** With RUM active, verify `X-Amzn-Trace-Id` header is present on the SSE fetch() request (visible in Network tab)
4. **No regression:** Verify all existing SSE functionality (event types, data parsing, state updates) works identically to EventSource
5. **Clean teardown:** Verify AbortController cancels the fetch on component unmount (no leaked connections)

---

## Edge Cases

- **Browser compatibility:** `fetch()` + `ReadableStream` is supported in all modern browsers (Chrome 43+, Firefox 65+, Safari 10.1+). No polyfill needed for the target browser matrix.
- **SSE frame spanning chunks:** A single SSE frame (`data: {...}\n\n`) may be split across multiple `ReadableStream` chunks. The parser must buffer partial frames.
- **Server-sent `retry:` directive:** The SSE spec defines `retry:` as a server hint for reconnection delay. The client must parse and respect this value.
- **CORS preflight:** The `X-Amzn-Trace-Id` header triggers a CORS preflight. Task 10 must add this header to `Access-Control-Allow-Headers` before this task deploys.

---

## SSE Reconnection Trace Correlation (FR-048 — Round 4)

When an SSE connection drops and the client reconnects using the new fetch()+ReadableStream client, the reconnection request gets a **new trace ID**. X-Ray has no native span links mechanism — the old trace (showing the connection drop) and the new trace (showing the reconnection) are completely disconnected.

Operators debugging SSE issues would see disconnected traces with no way to follow a user's session across reconnections.

### Solution: Annotation-Based Correlation

On each SSE reconnection request, the client MUST include metadata that the server annotates onto the X-Ray trace:

| Annotation Key | Value | Purpose |
|---------------|-------|---------|
| `session_id` | Stable identifier for the SSE session (e.g., UUID generated on first connect) | Links all traces from one user's SSE session |
| `previous_trace_id` | The `X-Amzn-Trace-Id` from the connection that dropped | Direct link from reconnection trace to its predecessor |
| `connection_sequence` | Integer counter (1 = first connection, 2 = first reconnection, etc.) | Shows reconnection history and frequency |

### Client Changes

The fetch()+ReadableStream client must:

1. **Generate `session_id`** on first SSE connection (UUID, stored in component state)
2. **Track `connection_sequence`** counter (incremented on each reconnection)
3. **Capture trace ID** from the `X-Amzn-Trace-Id` response header (if available) before connection drops
4. **Send on reconnection** via custom headers or query parameters:
   - `X-SSE-Session-Id: {session_id}`
   - `X-SSE-Previous-Trace: {previous_trace_id}`
   - `X-SSE-Connection-Seq: {connection_sequence}`

### Server Changes

The SSE Lambda must:

1. **Extract** reconnection headers from the request
2. **Annotate** the X-Ray trace/span with `session_id`, `previous_trace_id`, `connection_sequence`
3. X-Ray annotation values must be string type (X-Ray annotation types: str, int, float, bool only)

### Querying Reconnection History

Operators can query X-Ray for a complete SSE session:

```
annotation.session_id = "abc123"
```

This returns all traces for that session, ordered by `connection_sequence`, showing the full reconnection history including which connections dropped and when.

### Additional CORS Headers

Task 10 must add `X-SSE-Session-Id`, `X-SSE-Previous-Trace`, `X-SSE-Connection-Seq` to `Access-Control-Allow-Headers` in addition to `X-Amzn-Trace-Id`.

### Verification

1. Establish SSE connection, note trace ID
2. Kill connection (e.g., network disconnect)
3. Verify client reconnects with `session_id`, `previous_trace_id`, `connection_sequence=2`
4. Query X-Ray by `session_id` annotation — both traces appear
5. Verify `previous_trace_id` on the reconnection trace matches the original trace ID

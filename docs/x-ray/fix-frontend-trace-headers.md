# Task 10: Add Frontend Trace Header Propagation

**Priority:** P2
**Spec FRs:** FR-014, FR-015, FR-016
**Status:** TODO
**Depends on:** Task 1 (IAM permissions — backend must accept trace headers)
**Blocks:** Nothing

---

## Problem

Three gaps break the browser-to-backend trace chain:

1. **CORS**: `X-Amzn-Trace-Id` not in `Access-Control-Allow-Headers` — browsers will reject preflight
2. **API client**: Frontend `apiClient()` does not send `X-Amzn-Trace-Id` header
3. **SSE proxy**: Next.js API route does not forward `X-Amzn-Trace-Id` to upstream Lambda

---

## Current State

### CORS Configuration

**API Gateway** — `infrastructure/terraform/modules/api_gateway/main.tf:165,223`:
```
Access-Control-Allow-Headers: Content-Type,Authorization,X-User-ID
```

**Lambda Function URL (Dashboard)** — `infrastructure/terraform/main.tf:437-450`:
```
allow_headers: content-type, authorization, x-api-key, x-user-id, x-auth-type, x-csrf-token
```

**Lambda Function URL (SSE)** — `infrastructure/terraform/main.tf:755-764`:
```
allow_headers: content-type, x-user-id, last-event-id
```

None include `X-Amzn-Trace-Id`.

### Frontend API Client

**File:** `frontend/src/lib/api/client.ts`

`apiClient()` sets headers: `Content-Type`, `Authorization: Bearer`. No trace header.

### SSE Proxy

**File:** `frontend/src/app/api/sse/[...path]/route.ts`

Server-to-server call to SSE Lambda sends: `Authorization: Bearer`, `Accept: text/event-stream`. No trace header forwarding.

### CloudWatch RUM

**Config:** `enable_xray = true` — RUM generates browser-side trace contexts. 100% sampling in dev/preprod, 10% in prod.

---

## Files to Modify

| File | Change |
|------|--------|
| `infrastructure/terraform/modules/api_gateway/main.tf` | Add `X-Amzn-Trace-Id` to CORS allowed headers |
| `infrastructure/terraform/main.tf` | Add `x-amzn-trace-id` to Lambda Function URL CORS (Dashboard + SSE) |
| `frontend/src/lib/api/client.ts` | Add `X-Amzn-Trace-Id` header when RUM trace context available |
| `frontend/src/app/api/sse/[...path]/route.ts` | Forward `X-Amzn-Trace-Id` from incoming request to upstream |

---

## What to Change

### CORS (3 locations)

Add `X-Amzn-Trace-Id` (or lowercase `x-amzn-trace-id`) to the allowed headers list. This is additive — do not remove existing headers.

### Frontend API Client

When the browser has an active RUM/X-Ray trace context, extract the trace ID and include it as `X-Amzn-Trace-Id` on the fetch request. The CloudWatch RUM SDK provides this context.

If no trace context is available (90% of prod sessions where RUM sampling excludes them), do not send the header. Let API Gateway/Lambda assign the trace ID server-side.

### SSE Proxy

In the Next.js API route, check for `X-Amzn-Trace-Id` on the incoming request. If present, forward it to the upstream SSE Lambda call. If absent, do not generate a synthetic trace ID.

---

## Success Criteria

- [ ] CORS preflight allows `X-Amzn-Trace-Id` header on all 3 endpoints
- [ ] Frontend API client sends `X-Amzn-Trace-Id` when RUM trace context exists
- [ ] SSE proxy forwards `X-Amzn-Trace-Id` when present on incoming request
- [ ] SSE proxy does NOT generate trace IDs when header is absent
- [ ] Existing requests without trace headers continue to work (no breaking change)
- [ ] In dev/preprod (100% RUM sampling), every browser API request carries trace header

---

## Round 3: EventSource Limitation and SSE Client Migration

The native browser `EventSource` API does **NOT** support custom HTTP headers (WHATWG HTML Living Standard, Section 9.2). CloudWatch RUM's auto-instrumentation patches `fetch()` but NOT `EventSource`. This means:

- The SSE proxy path (browser → Next.js API route → Lambda) handles trace propagation for server-to-server calls — this is correct
- **Direct browser-to-Lambda SSE connections** (if any exist outside the proxy path) cannot carry `X-Amzn-Trace-Id` via `EventSource`
- **Task 15** addresses this by migrating the SSE client from `EventSource` to `fetch()` + `ReadableStream`, which enables RUM auto-injection of `X-Amzn-Trace-Id`

**Dependency:** CORS changes in this task (adding `X-Amzn-Trace-Id` to allowed headers) MUST deploy before Task 15's `fetch()`-based SSE client, otherwise the trace header will trigger CORS preflight failures.

---

## Blind Spots

1. **EventSource API limitation**: The native browser `EventSource` API does NOT support custom headers. The SSE proxy path handles this for proxied connections. For direct SSE connections, Task 15 migrates to `fetch()` + `ReadableStream` to enable trace header propagation.
2. **RUM SDK initialization**: The frontend may not have initialized the CloudWatch RUM client. If RUM is not initialized, no trace context exists, and the API client should gracefully skip the header (not error).
3. **CORS order of operations**: Deploy CORS changes BEFORE frontend changes (and before Task 15). If the frontend sends the header before CORS allows it, requests will fail with preflight errors.
4. **expose_headers**: The CORS `expose_headers` list may also need `X-Amzn-Trace-Id` if the frontend needs to read the response trace ID. Currently not required but worth considering.
5. **Task 15 prerequisite**: This task's CORS changes are a prerequisite for Task 15 (SSE client fetch migration). The `X-Amzn-Trace-Id` header triggers a CORS preflight — it must be in `Access-Control-Allow-Headers` before any `fetch()` request includes it.

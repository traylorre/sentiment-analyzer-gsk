# Task 13: Add Explicit SendGrid X-Ray Subsegment

**Priority:** P1
**Spec FRs:** FR-028
**Status:** TODO
**Depends on:** Task 1 (IAM permissions), Task 14 (tracer standardization)
**Blocks:** Nothing

---

## Problem

The SendGrid SDK uses `python-http-client` which relies on Python's stdlib `urllib.request` for HTTP transport. The X-Ray SDK's `patch_all()` does **NOT** auto-patch `urllib`. This means all SendGrid API calls (email sending) are invisible in X-Ray traces — they appear as untraced gaps in the Notification Lambda's service map.

This was discovered in Round 2 deep-dive when Assumption 1 ("X-Ray SDK auto-patches HTTP client libraries including the one used by SendGrid") was **invalidated**.

---

## Current State

**File:** `src/lambdas/notification/sendgrid_service.py` (364 lines)

- Uses `SendGridAPIClient` (from `sendgrid` package)
- `SendGridAPIClient` → `python_http_client.Client` → `urllib.request.urlopen()`
- `patch_all()` patches: `botocore`, `requests`, `httplib`, `sqlite3`, `mysql`, `psycopg2`, `pymongo`, `httpx`
- `patch_all()` does NOT patch: `urllib`, `urllib3`, `aiohttp`, `grpc`
- SendGrid calls are currently invisible to X-Ray

**Call pattern:**
```
handler.py → send_notification() → sendgrid_service.send_email() → SendGridAPIClient.send() → urllib.request.urlopen()
```

---

## Files to Modify

| File | Change |
|------|--------|
| `src/lambdas/notification/sendgrid_service.py` | Wrap SendGrid API call in explicit X-Ray subsegment |

---

## What to Change

At each point where `SendGridAPIClient.send()` is called:
1. Create an explicit X-Ray subsegment named `sendgrid_send_email`
2. Capture HTTP response status code as annotation
3. Capture request duration (subsegment timing handles this)
4. On SendGrid API error, mark subsegment as error with exception details
5. On HTTP error (non-2xx), mark subsegment as fault with status code

### Subsegment Annotations

| Key | Type | Description |
|-----|------|-------------|
| `http_status` | Number | SendGrid API response status code |
| `recipient_count` | Number | Number of email recipients |
| `template_used` | Boolean | Whether a SendGrid template was used |

### Subsegment Metadata

| Key | Description |
|-----|-------------|
| `response_headers` | SendGrid response headers (rate limit info) |
| `error_body` | Error response body on failure (for debugging) |

---

## Success Criteria

- [ ] SendGrid email API calls appear as explicit subsegments in X-Ray traces
- [ ] Subsegment captures HTTP status code as annotation
- [ ] Subsegment captures request duration via timing
- [ ] SendGrid API errors are marked as subsegment errors with exception details
- [ ] HTTP non-2xx responses are marked as subsegment faults
- [ ] No try/catch around X-Ray SDK calls (FR-018 — the subsegment wraps the SendGrid call, not the other way around)
- [ ] Notification Lambda service map shows SendGrid as a downstream node

---

## Blind Spots

1. **Retry logic**: If the notification service has retry logic around SendGrid calls, each retry attempt should be a separate subsegment (or the retry wrapper should be the subsegment boundary).
2. **Rate limiting**: SendGrid returns HTTP 429 for rate limits. This should be captured as a subsegment annotation, not an error (it's expected behavior under load).
3. **Batch sends**: If SendGrid is called with multiple recipients in a single API call, the subsegment should capture `recipient_count` to correlate trace duration with batch size.
4. **API key in headers**: SendGrid sends `Authorization: Bearer sg.xxx` header. This MUST NOT be captured in subsegment metadata. Only capture safe response headers.

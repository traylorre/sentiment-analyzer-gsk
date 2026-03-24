# Feature Specification: CloudFront + WAF for SSE Streaming

**Feature Branch**: `1255-cloudfront-sse-waf`
**Created**: 2026-03-24
**Status**: Draft
**Input**: "Add CloudFront distribution with Lambda Function URL origin for SSE streaming. Associate WAF WebACL (reusing Feature 1254 module with CLOUDFRONT scope). Shield Standard free with CloudFront."

## Context

### Current State

The SSE streaming Lambda serves 3 endpoints directly via Function URL (`authorization_type = NONE`, `invoke_mode = RESPONSE_STREAM`):

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/v2/stream` | Optional Bearer | Global SSE stream (real-time metrics) |
| `GET /api/v2/stream/status` | None | Connection pool status (JSON, not SSE) |
| `GET /api/v2/configurations/{id}/stream` | Bearer required | Per-config SSE stream |

Config: 1024 MB memory, 900s timeout, 25 reserved concurrency, CORS enabled with `allow_credentials = true`.

The frontend uses a Next.js server-side proxy at `/api/sse/[...path]/route.ts` that forwards requests to the Lambda Function URL. The SSE URL is discovered via `NEXT_PUBLIC_SSE_URL` env var (Amplify) and `/api/v2/runtime` endpoint.

**Gap**: No DDoS protection, no WAF, no per-IP rate limiting on SSE. A state-sponsored attacker can hold 25 concurrent SSE connections (exhausting reserved concurrency) from 25 IPs, blocking all legitimate users from real-time updates.

### Threat Model

**Connection exhaustion attack**: Attacker opens 25+ SSE connections (one per IP to evade per-connection limits). Each connection holds for up to 900s (Lambda timeout). With 25 reserved concurrency, this blocks ALL legitimate SSE connections.

**What this feature prevents**:
- Per-IP connection limiting via WAF rate-based rules
- Known bot signatures on SSE endpoints
- Shield Standard DDoS protection (automatic with CloudFront, no extra cost)
- Direct Lambda Function URL bypass (Feature 1256 completes this)

**What this feature does NOT prevent**:
- Sophisticated distributed attacks from thousands of unique IPs
- Application-level abuse of SSE data (requires application-level auth hardening)
- Direct Function URL access (Feature 1256)

### Cost Analysis

| Component | Monthly Cost |
|-----------|-------------|
| CloudFront (1M requests + 10GB transfer) | ~$1.00 |
| WAF WebACL (CLOUDFRONT scope) | $5.00 |
| WAF managed rules (reuse Feature 1254 groups) | $3.00 |
| WAF custom rules (rate-based + OPTIONS) | $2.00 |
| Shield Standard | $0.00 (free with CloudFront) |
| **Total** | **~$11/month** |

### Out of Scope

- Restricting Lambda Function URL to CloudFront only (Feature 1256)
- Custom domain for CloudFront distribution (can add later)
- CloudFront caching (SSE streams MUST NOT be cached — always no-cache)
- Changing SSE Lambda application code (infrastructure-only change)
- SSE authentication changes (existing Bearer token flow unchanged)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — SSE Traffic Routes Through CloudFront (Priority: P1)

All SSE streaming traffic routes through CloudFront instead of hitting the Lambda Function URL directly. CloudFront provides edge caching for non-SSE responses (status endpoint), DDoS protection via Shield Standard, and a single stable URL for the frontend.

**Why this priority**: Core value — puts SSE behind a protective edge layer.

**Independent Test**: Connect to SSE stream via CloudFront URL. Verify events arrive in real-time.

**Acceptance Scenarios**:

1. **Given** a client connects to the global SSE stream via CloudFront, **When** a new event is published, **Then** the client receives it in real-time (< 2s latency).
2. **Given** the CloudFront distribution is deployed, **When** the frontend's SSE URL is updated, **Then** all SSE connections route through CloudFront.
3. **Given** a request to `/api/v2/stream/status` via CloudFront, **Then** it returns JSON (not SSE) with connection pool info.

---

### User Story 2 — WAF Protects SSE from Abuse (Priority: P1)

WAF rate-based rules prevent single IPs from opening excessive connections. Managed rules block known attack patterns on SSE endpoints.

**Why this priority**: SSE connections are long-lived and expensive (900s Lambda timeout × reserved concurrency). Without rate limiting, 25 connections exhaust all capacity.

**Independent Test**: Open 2001+ requests from one IP in 5 minutes to the SSE endpoint. Verify WAF blocks with 403.

**Acceptance Scenarios**:

4. **Given** a single IP sends >2000 requests to SSE endpoints in 5 minutes, **Then** WAF blocks subsequent requests with 403.
5. **Given** WAF is associated with the CloudFront distribution, **Then** Shield Standard DDoS protection is automatically active.
6. **Given** a request with SQL injection patterns to SSE endpoints, **Then** WAF blocks with 403.

---

### User Story 3 — Frontend Uses CloudFront SSE URL (Priority: P1)

The frontend's SSE URL switches from Lambda Function URL to CloudFront distribution URL. The Next.js proxy at `/api/sse/[...path]` forwards to CloudFront instead of Lambda directly.

**Why this priority**: Without this, traffic bypasses CloudFront and WAF protection.

**Acceptance Scenarios**:

7. **Given** the Amplify deployment, **When** `NEXT_PUBLIC_SSE_URL` is checked, **Then** it points to the CloudFront distribution URL.
8. **Given** the `/api/v2/runtime` endpoint, **When** a client requests it, **Then** `sse_url` in the response is the CloudFront URL.

---

### User Story 4 — CloudFront Does Not Cache SSE Streams (Priority: P1)

SSE streams are real-time and MUST NOT be cached by CloudFront. The status endpoint (JSON) can optionally have a short cache TTL.

**Why this priority**: Caching SSE breaks real-time functionality. This is a correctness requirement.

**Acceptance Scenarios**:

9. **Given** a request to `/api/v2/stream`, **Then** CloudFront forwards it to origin without caching (Cache-Control: no-cache, no-store).
10. **Given** a request to `/api/v2/stream/status`, **Then** CloudFront may cache for a short period (5s TTL) or forward directly.

---

### Edge Cases

- **CloudFront timeout**: CloudFront has a 60s origin response timeout by default. SSE connections need longer. CloudFront supports origin read timeout up to 180s for streaming. However, Lambda can run 900s. This means CloudFront will disconnect SSE after 180s max — the frontend's reconnect logic (Last-Event-ID) handles this.
- **Chunked transfer encoding**: CloudFront supports chunked responses. Lambda RESPONSE_STREAM uses chunked encoding. Compatible.
- **CORS headers**: CloudFront must forward `Origin`, `Authorization`, `Last-Event-ID` headers to Lambda. Lambda returns CORS headers. CloudFront must not strip them.
- **Connection reuse**: CloudFront may pool connections to origin. SSE connections are per-client, so CloudFront must NOT reuse origin connections across different viewers.
- **Price class**: Use PriceClass_100 (US, Canada, Europe) to minimize cost. The app is not global.
- **WAF scope**: Feature 1254's WAF module uses REGIONAL scope for API Gateway. This feature creates a SECOND WAF WebACL with CLOUDFRONT scope. They are independent.
- **Two WAF WebACLs**: One REGIONAL (API Gateway, Feature 1254), one CLOUDFRONT (this feature). Each has its own rules and metrics. Rule configuration can differ (e.g., SSE rate limit may be lower than REST API rate limit).
- **Lambda Function URL still exposed**: Until Feature 1256 restricts it, attackers can bypass CloudFront. This feature adds protection but doesn't enforce it yet.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A CloudFront distribution MUST be created with the SSE Lambda Function URL as origin.
- **FR-002**: CloudFront MUST forward SSE streams without caching (Cache-Control: no-cache, no-store). The default cache behavior MUST disable caching for all SSE paths.
- **FR-003**: CloudFront origin read timeout MUST be set to 180s (maximum for streaming support).
- **FR-004**: CloudFront MUST forward `Authorization`, `Origin`, `Last-Event-ID`, `X-User-ID`, and `X-Amzn-Trace-Id` headers to the Lambda origin.
- **FR-005**: A WAF v2 WebACL MUST be created with CLOUDFRONT scope and associated with the distribution. Reuse the Feature 1254 WAF module with `scope = "CLOUDFRONT"`.
- **FR-006**: WAF rate-based rule MUST block IPs exceeding 2000 requests per 5-minute window on SSE endpoints.
- **FR-007**: The Amplify frontend MUST set `NEXT_PUBLIC_SSE_URL` to the CloudFront distribution URL.
- **FR-008**: The `/api/v2/runtime` endpoint response MUST return the CloudFront URL as `sse_url`.
- **FR-009**: CloudFront MUST use PriceClass_100 (US/Canada/Europe) to minimize cost.
- **FR-010**: Shield Standard DDoS protection MUST be active (automatic with CloudFront, no additional configuration).

### Key Entities

- **CloudFront Distribution**: Edge distribution proxying SSE traffic to Lambda Function URL origin. No caching. Streaming-optimized.
- **WAF WebACL (CLOUDFRONT)**: Separate from the API Gateway WAF (REGIONAL). Per-IP rate limiting and managed rules for SSE endpoints.
- **Origin Request Policy**: Controls which headers CloudFront forwards to Lambda. Must include auth and trace headers.
- **Cache Policy**: Disabled (CachingDisabled) for SSE streams.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: SSE events arrive at clients via CloudFront with < 2s additional latency vs direct Lambda.
- **SC-002**: WAF blocks IPs exceeding 2000 req/5min on SSE endpoints.
- **SC-003**: Frontend uses CloudFront URL for SSE (`NEXT_PUBLIC_SSE_URL`).
- **SC-004**: CloudFront does NOT cache SSE responses (verifiable: `X-Cache: Miss from cloudfront` on every SSE request).
- **SC-005**: Shield Standard active (verifiable: CloudFront distribution has Shield Standard by default).
- **SC-006**: Existing SSE E2E tests pass through CloudFront path (zero regression).
- **SC-007**: Monthly CloudFront + WAF cost < $15 at current traffic.

## Assumptions

- Lambda Function URL supports chunked transfer encoding via `RESPONSE_STREAM` (verified: already configured).
- CloudFront origin read timeout max is 180s. SSE connections longer than 180s will disconnect; frontend reconnect logic (Last-Event-ID) handles this (verified: existing frontend code).
- WAF module from Feature 1254 is reusable with `scope = "CLOUDFRONT"` (verified: module design).
- PriceClass_100 covers all current users (US-based application).
- No custom domain needed initially (CloudFront default `.cloudfront.net` domain).
- The Next.js proxy at `/api/sse/[...path]` will need its target URL updated to CloudFront (or the `NEXT_PUBLIC_SSE_URL` env var handles this via runtime discovery).

### Security Zone Map (After Feature 1255)

```
┌──────────────────────────────────────────────────────────────────────┐
│                        INTERNET                                       │
│                    ┌──────┴──────┐                                    │
│                    │             │                                    │
│   ┌────────────────▼──────┐  ┌──▼───────────────────────┐           │
│   │  WAF (REGIONAL)       │  │  CloudFront (NEW)         │           │
│   │  Feature 1254         │  │  + WAF (CLOUDFRONT) NEW   │           │
│   │  SQLi/XSS/Rate/Bots  │  │  + Shield Standard FREE   │           │
│   └────────────────┬──────┘  │  SQLi/XSS/Rate/Bots      │           │
│                    │         └──┬───────────────────────┘           │
│   ┌────────────────▼──────┐    │                                    │
│   │  API GATEWAY          │    │                                    │
│   │  Cognito + Rate Plan  │    │                                    │
│   │  Zone A/B             │    │                                    │
│   └────────────────┬──────┘    │                                    │
│                    │           │                                    │
│   ┌────────────────▼──────┐  ┌─▼────────────────────────┐          │
│   │  DASHBOARD LAMBDA     │  │  SSE STREAMING LAMBDA     │          │
│   │  Zone C/D             │  │  /stream, /status,        │          │
│   │                       │  │  /configurations/*/stream  │          │
│   └───────────────────────┘  └──────────────────────────┘          │
│                                                                      │
│   ┌──────────────────────────────────────────────────────┐          │
│   │  LAMBDA FUNCTION URLs (still exposed)                │ Feature  │
│   │  Dashboard + SSE — bypass CloudFront/API GW          │ 1256     │
│   └──────────────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────────────────┘
```

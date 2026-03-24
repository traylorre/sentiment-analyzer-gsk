# Feature Specification: Add WAF v2 WebACL to API Gateway

**Feature Branch**: `1254-api-gateway-waf`
**Created**: 2026-03-24
**Status**: Draft
**Input**: "Add WAF v2 WebACL to API Gateway with per-IP rate limiting (2000 req/5min), SQL injection protection, XSS protection, and bot detection rules. Feature 1254 in DDoS/auth hardening series. Threat model: state-sponsored attacker."

## Context

### Current State

After Feature 1253, the API Gateway serves as the primary entry point for all frontend REST traffic with Cognito JWT authorization. However, rate limiting remains **per API key** (100 req/s global via Usage Plan) — a single attacker IP can consume the entire quota, blocking legitimate users.

| Zone | Auth Level | Gap |
|------|-----------|-----|
| Zone A: Public routes | No Cognito (NONE) | No per-IP rate limiting — vulnerable to flood |
| Zone B: Protected routes | Cognito JWT | Invalid tokens rejected at $0 cost, but flood still consumes API Gateway capacity |
| Zone C: Application auth | Bearer token + DynamoDB | Defense-in-depth, only reached after A/B |
| Zone D: Admin/dev-only | Environment gate | Already blocked in prod (Feature 1249) |

WAF v2 adds a new perimeter **before** all zones — per-IP throttling, SQL injection, XSS, and bot detection that rejects malicious requests before they reach API Gateway rate limiting or Cognito authorization.

### Cost Analysis

| Component | Monthly Cost |
|-----------|-------------|
| WAF WebACL | $5.00 |
| 3 managed rule groups ($1 each) | $3.00 |
| Per-request ($0.60/million) at 100K req/day | ~$1.80 |
| **Total** | **~$10/month** |

Current budget: $50/month. WAF adds ~20%. Justified: a single DDoS flood on public endpoints generates Lambda invocations at $0.20/million — WAF blocks them at $0.60/million but prevents $0.20/million compute + Cognito authorizer overhead.

### Threat Model

**State-sponsored attacker** with:
- Distributed IP rotation (botnets, VPNs, cloud VMs)
- Automated SQL injection scanning (sqlmap, custom tools)
- XSS payload injection in query parameters, headers, request bodies
- Credential stuffing bots (rotating user agents, request timing)
- Budget exhaustion via flooding public endpoints
- Application-layer DDoS targeting expensive endpoints (`/configurations/refresh`)

**What this feature prevents**: Single-IP floods, SQL injection probes, XSS payloads, known bot signatures.

**What this feature does NOT prevent**: Distributed attacks from thousands of IPs each under threshold, zero-day attacks not in signatures, SSE stream abuse (Feature 1255).

### Interaction with Existing Rate Limiting

WAF and API Gateway Usage Plan are **independent layers**:

```
Internet → WAF (per-IP, SQLi, XSS, bots) → API Gateway (global 100 req/s) → Cognito → Lambda
```

A single IP exceeding 2000 req/5min → WAF blocks (403). Remaining traffic still has 100 req/s Usage Plan as second throttle.

### Out of Scope

- WAF for CloudFront/SSE streaming (Feature 1255)
- Custom application-specific WAF rules
- IP allowlists/blocklists (can add incrementally after WAF deployed)
- Geographic blocking (GeoMatch rules)
- WAF request logging to S3/Kinesis (start with CloudWatch metrics, add later)
- Bot Control advanced tier ($10/month — defer unless needed)
- Restricting Lambda Function URLs (Feature 1256)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Per-IP Rate Limiting Blocks Flood Attacks (Priority: P1)

Individual IP addresses exceeding 2000 requests per 5-minute window are temporarily blocked. Legitimate users are unaffected. This prevents a single attacker from consuming the global rate limit.

**Why this priority**: Primary security gap — per-IP throttling is the core value.

**Independent Test**: Send 2001 requests from one IP in 5 minutes → request 2001 gets 403. Send 10 from another IP → all succeed.

**Acceptance Scenarios**:

1. **Given** a single IP sends 2000 requests in 5 minutes, **When** request 2001 arrives, **Then** WAF blocks with 403.
2. **Given** a blocked IP waits for the window to reset, **Then** subsequent requests succeed.
3. **Given** two IPs each send 1500 requests in 5 minutes, **Then** all succeed (aggregate 3000, per-IP 1500 < 2000).
4. **Given** a legitimate user sends <50 requests/5min, **Then** zero blocks.

---

### User Story 2 — SQL Injection Attempts Blocked (Priority: P1)

Requests with SQL injection patterns in query parameters, headers, or bodies are blocked before reaching Lambda.

**Why this priority**: OWASP #1. Even with DynamoDB (not SQL), attackers probe indiscriminately — blocking saves compute cost and reduces log noise.

**Independent Test**: Send `?q='; DROP TABLE users; --` → 403.

**Acceptance Scenarios**:

5. **Given** a request with SQLi in a query parameter, **Then** WAF blocks with 403.
6. **Given** a request with SQLi in a header, **Then** WAF blocks with 403.
7. **Given** a request with SQL keywords in normal text (`?q=SELECT+a+ticker`), **Then** WAF allows it (false positive avoidance).

---

### User Story 3 — XSS Attempts Blocked (Priority: P1)

Requests with cross-site scripting payloads are blocked before reaching Lambda.

**Why this priority**: OWASP #7. Frontend renders user-provided config names — blocking XSS at WAF prevents storage of malicious payloads.

**Independent Test**: Send `<script>alert(1)</script>` in request body → 403.

**Acceptance Scenarios**:

8. **Given** XSS in a body field, **Then** WAF blocks with 403.
9. **Given** URL-encoded XSS, **Then** WAF blocks with 403.
10. **Given** legitimate content with angle brackets (`S&P 500 <2024>`), **Then** WAF allows it.

---

### User Story 4 — Known Bots Detected and Managed (Priority: P2)

Bot traffic is identified. Known malicious bots are blocked. Unknown bots are labeled for monitoring.

**Why this priority**: Reduces noise, prevents automated attacks. But starts in COUNT mode to avoid false positives on legitimate API clients.

**Acceptance Scenarios**:

11. **Given** a request from a vulnerability scanner user agent, **Then** WAF blocks with 403 (after transition from COUNT to BLOCK).
12. **Given** a request with no user agent, **Then** WAF labels for monitoring (COUNT mode).
13. **Given** a legitimate browser request, **Then** WAF allows.

---

### User Story 5 — WAF Metrics and Alerting (Priority: P2)

Blocked requests are counted in metrics. Spikes trigger alerts.

**Acceptance Scenarios**:

14. **Given** WAF blocks a request, **Then** the block appears in CloudWatch metrics with rule name.
15. **Given** >500 blocks in 5 minutes, **Then** alert fires.

---

### Edge Cases

- **False positives on ticker search**: `?q=SELECT` could match SQLi. Managed rules should start with low-sensitivity settings; ticker-specific false positives addressed via rule exceptions if observed.
- **Sliding window**: WAF uses trailing 5-minute window, not fixed. Steady 6.6 req/s fluctuates around threshold.
- **Distributed attacks**: 1000 IPs × 1999 req/5min = 2M requests. Usage Plan (100 req/s = 30K/5min) throttles aggregate.
- **OPTIONS preflight**: Must NOT count toward per-IP rate limit. CORS preflight is browser-generated, not user-initiated.
- **Health check IPs**: Deploy pipeline and monitoring send health checks. Should not be rate-limited. Can exclude via IP allowlist rule.
- **Rule evaluation order**: SQLi/XSS rules (priority 1-3) before rate-based rule (priority 4). Blocked malicious requests don't count toward rate.
- **Bot Control false positives**: Legitimate API clients (mobile apps, scripts) may not send browser user agents. Start in COUNT mode.
- **WAF 403 and CORS**: WAF blocks generate a 403 response before API Gateway processes the request. This response may lack CORS headers. Either configure WAF custom response body with CORS, or accept that WAF blocks are opaque to the browser (the user gets an error, frontend can detect network failure).
- **Regional vs CloudFront scope**: Feature 1254 uses REGIONAL scope for REST API. Feature 1255 uses CLOUDFRONT scope for SSE. Separate WebACLs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A WAF v2 WebACL MUST be created and associated with the API Gateway stage.
- **FR-002**: A per-IP rate-based rule MUST block IPs exceeding 2000 requests per 5-minute window with 403.
- **FR-003**: SQL injection detection MUST be enabled using AWS managed rules, blocking requests with SQLi patterns.
- **FR-004**: XSS detection MUST be enabled, blocking requests with XSS payloads.
- **FR-005**: Bot detection MUST be enabled using AWS managed rules, initially in COUNT mode.
- **FR-006**: WAF blocked responses SHOULD include CORS headers where possible. If WAF custom response bodies support CORS, configure them. If not, document the limitation.
- **FR-007**: WAF metrics MUST be published to CloudWatch. An alarm MUST fire when >500 blocks in 5 minutes.
- **FR-008**: Rule evaluation order MUST be: (1) IP allowlist (future), (2) Managed rules (SQLi, XSS, known bad inputs), (3) Bot detection, (4) Rate-based rule.
- **FR-009**: WAF MUST be a separate module for reuse with CloudFront in Feature 1255.
- **FR-010**: The WAF rate-based rule MUST NOT count OPTIONS preflight requests.

### Key Entities

- **WebACL**: WAF access control list associated with API Gateway stage. Contains all rules.
- **Rate-Based Rule**: Per-IP request counter over 5-minute sliding window. Blocks IPs exceeding threshold.
- **Managed Rule Group**: AWS-maintained rule sets for SQLi, XSS, known bad inputs, and bot detection.
- **WAF Action**: ALLOW (default), BLOCK (403), COUNT (log only).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Single IP >2000 req/5min is blocked (403 for subsequent requests).
- **SC-002**: SQL injection patterns blocked (403) before Lambda invocation.
- **SC-003**: XSS payloads blocked (403) before Lambda invocation.
- **SC-004**: Normal user traffic (<50 req/5min per IP) experiences zero false positives.
- **SC-005**: Blocked request count visible in CloudWatch per rule.
- **SC-006**: Alert fires when >500 blocks in 5 minutes.
- **SC-007**: Existing E2E tests pass (zero functional regression).
- **SC-008**: Monthly WAF cost <$15 at current traffic levels.

## Assumptions

- API Gateway `api_arn` and `stage_name` outputs available for WAF association (verified in outputs.tf).
- WAF v2 regional scope required for REST API (not CloudFront scope).
- 2000 req/5min per-IP is appropriate for expected user base (adjustable via variable).
- Bot Control common tier ($1/month) sufficient; targeted tier ($10/month) deferred.
- AWS managed rule groups available in us-east-1.
- WAF custom response bodies support CORS headers (to be verified during implementation).

### Security Zone Map (After Feature 1254)

```
┌──────────────────────────────────────────────────────────────────┐
│                      INTERNET                                     │
│                         │                                         │
│  ┌──────────────────────▼───────────────────────┐                │
│  │         WAF v2 WebACL (Feature 1254)          │                │
│  │  Rule 1: Managed SQLi/XSS/BadInputs (BLOCK)  │                │
│  │  Rule 2: Bot Control (COUNT → BLOCK)          │                │
│  │  Rule 3: Per-IP Rate 2000/5min (BLOCK)        │                │
│  │  Default: ALLOW                                │                │
│  └──────────────────────┬───────────────────────┘                │
│                         │                                         │
│  ┌──────────────────────▼───────────────────────┐                │
│  │      API GATEWAY (REST API v1)                │                │
│  │  Usage Plan: 100 req/s global                 │                │
│  │  Zone A: Public (NONE) │ Zone B: Cognito      │                │
│  └──────────────────────┬───────────────────────┘                │
│                         │                                         │
│  ┌──────────────────────▼───────────────────────┐                │
│  │  DASHBOARD LAMBDA (Zone C: App auth, Zone D)  │                │
│  └───────────────────────────────────────────────┘                │
│                                                                    │
│  ┌───────────────────────────────────────────────┐  UNPROTECTED  │
│  │   LAMBDA FUNCTION URLs (no WAF, no auth)      │ ◄── Feature   │
│  │   Dashboard + SSE streaming                   │    1256        │
│  └───────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────┘
```

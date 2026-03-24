# Security Posture Report: sentiment-analyzer-gsk

**Date**: 2026-03-23 | **Scope**: Full attack surface audit
**Author**: Claude Opus 4.6 (automated security audit)

---

## BEFORE — Current State (Pre-Hardening)

### Attack Surface Map

**Two Lambda Function URLs, both `authorization_type = NONE`:**

| Lambda | Mode | Public? | Auth Layer |
|--------|------|---------|------------|
| Dashboard | BUFFERED | Yes | Application-level only |
| SSE Streaming | RESPONSE_STREAM | Yes | Application-level only |

**API Gateway Cognito auth: DISABLED** (`enable_cognito_auth = false`)

**WAF: None deployed**

### Unauthenticated Endpoints (19 total)

| # | Endpoint | Severity | What's Exposed |
|---|----------|----------|----------------|
| 1 | `GET /` | CRITICAL | Full admin HTMX dashboard |
| 2 | `GET /chaos` | CRITICAL | Chaos engineering UI with start/stop controls |
| 3 | `GET /static/*` | HIGH | JS/CSS revealing internal implementation |
| 4 | `GET /api` | CRITICAL | Complete endpoint catalog (50+ routes, including chaos) |
| 5 | `GET /health` | HIGH | DynamoDB table name + environment name |
| 6 | `GET /favicon.ico` | LOW | Browser asset |
| 7 | `GET /api/v2/runtime` | MEDIUM | SSE Lambda Function URL + environment |
| 8 | `POST /api/v2/auth/anonymous` | MEDIUM | Session creation (no rate limit enforced) |
| 9 | `POST /api/v2/auth/check-email` | HIGH | User enumeration vector |
| 10 | `GET /api/v2/auth/magic-link/verify` | LOW | Magic link verification |
| 11 | `GET /api/v2/auth/oauth/urls` | LOW | OAuth provider URLs |
| 12 | `POST /api/v2/auth/oauth/callback` | LOW | OAuth callback |
| 13 | `GET /api/v2/configurations/{id}/refresh/status` | HIGH | **MISSING AUTH BUG** — no `_require_user_id()` |
| 14 | `GET /api/v2/timeseries/{ticker}` | MEDIUM | Proprietary sentiment data |
| 15 | `GET /api/v2/timeseries/batch` | MEDIUM | Bulk sentiment data (up to 20 tickers) |
| 16 | `GET /api/v2/stream` | MEDIUM | Real-time global sentiment SSE stream |
| 17 | `GET /api/v2/stream/status` | MEDIUM | Connection pool internals |
| 18 | `GET /api/v2/tickers/validate` | LOW | Ticker validation |
| 19 | `GET /api/v2/market/status` | LOW | Market open/closed |

### Chaos Attack Chain (Current)

An attacker who discovers the Function URL can:

1. `GET /api` — discovers chaos endpoints (self-documenting)
2. `GET /health` — learns table names + environment
3. `POST /chaos/experiments` — create experiment (anonymous accepted in non-prod)
4. `POST /chaos/experiments/{id}/start` — **directly degrades AWS infrastructure**
   - Sets Lambda concurrency=0 (halts ingestion)
   - Attaches IAM deny-write policies
   - Disables EventBridge rules
5. `DELETE /chaos/experiments/{id}` — cleans up audit trail

**No rate limiting. No approval workflow. No time enforcement on running experiments.**

### Positive Findings (Already Correct)

- DynamoDB PITR enabled (35-day retention)
- `prevent_destroy` on all stateful resources
- X-Ray tracing on all Lambdas
- Secrets Manager used for API keys (no hardcoded secrets)
- Lambda IAM roles properly scoped with namespace conditions
- S3 state bucket has full public access block
- Cognito MFA available (optional mode)
- Chaos blocked in prod environment (but not preprod/dev)

### Current Score: ~4.5/10

---

## Bundle Allocation

### Feature 1249: Admin Dashboard Lockdown
- Admin routes (/, /chaos, /static/*, /api, /favicon.ico) return 404 in prod/preprod
- Health endpoint stripped of internal info
- `/api/v2/runtime` stripped of SSE URL in prod/preprod
- validate_session=False flipped to True on 4 endpoints
- Missing auth on `/configurations/{id}/refresh/status` fixed
- S3 deployment bucket public access block uncommented
- CORS consistency check

### Feature 1250: Chaos Security Hardening (THIS BRANCH)
- Chaos API route gating (POST/GET/DELETE /chaos/experiments/*) in non-dev environments
- Chaos experiment duration enforcement (auto-restore after timeout)
- DynamoDB chaos table TTL
- CloudTrail alerting on IAM policy attachment
- Authenticated-only chaos access (remove anonymous exception)
- Rate limiting on chaos experiment creation

---

## Blind Spots Identified

### Blind Spot 1: Chaos API Still Accessible After UI Lockdown (CRITICAL)
**Affected by**: Feature 1249 blocks `/chaos` HTML but NOT `/chaos/experiments/*` API routes.
**Resolution**: Assigned to Feature 1250 (this branch).

### Blind Spot 2: `validate_session=False` on Multiple Endpoints (HIGH)
**Endpoints**: `/api/v2/sentiment`, `/api/v2/trends`, `/api/v2/articles`, `/api/v2/metrics`
**Resolution**: Assigned to Feature 1249.

### Blind Spot 3: No Time Enforcement on Running Chaos Experiments (HIGH)
**Impact**: Experiments with duration_seconds not enforced; infrastructure stays degraded until manual /stop.
**Resolution**: Assigned to Feature 1250 (this branch).

### Blind Spot 4: Lambda Deployment S3 Bucket Missing Public Access Block (MEDIUM)
**Resolution**: Assigned to Feature 1249.

### Blind Spot 5: CORS Allow-Credentials on SSE with Broad Origins (MEDIUM)
**Resolution**: Assigned to Feature 1249.

### Blind Spot 6: `/api/v2/runtime` Exposes SSE Lambda URL (MEDIUM)
**Resolution**: Assigned to Feature 1249.

### Blind Spot 7: DynamoDB Chaos Table Has No TTL (LOW)
**Resolution**: Assigned to Feature 1250 (this branch).

### Blind Spot 8: No CloudTrail Alerting on IAM Policy Attachment (MEDIUM)
**Resolution**: Assigned to Feature 1250 (this branch).

---

## Severity Triage

| Priority | Issue | Feature | Status |
|----------|-------|---------|--------|
| P0 | Chaos API still accessible after UI lockdown | 1250 | Not started |
| P0 | Missing auth on `/configurations/{id}/refresh/status` | 1249 | In spec |
| P1 | `validate_session=False` on 4+ endpoints | 1249 | In spec |
| P1 | No chaos experiment duration enforcement | 1250 | Not started |
| P1 | User enumeration via check-email | Future | Out of scope |
| P2 | `/api/v2/runtime` exposes SSE URL | 1249 | In spec |
| P2 | S3 deployment bucket public access block | 1249 | In spec |
| P2 | Anonymous session flood | Future | Out of scope |
| P3 | Chaos table no TTL | 1250 | Not started |
| P3 | No CloudTrail alerting on IAM changes | 1250 | Not started |

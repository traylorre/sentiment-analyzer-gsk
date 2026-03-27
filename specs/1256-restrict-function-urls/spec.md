# Feature Specification: Restrict Lambda Function URLs to Authorized Callers

**Feature Branch**: `1256-restrict-function-urls`
**Created**: 2026-03-24
**Status**: Draft
**Input**: "Restrict Lambda Function URLs to authorized callers only — API Gateway and CloudFront. Final feature in DDoS/auth hardening series."

## Context

### Current State

Both Lambda Function URLs are exposed to the internet with `authorization_type = NONE`:

| Lambda | Function URL Auth | Used By | Bypass Risk |
|--------|-------------------|---------|-------------|
| Dashboard | NONE | API Gateway (proxy integration), deploy smoke tests (direct invoke) | Attacker bypasses Cognito auth, WAF rate limiting |
| SSE Streaming | NONE | CloudFront origin (Feature 1255) | Attacker bypasses WAF, Shield Standard |

An attacker who discovers a Function URL (via DNS enumeration, CloudTrail logs, GitHub repository search, or error messages) can call Lambda directly, bypassing ALL protective infrastructure:
- API Gateway Cognito JWT validation (Feature 1253)
- WAF per-IP rate limiting, SQLi/XSS detection (Feature 1254)
- CloudFront Shield Standard DDoS protection (Feature 1255)

This is the **final gap** in the security hardening series. After this feature, the only paths to Lambda are through the protected infrastructure layers.

### Approach: Function URL Auth Type vs Resource Policy

Two options exist for restricting Function URL access:

**Option A: `authorization_type = AWS_IAM`** — Requires IAM SigV4 signing on every request. API Gateway's proxy integration already uses IAM (it signs requests via `lambda:InvokeFunctionUrl`). CloudFront can use Origin Access Control (OAC) for Lambda. Deploy smoke tests use `aws lambda invoke` (already IAM-signed). **This is the correct approach** — it enforces authentication at the Lambda level.

**Option B: Resource policy deny** — Add an explicit deny policy that blocks all callers except specific source ARNs. More complex, harder to debug, and redundant with `AWS_IAM` auth. Not recommended.

**Decision**: Option A — switch `authorization_type` from `NONE` to `AWS_IAM` on both Function URLs.

### Impact Analysis

| Caller | Current Access | After Feature 1256 | Action Needed |
|--------|---------------|---------------------|---------------|
| API Gateway | `lambda_invoke_arn` (IAM-signed) | Works — API GW already uses IAM permission | None — existing `aws_lambda_permission` handles this |
| CloudFront OAC | N/A (direct HTTPS) | Needs OAC + Lambda permission | Add CloudFront OAC for Lambda Function URL |
| Deploy smoke test | `aws lambda invoke` (IAM-signed) | Works — CLI uses IAM credentials | None — direct invoke bypasses Function URL auth |
| Direct browser/curl | Function URL (no auth) | **BLOCKED** — 403 Forbidden | This is the goal |
| Frontend (Amplify) | Via API Gateway / CloudFront | Works — traffic routed through protected layers | None |

### Threat Model

**State-sponsored attacker** who has discovered Function URLs can currently:
- Call Dashboard Lambda directly with crafted requests, bypassing Cognito JWT check
- Flood SSE Lambda with connections, bypassing WAF rate limiting
- Send SQL injection / XSS payloads directly to Lambda, bypassing WAF managed rules
- Exhaust Lambda concurrency from unprotected path

After Feature 1256: Direct Function URL access returns 403. Attacker MUST go through API Gateway (Cognito + WAF) or CloudFront (WAF + Shield).

### Out of Scope

- Removing Function URLs entirely (they're needed as API Gateway proxy integration targets and CloudFront origins)
- Changing Lambda application code (infrastructure-only change)
- Custom domain for Function URLs
- VPC configuration for Lambda (not needed — IAM auth is sufficient)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Direct Function URL Access Is Blocked (Priority: P1)

Anyone attempting to call a Lambda Function URL directly (via browser, curl, or script) receives 403 Forbidden. This closes the bypass vulnerability.

**Why this priority**: This is the entire purpose of the feature — eliminating the Function URL bypass.

**Independent Test**: `curl` the Dashboard Lambda Function URL directly. Verify 403 response.

**Acceptance Scenarios**:

1. **Given** the Dashboard Lambda Function URL, **When** a request is sent without IAM signing, **Then** it returns 403 Forbidden.
2. **Given** the SSE Lambda Function URL, **When** a request is sent without IAM signing, **Then** it returns 403 Forbidden.
3. **Given** an attacker has discovered a Function URL, **When** they send a valid-looking request with a Bearer token, **Then** it still returns 403 (IAM SigV4 required, not Bearer).

---

### User Story 2 — API Gateway Still Reaches Dashboard Lambda (Priority: P1)

API Gateway's proxy integration continues to invoke the Dashboard Lambda successfully. All frontend REST traffic works unchanged.

**Why this priority**: Breaking API Gateway → Lambda breaks the entire application.

**Independent Test**: Send a request through API Gateway to a public endpoint. Verify 200 response.

**Acceptance Scenarios**:

4. **Given** API Gateway proxies a request to Dashboard Lambda, **When** using the existing IAM permission, **Then** Lambda processes the request and returns a response.
5. **Given** a frontend user accesses the application through API Gateway, **Then** all functionality works exactly as before Feature 1256.

---

### User Story 3 — CloudFront Still Reaches SSE Lambda (Priority: P1)

CloudFront's origin connection to the SSE Lambda Function URL continues to work via Origin Access Control (OAC).

**Why this priority**: Breaking CloudFront → SSE breaks real-time updates.

**Acceptance Scenarios**:

6. **Given** CloudFront forwards an SSE request to the Lambda origin, **When** using OAC IAM signing, **Then** Lambda processes the request and streams events.
7. **Given** a frontend user connects to SSE via CloudFront, **Then** real-time events arrive normally.

---

### User Story 4 — Deploy Pipeline Still Works (Priority: P1)

The deploy smoke test uses `aws lambda invoke` (direct Lambda invocation, not Function URL). This continues to work because direct invoke uses IAM credentials independently of Function URL auth type.

**Why this priority**: Breaking deploys blocks all future releases.

**Acceptance Scenarios**:

8. **Given** the deploy pipeline runs `aws lambda invoke`, **Then** it succeeds (direct invoke is IAM-authenticated separately from Function URL).
9. **Given** the deploy pipeline's health check uses API Gateway URL (Feature 1253), **Then** it succeeds through the protected path.

---

### Edge Cases

- **CloudFront OAC for Lambda Function URLs**: CloudFront Origin Access Control supports Lambda Function URLs as of 2024. OAC signs requests with SigV4 automatically. The Lambda needs a resource-based policy allowing CloudFront's service principal.
- **Existing `aws_lambda_permission` for API Gateway**: The API Gateway module already creates `aws_lambda_permission.api_gateway` allowing API Gateway to invoke Lambda. This permission covers the proxy integration (which uses `lambda:InvokeFunction`, not Function URL). No change needed.
- **Function URL vs direct invoke**: `authorization_type = AWS_IAM` only affects Function URL access. Direct `aws lambda invoke` via SDK/CLI uses IAM `lambda:InvokeFunction` permission, which is separate. Deploy pipeline is unaffected.
- **CORS on Function URL**: With `AWS_IAM` auth, CORS preflight OPTIONS still works because Lambda Function URL handles OPTIONS before auth check. However, browsers cannot sign requests with SigV4, so direct browser access to Function URL is effectively blocked (which is the goal).
- **Rollback**: Setting `authorization_type` back to `NONE` restores open access. Single variable change per Lambda.
- **E2E tests**: Current E2E tests use `PREPROD_API_URL` (API Gateway) or `PREPROD_TRANSPORT=invoke` (direct Lambda invoke). Neither uses Function URL directly. No E2E test changes needed.
- **Amplify SSE proxy**: The Next.js server-side proxy at `/api/sse/[...path]` fetches from `NEXT_PUBLIC_SSE_URL` (now CloudFront URL per Feature 1255). CloudFront OAC handles auth to Lambda. No proxy change needed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Dashboard Lambda Function URL `authorization_type` MUST be changed from `NONE` to `AWS_IAM`.
- **FR-002**: SSE Streaming Lambda Function URL `authorization_type` MUST be changed from `NONE` to `AWS_IAM`.
- **FR-003**: A CloudFront Origin Access Control (OAC) MUST be configured for the SSE Lambda Function URL origin, allowing CloudFront to sign requests with SigV4.
- **FR-004**: A Lambda resource-based policy MUST be added to the SSE Lambda allowing the CloudFront distribution to invoke it via OAC.
- **FR-005**: Existing API Gateway Lambda permission (`aws_lambda_permission.api_gateway`) MUST remain unchanged — it already authorizes API Gateway to invoke the Dashboard Lambda.
- **FR-006**: Deploy pipeline smoke tests MUST continue working via `aws lambda invoke` (direct invoke, unaffected by Function URL auth type) and API Gateway URL health checks.
- **FR-007**: Direct access to either Function URL without IAM SigV4 signing MUST return 403 Forbidden.

### Key Entities

- **Function URL Authorization Type**: Controls whether Function URL requires IAM SigV4 signing. `NONE` = open to internet. `AWS_IAM` = requires signed requests.
- **Origin Access Control (OAC)**: CloudFront mechanism for signing origin requests with SigV4. Replaces the older Origin Access Identity (OAI) pattern. Supports Lambda Function URLs.
- **Lambda Resource-Based Policy**: IAM policy attached to the Lambda function that specifies which AWS services/accounts can invoke it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Direct `curl` to Dashboard Lambda Function URL returns 403 (currently returns 200).
- **SC-002**: Direct `curl` to SSE Lambda Function URL returns 403 (currently returns 200).
- **SC-003**: API Gateway health check (`/v1/health`) returns 200 through the protected path.
- **SC-004**: SSE stream via CloudFront returns events (real-time connection works).
- **SC-005**: Deploy pipeline `aws lambda invoke` succeeds.
- **SC-006**: All existing E2E tests pass (zero regression).
- **SC-007**: No additional monthly cost (IAM auth and OAC are free).

## Assumptions

- CloudFront OAC supports Lambda Function URLs (verified: AWS launched this in 2024).
- API Gateway proxy integration uses `lambda:InvokeFunction` via IAM, not Function URL. Changing Function URL auth type doesn't affect API Gateway.
- Deploy pipeline uses `aws lambda invoke` (direct SDK call), not Function URL HTTP endpoint. Verified in deploy.yml smoke test section.
- E2E tests use `PREPROD_API_URL` (API Gateway) or `PREPROD_TRANSPORT=invoke` mode. Neither hits Function URL directly.
- Setting `authorization_type = AWS_IAM` on Function URL is a single-variable change per Lambda — no code changes needed.

### Security Zone Map (FINAL — After Feature 1256)

```
┌──────────────────────────────────────────────────────────────────────┐
│                        INTERNET                                       │
│                    ┌──────┴──────┐                                    │
│                    │             │                                    │
│   ┌────────────────▼──────┐  ┌──▼───────────────────────┐           │
│   │  WAF (REGIONAL)       │  │  CloudFront               │           │
│   │  Feature 1254         │  │  + WAF (CLOUDFRONT) 1255  │           │
│   │  SQLi/XSS/Rate/Bots  │  │  + Shield Standard        │           │
│   └────────────────┬──────┘  └──┬───────────────────────┘           │
│                    │            │                                     │
│   ┌────────────────▼──────┐    │ OAC (SigV4)                        │
│   │  API GATEWAY          │    │                                     │
│   │  Cognito + Rate Plan  │    │                                     │
│   └────────────────┬──────┘    │                                     │
│                    │ IAM       │                                     │
│   ┌────────────────▼──────┐  ┌─▼────────────────────────┐          │
│   │  DASHBOARD LAMBDA     │  │  SSE STREAMING LAMBDA     │          │
│   │  auth_type=AWS_IAM    │  │  auth_type=AWS_IAM        │          │
│   │  ✓ API Gateway (IAM)  │  │  ✓ CloudFront (OAC)      │          │
│   │  ✗ Direct URL (403)   │  │  ✗ Direct URL (403)      │          │
│   └───────────────────────┘  └──────────────────────────┘          │
│                                                                      │
│   ┌──────────────────────────────────────────────────────┐          │
│   │  LAMBDA FUNCTION URLs                                │          │
│   │  ✗ BLOCKED — authorization_type = AWS_IAM            │ CLOSED   │
│   │  No more direct internet access                      │          │
│   └──────────────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────────────────┘

Security Score: ~9.0/10 (target achieved)
```

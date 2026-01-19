# Research: Remove CloudFront References from Documentation

**Feature**: 1209-remove-cloudfront-docs
**Date**: 2026-01-19

## Context

CloudFront was removed from the sentiment-analyzer-gsk infrastructure in Features 1203-1207. The frontend is now served by AWS Amplify and APIs are exposed via Lambda Function URLs directly. Documentation still references CloudFront as an active component, causing confusion.

## Research Tasks

### R-001: Current Amplify Architecture

**Question**: What is the current frontend hosting architecture?

**Finding**: AWS Amplify with Next.js SSR (Server-Side Rendering)

**Evidence**:
- `/infrastructure/terraform/main.tf` line 940-942: Comment confirms Next.js frontend via Amplify
- `/infrastructure/terraform/modules/amplify/main.tf`: `platform = "WEB_COMPUTE"` for SSR support
- Amplify connects to GitHub repo and auto-builds on push
- Default domain: `main.d*.amplifyapp.com`

**Decision**: Document frontend as "AWS Amplify (Next.js SSR)" serving directly to users.

**Rationale**: Terraform confirms this is the deployed architecture. No CloudFront distribution exists.

---

### R-002: Lambda Function URL Direct Access

**Question**: How are APIs exposed to the frontend?

**Finding**: Lambda Function URLs without CDN or API Gateway

**Evidence**:
- `/infrastructure/terraform/main.tf` lines 408, 961: Lambda modules expose Function URLs
- `module.dashboard_lambda.function_url` and `module.sse_streaming_lambda.function_url` passed to Amplify
- No `aws_cloudfront_distribution` or `aws_apigateway_*` resources in Terraform
- Feature 1203 explicitly removed CloudFront module

**Decision**: Document APIs as "Lambda Function URLs" without CDN layer.

**Rationale**: Direct Lambda access is the deployed pattern. This simplifies architecture but removes edge caching.

---

### R-003: Security Boundary Redesign

**Question**: How should security diagrams represent the edge layer without CloudFront?

**Finding**: Security boundary is now at Lambda Function URL and Amplify level

**Evidence**:
- Lambda Function URLs support IAM auth_type for authentication
- Amplify provides managed HTTPS termination
- No WAF, no geographic restrictions (CloudFront features that are gone)
- CORS configuration is at Lambda level, not CloudFront

**Decision**: Replace "ZONE 0: CloudFront" with "Edge: Lambda Function URL + Amplify".

**Rationale**: The security boundary still exists but at a different layer. Lambda IAM auth provides request-level security, Amplify handles TLS.

**Implications**:
- DDoS protection is now AWS-managed at Lambda/Amplify level (not as configurable as CloudFront Shield)
- No edge caching - all requests hit Lambda
- CORS is enforced at Lambda, not edge

---

### R-004: SSE Streaming Timeout Handling

**Question**: How do SSE streaming timeouts work without CloudFront?

**Finding**: Lambda Function URLs have better timeout support than CloudFront

**Evidence**:
- CloudFront had 60-second origin timeout (required keepalive workarounds)
- Lambda Function URLs support up to 15-minute timeout by default
- Lambda Web Adapter handles RESPONSE_STREAM mode natively
- Feature 1207 removed CloudFront timeout workaround code

**Decision**: Remove CloudFront 60s timeout references. Document Lambda Function URL 15-minute default.

**Rationale**: This is actually an improvement - longer streaming sessions without keepalive hacks.

---

### R-005: Gap Analysis Documents Treatment

**Question**: Should CloudFront be removed from security/cost analysis docs?

**Finding**: Keep as proposed future enhancement with clarification

**Evidence**:
- `docs/DASHBOARD_SECURITY_ANALYSIS.md` recommends CloudFront for DDoS protection
- `docs/API_GATEWAY_GAP_ANALYSIS.md` includes CloudFront in cost analysis
- These are planning documents, not architecture documentation
- CloudFront could be re-added in future if needed

**Decision**: Add "Note: CloudFront is not currently deployed" clarification; keep recommendations.

**Rationale**: Gap analysis should show options available. Removing CloudFront entirely loses valuable cost/security analysis.

**Implementation**:
- Add note at top of CloudFront sections: "Note: CloudFront is not currently deployed (removed in Feature 1203). The following represents potential future enhancement options."

---

## Summary

| Task | Decision | Impact |
|------|----------|--------|
| R-001 | Document Amplify as frontend | README, diagrams |
| R-002 | Document Lambda Function URLs | README, diagrams |
| R-003 | Replace ZONE 0 CloudFront | security-flow.mmd |
| R-004 | Remove timeout workarounds | sse-lambda-streaming.mmd |
| R-005 | Clarify gap analysis docs | 2 security docs |

All research tasks complete. No NEEDS CLARIFICATION items remain.

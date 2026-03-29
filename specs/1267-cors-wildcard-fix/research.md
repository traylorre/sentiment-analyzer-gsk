# Research: CORS Wildcard Origin Fix

**Feature**: 1268-cors-wildcard-fix
**Date**: 2026-03-28

## Research Questions

### Q1: Can API Gateway MOCK integration responses perform origin validation?

**Decision**: No. MOCK integrations can only echo request headers verbatim using `method.request.header.Origin`. They cannot perform conditional logic (if/else, allowlist checking).

**Rationale**:
- API Gateway integration responses support static values (`'value'`) or request header references (`method.request.header.HeaderName`)
- There is no VTL (Velocity Template Language) support in integration response parameter mappings for MOCK integrations
- Gateway responses (4xx/5xx) also use the echo pattern -- this is the established AWS practice
- The existing gateway error responses in this codebase (lines 76, 101, 125) already use `method.request.header.origin` proving this pattern works

**Alternatives Considered**:
1. Lambda-backed OPTIONS handler (rejected: adds latency, cost, and complexity for a preflight response)
2. HTTP API instead of REST API (rejected: would require full API Gateway migration, out of scope)
3. Request Validator with regex pattern (rejected: request validators validate request body/parameters, not used for response header logic)

### Q2: Is origin echoing without allowlist validation a security risk?

**Decision**: Acceptable. The CORS spec's layered security model makes this safe.

**Rationale**:
- OPTIONS preflight only tells the browser "you may send this cross-origin request"
- The actual response (from Lambda) still needs its own CORS headers
- Lambda middleware (`security_headers.py`) validates origin against `CORS_ORIGINS` env var
- An attacker gets past preflight but the data response is blocked by Lambda's origin check
- This is the standard pattern used by AWS, CloudFlare, and most API gateways

**Evidence**:
- Fetch Standard Section 3.2.5: "If credentials flag is set... and the value of `Access-Control-Allow-Origin` is `*`, then set the CORS check to failure"
- AWS documentation recommends `method.request.header.Origin` for CORS with credentials
- The existing gateway error responses in this repo already use this exact pattern

### Q3: What are all the locations that need fixing?

**Decision**: Three distinct locations in `modules/api_gateway/main.tf`, plus method_response updates.

**Findings**:

| Location | Line | Current Value | Used By | Fix |
|----------|------|---------------|---------|-----|
| `local.cors_headers` | 212 | `'*'` | fr012_options, fr012_proxy_options, public_leaf_options, public_proxy_options | Change to `method.request.header.Origin` |
| `proxy_options` integration response | 619 | `'*'` | Catch-all `{proxy+}` route | Change to `method.request.header.Origin` + add credentials |
| `root_options` integration response | 679 | `'*'` | Root `/` route | Change to `method.request.header.Origin` + add credentials |

**Additional findings**:
- The proxy_options and root_options handlers are MISSING `Access-Control-Allow-Credentials: true` -- this is a secondary bug
- The proxy_options and root_options handlers don't use `local.cors_headers` -- they have inline parameters
- The proxy_options and root_options handlers use different header lists than `local.cors_headers`

### Q4: Does the proxy_options method need request_parameters for Origin?

**Decision**: No. API Gateway automatically makes all request headers available via `method.request.header.*` without explicit declaration in `request_parameters`.

**Rationale**:
- `request_parameters` is only needed for path parameters and query strings that need explicit mapping
- Request headers are always available in integration response mappings
- The existing gateway error responses reference `method.request.header.origin` without any `request_parameters` declaration

### Q5: Is Vary: Origin necessary for API Gateway?

**Decision**: Yes, add `Vary: Origin` to prevent cache poisoning.

**Rationale**:
- API Gateway responses may be cached by CloudFront (if present) or browser HTTP cache
- Without `Vary: Origin`, a cached response for origin A could be served to origin B
- This would cause CORS failures for origin B since the cached `Access-Control-Allow-Origin` doesn't match
- The fix is simple: add `Vary` to the response headers

**Note**: API Gateway REST API does not cache by default, but CloudFront (Feature 1255) sits in front of SSE. Adding Vary is defensive and costs nothing.

### Q6: What is the case sensitivity of the Origin header reference?

**Decision**: Use lowercase `method.request.header.Origin` with capital O.

**Rationale**:
- HTTP headers are case-insensitive per RFC 7230
- The existing gateway responses use lowercase: `method.request.header.origin`
- API Gateway normalizes header name lookups, so both work
- For consistency with existing code, use lowercase `origin`
